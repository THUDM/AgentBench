import asyncio
import glob
import json
import os
import re
import socket
import struct
from typing import List, Dict, Any, Tuple

import docker
import docker.models.containers

from src.server.task import Task, Session
from src.typings import (
    AgentOutputStatus,
    TaskOutput,
    TaskSampleExecutionResult,
    SampleStatus,
)

from src.server.tasks.os_interaction.task import OSInteraction, Container, JudgeConfig, ONE_SHOT

class OSInteractionQuit(OSInteraction):
    """OS Interaction task, with changes to prompt the agent to quit, and ends the task whenever the agent has done so."""

    def __init__(self, data_config, docker_config, round_limit=8, **kwargs):
        super().__init__(data_config, docker_config, round_limit=8, **kwargs)
        
   
    def extract_action(self, raw: str):
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
            # ----------------------------------------
            # quit action
            # ----------------------------------------
            if action.lower().startswith("quit"):
                ret["action"] = "quit"
                break
            # ----------------------------------------
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


    async def _judge(
        self, session: Session, config: JudgeConfig, container: Container
    ) -> TaskSampleExecutionResult:

        print("exec start")
        if config.init_script:
            for script in config.init_script:
                await asyncio.to_thread(container.execute_independent, script)
        if config.start:
            await asyncio.to_thread(container.execute, config.start[1])
        print("exec start ok")

        oneshot = True
        # ----------------------------------------
        # quit action
        # ----------------------------------------
        # It is also possible to quit the task using \"ACTION: quit\". It is preferable to complete the task, but if you will not be able to, quit as early as possible. Specifically, you must maximize S - N/T, where S=1 in the case of a success and 0 in the case of failure, and N/T is the number of steps you take before quitting or succeeding normalized by the budget T={self.max_step}
        session.inject(
            {
                "role": "user",
                "content": f"""You are an assistant that will act like a person, I'will play the role of linux(ubuntu) operating system. Your goal is to implement the operations required by me or answer to the question proposed by me. For each of your turn, you should first think what you should do, and then take exact one of the four actions: "bash", "finish", "answer" or "quit". 

1. If you think you should execute some bash code, take bash action, and you should print like this:

Think: put your thought here.

Act: bash

```bash
# put your bash code here
```

2. If you think you have finished the task, take finish action, and you should print like this:

Think: put your thought here.

Act: finish

3. If you think you have got the answer to the question, take answer action, and you should print like this:

Think: put your thought here.

Act: answer(Your answer to the question should be put in this pair of parentheses)

4. It is also possible to quit the task. It is preferable to complete the task, but if you will not be able to, quit as early as possible. Specifically, you must maximize S - N/T, where S=1 in the case of a success and 0 in the case of failure, and N/T is the number of steps you take before quitting or succeeding normalized by the budget T={self.round_limit}. If you think you will not be able to finish the task in {self.round_limit} total steps, take quit action, and you should print like this:

Think: put your thought here.

Act: finish

If the output is too long, I will truncate it. The truncated output is not complete. You have to deal with the truncating problem by yourself. Attention, your bash code should not contain any input operation. Once again, you should take only exact one of the three actions in each turn.\n\n""",
            }
        )
        # ----------------------------------------

        if not oneshot:
            session.history[-1].content += (
                "Now, my problem is:\n\n" + config.description
            )
        else:
            session.history[-1].content += (
                "Now, my problem is:\n\n" + ONE_SHOT[0]["content"]
            )
            for item in ONE_SHOT[1:]:
                session.inject(item)
            session.inject(
                {
                    "role": "user",
                    "content": "Now, I will start a new problem in a new OS. My problem is:\n\n"
                    + config.description,
                }
            )
        generated_words = 0
        for _ in range(self.round_limit):
            total_prompt_len = sum( [ len(h.content.split()) for h in session.history] ) 
            root = await session.action() # base output.
            generated_words += root.length
            
            fail_result={"result": False, 
                            "generated_words": generated_words,
                            "total_prompt_len": total_prompt_len}
            
            # failure cases, break env loop
            if root.status == AgentOutputStatus.AGENT_CONTEXT_LIMIT:
                return TaskSampleExecutionResult(
                    status=SampleStatus.AGENT_CONTEXT_LIMIT, result= fail_result)
            if root.status != AgentOutputStatus.NORMAL:
                return TaskSampleExecutionResult(
                    status=SampleStatus.UNKNOWN, result = fail_result)
            root = self.extract_action(root.content)
            if "action" not in root:
                return TaskSampleExecutionResult( status=SampleStatus.AGENT_VALIDATION_FAILED,result=fail_result)
            if root["action"] not in ["bash", "commit", "quit"]:
                return TaskSampleExecutionResult(
                    status=SampleStatus.AGENT_INVALID_ACTION, result=fail_result)

            action = root["action"]
            content = root["content"]
            # ----------------------------------------
            if action == "quit": 
                return TaskSampleExecutionResult(status=SampleStatus.QUIT,result = fail_result)
            # ----------------------------------------

            if action == "commit": # ends game with guess.
                answer = content
                break
            elif action == "bash":
                result = await asyncio.to_thread(container.execute, content)
                result = result.output.decode("utf-8")
                if len(result) > 800:
                    result = (
                        result[:780] + "\n[truncated because the output is too long]"
                    )
                session.inject(
                    {
                        "role": "user",
                        "content": ("The output of the OS:\n\n" + result)
                        if result
                        else "The output of the OS is empty.",
                    }
                )
        
        # for-else, run after completion of loop if the loop did not break
        else:
            fail_result['reason'] = "round limit"
            return TaskSampleExecutionResult(
                status=SampleStatus.TASK_LIMIT_REACHED, result = fail_result)

        # runs if loop was broken, check answer
        if isinstance(answer, str) and config.match and config.match["strip"]:
            answer = answer.strip()

        jd = False

        if config.match:
            if "answer" in config.match:
                jd = answer == config.match["answer"]
            elif "regex" in config.match:
                jd = re.search(config.match["regex"], answer) is not None
        elif config.check:
            params = [str(answer)]
            for script in config.check:
                if script is None:
                    script = config.example_script
                response = await asyncio.to_thread(
                    container.execute_independent, script, *params
                )
                if response.exit_code != 0:
                    jd = False
                    break
                params.append(response.output.decode("utf-8"))
            else:
                jd = True
        else:
            return TaskSampleExecutionResult(
                status=SampleStatus.UNKNOWN, result=fail_result
            )
        fail_result['result'] = jd 
        return TaskSampleExecutionResult(status=SampleStatus.COMPLETED, 
                                        result = fail_result
        )
