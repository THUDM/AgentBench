import sys
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


class Player:

    def __init__(self, name, num_players, id, config:AvalonConfig, session: SessionWrapper=None, side=None, seed=None, **kwargs):
        self.name = name
        self.id = id
        self.num_players = num_players
        self.role = None
        self.team = None
        self.side = side # 1 for good, 0 for evil
        self.session = session

        self.merlin = kwargs.pop("merlin")
        self.percival = kwargs.pop("percival")
        self.morgana = kwargs.pop("morgana")
        self.mordred = kwargs.pop("mordred")
        self.oberon = kwargs.pop("oberon")

        self.num_good = kwargs.pop("num_good")
        self.num_evil = kwargs.pop("num_evil")
        self.player_list = kwargs.pop("player_list")

        self.seed = seed

        self.config = config


    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name
    

    
    async def propose_team(self, team_size, discussion_history, mission_id, mode):
        if mode == "discussion":
            # content_prompt = "You are the leader this round. Please make some statements about what team you want to propose."
            content_prompt = CHOOSE_TEAM_LEADER
        elif mode == "action":
            # content_prompt = "Please choose {} players from player ids 0 to {} as team members.".format(team_size, self.num_players-1)
            content_prompt = CHOOSE_TEAM_ACTION.format(team_size, self.num_players-1)

        if self.strategy is not None:
            naive_result = self.strategy.propose_team(mission_id=mission_id)
        else:
            raise RuntimeError
        

        thought = COTHOUGHT_PROMPT
        input = {
            "role": "user",
            "content": content_prompt + '\n' + thought,
            "team_size": team_size,
            "mode": "choose_quest_team_" + mode,
            "seed": self.seed,
            "role_name": self.role_name,
            "naive_result": list(naive_result)
        }
        proposed_team = await self.session.action(input)

        if mode == "action":
            # print(proposed_team)
            if isinstance(self.session.session, Session):
                proposed_team = await self.session.parse_result(input, proposed_team)
            proposed_team = frozenset(proposed_team)

        if mode == "action":
            if isinstance(proposed_team, frozenset):
                return proposed_team, None
            else:
                return str(proposed_team), None
        elif mode == "discussion":
            return None, proposed_team
    
    async def vote_on_team(self, team, statement_history, mission_id, mode="discussion"):
        if mode == "discussion":
            # content_prompt = ' '.join(statement_history) + ' ' + "Discussion Phase. Please discuss your thoughts on the team {} and what players should do in the current situation.".format(list(team))
            content_prompt = ' '.join(statement_history) + ' ' + VOTE_TEAM_DISCUSSION.format(list(team))
        elif mode == "action":
            # content_prompt = f"Based on the discussion, and your observations and preferences, do you approve or reject the team {list(team)}?"
            # content_prompt = "Based on your observations and preferences, do you approve or reject the team {}?".format(list(team))
            content_prompt = VOTE_TEAM_ACTION.format(list(team))
        else:
            raise RuntimeError(
                f"Unexpected Mode {mode}."
            )
        
        if self.strategy is not None:
            naive_result = self.strategy.vote_on_team(mission_id=mission_id, team=team)
        else:
            raise RuntimeError
        
        thought = COTHOUGHT_PROMPT
        input = {
            "role": "user",
            "content": content_prompt + "\n" + thought,
            "side": int(self.side),
            "mode": "vote_on_team",
            "seed": self.seed,
            "role_name": self.role_name,
            "naive_result": naive_result
        }
        vote_result = await self.session.action(input)

        if mode == "statement":
            statement_history.append(f"Statements from {self.name}: {vote_result}")

        if isinstance(self.session.session, Session):
            vote_result = await self.session.parse_result(input, vote_result)
        if isinstance(vote_result, int):
            return vote_result
        else:
            return str(vote_result)
    
    async def vote_on_mission(self, statement_history, mission_id, team, mode="statement"):
        if mode == "statement":
            content_prompt = ' '.join(statement_history) + ' ' + f"Please vote on the quest."
        elif mode == "action":
            # content_prompt = "The team {} was approved, which includes you. Based on your preferences, do you want to help the mission succeed or fail it?".format(list(team))
            content_prompt = VOTE_MISSION_ACTION.format(list(team))
        else:
            raise RuntimeError(
                f"Unexpected Mode {mode}."
            )
        
        if self.strategy is not None:
            naive_result = self.strategy.vote_on_mission(mission_id=mission_id, team=team)
        else:
            raise RuntimeError

        thought = COTHOUGHT_PROMPT
        input = {
            "role": "user",
            "content": content_prompt + "\n" + thought,
            "side": int(self.side),
            "mode": "vote_on_mission",
            "seed": self.seed,
            "role_name": self.role_name,
            "naive_result": naive_result
        }
        vote_result = await self.session.action(input)

        if mode == "action":
            statement_history.append(f"{self.name} votes {vote_result} on the mission")

        if isinstance(self.session.session, Session):
            vote_result = await self.session.parse_result(input, vote_result)
        if isinstance(vote_result, int):
            return vote_result
        else:
            raise ValueError
        

    async def assassinate(self, player, assassin_history=None):
        if player >= self.num_players:
            raise ValueError(f"Player {player} does not exist.")
        if self.role != 7:
            raise ValueError("Only the Assassin can assassinate.")
        
        assert isinstance(self.strategy, NaiveAssassin)
        if self.strategy is not None:
            naive_result = self.strategy.assassinate()
        else:
            raise RuntimeError
        
        thought = COTHOUGHT_PROMPT
        input = {
            "role": "user",
            # "content": "Assassination phase. Your job is to assassinate Merlin. \
            #     Choose a player (id) to assassinate. Choose the player id from 0 to {}.".format(self.num_players-1) + "\n" + thought,
            "content": ASSASSINATION_PHASE.format(self.num_players-1) + "\n" + thought,
            "mode": "assassination",
            "seed": self.seed,
            "role_name": self.role_name,
            "naive_result": naive_result,
            "assassin_history": assassin_history,
        }
        assassinate_result = await self.session.action(input)

        if isinstance(self.session.session, Session):
            assassinate_result = await self.session.parse_result(input, assassinate_result)
        if isinstance(assassinate_result, int):
            return assassinate_result
        else:
            return str(assassinate_result)
    
    def assign_side(self, side):
        self.side = side


    def assign_role(self, role, role_name):
        self.role = role
        self.role_name = role_name

        if role_name == "Merlin":
            self.strategy = NaiveMerlin(self.id, self.name, self.config)
        elif role_name == "Minion":
            self.strategy = NaiveMinion(self.id, self.name, self.config)
        elif role_name == "Assassin":
            self.strategy = NaiveAssassin(self.id, self.name, self.config)
        elif role_name == "Servant":
            self.strategy = NaiveServant(self.id, self.name, self.config)


        """
        Introduction Prompt
        """
        verbal_side = ["Evil", "Good"]
        intro_prompt = INTRODUCTION
        # if args.local_llm:
        #     intro_prompt = ''
        # else:
        intro_prompt += '\n'
        content_prompt = intro_prompt + INFO_ROLE.format(self.num_players, self.num_good, int(self.merlin), self.num_good - int(self.merlin) - int(self.percival), self.num_evil, self.num_evil - int(self.morgana) - int(self.mordred) - int(self.oberon) - 1)
        identity_prompt = INFO_YOUR_ROLE.format(self.name, role_name, verbal_side[self.side]) # and do not pretend to be other roles throughout the game."
        self.identity_prompt = identity_prompt

        """
        One-shot Prompts
        """


        """
        Tutorial on strategies
        """
        # strategy_prompt = TUTORIAL_STRATEGIES_PROMPTS_ZERO_SHOT[role_name]
        # for prompt in strategy_prompt:
        #     self.session.inject({
        #         "role": "user",
        #         "content": prompt
        #     })
        #     self.session.inject({
        #         "role": "agent",
        #         "content": prompt
        #     })      

        """
        Reveal Phase
        """
        reveal_info = ''
        minion_list = []
        servant_list = []
        assassin = ''
        merlin = ''
        for idx, player_info in enumerate(self.player_list):
            if player_info[1] == "Minion":
                minion_list.append(str(idx))
            elif player_info[1] == "Servant":
                servant_list.append(str(idx))
            elif player_info[1] == "Assassin":
                assassin = str(idx)
            elif player_info[1] == "Merlin":
                merlin = str(idx)
        if role_name == "Merlin":
            if len(minion_list) == 1:
                reveal_info = REVEAL_PROMPTS['Merlin'][0].format(', '.join(minion_list), ', '.join(servant_list))
            elif len(minion_list) > 1:
                reveal_info = REVEAL_PROMPTS['Merlin'][1].format(', '.join(minion_list))
        if role_name == "Minion":
            if len(minion_list) == 1:
                reveal_info = REVEAL_PROMPTS['Minion'][0].format(assassin, ', '.join(servant_list + [merlin]))
            elif len(minion_list) > 1:
                reveal_info = REVEAL_PROMPTS['Minion'][1].format(', '.join(minion_list))
        if role_name == "Assassin":
            if len(minion_list) == 1:
                reveal_info = REVEAL_PROMPTS['Assassin'][0].format(', '.join(minion_list), ', '.join(servant_list + [merlin]))

        # Seperately pass the reveal info to the agent, so as to meet the requirement in filer_messages
        # TODO: is `system` allowed? 
        self.session.inject({
            # "role": "system",
            "role": "user",
            "content": content_prompt,
            "mode": "system",
        })
        self.session.inject({
            # "role": "system",
            "role": "user",
            "content": identity_prompt + '\n' + reveal_info,
            "mode": "system",
        })

        """
        Thought: what is my strategy for this game?
        """
        # self.session.action({
        #     "role": "user",
        #     "content": f"Based on the tutorial, what is my strategy for this game?",
        #     "mode": "strategy"
        # })


class AvalonBench(Task):
    def __init__(self, num_games, **configs):
        super().__init__(**configs)

        self.num_games = num_games
        self.num_players = configs.pop('num_players')

        self.data: List[Tuple[dict, set]] = []
        self.inputs: List[dict] = []
        self.targets: List[set] = []

        self.team_discussion: bool
        self.summarize: bool

        self.team_discussion = False
        self.summarize = True

        self.true_player_sides = []
        self.believed_player_sides = []
        self.game_info_player_0 = []

        self.avalon_config = AvalonConfig(self.num_players)
        self.env = AvalonGameEnvironment(self.avalon_config)
        self.socring = AvalonScoring(self.avalon_config)

        for _ in range(self.num_games):
            self.data.append((0, 0))
            self.inputs.append(0)
            self.targets.append(0)

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        outputs = [None for _ in range(len(self.data))]

        win_counter = 0
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
        data_item = self.inputs[index]
        env = self.env
        for _ in range(index):
            env.reset()

        sessions = [SessionWrapper(FakeSession()) for _ in range(self.num_players)]
        sessions[0] = SessionWrapper(session)

        # logger.debug("-"*100)
        # l = " New Game! "
        # logger.debug("-"*((100-len(l))//2) + l + "-"*(100-(100-len(l))//2 - len(l)))
        # logger.debug("-"*100)
        num_players = self.num_players
        # env.reset()
        # if args.test_role is not None:
        #     while env.get_roles()[0][1] != args.test_role:
        #         env.reset()

        seed = data_item

        player_list = []

        if num_players != len(sessions):
            raise ValueError(
                f"Number of players {num_players} doesn't match number of sessions {len(sessions)}"
            )


        for i, (role_i, role_name, side) in enumerate(env.get_roles()):
            # player_list.append(agents[role_i](i, f"Player {i}", config))
            # random.seed(0, version=1)
            player_list.append(Player(
                                    name=f"Player {i}",
                                    num_players=num_players,
                                    session=sessions[i],
                                    # random.choice([0, 1]),
                                    id = i,
                                    config = self.avalon_config,
                                    merlin = env.merlin,
                                    percival = env.percival,
                                    morgana = env.morgana,
                                    mordred = env.mordred,
                                    oberon = env.oberon,
                                    num_good = env.num_good,
                                    num_evil = env.num_evil,
                                    player_list = env.get_roles(),
                                    seed=seed
                                    ))
            

        # logger.debug(env.get_roles())


        player_sides = [side for _, _, side in env.get_roles()]
        for i, (role_i, role_name, side) in enumerate(env.get_roles()):
            player_list[i].assign_side(side)
            player_list[i].assign_role(role_i, role_name)
            # logger.debug(f"{player_list[i]} is {role_name}")

            if role_i == 0 or side == 0:
                assert player_list[i].strategy is not None
                assert player_list[i].strategy.role == 0 or player_list[i].strategy.side == 0
                player_list[i].strategy.see_sides(player_sides)


        """
        Benchmark Assassination
        """
        # if args.benchmark_assassination:
        #     assassin = env.get_assassin()
        #     target = int(player_list[assassin].assassinate(assassin, args.assassin_history))

        #     if target != int(args.merlin):
        #         logger.info("Failed")
        #     else:
        #         logger.info("Succeeded")
            
        #     return target != int(args.merlin)

        while not env.done:
            # print phase from env
            phase = env.get_phase()[0]
            # logger.debug("_"*50)
            # logger.debug(env.get_phase()[1] + ' ' + f"(Mission {env.turn}, Round {env.round})")
            
            # if phase is team selection phase, ask for team
            if phase == 0:
                discussion_history = []
                leader = env.get_quest_leader()
                """
                Summary
                """
                if self.summarize:
                    for idx, session in enumerate(sessions):
                        summary = await session.action({
                            "role": "user",
                            "content": "Please summarize the history. Try to keep all useful information, including your identity, other player's identities, and your observations in the game.",
                            "mode": "summarize"
                        })
                        # print(summary)
                        past_history = deepcopy(session.get_history())
                        session.overwrite_history(past_history[:2])
                        session.inject({
                            'role': "user",
                            'content': summary
                        })
                        print("History after summarization: ", session.get_history())
                """
                Leader speaks & Discussion
                """
                if self.team_discussion:
                    # logger.info("Discussion starts")
                    """
                    Leader speaks
                    """
                    team, statement = await player_list[leader].propose_team(env.get_team_size(), discussion_history, env.turn, mode="discussion")
                    # logger.debug(f"Please choose {env.get_team_size()} players in this round.")
                    # logger.debug(f"Leader's Statement: {statement}")

                    """
                    Discussion (sequential, once, in order for now) and Summarize
                    """
                    for idx, session in enumerate(sessions):
                        # if args.team_discussion:
                        if len(discussion_history) > 0:
                            contents = f"Statement from Leader {player_list[leader]}: \n\"{statement}\"\nAnd words from other players:\n{' '.join(discussion_history)}\n This is discussion phase, and you don't need to take an action. Please discuss about words from the leader and other players with just one sentence."
                        else:
                            contents = f"Statement from Leader {player_list[leader]}: \n\"{statement}\"\nThis is discussion phase, and you don't need to take an action. Please discuss with just one sentence. Please remember that you are Player {idx}, please do not pretend you are other players. Your words will be visible to other players."
                        discussion = await session.action({
                            "role": "user",
                            "content": contents,
                            "mode": "discuss_on_team"
                        })
                        discussion_history.append(f"Player {idx} : " + discussion + '\n')

                    for idx, session in enumerate(sessions):
                        session.inject({
                            "role": "user",
                            "content": f"Discussion has ended. Here are the contents:\nStatement from Leader {player_list[leader]}: \n\"{statement}\"\nAnd words from other players:\n{' '.join(discussion_history)}"
                        })
                        session.inject({
                            "role": "agent",
                            "content": "I understand."
                        })
                    # logger.info("Discussion has ended.")
                """
                Choose a team
                """
                team, statement = await player_list[leader].propose_team(env.get_team_size(), discussion_history, env.turn, mode="action")
                # logger.debug(team)
                env.choose_quest_team(team, leader)
                # logger.debug(f"{player_list[leader]} proposed team {list(team)}")

            # if phase is team voting phase, ask for votes
            elif phase == 1:
                discussion_history = []
                # votes_first_round = [player_list[i].vote_on_team(env.get_current_quest_team(), discussion_history, mode="statement"
                #                                      ) for i in range(num_players)]
                votes = [await player_list[i].vote_on_team(team=env.get_current_quest_team(), statement_history=discussion_history, mission_id=env.turn, mode="action"
                                                    ) for i in range(num_players)]
                # logger.debug(votes)
                outcome = env.vote_on_team(votes)
                # logger.info(f"Team votes: {votes}, team outcome: {outcome[2]}")
                """
                Thought on result of Team Selection TODO: polish the prompt
                """
                # for session in sessions:
                #     session.action({
                #         "role": "user",
                #         "content": f"{player_list[leader]} proposed team {team}. What do you think?",
                #         "mode": "thought_on_quest_and_team_result"
                #     })
                for session in sessions:
                    await session.action({
                        "role": "user",
                        # "content": f"Team votes: {votes}, team outcome: {outcome[2]}",
                        "content": verbalize_team_result(votes, outcome[2]),
                        "mode": "system"
                    })


            # if phase is quest voting phase, ask for votes
            elif phase == 2:
                discussion_history = []
                # votes_first_round = [player_list[i].vote_on_mission(discussion_history, mode="statement"
                #                                                     ) for i in env.get_current_quest_team()]
                votes = [await player_list[i].vote_on_mission(discussion_history, env.turn, env.get_current_quest_team(), mode="action"
                                                        ) for i in env.get_current_quest_team()]
                outcome = env.vote_on_quest(votes)
                # logger.info(f"Quest votes: {votes}, mission outcome: {outcome[2]}")
                outcome_verbal = ["failed", "succeeded"]
                """
                Thought on Quest result
                """
                for idx, session in enumerate(sessions):
                    await session.action({
                        "role": "user",
                        # "content": f"This mission has {outcome_verbal[int(outcome[2])]} with the team {list(team)} based on the quest results.",
                        "content": verbalize_mission_result(list(team), outcome[2]),
                        "mode": "system",
                        # "seed": self.seed,
                        "role_name": player_list[idx].role_name
                    })

                # Observe mission/quest result
                for single_player in player_list:
                    single_player.strategy.observe_mission(env.get_current_quest_team(), env.turn-1, outcome[3])
            
            # if phase is assassination phase, ask for assassination
            elif phase == 3:
                '''
                    TODO: Discussion before Assassination Phase
                '''
                # discussion_history = []
                # for session in sessions:
                #     discussion = session.action({
                #         "role": "user",
                #         "content": ' '.join(discussion_history) + ' ' + "Discussion Phase. Please discuss on the assassination target.",
                #         "mode": "vote"
                #     })
                #     discussion_history.append(f"{session.name}: " + discussion)


                assassin = env.get_assassin()
                target = int(await player_list[assassin].assassinate(assassin))
                # target = int(input(f"Enter assassination target: "))
                # logger.info(f"Assassination target: {target}")
                _, _, assassinated = env.choose_assassination_target(assassin, target)

                # logger.debug(f"assassinate outcome {assassinated}")
        
        for idx, session in enumerate(sessions):
            if player_list[idx].role_name == "Servant":
                believed_player_sides = await session.action({
                    "role": "user",
                    "content": GET_BELIEVED_SIDES,
                    "mode": "get_believed_sides",
                    "naive_result": list(map(int, player_list[idx].strategy.get_believed_sides()))
                })
                self.true_player_sides.append(list(map(int, env.is_good)))
                self.believed_player_sides.append(believed_player_sides)
            # pass

        # print whether good or evil won
        # for idx, session in enumerate(sessions):
            # logger.info(f"History in the last round of Player {idx}:")
            # logger.info(str(session.history))

        verbal_game_result = {
            -1: "Evil wins by mission!",
            0: "Evil wins by assassination!",
            1: "Good wins!"
        }
        if env.good_victory:
            # logger.info("Good wins!")
            answer = 1
        else:
            # logger.info("Evil wins!")
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
