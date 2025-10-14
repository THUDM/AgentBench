import asyncio
import json
import logging
import re
import weakref
from functools import cache
from typing import List, Tuple, Optional

from agentrl.worker.environment import create_controller
from agentrl.worker.task import Task, Session
from agentrl.worker.typings import (AgentCancelledException,
                                    RewardHistoryItem,
                                    SampleIndex,
                                    SampleStatus,
                                    TaskSampleExecutionResult)
from openai.types.chat import (ChatCompletionSystemMessageParam,
                               ChatCompletionToolMessageParam,
                               ChatCompletionUserMessageParam)

from .api import API
from .const import *
from .environment import KnowledgeGraphEnvironmentDelegation, ENV_SUBTYPE
from .utils.sparql_executer import SparqlExecuter


class KnowledgeGraph(Task):

    def __init__(self,
                 data_file: str,
                 max_rounds: int = 15,
                 one_shot: bool = False,
                 database_file: Optional[str] = None,
                 env_driver: str = 'manual',
                 env_options: Optional[dict] = None,
                 **kwargs):
        super().__init__(tools=TOOLS, **kwargs)
        self.logger = logging.getLogger(__name__)

        self.max_rounds = max_rounds
        self.one_shot = one_shot
        self.data: List[Tuple[dict, set]] = []
        self.inputs: List[dict] = []
        self.targets: List[set] = []
        with open(data_file, 'r') as f:
            data_object = json.load(f)
        for item in data_object:
            answer = item.pop("answer")
            gold_answer = set()
            for a in answer:
                gold_answer.add(a["answer_argument"])
            self.data.append((item, gold_answer))  # input and target
            self.inputs.append(item)
            self.targets.append(gold_answer)

        self.env_delegation = KnowledgeGraphEnvironmentDelegation(database_file)
        self.env_controller = create_controller(env_driver, self.env_delegation, **env_options)
        self.env_controller_background_task = None

    @cache
    def get_indices(self) -> List[SampleIndex]:
        return list(range(len(self.data)))

    async def start_sample(self, index: SampleIndex, session: Session) -> TaskSampleExecutionResult:
        self.env_controller.loop = asyncio.get_running_loop()
        if not self.env_controller_background_task:
            self.env_controller_background_task = asyncio.create_task(self.env_controller.background_task())
            weakref.finalize(self, self.env_controller_background_task.cancel)

        return await super().start_sample(index, session)

    def sync_start_sample(self, index: SampleIndex, session: Session) -> TaskSampleExecutionResult:
        self.logger.info(f'starting sample {index} with session id {session.id}')

        data_item = self.inputs[index]
        question = data_item['question']
        entities = data_item['entities']
        self.logger.info(f'[session {session.id}] Processing question: {question[:50]}...')

        session_id, _, urls = self.env_controller.sync_start_session(ENV_SUBTYPE)
        try:
            sparql_url = urls[ENV_SUBTYPE]
            sparql_executor = SparqlExecuter(sparql_url)
            api = API(sparql_executor, session.id)

            session.inject(ChatCompletionSystemMessageParam(
                role='system',
                content=INSTRUCTIONS.format(max_round=self.max_rounds)
            ))
            if self.one_shot:
                session.inject(ONE_SHOT)
            session.inject(ChatCompletionUserMessageParam(
                role='user',
                content=f'{question}\nEntities: [{", ".join([entity for entity in entities])}]'
            ))

            variables_list = []
            for current_round in range(self.max_rounds):
                response = session.sync_action()

                tool_calls = response.messages[0].get('tool_calls') or []
                if not tool_calls:
                    try:
                        final_message = response.messages[0].get('content') or ''
                        final_message = final_message.split("Observation:")[0]
                        final_message = final_message.replace("\\_", "_")
                        final_answer = re.findall(r'(?:Find|Final) Answer: #(\d+)', final_message)

                        if final_answer:
                            var_idx = int(final_answer[0])
                            answer_variable = variables_list[var_idx]

                            # base reward for submitting answer
                            predicted_answer = set(api.final_execute(answer_variable))
                            gold_answer = self.targets[index]

                            # calculate correctness and F1 score
                            is_correct = (len(gold_answer.intersection(predicted_answer)) == len(gold_answer) and
                                          len(gold_answer.intersection(predicted_answer)) == len(predicted_answer))
                            f1_score = self._calculate_f1(predicted_answer, gold_answer)

                            session.inject(RewardHistoryItem(reward=int(is_correct), score=f1_score))
                            return TaskSampleExecutionResult(status=SampleStatus.COMPLETED)

                    except IndexError:
                        self.logger.info(f'[session {session.id}] invalid variable index')
                        return TaskSampleExecutionResult(status=SampleStatus.AGENT_VALIDATION_FAILED)

                    except Exception:
                        self.logger.warning(f'[session {session.id}] error parsing final answer', exc_info=True)
                        return TaskSampleExecutionResult(status=SampleStatus.AGENT_VALIDATION_FAILED)

                    # no executable tool call
                    session.inject(ChatCompletionUserMessageParam(
                        role='user',
                        content='No valid function calls found! Need to recheck the function calls.'
                    ))
                    continue

                # process tool calls
                for tool_call in tool_calls:
                    tool_call_id: Optional[str] = None
                    try:
                        function_name = tool_call['function']['name']
                        tool_call_id = tool_call['id']
                        arguments = json.loads(tool_call['function']['arguments'])

                        try:
                            function = getattr(api, function_name)
                        except AttributeError:
                            session.inject(ChatCompletionToolMessageParam(
                                role='tool',
                                content=f'Provide an invalid function name. Function {function_name} does not exist',
                                tool_call_id=tool_call_id
                            ))
                            continue

                        try:
                            function_arguments = []
                            for argument_name in TOOLS_PARAM_ORDER[function_name]:
                                value = arguments[argument_name]
                                if isinstance(value, str) and value.startswith("#"):
                                    function_arguments.append(variables_list[int(value[1:])])
                                elif value in entities:
                                    function_arguments.append(entities[value])
                                else:
                                    function_arguments.append(value)
                        except KeyError:
                            session.inject(ChatCompletionToolMessageParam(
                                role='tool',
                                content=f'Arguments do not match the function signature. Error processing arguments for {function_name}',
                                tool_call_id=tool_call_id
                            ))
                            continue

                        execution, execution_message = function(*function_arguments)
                        self.logger.info(f'[session {session.id}] function {function_name} executed successfully')

                        if "##" in execution_message:
                            execution_message = execution_message.replace('##', f'#{len(variables_list)}')
                            variables_list.append(execution)

                        session.inject(ChatCompletionToolMessageParam(
                            role='tool',
                            content=execution_message,
                            tool_call_id=tool_call_id
                        ))

                    except Exception as e:
                        self.logger.warning(f'[session {session.id}] error executing tool call', exc_info=True)
                        if tool_call_id:
                            session.inject(ChatCompletionToolMessageParam(
                                role='tool',
                                content=f'Error processing tool call: {e}',
                                tool_call_id=tool_call_id
                            ))
                        else:
                            session.inject(ChatCompletionUserMessageParam(
                                role='user',
                                content=f'Error processing tool call: {e}'
                            ))

            # max rounds reached
            else:
                self.logger.info(f'[session {session.id}] max rounds reached')
                return TaskSampleExecutionResult(status=SampleStatus.TASK_LIMIT_REACHED)

        except AgentCancelledException:
            return TaskSampleExecutionResult(status=SampleStatus.CANCELLED)
        except Exception:
            self.logger.exception(f'error in task execution of {index=}, {session.id=}')
            return TaskSampleExecutionResult(status=SampleStatus.TASK_ERROR)
        finally:
            self.env_controller.sync_end_session(session_id)

    @staticmethod
    def _calculate_f1(predict_answer, gold_answer):
        if not isinstance(predict_answer, set):
            predict_answer = set(predict_answer)
        if not isinstance(gold_answer, set):
            gold_answer = set(gold_answer)

        TP = len(gold_answer.intersection(predict_answer))
        FP = len(predict_answer) - TP
        FN = len(gold_answer) - TP

        if TP == 0:
            return 0.0

        precision = TP / (TP + FP)
        recall = TP / (TP + FN)

        return 2 * precision * recall / (precision + recall)
