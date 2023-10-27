import sys
import json
from copy import deepcopy
from typing import List, Tuple, Dict, Any

from src.server.task import Task, Session
from src.typings import TaskSampleExecutionResult, TaskOutput, SampleIndex, AgentOutputStatus, SampleStatus

from .engine import *
from .task_scoring import *

from .prompts import *
from .baseline_agents import *

from .wrapper import FakeSession, SessionWrapper
from .utils import verbalize_team_result, verbalize_mission_result

from .llm_with_discussion import LLMAgentWithDiscussion

AGENT_FINDER = {
    'naive': find_naive_agent,
    'llm': LLMAgentWithDiscussion
}

class AvalonBench(Task):
    def __init__(self, num_games, num_players, agent_list, discussion, data_file, **configs):
        super().__init__(**configs)

        self.num_games = num_games
        self.num_players = num_players
        self.agent_list = agent_list

        self.discussion = discussion
        self.data_file = data_file


        self.data: List[Tuple[dict, set]] = []
        with open(self.data_file, "r") as f:
            data_object = json.load(f)
        for data_item in data_object:
            self.data.append((data_item, -1))
        self.inputs = data_object

        self.team_discussion: bool
        self.summarize: bool

        self.team_discussion = False
        self.summarize = True

        self.true_player_sides = []
        self.believed_player_sides = []
        self.game_info_player_0 = []

        self.seed = 0

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        outputs = [None for _ in range(len(self.data))]

        win_counter = 0
        print(results)
        for result in results:
            if result.result['Player_0_wins']:
                win_counter += 1


        return {
            "win rate of Player 0": win_counter / len(outputs)
        }

    def get_indices(self) -> List[SampleIndex]:
        return list(range(len(self.data)))

    async def start_sample(self, index: SampleIndex, session: Session) -> TaskSampleExecutionResult:
        assert isinstance(index, int), "Index must be an integer"
        assert self.inputs[index]['num_players'] == self.num_players, "Number of players must be the same"
        self.env = AvalonGameEnvironment.from_presets(self.inputs[index])
        self.socring = AvalonScoring(self.env.config)

        env = self.env

        sessions = [SessionWrapper(FakeSession()) for _ in range(self.num_players)]
        llm_counter = 0
        for idx, agent_name in enumerate(self.agent_list):
            if agent_name != "naive":
                sessions[0] = SessionWrapper(session)
                llm_counter += 1
        assert llm_counter <= 1, "Only at most one LLM agent is allowed."

        num_players = self.num_players

        player_list = []

        if num_players != len(sessions):
            raise ValueError(
                f"Number of players {num_players} doesn't match number of sessions {len(sessions)}"
            )

        # Initialize players. Please remember to let Merlin and Evil players see the sides of all players.
        for i, (role_i, role_name, side) in enumerate(env.get_roles()):
            player_list.append(AGENT_FINDER[self.agent_list[i]](
                                    id          =   i,
                                    name        =   f"Player {i}",
                                    config      =   self.env.config,
                                    side        =   side,
                                    role        =   role_i,
                                    num_players =   num_players,
                                    session     =   sessions[i],
                                    role_name   =   role_name,
                                    merlin      =   env.config.merlin,
                                    percival    =   env.config.percival,
                                    morgana     =   env.config.morgana,
                                    mordred     =   env.config.mordred,
                                    oberon      =   env.config.oberon,
                                    num_good    =   env.config.num_good,
                                    num_evil    =   env.config.num_evil,
                                    seed        =   self.seed # TODO: seed
                                    ))
            # If the player is Merlin or Evil, let them see the sides of all players.
            player_sides = [side for _, _, side in env.get_roles()]
            if player_list[i].role == 0 or player_list[i].side == 0:
                player_list[i].see_sides(player_sides)

        while not env.done:
            phase = env.get_phase()[0]
            
            # if phase is team selection phase, ask for team
            if phase == 0:
                leader = env.get_quest_leader()
                """
                Summary TODO: Should implement this in agents
                """
                # for player in player_list:
                #     await player.summarize()
                    
                """
                Leader speaks & Discussion
                """
                discussion_history = []
                if self.team_discussion:
                    # Leader speaks
                    team, statement = await player_list[leader].team_discussion(env.get_team_size(), discussion_history, env.turn,)
                    discussion_history.append(f"Leader {leader} : " + statement + '\n')

                    # Discussion (sequential, once, in order for now) and Summarize
                    for idx, player in enumerate(player_list):
                        if idx == leader:
                            continue
                        discussion = await player.team_discussion(env.get_team_size(), team, leader, discussion_history, env.turn)
                        discussion_history.append(f"Player {idx} : " + discussion + '\n')

                    for idx, player in enumerate(player):
                        player.discussion_end({
                            "role": "user",
                            "content": f"Discussion has ended. Here are the contents:\nStatement from Leader {player_list[leader]}: \n\"{statement}\"\nAnd words from other players:\n{' '.join(discussion_history)}"
                        })

                # Choose a team
                team = await player_list[leader].propose_team(
                    team_size=env.get_team_size(),
                    mission_id=env.turn,
                    discussion_history=discussion_history
                    )
                env.choose_quest_team(team, leader)

            # if phase is team voting phase, ask for votes
            elif phase == 1:
                discussion_history = []
                votes = [
                    await player_list[i].vote_on_team(
                        team=env.get_current_quest_team(),
                        mission_id=env.turn,
                        discussion_history=discussion_history
                        ) for i in range(num_players)
                        ]
                outcome = env.vote_on_team(votes)
                """
                Thought on result of Team Selection TODO: polish the prompt
                """
                for player in player_list:
                    await player.team_result(
                        mission_id=env.turn,
                        result={
                            'team': env.get_current_quest_team(),
                            'votes': votes,
                            'outcome': outcome[2],
                        }
                    )


            # if phase is quest voting phase, ask for votes
            elif phase == 2:
                discussion_history = []
                votes = [
                    await player_list[i].vote_on_mission(
                        discussion_history=discussion_history,
                        mission_id=env.turn,
                        team=env.get_current_quest_team()
                        ) for i in env.get_current_quest_team()
                        ]
                outcome = env.vote_on_quest(votes)
                """
                Thought on Quest result
                """
                for idx, player in enumerate(player_list):
                    await player.quest_result(
                        mission_id=env.turn,
                        result={
                            'quest_team': env.get_current_quest_team(),
                            'votes': votes,
                            'outcome': outcome[2],
                        }
                    )

                # Observe mission/quest result
                for player in player_list:
                    await player.observe_mission(
                        team=env.get_current_quest_team(),
                        mission_id=env.turn-1,
                        num_fails=outcome[3]
                        )
            
            # if phase is assassination phase, ask for assassination
            elif phase == 3:
                '''
                    TODO: Discussion before Assassination Phase
                '''
                assassin = env.get_assassin()
                target = int(await player_list[assassin].assassinate())

                _, _, assassinated = env.choose_assassination_target(assassin, target)
        
        # reflect sides of each player at the end of the game
        for idx, player in enumerate(player_list):
            if player_list[idx].role_name == "Servant":
                believed_player_sides = await player.get_believed_sides()

                self.true_player_sides.append(list(map(int, env.is_good)))
                self.believed_player_sides.append(believed_player_sides)

        verbal_game_result = {
            -1: "Evil wins by mission!",
            0: "Evil wins by assassination!",
            1: "Good wins!"
        }
        if env.good_victory:
            answer = 1
        else:
            if sum(env.quest_results) >= 3:
                answer = 0
            else:
                answer = -1
        finish_reason = SampleStatus.COMPLETED
        return TaskSampleExecutionResult(status=finish_reason, result={
            "game_result": verbal_game_result[answer],
            "role_of_Player_0": player_list[0].role_name,
            "Player_0_wins": (answer > 0) == bool(player_list[0].side),
        })
