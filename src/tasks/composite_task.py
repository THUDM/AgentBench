from src.task import Task, Dataset, DataPiece, Session
from src.configs import YAMLConfig
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
from src.agent import Agent, Session
from src.utils import serialize
from typing import Dict, Callable, Type, Tuple, List, Any, Union, Iterable, Generic, TypeVar


class CompositeTask(Task):
    def __init__(self, **configs):
        tasks = configs.pop("tasks", [])
        self.tasks: List[Task] = []
        super().__init__(**configs)
        for task in tasks:
            assert "src" in task
            if self.workers:
                task.update({"workers": self.workers})
            src = os.path.join(os.path.dirname(configs["src"]), task.pop("src"))
            sub_task = YAMLConfig.create_from_yaml(src, task)
            sub_task.get_output_dir = (lambda s: (lambda: self._sub_output_dir(s)))(sub_task)
            self.tasks.append(sub_task)

    def evaluate(self, agent: Agent) -> Dict[str, Dict[str, Any]]:
        print(f"Evaluating Composite Task '{self.name}' ...")
        results = {}
        for task in self.tasks:
            result = task.evaluate(agent)
            results[task.name] = result
        self.save_metrics_all(results)
        return results

    def _sub_output_dir(self, sub_task: Task) -> str:
        target_category = sub_task.category or sub_task.name or "default"
        return os.path.join(self.get_output_dir(), target_category)

    def release(self):
        # print("> Kill Composite")
        for task in self.tasks:
            task.release()
        del self.tasks
