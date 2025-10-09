import json
import logging
from typing import Dict, List, Any
from uuid import uuid4

from agentrl.worker.task import Task, Session
from agentrl.worker.typings import (AgentCancelledException,
                                    RewardHistoryItem,
                                    SampleStatus,
                                    TaskOutput,
                                    TaskSampleExecutionResult)
from openai.types.chat import (ChatCompletionSystemMessageParam,
                               ChatCompletionToolMessageParam,
                               ChatCompletionUserMessageParam)
from web_agent_site.envs.web_agent_text_env import WebAgentTextEnv

prompt_with_max_turn = """
You are web shopping.
I will give you instructions about what to do.
You have to follow the instructions.
Every round I will give you an observation and a list of available actions,
you have to respond with calling a tool provided based on the state and instruction.
You can use search tool if search is available.
You can click one of the buttons in clickables.
If the action is not valid, perform nothing.
Keywords in search are up to you, but the value in click must be a value in the list of available actions.
Remember that your keywords in search should be carefully designed.
Your should first think about what to do, then call a tool correspondingly.
You should always use a tool, even if you have questions to confirm. You can use whatever tool is available and do not need permission from the user.
"""


class WebShop(Task):
    def __init__(self, tools=None, **configs):
        super().__init__(**configs)
        self.logger = logging.getLogger(__name__)
        self.ranging = (configs.pop("start", 0), configs.pop("end", 500))
        self.logger.info('Initializing WebShop environment...')
        self.server = WebAgentTextEnv(observation_mode="text", human_goals=True).server
        self.tools = tools
        self.max_rounds = configs.get('round', 20)

    def get_indices(self) -> List[Any]:
        return list(range(*self.ranging))

    def sync_start_sample(self, index: int, session: Session) -> TaskSampleExecutionResult:
        history = []

        env = WebAgentTextEnv(
            observation_mode="text",
            server=self.server,
            human_goals=True,
            session_prefix=str(uuid4()) + '-'
        )
        try:
            env.reset(index)
            session.inject(ChatCompletionSystemMessageParam(
                role='system',
                content=prompt_with_max_turn
            ))

            action = None
            observation = env.observation
            reward = 0
            call_id = None
            for j in range(self.max_rounds):
                available_actions = env.get_available_actions()
                if j == 0:
                    session.inject(ChatCompletionUserMessageParam(
                        role='user',
                        content=f'The initial observation:\n{observation}\n\nAvailable Actions:\n{available_actions}'
                    ))
                else:
                    if action is None:
                        session.inject(ChatCompletionUserMessageParam(
                            role='user',
                            content=f'Observation:\n{observation}\n\nAvailable Actions:\n{available_actions}'
                        ))
                    else:
                        session.inject(ChatCompletionToolMessageParam(
                            role='tool',
                            content=f'Action: {action}\n\nObservation:\n{observation}\n\nAvailable Actions:\n{available_actions}',
                            tool_call_id=call_id
                        ))

                response = session.sync_action()

                tool_calls = []
                for message in response.messages:
                    tool_calls.extend(message.get('tool_calls', []) or [])

                finish_reason = SampleStatus.COMPLETED
                if not tool_calls:
                    action = None
                    observation = "No executable tool calls found! You should call a tool instead."
                else:
                    action = None
                    try:
                        tool_call = tool_calls[0]
                        func_name = tool_call["function"]["name"]
                        arguments = tool_call["function"]["arguments"]
                        arguments = json.loads(arguments)
                        arguments = list(arguments.values())
                        call_id = tool_call["id"]
                        if func_name == "search_action":
                            action = f"search[{arguments[0]}]"
                        elif func_name == "click_action":
                            action = f"click[{arguments[0]}]"
                    except:
                        self.logger.warning(f'Error processing tool call. {tool_calls=}', exc_info=True)
                        session.inject(ChatCompletionUserMessageParam(
                            role='user',
                            content=f"No valid tool call found from agent."
                        ))
                        session.inject(RewardHistoryItem(reward=0, score=0))
                        continue
                history.append(
                    {
                        "observation": observation,
                        "available_actions": available_actions,
                        "response": response,
                        "action": action,
                    }
                )
                if not action:
                    reward = 0
                    done = False
                    round_reward = 0
                else:
                    observation, reward, done, info = env.step(action)
                    round_reward = reward
                history[-1]["reward"] = reward
                history[-1]["done"] = done
                rewardhistory = RewardHistoryItem(reward=round_reward, score=round_reward)
                session.inject(rewardhistory)
                if done:
                    break
            else:
                finish_reason = SampleStatus.TASK_LIMIT_REACHED
                rewardhistory = RewardHistoryItem(reward=0, score=0)
                session.inject(rewardhistory)
                session.inject(ChatCompletionToolMessageParam(
                    role='tool',
                    content='Task limit reached.',
                    tool_call_id=call_id
                ))

            return TaskSampleExecutionResult(
                status=finish_reason,
                result={
                    "reward": reward,
                    "history": history,
                },
            )
        except AgentCancelledException:
            session.inject(RewardHistoryItem(reward=0, score=0))
            return TaskSampleExecutionResult(
                status=SampleStatus.CANCELLED,
                result={
                    "reward": 0,
                    "history": history,
                },
            )
        except:
            self.logger.exception(f'Error during sample execution')
            return TaskSampleExecutionResult(
                status=SampleStatus.TASK_ERROR,
                result={
                    "reward": 0,
                    "history": history,
                },
            )
        finally:
            try:
                env.close()
            except:
                pass

    def calculate_overall(self, results: List[TaskOutput]) -> Dict:
        def factory(key):
            def f(output):
                output = [x for x in output if x]
                if key == "history":
                    return (
                        sum([len(x[key]) for x in output]) / len(output)
                        if len(output) > 0
                        else 0
                    )
                return (
                    sum([x[key] for x in output]) / len(output)
                    if len(output) > 0
                    else 0
                )

            return f

        results = [x.result for x in results if x]

        return {
            "reward": factory("reward")(results),
        }
