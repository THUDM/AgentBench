#Structure documentation https://github.com/THUDM/AgentBench/blob/main/docs/Extension_en.md
from typing import Callable, Dict, List, Any
from src.server.task import Task, Session
from src.typings import TaskOutput, SampleStatus, AgentOutputStatus
from .utils import *
from .eval import eval

import json

MedAgentBench_prompt = """You are an expert in using FHIR functions to assist medical professionals. You are given a question and a set of possible functions. Based on the question, you will need to make one or more function/tool calls to achieve the purpose.

1. If you decide to invoke a GET function, you MUST put it in the format of
GET url?param_name1=param_value1&param_name2=param_value2...

2. If you decide to invoke a POST function, you MUST put it in the format of
POST url
[your payload data in JSON format]

3. If you have answered all the questions and finished all the requested tasks, you MUST put it in the format of
FINISH([answer1, answer2, ...])

Your response must be in the format of one of the three cases, and you SHOULD NOT include any other text in the response.

Here is a list of functions in JSON format that you can invoke. Note that you should use {api_base} as the api_base.
{functions}

Context: {context}
Question: {question}"""

class MedAgentBench(Task):
    def __init__(self, **configs):
        super().__init__(**configs)
        self.data_file = configs.pop("data_file")
        with open(self.data_file, 'r') as f:
            self.data = json.load(f)
        
        self.func_file = configs.pop("func_file")
        with open(self.func_file, 'r') as f:
            self.funcs = json.load(f)
        
        self.max_round = configs.pop("max_round", 5)

        self.fhir_api_base = configs.pop("fhir_api_base")
        if verify_fhir_server(self.fhir_api_base) is False:
            print('FHIR server connection error! Please check FHIR server status and fhir_api_base in configs/tasks/medagentbench.yaml')
        print(2, flush=True)

    def get_indices(self) -> List[Any]:
        return list(range(len(self.data))) #list(range(3))

    async def start_sample(self, index, session: Session):
        print(f"task start {index}")
        case = self.data[index]
        session.inject({"role": "user", "content": MedAgentBench_prompt.format(api_base=self.fhir_api_base,
                                                                               functions=json.dumps(self.funcs),
                                                                               context=case['context'],
                                                                               question=case['instruction'])})
        try:
            for round in range(self.max_round):
                res = (await session.action())
                if res.status == AgentOutputStatus.AGENT_CONTEXT_LIMIT:
                    return TaskOutput(
                    status=SampleStatus.AGENT_CONTEXT_LIMIT,
                    history=session.history
                )
                r = res.content.strip()
                if r.startswith('GET'):
                    url = r[3:].strip() + '&_format=json'
                    print(f'GET {url}')
                    get_res = send_get_request(url)
                    if "data" in get_res:
                        session.inject({"role": "user", "content": f"Here is the response from the GET request:\n{get_res['data']}"})
                    else:
                        session.inject({"role": "user", "content": f"Error in sending the GET request: {get_res['error']}"})

                elif r.startswith('POST'):
                    try:
                        payload = json.loads('\n'.join(r.split('\n')[1:]))
                    except Exception as e:
                        session.inject({"role": "user", "content": "invalid POST request"})
                    else:
                        session.inject({"role": "user", "content": "POST request accepted"})
                elif r.startswith('FINISH('):
                    return TaskOutput(
                        status=SampleStatus.COMPLETED,
                        result=r[len('FINISH('):-1], #Trim to a list
                        history=session.history
                    )
                else:
                    return TaskOutput(
                        status=SampleStatus.AGENT_INVALID_ACTION,
                        history=session.history
                    )
                
        except Exception as e:
            return TaskOutput(
                status=SampleStatus.TASK_ERROR,
                result={"error": str(e)},
                history=session.history
            )
        
        return TaskOutput(
            status=SampleStatus.TASK_LIMIT_REACHED,
            history=session.history
        )

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        total_task = len(results)
        assert len(self.get_indices()) == total_task
        correct_count = 0
        for i in range(total_task):
            if getattr(results[i], "result") is not None:
                index = results[i].index
                if eval(self.data[index], results[i], self.fhir_api_base) is True:
                    correct_count += 1
                    results[i].status += 'Correct'
                else:
                    results[i].status += 'Incorrect'

        return {'accuracy': correct_count/total_task, 'raw_results': results}