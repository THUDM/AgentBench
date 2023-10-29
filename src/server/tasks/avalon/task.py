import sys
import json
from copy import deepcopy
from typing import List, Tuple, Dict, Any

from src.server.task import Task, Session
from src.typings import TaskSampleExecutionResult, TaskOutput, SampleIndex, AgentOutputStatus, SampleStatus

from .engine import *
from .task_scoring import *

from .prompts import *
from .agents.baseline_agents import *

from .wrapper import FakeSession, SessionWrapper
from .utils import verbalize_team_result, verbalize_mission_result

from .agents.llm_with_discussion import LLMAgentWithDiscussion

AGENT_FINDER = {
    'naive': find_naive_agent,
    'llm': LLMAgentWithDiscussion
}

class AvalonBench(Task):
    def __init__(self, num_players, agent_list, discussion, data_file, **configs):
        super().__init__(**configs)

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

        self.seed = 0

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        outputs = [None for _ in range(len(self.data))]
        for result in results:
            outputs[result.index] = result.result

        win_counter = 0
        deduc_acc = 0
        valid_games = 0
        print(results)
        for result in results:
            if result.status == SampleStatus.AGENT_VALIDATION_FAILED:
                pass
            else:
                llm_idx = result.result['llm_idx']
                if result.result[f'Player_{llm_idx}_wins']:
                    win_counter += 1
                deduc_acc += result.result[f'Player_{llm_idx}_deduc_acc']
                valid_games += 1
        

        return {
            "Win rate of Player 0": win_counter / len(outputs),
            "Avg deduction acc of Player 0": deduc_acc / len(outputs),
            "Valid number of games": valid_games,
        }

    def get_indices(self) -> List[SampleIndex]:
        return list(range(len(self.data)))

    async def start_sample(self, index: SampleIndex, session: Session) -> TaskSampleExecutionResult:
        assert isinstance(index, int), "Index must be an integer"
        assert self.inputs[index]['num_players'] == self.num_players, "Number of players must be the same"
        self.env = AvalonGameEnvironment.from_presets(self.inputs[index])
        self.socring = AvalonScoring(self.env.config)

        env = self.env

        self.true_player_sides = []
        self.believed_player_sides = []
        self.game_env_log = []

        print(self.agent_list)

        llm_idx = 0
        sessions = [SessionWrapper(FakeSession()) for _ in range(self.num_players)]
        llm_counter = 0
        for idx, agent_name in enumerate(self.agent_list):
            print((idx, agent_name))
            if agent_name != "naive":
                llm_idx = idx
                sessions[idx] = SessionWrapper(session)
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
                                    discussion  =   self.discussion,
                                    seed        =   self.seed # TODO: seed
                                    ))
            # If the player is Merlin or Evil, let them see the sides of all players.
            player_sides = [side for _, _, side in env.get_roles()]
            if player_list[i].role == 0 or player_list[i].side == 0:
                player_list[i].see_sides(player_sides)
                await player_list[i].initialize_game_info(player_list=env.get_roles())
            else:
                await player_list[i].initialize_game_info(player_list=[])
        
        for player in player_list:
            print(player.role_name, player.role, player.side)
        try:
            while not env.done:
                phase = env.get_phase()[0]
                
                # if phase is team selection phase, ask for team
                if phase == 0:
                    leader = env.get_quest_leader()
                    self.game_env_log.append(f"Selection Phase, the leader is Player {leader}")
                    """
                    Leader speaks & Discussion
                    """
                    discussion_history = []
                    if self.discussion:
                        # Leader speaks
                        team, statement = await player_list[leader].team_discussion(
                                team_size           =   env.get_team_size(),
                                team                =   team,
                                team_leader_id      =   leader,
                                discussion_history  =   discussion_history,
                                mission_id          =   env.turn
                            )
                        discussion_history.append(f"Leader {leader} : " + statement + '\n')

                        # Discussion (sequential, once, in order for now) and Summarize
                        for idx, player in enumerate(player_list):
                            if idx == leader:
                                continue
                            discussion = await player.team_discussion(
                                team_size           =   env.get_team_size(),
                                team                =   team,
                                team_leader_id      =   leader,
                                discussion_history  =   discussion_history,
                                mission_id          =   env.turn
                            )
                            discussion_history.append(f"Player {idx} : " + discussion + '\n')

                        for idx, player in enumerate(player):
                            player.discussion_end(
                                leader              =   leader,
                                leader_statement    =   statement,
                                discussion_history  =   discussion_history
                            )

                    # Choose a team
                    team = await player_list[leader].propose_team(
                        team_size           =   env.get_team_size(),
                        mission_id          =   env.turn,
                        discussion_history  =   discussion_history
                    )
                    env.choose_quest_team(
                        team   =  frozenset(team),
                        leader =  leader
                    )
                    self.game_env_log.append(f"Leader Player {leader} chooses team {list(team)}")

                # if phase is team voting phase, ask for votes
                elif phase == 1:
                    self.game_env_log.append("Team voting Phase")
                    discussion_history = []
                    votes = [
                        await player_list[i].vote_on_team(
                            team                =   env.get_current_quest_team(),
                            mission_id          =   env.turn
                            ) for i in range(num_players)
                            ]
                    outcome = env.gather_team_votes(votes)
                    self.game_env_log.append(f"Team votes at this round: {str(votes)}")

                    # Observe results of Team Selection
                    for player in player_list:
                        await player.observe_team_result(
                            mission_id  =   env.turn,
                            team        =   env.get_current_quest_team(),
                            votes       =   votes,
                            outcome     =   outcome[2],
                    )
                    self.game_env_log.append("Team result: " + verbalize_team_result(team=env.get_current_quest_team(), votes=votes, outcome=outcome[2]))


                # if phase is quest voting phase, ask for votes
                elif phase == 2:
                    self.game_env_log.append("Quest voting phase")
                    '''
                    TODO: Can have a discussion before voting on quest
                    '''
                    discussion_history = []
                    votes = [
                        await player_list[i].vote_on_mission(
                            team=env.get_current_quest_team(),
                            mission_id=env.turn,
                            discussion_history=discussion_history,
                            ) for i in env.get_current_quest_team()
                            ]
                    outcome = env.gather_quest_votes(votes)
                    self.game_env_log.append(f"Quest votes at this round: {str(votes)}")

                    # Observe mission/quest result
                    for player in player_list:
                        await player.observe_mission(
                            team        =   env.get_current_quest_team(),
                            mission_id  =   env.turn-1,
                            num_fails   =   outcome[3],
                            votes       =   votes,
                            outcome     =   outcome[2],
                    )
                    self.game_env_log.append("Quest result: " + verbalize_mission_result(team=env.get_current_quest_team(), outcome=outcome[2]))
                
                # if phase is assassination phase, ask for assassination
                elif phase == 3:
                    self.game_env_log.append("Assassination phase")
                    '''
                        TODO: Discussion before Assassination Phase
                    '''
                    assassin = env.get_assassin()
                    target = int(await player_list[assassin].assassinate())

                    _, _, assassinated = env.choose_assassination_target(assassin, target)
                    self.game_env_log.append(f"Assassin Player {assassin} chooses to assassinate Player {target}")
            
            # reflect sides of each player at the end of the game
            for idx, player in enumerate(player_list):
                if idx == llm_idx:
                    believed_player_sides = await player.get_believed_sides(num_players=self.num_players)

                    self.true_player_sides.append(list(map(int, env.is_good)))
                    self.believed_player_sides.append(believed_player_sides)

            if env.good_victory:
                answer = 1
            else:
                if sum(env.quest_results) >= 3:
                    answer = 0
                else:
                    answer = -1
            finish_reason = SampleStatus.COMPLETED
        except:
            finish_reason = SampleStatus.AGENT_VALIDATION_FAILED
        
        verbal_game_result = {
            -1: "Evil wins by mission!",
            0: "Evil wins by assassination!",
            1: "Good wins!"
        }
        if finish_reason == SampleStatus.COMPLETED:
            return TaskSampleExecutionResult(status=finish_reason, result={
                "game_result": verbal_game_result[answer],
                "llm_idx": llm_idx,
                f"role_of_Player_{llm_idx}": player_list[llm_idx].role_name,
                f"Player_{llm_idx}_wins": (answer > 0) == bool(player_list[llm_idx].side),
                f"Player_{llm_idx}_deduc_acc": self.socring.deduction_acc(self.true_player_sides, self.believed_player_sides),
                "game_env_log": self.game_env_log
            })
        elif finish_reason == SampleStatus.AGENT_VALIDATION_FAILED:
            return TaskSampleExecutionResult(status=finish_reason, result={
                "game_result": "Agent validation failed",
            })