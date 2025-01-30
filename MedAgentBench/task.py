import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel
from agentbench import Task, TaskSampleExecutionResult, SampleStatus, TaskOutput, ChatHistoryItem, Session

class FHIRTask(Task):
    def __init__(self, test_data: List[Dict[str, Any]], *args, **kwargs):
        """
        Initialize the FHIRTask with test data.
        :param test_data: List of test cases, each containing 'id', 'instruction', and 'sol' (expected solution).
        """
        super().__init__(name="fhir-task", *args, **kwargs)
        self.data = test_data  # Dynamically load test data

    def get_indices(self) -> List[int]:
        # Return indices for each test sample
        return list(range(len(self.data)))

    async def start_sample(self, index: int, session: Session) -> TaskSampleExecutionResult:
        # Get the test sample
        sample = self.data[index]
        instruction = sample["instruction"]
        expected_sol = sample["sol"]

        # Parse the instruction to extract patient name and DOB
        name = instruction.split("name ")[1].split(" and DOB")[0].strip()
        dob = instruction.split("DOB of ")[1].split("?")[0].strip()

        # Call your existing task1_sol function to get the result
        result = task1_sol(name, dob)

        # Compare the result with the expected solution
        status = SampleStatus.COMPLETED if result == expected_sol else SampleStatus.TASK_ERROR

        # Return the result and status
        return TaskSampleExecutionResult(
            status=status,
            result={
                "id": sample["id"],
                "instruction": instruction,
                "expected": expected_sol,
                "actual": result,
                "status": "correct" if result == expected_sol else "incorrect"
            }
        )

    def calculate_overall(self, results: List[TaskOutput]) -> Dict[str, Any]:
        # Calculate the overall score and error rate
        total_samples = len(results)
        correct_samples = sum(1 for result in results if result.result["status"] == "correct")
        score = correct_samples / total_samples if total_samples > 0 else 0
        return {
            "total_samples": total_samples,
            "correct_samples": correct_samples,
            "score": score
        }
