#Structure documentation https://github.com/THUDM/AgentBench/blob/main/docs/Extension_en.md
from typing import Callable, Dict, List, Any
from src.server.task import Task, Session
from src.typings import TaskOutput, SampleStatus
from .utils import *

import json

MedAgentBench_prompt = """You are an expert in using FHIR functions to assist medical professionals. You are given a question and a set of possible functions. Based on the question, you will need to make one or more function/tool calls to achieve the purpose.

1. If you decide to invoke a GET function, you MUST put it in the format of
GET url?param_name1=param_value1&param_name2=param_value2...

2. If you decide to invoke a POST function, you MUST put it in the format of
POST url
[your payload data in JSON format]

3. If you have answered all the questions and finished all the requested tasks, you MUST put it in the format of
finish(["answer1", "answer2", ...])

Your response must be in the format of one of the three cases, and you SHOULD NOT include any other text in the response.

Here is a list of functions in JSON format that you can invoke. Note that you should use {api_base} as the api_base.
{functions}

Context: {context}
Question: {question}"""

class MedAgentBench(Task):
    def __init__(self, **configs):
        super().__init__(**configs)
        self.data_file = configs.pop("data_file")
        self.func_file = configs.pop("func_file")
        with open(self.func_file, 'r') as f:
            self.funcs = json.load(f)
        self.max_round = configs.pop("max_round", 5)
        self.fhir_api_base = configs.pop("fhir_api_base")

        if verify_fhir_server(self.fhir_api_base) is False:
            print('FHIR server connection error! Please check FHIR server status and fhir_api_base in configs/tasks/medagentbench.yaml')
        print(2, flush=True)

    def get_indices(self) -> List[Any]:
        return list(range(2))

    async def start_sample(self, index, session: Session):
        print(f"task start {index}")
        session.inject({"role": "user", "content": f"Which model are you? {index}"})

        res = (await session.action()).content or ""
        return TaskOutput(
            status=SampleStatus.COMPLETED,
            result={"result": "ok"},
            history=session.history
        )

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        return results #{"score": 0.4}