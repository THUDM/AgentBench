#Structure documentation https://github.com/THUDM/AgentBench/blob/main/docs/Extension_en.md
from src.server.task import Task, Session
from src.typings import TaskOutput, SampleStatus, AgentOutputStatus

class MedAgentBench(Task):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(name="MedAgentBench", *args, **kwargs)

    def get_indices(self) -> List[Any]:
        return list(range(10))

    async def start_sample(self, index, session: Session):
        print("task start sample")
        for loop_times in range(3):
            await asyncio.sleep(1)
            res = await session.action(
                {"role": "user", "content": "Loop: %d" % loop_times}
            )
            print("TASK", res.content)
        return TaskSampleExecutionResult(
            status=SampleStatus.COMPLETED,
            result={"result": "ok"},
        )

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        return {"score": 0.4}