import os
from typing import Dict, Any

from src.server.quit_wrapper import QuitWrapper
from src.server.task import Task, Session
from src.server.tasks.alfworld.environment import SingleAlfredTWEnv
from src.server.tasks.alfworld.utils import *
from src.typings import TaskOutput, TaskSampleExecutionResult, SampleStatus, AgentOutputStatus
from copy import deepcopy
import traceback
from src.server.tasks.alfworld.task import ALFWorld # Base task we will overwrite

class ALFWorldQuit(ALFWorld):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # overwrite to include quitting as a valid action
    @staticmethod
    def get_available_actions(actions):
        actions = "\n".join(actions)
        actions += "\n quit"
        return " AVAILABLE ACTIONS: " + actions + "\n"
    
    # overwrite to give instructions to quit
    def get_task_instruction(self):
        # return "Interact with a household to solve a task. Imagine you are an intelligent agent in a household environment and your target is to perform actions to complete the task goal. In the beginning of your interactions, you will be given the detailed description of the current environment and your goal to accomplish. For each of your turn, you should choose from two actions: \"THOUGHT\" or \"ACTION\". If you choose \"THOUGHT\", you should first think about the current condition and plan for your future actions, and then output your action in this turn. Your output must strictly follow this format:\"THOUGHT: your thoughts.\n ACTION: your next action\n\"; If you choose \"ACTION\", you should directly output the action in this turn. Your output must strictly follow this format:\"ACTION: your next action\n\". After your each turn, the environment will give you immediate feedback based on which you plan your next few steps. if the envrionment output \"Nothing happened\", that means the previous action is invalid and you should try more options.\n\n"
        return f"Interact with a household to solve a task. Imagine you are an intelligent agent in a household environment and your target is to perform actions to complete the task goal. At the beginning of your interactions, you will be given the detailed description of the current environment and your goal to accomplish. For each of your turn, you will be given a list of actions which you can choose one to perform in this turn. You should choose from two actions: \"THOUGHT\" or \"ACTION\". If you choose \"THOUGHT\", you should first think about the current condition and plan for your future actions, and then output your action in this turn. Your output must strictly follow this format:\"THOUGHT: your thoughts.\n ACTION: your next action\n\"; If you choose \"ACTION\", you should directly output the action in this turn. Your output must strictly follow this format:\"ACTION: your next action\n\". After your each turn, the environment will give you immediate feedback based on which you plan your next few steps. if the environment output \"Nothing happened\", that means the previous action is invalid and you should try more options.\n It is also possible to quit the task using \"ACTION: quit\". It is preferable to complete the task, but if you will not be able to, quit as early as possible. Specifically, you must maximize S - N/T, where S=1 in the case of a success and 0 in the case of failure, and N/T is the number of steps you take before quitting or succeeding normalized by the budget T={self.max_step}. Thus, it is preferable to quit over failing.\n Reminder: \n1. the action must be chosen from the given available actions. Any actions except provided available actions will be regarded as illegal. \n2. Think when necessary, try to act directly more in the process.\n\n"

    async def start_sample(self, index, session: Session) -> TaskSampleExecutionResult:
        print("start sample")
        data_item = self.data_files[index]
        print("creating env")
        env = SingleAlfredTWEnv(self.config, data_item)
        print("initializing env")
        env = env.init_env(batch_size=1)
        env = QuitWrapper(env)
        print("Quit wrapper placed around env.")
        # print("resetting")
        # env.reset()
        # print(env.step(['quit']))
        try:
            print("running env")
            result, log_info, finish_reason = await self.alfworld_run(session, env)
        except Exception as e:
            print()
            print("error", e)
            traceback.print_exc()
            return TaskSampleExecutionResult(status=SampleStatus.UNKNOWN, result={"result": False, "error": e})
        log_info.update({"result": result})
        return TaskSampleExecutionResult(status=finish_reason, result=log_info)
    
    # modify alfworld run to record quitting, and 
    async def alfworld_run(self, session: Session, env: Any):
        finish_reason = SampleStatus.COMPLETED
        # env init
        ob, info = env.reset()
        ob = '\n'.join(ob[0].split('\n\n')[1:])
        name = '/'.join(info['extra.gamefile'][0].split('/')[-3:-1])
        log_info = {"log": []}
        session.inject({"role": "user", "content": self.get_task_instruction()})
        session.inject(
            {"role": "agent", "content": "OK. I'll follow your instructions and try my best to solve the task."})

        # 1-shot naive example
        history = self.get_prompt(name)
        history[0] = "Here is one example.\n" + history[0]
        self.inject_info(session, history)

        init_prompt = "Here is your task. " + ob + ALFWorldQuit.get_available_actions(info.get('admissible_commands', [[]])[0])
        log_info["init_prompt"] = init_prompt
        session.inject({"role": "user", "content": init_prompt})


        # interact
        for i in range(0, self.max_step):
            output = await session.action()
            if output.status == AgentOutputStatus.AGENT_CONTEXT_LIMIT:
                finish_reason = SampleStatus.AGENT_CONTEXT_LIMIT
                break
            generated_words = output.length
            output = output.content or ""

            # process action
            admissible_commands = info.get('admissible_commands', [[]])[0]
            action = process_action(output, admissible_commands)
            if not action:
                finish_reason = SampleStatus.AGENT_INVALID_ACTION
                break
            session.history[-2].content = session.history[-2].content.split("AVAILABLE ACTIONS")[
                0]  # reduce the prompt length

            observation, reward, done, info = env.step([action])
            
            if action != 'quit': # in the case of quitting, the quit env returns obs: str, info: dict, done: bool, reward: int, not lists...
                observation, reward, done = process_ob(observation[0]), info['won'][0], done[0]
            if action == "quit":
                print("Quit action occurred")
                print("Done: ", done)
                print("Reward: ", reward)
                print("Info: ", info)
                finish_reason = SampleStatus.QUIT
                
            session.inject({"role": "user", "content": observation + ALFWorldQuit.get_available_actions(
                info.get('admissible_commands', [[]])[0])})

            # save
            payload = {
                "round": i + 1,
                "output": output,
                "action": action,
                "observation": observation,
                "done": done,
                "quit": info['quit'],
                "reward": reward,
                "words_generated": generated_words,
                "prompt_length": sum( [ len(h.content.split()) for h in session.history] ) 
                # "admissible_commands": admissible_commands,
            }
            log_info["log"].append(payload)

            # print("====== action ======")
            # print("output: ", output)
            # print("action: ", action)
            # print("obs and commands: ", session.history[-1]["content"])
            # print("====== end action =======")
            # print("====== ob =======")
            # print("ob: ", observation)
            # print("====== end ob =======\n")
            # print("action: ", action, "ob: ", observation)

            # failure test
            if len(log_info["log"]) > 3:
                pre_logs = log_info["log"][-3:]
                pre_acts = [pre_log["output"] for pre_log in pre_logs]
                if len(list(set(pre_acts))) == 1:
                    print("repeat actions for 3 times: failure")
                    return 0, log_info, SampleStatus.AGENT_INVALID_ACTION

            if done:
                return reward, log_info, finish_reason
        else:
            finish_reason = SampleStatus.TASK_LIMIT_REACHED
        return 0, log_info, finish_reason
