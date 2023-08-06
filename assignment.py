import os
import json
import sys
import time
import re
import math
import random
import datetime
import argparse
import requests
import yaml
from typing import List, Dict, Any, Optional, Union, Tuple, Callable, Type, TypeVar

import time
import importlib
import argparse
import yaml

from os.path import join, isdir, isfile, relpath
from glob import glob

from src import YAMLConfig, print_rank_0, Task, Agent, serialize
from pydantic import BaseModel
from copy import deepcopy
import subprocess
from subprocess import Popen, PIPE, STDOUT
import shlex
from src.utils import ColorMessage
import signal
import traceback
import subprocess

ASSIGMENT_TIMESTAMP = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

class InstanceFactory(BaseModel):
    module: str
    parameters: Dict[str, Any]
    
    def create(self) -> Union[Task, Agent]:
        path = ".".join(self.module.split(".")[:-1])
        mod = __import__(path, fromlist=[self.module.split(".")[-1]])
        # print(mod)
        return getattr(mod, self.module.split(".")[-1])(**self.parameters)
    
    def pretty(self, offset=0):
        ret = "    " * offset + f"Module: {self.module}"
        ret += "\n" + "    " * offset + "Parameters:"
        for key, value in self.parameters.items():
            ret += "\n" + "    " * offset + f"    {key}: {value}"
        return ret
    
    def to_json(self):
        return {
            "module": self.module,
            "parameters": self.parameters,
        }

class Assigment(BaseModel):
    agent: InstanceFactory
    task: InstanceFactory
    output: str
    docker_image: Union[str, None] = None
    
    @staticmethod
    def from_config(args: Dict):
        """
        Load an assignment from a dict.
        
        output can contain parameters with {KEY}. Where:
            - TIMESTAMP: the timestamp that the assignment is loaded
            - TASK_NAME: the name of the task. If no name is specified, the name of the task is the name of the task class with hash suffix.
            - AGENT_NAME: the name of the agent. If no name is specified, the name of the agent is the name of the agent class with hash suffix.
        """
        docker_image = args.get("task").pop("docker_image", None)
        agent = InstanceFactory(**args.pop("agent"))
        task = InstanceFactory(**args.pop("task"))
        agent_name = agent.parameters.get("name") or (agent.module.split(".")[-1] + "-" + str(hash(json.dumps(agent.parameters)) % 100000))
        task_name = task.parameters.get("name") or (task.module.split(".")[-1] + "-" + str(hash(json.dumps(task.parameters)) % 100000))
        output = (args.pop("output") or "outputs/{TIMESTAMP}/{AGENT_NAME}/{TASK_NAME}").format(
            TIMESTAMP=ASSIGMENT_TIMESTAMP,
            TASK_NAME=task_name,
            AGENT_NAME=agent_name,
        )
        return Assigment(agent=agent, task=task, output=output, docker_image=docker_image)
    
    def to_json(self):
        return {
            "agent": self.agent.to_json(),
            "task": self.task.to_json(),
            "output": self.output,
            "docker_image": self.docker_image,
        }
        

    def pretty(self, offset=0):
        ret = "    " * offset + "Agent:"
        ret += "\n" + self.agent.pretty(offset=offset+1)
        ret += "\n" + "    " * offset + "Task:"
        ret += "\n" + self.task.pretty(offset=offset+1)
        ret += "\n" + "    " * offset + f"Output: {self.output}"
        return ret

def deep_merge(raw_item, new_item):
    if isinstance(raw_item, dict) and isinstance(new_item, dict):
        ret = deepcopy(raw_item)
        for key in new_item:
            if key in ret:
                ret[key] = deep_merge(ret[key], new_item[key])
            else:
                ret[key] = new_item[key]
        return ret
    if isinstance(raw_item, list) and isinstance(new_item, list):
        ret = deepcopy(raw_item)
        ret.extend(new_item)
        return ret
    return new_item


def load_instance_factory(instance_config: Union[Dict, str]) -> Dict:
    if isinstance(instance_config, str):
        with open(instance_config, "r") as f:
            instance_config = yaml.safe_load(f)
    if isinstance(instance_config, dict):
        if "from" in instance_config:
            with open(instance_config.pop("from"), "r") as f:
                config = yaml.safe_load(f)
            instance_config = deep_merge(config, instance_config)
    return instance_config

def load_assignment_config(assignment_config: Dict, global_config: Dict=None) -> Dict:
    agent = load_instance_factory(assignment_config.pop("agent", {}))
    task = load_instance_factory(assignment_config.pop("task", {}))
    output = assignment_config.pop("output", None)
    if global_config:
        if "agent" in global_config:
            agent = deep_merge(global_config["agent"], agent)
        if "task" in global_config:
            task = deep_merge(global_config["task"], task)
    return {
        "agent": agent,
        "task": task,
        "output": output,
    }

def load_assignments(config: Dict) -> List[Assigment]:
    if "assignments" not in config and "assignment" not in config["assignments"]:
        raise ValueError("Invalid assignment config: 'assignments' or 'assignment' not found.")
    if "assignments" in config and "assignment" in config["assignments"]:
        raise ValueError("Invalid assignment config: 'assignments' and 'assignment' cannot be both specified.")
    raw_assignments = config.pop("assignments", None) or config.pop("assignment", None)
    global_vars = config.pop("default", None)
    if global_vars:
        global_vars = load_assignment_config(global_vars)
    if not isinstance(raw_assignments, list):
        raw_assignments = [raw_assignments]
    assignments = []
    for raw_assignment in raw_assignments:
        assignment = load_assignment_config(raw_assignment, global_vars)
        # docker_image = assignment["task"].pop("docker_image", None)
        # print(json.dumps(assignment, indent=4))
        # print(json.dumps(raw_assignment, indent=4))
        assignments.append(Assigment.from_config(assignment))
    return assignments

def kill_process_and_descendants(pid):
    ps_command = subprocess.Popen("ps -o pid --ppid %d --noheaders" % pid, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
    ps_output = ps_command.stdout.read()
    retcode = ps_command.wait()
    if retcode:
        print(ColorMessage.yellow("[Kill-Message] COMMAND 'ps -o pid --ppid %d --noheaders' RETURNED %d." % (pid, retcode)))
    os.kill(pid, signal.SIGTERM)
    print(ColorMessage.yellow(f"[Kill-Message] Kill process {pid}"))
    for pid_str in ps_output.split("\n")[:-1]:
        kill_process_and_descendants(int(pid_str))
    

def run_command(command):
    # if isinstance(command, str):
    #     command = shlex.split(command)
    try:
        process = Popen(command, stdout=PIPE, stderr=STDOUT)
        while True: 
            nextline = process.stdout.read(1)
            # nextline = process.stdout.readline()
            if not nextline and process.poll() is not None:
                break
            # if nextline == '\n':
            #     nextline = '\r\n'
            # print(ord(nextline), nextline, end='\r\n')
            # write byte 'nextline'
            sys.stdout.buffer.write(nextline)
            sys.stdout.flush()
            # sys.stdout.write(nextline.decode('utf-8'))
            # sys.stdout.flush()
        output = process.communicate()[0]
        exitCode = process.returncode
        
        return exitCode, output
    except KeyboardInterrupt as e:
        print(ColorMessage.yellow("KeyboardInterrupt, Please wait for the process to exit..."))
        # print(process.pid)
        # kill process and all of its descendant processes
        print(ColorMessage.yellow(f"[Kill-Message] Start kill {process.pid} and its descendants."))
        kill_process_and_descendants(process.pid)
        # process.kill()
        # process.wait()
        raise e

def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-a", "--assignment", type=str, required=True, help="Assignment config to load")
    args = arg_parser.parse_args()
    
    with open(args.assignment, "r") as f:
        config = yaml.safe_load(f)
    assignments = load_assignments(config)
    
    print(ColorMessage.cyan(f"\n[System] {len(assignments)} assignment(s) loaded:"))
    for idx, assignment in enumerate(assignments):
        print(ColorMessage.cyan(f"\t{idx:02}: \n\t\tAgent: {assignment.agent.module}\n\t\tTask: {assignment.task.module}\n\t\tOutput: {assignment.output}"))
    print()
    
    bash_script = "#!/bin/bash\n\nsource scripts/eval_utils.sh\n\n"
    
    for idx, assignment in enumerate(assignments):
        print(ColorMessage.cyan(f"\n[System] Create Assignment {idx:02}:"))
        print(ColorMessage.cyan(assignment.pretty(offset=1)))
        print()
        os.makedirs(assignment.output)
        agent_config_path = os.path.join(assignment.output, "agent.yaml")
        task_config_path = os.path.join(assignment.output, "task.yaml")
        with open(agent_config_path, "w", encoding='utf-8') as f:
            f.write(yaml.dump(assignment.agent.to_json(), indent=4, allow_unicode=True))
        with open(task_config_path, "w", encoding='utf-8') as f:
            f.write(yaml.dump(assignment.task.to_json(), indent=4, allow_unicode=True))
        if not assignment.docker_image:
            bash_script += f"evaluate_directly --task \"{task_config_path}\" --agent \"{agent_config_path}\" --output \"{assignment.output}\"\n"
        else:
            bash_script += f"evaluate_in_docker \"{assignment.docker_image}\" --task \"{task_config_path}\" --agent \"{agent_config_path}\" --output \"{assignment.output}\"\n"
    assigment_file_path = ".assignments/" + ASSIGMENT_TIMESTAMP + ".sh"
    os.makedirs(os.path.dirname(assigment_file_path), exist_ok=True)
    with open(assigment_file_path, "w", encoding='utf-8') as f:
        f.write(bash_script)
    print(ColorMessage.cyan(f"\n[System] Create assignment bash script at .assignment.bash"))
    print(ColorMessage.cyan(f"\n[System] Run the following command to start evaluation:\n\t" + "bash " + assigment_file_path))

if __name__ == "__main__":
    main()
