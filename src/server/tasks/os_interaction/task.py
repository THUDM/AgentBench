from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import re
import traceback
import weakref
from typing import List, Dict, Any, Tuple, TYPE_CHECKING
from typing import Optional

from agentrl.worker.environment import create_controller
from agentrl.worker.task import Task, Session
from agentrl.worker.typings import (AgentCancelledException,
                                    TaskOutput,
                                    TaskSampleExecutionResult,
                                    SampleStatus,
                                    RewardHistoryItem)
from openai.types.chat import (ChatCompletionSystemMessageParam,
                               ChatCompletionToolMessageParam,
                               ChatCompletionUserMessageParam)

from .environment import OSEnvironmentDelegation

if TYPE_CHECKING:
    from agentrl.worker.environment import EnvironmentController


class Container:
    def __init__(self, controller: EnvironmentController, image: str):
        self.image = image
        self.controller = controller
        self.session_id: Optional[str] = None
        self.container_id: Optional[str] = None

    async def initialize(self):
        res = await self.controller.start_session(self.image)
        self.session_id = res[0]
        self.container_id = res[1][self.image]

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def cleanup(self):
        await self.controller.end_session(self.session_id)

    async def execute(self, command: str):
        """异步执行命令"""

        class DummyOutput:
            output: bytes
            exit_code: int

            def __init__(self, code, o):
                self.output = o
                self.exit_code = code

        # call environment controller to renew session
        await self.controller.renew_session(self.session_id)

        if not isinstance(command, str):
            logging.warning("Invalid command type, expected string")
            return DummyOutput(-1, b"")

        output = await self.controller.execute_shell(self.container_id, command)

        # Clean up the output by removing terminal control sequences, removes escape sequences starting with
        # ESC (0x1b), followed by...
        # ... any characters, an '@' character, any characters, ending with '#' or '$'
        output = re.sub(b"\x1b.+@.+[#|$] ", b'', output)
        # ... '[' and any combination of digits and semicolons, ending with a letter (a-z or A-Z)
        output = re.sub(b'\x1b\\[[0-9;]*[a-zA-Z]', b'', output)
        # ... ']' and any digits, a semicolon, any characters except BEL (0x07), and ending with BEL
        output = re.sub(b'\x1b][0-9]*;[^\x07]*\x07', b'', output)
        # ... '[?2004' and either 'h' or 'l'
        output = re.sub(b'\x1b\[\?2004[hl]', b'', output)

        # Remove BEL characters (0x07)
        output = re.sub(b'\x07', b'', output)

        return DummyOutput(0, output)

    async def execute_independent(self, command, *params) -> Tuple[int, bytes, bytes]:
        """异步执行独立命令"""

        # call environment controller to renew session
        await self.controller.renew_session(self.session_id)

        language, command = command

        if language == "bash":
            cmd = ["bash", "-c", command]
            if params:
                cmd.append("--")
                cmd.extend(params)
        elif language == "python":
            cmd = ["python3", "-c", command, *params]
        elif language == "c++" or language == "c":
            if language == "c++":
                compile_cmd = (
                    "bash",
                    f'echo "{json.dumps(command)}" > /tmp/main.cpp && '
                    f"g++ -o /tmp/a.out /tmp/main.cpp",
                )
            else:  # c
                compile_cmd = (
                    "bash",
                    f'echo "{json.dumps(command)}" > /tmp/main.cpp && '
                    f"gcc -o /tmp/a.out /tmp/main.cpp",
                )

            # 编译代码
            await self.execute_independent(compile_cmd, None)
            cmd = ["/tmp/a.out", *params]
        else:
            raise ValueError("Unsupported language")

        return await self.controller.execute_command(self.container_id, cmd)


class JudgeConfig:
    image: str = None
    init_script: List[Tuple[str, str]] = None
    start: Tuple[str, str] = None
    description: str
    check: list = None
    match: dict = None
    example_script: str = None

    def get_evaluation_type(self):
        if self.check:
            return "check"
        elif self.match:
            return "match"

    def get_evaluation_content(self):
        return self.check or self.match


class OSInteraction(Task):

    def __init__(self,
                 data_config,
                 docker_config,
                 round_limit=8,
                 tools=None,
                 env_driver: str = 'docker',
                 env_options: Optional[dict] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.round_limit: int = round_limit
        self.data_config = data_config
        self.docker_config = docker_config
        self.tools = tools
        self.full_async = True
        self.problem_configs: Dict[str, Dict[str, Any]] = {}  # {index: CONFIG}

        matches = []
        for item in self.data_config["files"]:
            path = item["problem_file"]
            for file in glob.glob(path):
                if file.endswith(".json") or file.endswith(".jsonl"):
                    matches.append(
                        {
                            "problem_file": file,
                            "script_dir": item["script_dir"],
                            "index_prefix": item["index_prefix"]
                                            + os.path.basename(file)
                                            .removesuffix(".json")
                                            .removesuffix(".jsonl")
                                            + "-",
                        }
                    )
        self.data_config["files"] = matches

        next_idx = 0
        for item in self.data_config["files"]:
            problem_file = item["problem_file"]
            single_file_configs = self._load_configs(problem_file, item["script_dir"])
            dict_configs = {}
            for config in single_file_configs:
                dict_configs[next_idx] = {
                    "file": problem_file,
                    "config": config,
                    "index": next_idx,
                }
                next_idx += 1
            self.problem_configs.update(dict_configs)

        logging.info(f"Initialized OSInteraction with {len(self.problem_configs)} problem configs")

        self.env_delegation = OSEnvironmentDelegation(self.docker_config['localhost'])
        self.env_controller = create_controller(env_driver, self.env_delegation, **env_options)
        self.env_controller_background_task = None

    def _load_configs(self, config_path, script_root_dir=".") -> List[JudgeConfig]:
        def load_script(script_obj):
            if script_obj is None:
                return None
            if type(script_obj) is str:
                return "bash", script_obj
            if "language" not in script_obj:
                language = "bash"
            else:
                language = script_obj["language"]
            if "file" in script_obj:
                with open(
                        os.path.join(script_root_dir, script_obj["file"]), encoding="utf-8"
                ) as f:
                    return language, f.read()
            elif "code" in script_obj:
                return language, script_obj["code"]
            else:
                raise ValueError("Invalid Script Object")

        # 1. handle input file:
        logging.info(f"Loading config from: {config_path}")
        if config_path.endswith(".json"):
            with open(config_path, encoding="utf-8") as f:
                config_raw = json.load(f)
            if isinstance(config_raw, list):
                pass
            elif isinstance(config_raw, dict):
                config_raw = [config_raw]
            else:
                raise ValueError("Invalid Config File")
        elif config_path.endswith(".jsonl"):
            with open(config_path, encoding="utf-8") as f:
                config_raw = [json.loads(line) for line in f.readlines()]
        else:
            raise ValueError("Invalid Config File")

        # 2. handle configs
        configs: list[JudgeConfig] = []
        for item in config_raw:
            config = JudgeConfig()
            config.description = item["description"]
            if "create" in item:
                config.image = (
                    item["create"]["local"]
                    if ("local" in item["create"])
                    else 'default'
                )
                if "init" in item["create"]:
                    if type(item["create"]["init"]) is not list:
                        config.init_script = [load_script(item["create"]["init"])]
                    else:
                        config.init_script = [
                            load_script(script_obj)
                            for script_obj in item["create"]["init"]
                        ]
                else:
                    config.init_script = []
            else:
                config.image = 'default'
            if "start" in item:
                config.start = load_script(item["start"])
            evaluation = item["evaluation"]
            if "match" in evaluation:
                if type(evaluation["match"]) is str:
                    config.match = {"answer": evaluation["match"], "strip": True}
                else:
                    config.match = evaluation["match"]
            elif "check" in evaluation:
                if type(evaluation["check"]) is not list:
                    config.check = [load_script(evaluation["check"])]
                else:
                    config.check = [
                        load_script(script_obj) for script_obj in evaluation["check"]
                    ]
            else:
                raise ValueError("check or match must exist.")
            if "check" in evaluation and "example" in evaluation:
                config.example_script = load_script(evaluation["example"])
            configs.append(config)

        logging.info(f"Loaded {len(configs)} configuration(s) from {config_path}")
        return configs

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        overall = {
            "total": len([config for config in results if config]),
            "pass": len(
                [
                    config
                    for config in results
                    if (config and config.result and config.result.get("result", False))
                ]
            ),
        }
        overall["wrong"] = overall["total"] - overall["pass"]
        overall["acc"] = overall["pass"] / overall["total"] if overall["total"] else 0
        return {
            "overall": overall,
        }

    def get_indices(self) -> List[Any]:
        return list(self.problem_configs.keys())

    @staticmethod
    def _extract_action(raw: str):
        think_pattern = r"Think:\s*(.+)"
        act_pattern = r"Act:\s*(.+)"

        think = re.findall(think_pattern, raw)
        act = re.findall(act_pattern, raw)

        ret = {"thought": "\n".join(think), "action": None, "content": None}

        # reversly iterate over the action list
        for action in act[::-1]:
            if action.lower().startswith("bash"):
                ret["action"] = "bash"
                break
            if action.lower().startswith("finish"):
                ret["action"] = "commit"
                break
            if action.lower().startswith("answer"):
                content = action[6:].strip()
                left_par_pos = content.find("(")
                right_par_pos = content.rfind(")")
                if left_par_pos == -1 or right_par_pos == -1:
                    continue
                content = content[left_par_pos + 1: right_par_pos]
                ret["action"] = "commit"
                ret["content"] = content
                break

        if ret["action"] == "bash":
            # extract from ```bash to ```
            content_pattern = r"```bash\n(.*?)\n```"
            content = re.findall(content_pattern, raw, re.DOTALL)
            content = "\n\n".join(content)
            ret["content"] = content

        return ret

    # added for function calling
    @staticmethod
    def _extract_function(func_name: str, arguments: List, thought: str):
        ret = {"thought": thought, "action": None, "content": None}
        if func_name == "bash_action":
            ret["action"] = "bash"
            ret["content"] = arguments[0]
        if func_name == "finish_action":
            ret["action"] = "commit"
            ret["content"] = arguments[0] if arguments else None
        if func_name == "answer_action":
            ret["action"] = "commit"
            ret["content"] = arguments[0]

        return ret

    async def start_sample(self, index, session: Session) -> TaskSampleExecutionResult:
        if not self.env_controller_background_task:
            self.env_controller_background_task = asyncio.create_task(self.env_controller.background_task())
            weakref.finalize(self, self.env_controller_background_task.cancel)

        logging.info(f"Starting sample with index: {index}")
        data_item = self.problem_configs[index]
        config = data_item["config"]
        file = data_item["file"]
        index_in_file = data_item["index"]

        container = Container(self.env_controller, config.image)
        try:
            logging.info("Initializing container")
            await container.initialize()
            logging.info("Container initialized successfully")

            logging.info("Starting judge process")
            result = await self._judge(session, config, container)
            result.result["file"] = file
            result.result["index_in_file"] = index_in_file
            logging.info(f"Judge process completed with status: {result.status}")
            return result
        except AgentCancelledException:
            session.inject(RewardHistoryItem(reward=0, score=0))
            return TaskSampleExecutionResult(status=SampleStatus.CANCELLED)
        except:
            logging.exception(f"Error in start_sample")
            session.inject(RewardHistoryItem(reward=0, score=0))
            return TaskSampleExecutionResult(
                status=SampleStatus.TASK_ERROR,
                result={"result": False, "error": traceback.format_exc()},
            )
        finally:
            try:
                await container.cleanup()
            except Exception as e:
                logging.error(f"Error during container cleanup: {str(e)}")

    async def _judge(
            self, session: Session, config: JudgeConfig, container: Container
    ) -> TaskSampleExecutionResult:
        """执行任务判断的主要逻辑"""
        logging.info("Starting execution")

        # 初始化环境
        setup_result = await self._setup_execution_environment(config, container)
        if setup_result:
            return setup_result

        # 注入初始消息
        self._inject_initial_messages(session, config.description)

        # 初始化状态变量
        finish = False
        function_name = None
        call_id = None

        # 主交互循环
        for round_num in range(self.round_limit):
            logging.info(f"Starting round {round_num + 1}/{self.round_limit}")
            round_reward = 0

            # 处理Agent行动
            action_result = await self._handle_agent_action(
                session, container, round_num, finish, round_reward, function_name, call_id
            )

            # 更新状态
            function_name = action_result.get("function_name", function_name)
            call_id = action_result.get("id", call_id)
            finish = action_result.get("finish", finish)

            # 检查是否有错误或需要提前结束
            if action_result.get("early_return"):
                return action_result.get("result")

            # 如果得到答案，跳出循环
            if "answer" in action_result:
                answer = action_result["answer"]
                break
        else:
            # 处理回合数用尽的情况
            logging.warning("Task round limit reached")

            # 注入奖励
            final_rewardhistory = RewardHistoryItem(reward=0, score=0)
            session.inject(final_rewardhistory)

            return TaskSampleExecutionResult(
                status=SampleStatus.TASK_LIMIT_REACHED,
                result={"result": False, "reason": "round limit"},
            )

        # 评估答案
        evaluation_result = await self._evaluate_answer(answer, config, container, session)

        # 如果发生评估错误
        if evaluation_result.get("error"):
            return evaluation_result.get("result")

        # 设置最终奖励
        jd = evaluation_result.get("success", False)
        os_score = 1 if jd else 0
        final_reward = 1 if jd else 0

        logging.info(f"Task completed {'successfully' if jd else 'unsuccessfully'}")

        # 注入最终奖励
        final_rewardhistory = RewardHistoryItem(reward=final_reward, score=os_score)
        session.inject(final_rewardhistory)

        return TaskSampleExecutionResult(
            status=SampleStatus.COMPLETED, result={"result": jd}
        )

    async def _setup_execution_environment(
            self, config: JudgeConfig, container: Container
    ) -> Optional[TaskSampleExecutionResult]:
        """设置执行环境，运行初始化和启动脚本"""
        # 运行初始化脚本
        if config.init_script:
            for i, script in enumerate(config.init_script):
                logging.info(f"Running init script {i + 1}/{len(config.init_script)}")
                exit_code, _, stderr = await container.execute_independent(script)
                if exit_code != 0:
                    logging.error(f"Init script failed with exit code: {exit_code}")
                    return TaskSampleExecutionResult(
                        status=SampleStatus.UNKNOWN,
                        result={"result": False, "error": f'Init script {script} failed: {stderr}'}
                    )

        # 运行启动脚本
        if config.start:
            logging.info("Running start script")
            try:
                start = await container.execute(config.start[1])
                if start.exit_code != 0:
                    logging.error(f"Start script failed with exit code: {start.exit_code}")
                    return TaskSampleExecutionResult(
                        status=SampleStatus.UNKNOWN,
                        result={"result": False, "error": f'Start script {config.start} failed: {start}'}
                    )
            except Exception as e:
                logging.error(f"Error in start script: {str(e)}")
                return TaskSampleExecutionResult(
                    status=SampleStatus.UNKNOWN,
                    result={"result": False, "error": f'Error in start script: {str(e)}'}
                )

        logging.info("Execution setup completed successfully")
        return None

    def _inject_initial_messages(self, session: Session, description: str) -> None:
        """注入系统消息和问题描述"""
        # 系统消息
        system_message = """You are an assistant that will act like a person. I will play the role of a Linux (Ubuntu) operating system.
Your goal is to implement the operations required by me or answer the questions proposed by me.
For each of your turns, you should first think about what you should do, and then call exactly one of the provided tools according to the situation.
If you think the output is too long, I will truncate it. The truncated output is not complete. You have to deal with the truncating problem by yourself.
Attention, your bash code should not contain any input operation. Once again, you should use one tool in each turn, and should not respond without function calling.
Note that if you think the task has been finished, or there is some message missing to completely complete the task, you should respond with calling the function "finish_action", as no additional information will be provided.
Also, note that if you have gotten the answer to the question, you should call the "answer_action" tool instead of simply writing your answer in your response.
Your answers should be exact and precise (for example, a single number), do not answer with full sentences or phrases.
Always use a tool provided instead of simply responding with content."""

        session.inject(ChatCompletionSystemMessageParam(
            role='system',
            content=system_message
        ))
        session.inject(ChatCompletionUserMessageParam(
            role='user',
            content=f'Now, I will start a new problem in a new OS. My problem is:\n\n{description}'
        ))

    async def _handle_agent_action(
            self, session: Session, container: Container, round_num: int,
            finish: bool, round_reward: float, function_name: Optional[str], call_id: Optional[str]
    ) -> dict:
        # 获取Agent行动
        response = await session.action()

        result = {
            "finish": finish,
            "round_reward": round_reward,
            "function_name": function_name,
            "id": call_id
        }

        # 提取工具调用
        response_content = None
        tool_calls = []
        for message in response.messages:
            if not response_content:
                response_content = message.get('content')
            tool_calls.extend(message.get('tool_calls', []) or [])

        # 检查是否有有效的工具调用
        if len(tool_calls) == 0:
            logging.warning("Empty tool calls array")
            session.inject(ChatCompletionUserMessageParam(
                role='user',
                content="No executable tool calls found. Please call a tool instead"
            ))
            round_rewardhistory = RewardHistoryItem(reward=round_reward, score=0)
            session.inject(round_rewardhistory)
            return result

        # 获取第一个工具调用
        tool_call = tool_calls[0]
        function_name = tool_call["function"]["name"]
        logging.info(f"Processing tool call: {function_name}")
        result["function_name"] = function_name

        # 解析参数
        try:
            arguments = tool_call["function"]["arguments"]
            arguments = json.loads(arguments)
            if not response_content and 'thought' in arguments:
                response_content = arguments['thought']
            arguments = list(arguments.values())
        except Exception as e:
            logging.error(f"Error parsing arguments: {str(e)}")
            call_id = tool_call.get("id")
            result["id"] = call_id
            session.inject(ChatCompletionToolMessageParam(
                role='tool',
                content=str(e),
                tool_call_id=call_id
            ))
            round_rewardhistory = RewardHistoryItem(reward=round_reward, score=0)
            session.inject(round_rewardhistory)
            return result

        # 提取工具调用ID和思考内容
        call_id = tool_call["id"]
        result["id"] = call_id

        # 提取函数
        action_data = self._extract_function(function_name, arguments, response_content)

        # 检查动作有效性
        if "action" not in action_data:
            logging.warning("Invalid action in function extraction")
            session.inject(ChatCompletionToolMessageParam(
                role='tool',
                content="Invalid function call. Please call a tool instead",
                tool_call_id=call_id
            ))
            round_rewardhistory = RewardHistoryItem(reward=round_reward, score=0)
            session.inject(round_rewardhistory)
            return result

        if action_data["action"] not in ["bash", "commit"]:
            logging.warning(f"Unsupported action: {action_data['action']}")
            session.inject(ChatCompletionToolMessageParam(
                role='tool',
                content="Invalid function call. Please call a tool instead",
                tool_call_id=call_id
            ))
            round_rewardhistory = RewardHistoryItem(reward=round_reward, score=0)
            session.inject(round_rewardhistory)
            return result

        # 处理有效的动作
        action = action_data["action"]
        content = action_data["content"]

        # 提交答案
        if action == "commit":
            logging.info("Received commit action with answer")
            result["answer"] = content
            result["finish"] = True
        # 执行bash命令
        elif action == "bash":
            await self._execute_bash_command(session, container, content, call_id)

        # 注入回合奖励
        round_rewardhistory = RewardHistoryItem(reward=round_reward, score=0)
        session.inject(round_rewardhistory)

        return result

    async def _execute_bash_command(
            self, session: Session, container: Container, command: str, id: str
    ) -> None:
        """执行bash命令并处理结果"""
        logging.info("Executing bash command")

        # 执行命令
        result = await container.execute(command)

        # 解码输出
        try:
            result_text = result.output.decode("utf-8")
        except Exception as e:
            logging.error(f"Error decoding output: {str(e)}")
            result_text = "OS Environment output cannot be decoded as UTF-8"

        # 截断过长输出
        if len(result_text) > 800:
            logging.debug("Output truncated due to length")
            result_text = result_text[:780] + "\n[truncated because the output is too long]"

        # 注入结果
        session.inject(ChatCompletionToolMessageParam(
            role='tool',
            content=f'The output of the OS:\n\n{result_text}' if result_text else "The output of the OS is empty.",
            tool_call_id=id
        ))

    async def _evaluate_answer(
            self, answer, config: JudgeConfig, container: Container, session: Session
    ) -> dict:
        """评估答案"""
        result = {"success": False}

        # 处理答案格式
        if isinstance(answer, str) and config.match and config.match["strip"]:
            answer = answer.strip()
        logging.info(f"Final answer: {answer}")

        # 使用匹配标准评估
        if config.match:
            result["success"] = self._evaluate_by_match(answer, config)
        # 使用检查脚本评估
        elif config.check:
            result["success"] = await self._evaluate_by_check_scripts(answer, config, container)
        # 无评估方法
        else:
            logging.error("No evaluation method specified")
            final_rewardhistory = RewardHistoryItem(reward=0, score=0)
            session.inject(final_rewardhistory)
            result["error"] = True
            result["result"] = TaskSampleExecutionResult(
                status=SampleStatus.TASK_ERROR, result={"result": False}
            )

        return result

    def _evaluate_by_match(self, answer: str, config: JudgeConfig) -> bool:
        """使用匹配标准评估答案"""
        logging.info("Evaluating answer with match criteria")

        if "answer" in config.match:
            success = (answer == config.match["answer"])
        elif "regex" in config.match:
            success = (re.search(config.match["regex"], answer) is not None)
        else:
            success = False

        logging.info(f"Match evaluation result: {success}")
        return success

    async def _evaluate_by_check_scripts(
            self, answer: str, config: JudgeConfig, container: Container
    ) -> bool:
        """使用检查脚本评估答案"""
        logging.info("Evaluating answer with check scripts")
        params = [str(answer)]

        for script_index, script in enumerate(config.check):
            if script is None:
                script = config.example_script

            logging.info(f"Running check script {script_index + 1}/{len(config.check)}")
            exit_code, stdout, _ = await container.execute_independent(script, *params)
            logging.info(f"Check script output: {stdout.decode('utf-8')}")

            if exit_code != 0:
                logging.warning(f"Check script failed with exit code: {exit_code}")
                return False

            params.append(stdout.decode("utf-8"))

        logging.info("Check evaluation result: True")
        return True
