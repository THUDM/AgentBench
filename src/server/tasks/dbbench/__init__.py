import json
import re
from typing import Callable, Dict, List, Any

from src.server.task import Task, Session
from src.typings import TaskOutput, SampleStatus, AgentOutputStatus
from .Interaction import FHIRClient

big_prompt = """
I will ask you a question, then you should help me operate a FHIR server to answer the question.
You have to explain the problem and your solution to me and write down your thoughts.
After thinking and explaining thoroughly, every round you can choose to operate or to answer.
Your operation should be like this:
Action: Operation
```json
{ "resourceType": "Patient", "query": { "name": "John" } }
```
You MUST put JSON in markdown format without any other comments. 
Your query must be valid FHIR JSON. Every time you can only execute one operation. I will only execute the operation in the first JSON code block. 
You are allowed to use the following FHIR API calls: Patient.Search and Observation.Search.
If you are done operating, and you want to commit your final answer, then write down: Action: Answer Final Answer: ["ANSWER1", "ANSWER2", ...] 
DO NOT write this pattern unless you are sure about your answer. I expect an accurate and correct answer. 
Your answer should be accurate. Your answer must be exactly the same as the correct answer. 
If the question is about modifying the database, then after done operation, your answer field can be anything. 
If your response cannot match any pattern I mentioned earlier, you will be judged as FAIL immediately. 
Your input will be raw FHIR server response, and you have to deal with it by yourself. 
"""


def build_init_resources(entry):
    """ Builds FHIR resource initialization data from the entry. """ 
    resources = entry["table"]["table_info"]["rows"] 
    resource_type = entry["table"]["table_name"] 
    return resource_type, resources


class DBBench(Task):
    def __init__(self, **configs):
        super().__init__(**configs)
        self.data_file = configs.pop("data_file")
        self.max_round = configs.pop("max_round", 5)
        self.dataset = []

        with open(self.data_file) as f:
            if self.data_file.endswith("json"):
                data = json.loads(f.read())
            else:
                data = [json.loads(line) for line in f.readlines()]

        for entry in data:
            ans = entry.pop("sol")
            inp = entry
            self.dataset.append((inp, ans))

        self.server = FHIRClient()

    def get_indices(self) -> List[Any]:
        return list(range(len(self.dataset)))

    async def start_sample(self, index: int, session: Session) -> TaskOutput:
        entry = self.dataset[index][0] # (inp, ans)
        fhir_client = self.server
        resource_type, resources = build_init_resources(entry)

        # Initialize resources
        for resource in resources:
            fhir_client.create_resource(resource_type, resource)

        session.inject({"role": "user", "content": big_prompt})
        session.inject({"role": "agent", "content": "Ok."})
        prompt = entry["instruction"] + "\n" + entry["context"]
        session.inject({"role": "user", "content": prompt})

        res = (await session.action()).content or ""
        answer = ""
        finish_reason = SampleStatus.COMPLETED

        try:
            action = re.search(r"Action: (.*?)\n", res)
            rounds = 0
            while action and action.group(1) == "Operation" and rounds < self.max_round:
                res = re.search(r"```json\n([\s\S]*?)\n```", res)
                if not res:
                    finish_reason = SampleStatus.AGENT_VALIDATION_FAILED
                    break
                fhir_query = json.loads(res.group(1).strip())
                print(fhir_query)
                resource_type = fhir_query.get("resourceType")
                query = fhir_query.get("query")

                # Perform the FHIR search operation
                response = fhir_client.search_resources(resource_type, query)

                if response:
                    session.inject({"role": "user", "content": json.dumps(response)})
                else:
                    session.inject({"role": "user", "content": "No results found."})

                res = await session.action()
                if res.status == AgentOutputStatus.AGENT_CONTEXT_LIMIT:
                    finish_reason = SampleStatus.AGENT_CONTEXT_LIMIT
                    break

                res = res.content
                action = re.search(r"Action: (.*?)\n", res)
                rounds += 1
            else:
                answer = re.search(r"\nFinal Answer:(.*)", res)
                if answer:
                    answer = answer.group(1)
                else:
                    answer = ""
                    finish_reason = SampleStatus.AGENT_VALIDATION_FAILED
                if rounds >= self.max_round and not answer:
                    finish_reason = SampleStatus.TASK_LIMIT_REACHED
        except Exception as e:
            error = str(e)
            answer = ""
            finish_reason = SampleStatus.UNKNOWN
        else:
            error = ""

        return TaskOutput(
            status=finish_reason,
            result={
                "answer": str(answer),
                "type": entry["type"][0],
                "error": error,
            },
            history=session.history,
        )

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        metrics = self.metrics
        ret = {}
        outputs = []
        answers = []
        for result in results:
            outputs.append(result.result)
            answers.append(self.dataset[result.index][1])
        for key, func in metrics.items():
            ret[key] = func(outputs, answers)
        return ret

    @property
    def metrics(self) -> Dict[str, Callable[[List[Dict[str, Any]], List[str]], float]]:
        # Same as before but adapted for FHIR context
        def factory(typ):
            def acc(inp: List[Dict[str, Any]], tar: List[str]) -> float:
                correct = 0
                total = 0
                for entry, cor in zip(inp, tar):
                    if not entry:
                        continue
                    ans, t = entry["answer"], entry["type"]
                    if t != typ:
                        continue
                    correct += ans == cor
                    total += 1
                if total == 0:
                    print(f"WARNING: {typ} does not exist!")
                    return 0
                return correct / total

            return acc

        types = ["SELECT", "CREATE", "DELETE", "UPDATE"]
        ret = {typ + "_accuracy": factory(typ) for typ in types}
        ret["overall_accuracy"] = lambda inp, tar: sum(ret.values()) / len(ret)
        return ret

    def release(self):
        # No explicit release needed for FHIRClient
        pass
