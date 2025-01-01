#Structure documentation https://github.com/THUDM/AgentBench/blob/main/docs/Extension_en.md
from typing import Callable, Dict, List, Any
from src.server.task import Task, Session
from src.typings import TaskOutput, SampleStatus
from .utils import *

class MedAgentBench(Task):
    def __init__(self, **configs):
        super().__init__(**configs)
        self.data_file = configs.pop("data_file")
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