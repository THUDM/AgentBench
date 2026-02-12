import enum
import json
import random

import requests

from src.typings import *
from src.utils import *
from .agent import AgentClient


class TaskError(enum.Enum):
    START_FAILED = "START_FAILED"
    INTERACT_FAILED = "INTERACT_FAILED"
    AGENT_FAILED = "AGENT_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    NOT_AVAILABLE = "NOT_AVAILABLE"


# Direct worker address mapping (bypassing buggy controller)
# Add port mappings in docker-compose.yml for each worker you want to use
WORKER_ADDRESSES = {
    "alfworld-std": "http://localhost:5021/api",
    "dbbench-std": "http://localhost:5022/api",
    "os-std": "http://localhost:5023/api",
    "kg-std": "http://localhost:5024/api",
    "webshop-std": "http://localhost:5025/api",
}


class TaskClient:
    def __init__(
        self, name: str, controller_address: str = "http://localhost:5000/api", *_, **__,
    ) -> None:
        self.name = name
        self.controller_address = controller_address
        # Use direct worker address if available
        self.worker_address = WORKER_ADDRESSES.get(name)
        print("TaskClient created: {} ({})".format(name, controller_address))
        if self.worker_address:
            print(f"  -> Using direct worker address: {self.worker_address}")

    def get_indices(self) -> List[SampleIndex]:
        result = requests.get(
            self.controller_address + "/get_indices", params={"name": self.name}
        )
        if result.status_code != 200:
            raise AgentBenchException(result.text, result.status_code, self.name)
        return result.json()

    def get_concurrency(self) -> int:
        try:
            result = requests.get(
                self.controller_address + "/list_workers"
            )
        except Exception as e:
            print(ColorMessage.yellow(f"Warning task {self.name} cannot connect to controller {e}"))
            return 0
        if result.status_code != 200:
            raise AgentBenchException(result.text, result.status_code, self.name)
        result = result.json()
        if self.name not in result:
            print(ColorMessage.yellow(f"task {self.name} not found in worker list"))
            return 0
        concurrency = 0
        for worker in result[self.name]["workers"].values():
            # API returns status as string "ALIVE", not the IntEnum value
            if worker["status"] == "ALIVE":
                concurrency += worker["capacity"] - worker["current"]
        return concurrency

    def run_sample(self, index: SampleIndex, agent: AgentClient) -> TaskClientOutput:
        # Use direct worker communication if available (bypasses buggy controller)
        if self.worker_address:
            return self._run_sample_direct(index, agent)
        else:
            return self._run_sample_via_controller(index, agent)
    
    def _run_sample_direct(self, index: SampleIndex, agent: AgentClient) -> TaskClientOutput:
        """Run sample by talking directly to the worker (new OpenAI-style API)."""
        # Generate a unique session ID
        sid = random.randint(10000, 99999)
        
        # Track conversation history for output
        history = []
        conversation_messages = []  # Full conversation for agent
        
        try:
            # Start sample on worker directly
            response = requests.post(
                self.worker_address + "/start_sample",
                json={"index": index, "session_id": sid},
                timeout=60
            )
        except Exception as e:
            return TaskClientOutput(error=TaskError.NETWORK_ERROR.value, info=str(e))
        
        if response.status_code != 200:
            return TaskClientOutput(
                error=TaskError.START_FAILED.value, info=response.text
            )
        
        result = response.json()
        
        # Extract messages and tools from response
        messages = result.get("messages", [])
        tools = result.get("tools", [])
        conversation_messages = messages.copy()
        
        # Record initial messages in history
        for msg in messages:
            content = msg.get("content", "")
            if msg["role"] in ("system", "user"):
                history.append(ChatHistoryItem(role="user", content=content or ""))
        
        max_turns = 50
        turn = 0
        
        while result.get("status") == "running" and not result.get("finish", False) and turn < max_turns:
            turn += 1
            
            try:
                # Prepare input for agent - full conversation with tools
                agent_input = {
                    "messages": conversation_messages,
                    "tools": tools
                }
                content = agent.inference(agent_input)
            except AgentContextLimitException:
                # Cancel and return
                try:
                    requests.post(self.worker_address + "/cancel", json={"session_id": sid}, timeout=10)
                except:
                    pass
                return TaskClientOutput(
                    output=TaskOutput(status=SampleStatus.AGENT_CONTEXT_LIMIT, history=history)
                )
            except Exception as e:
                model_name = getattr(agent, "model_name", None) or getattr(agent, "name", None) or agent.__class__.__name__
                print(f"ERROR: {model_name}/{self.name} agent error", e)
                try:
                    requests.post(self.worker_address + "/cancel", json={"session_id": sid}, timeout=10)
                except:
                    pass
                return TaskClientOutput(
                    error=TaskError.AGENT_FAILED.value,
                    info=str(e),
                    output=TaskOutput(status=SampleStatus.TASK_ERROR, history=history),
                )
            
            # Record agent response in history
            history.append(ChatHistoryItem(role="agent", content=content or ""))
            
            # Build assistant message with tool call for the worker
            # The worker expects OpenAI-style tool calls
            tool_call_id = f"call_{turn}"
            assistant_message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "take_action",
                        "arguments": json.dumps({"action": content})
                    }
                }]
            }
            
            # Add to conversation
            conversation_messages.append(assistant_message)
            
            try:
                # Send interact request to worker
                response = requests.post(
                    self.worker_address + "/interact",
                    json={
                        "session_id": sid,
                        "messages": [assistant_message]
                    },
                    timeout=60
                )
            except Exception as e:
                return TaskClientOutput(
                    error=TaskError.NETWORK_ERROR.value,
                    info=str(e),
                    output=TaskOutput(status=SampleStatus.RUNNING, history=history),
                )
            
            if response.status_code != 200:
                return TaskClientOutput(
                    error=TaskError.INTERACT_FAILED.value,
                    info=response.text,
                    output=TaskOutput(status=SampleStatus.RUNNING, history=history),
                )
            
            result = response.json()
            
            # Extract environment output
            env_out = result.get("env_out", result)
            new_messages = env_out.get("messages", [])
            
            # Add tool response to conversation
            for msg in new_messages:
                conversation_messages.append(msg)
                content = msg.get("content", "")
                if content:
                    history.append(ChatHistoryItem(role="user", content=content))
            
            # Update status from env_out
            result["status"] = env_out.get("status", "running")
            result["finish"] = env_out.get("finish", False)
        
        # Determine final status
        if result.get("finish", False) or result.get("status") == "completed":
            final_status = SampleStatus.COMPLETED
        elif turn >= max_turns:
            final_status = SampleStatus.TASK_LIMIT_REACHED
        else:
            final_status = SampleStatus.COMPLETED
        
        return TaskClientOutput(output=TaskOutput(
            status=final_status,
            history=history,
            result=result.get("metric", {}).get("score", 0)
        ))
    
    def _run_sample_via_controller(self, index: SampleIndex, agent: AgentClient) -> TaskClientOutput:
        """Original method - run sample via controller (has bugs with current controller)."""
        try:
            response = requests.post(
                self.controller_address + "/start_sample",
                json=StartSampleRequest(name=self.name, index=index).dict(),
            )
        except Exception as e:
            return TaskClientOutput(error=TaskError.NETWORK_ERROR.value, info=str(e))
        if response.status_code == 406:
            return TaskClientOutput(
                error=TaskError.NOT_AVAILABLE.value, info=response.text
            )
        if response.status_code != 200:
            return TaskClientOutput(
                error=TaskError.START_FAILED.value, info=response.text
            )
        
        result = response.json()
        sid = response.headers.get("Session_id") or response.headers.get("session_id") or result.get("session_id")
        if sid is None:
            return TaskClientOutput(
                error=TaskError.START_FAILED.value, 
                info=f"No session_id in response"
            )
        sid = int(sid)
        
        history = []
        max_turns = 50
        turn = 0
        
        while turn < max_turns:
            turn += 1
            if "output" in result and "status" in result["output"]:
                if SampleStatus(result["output"]["status"]) != SampleStatus.RUNNING:
                    break
            elif "status" in result:
                if result["status"] not in ("running", "RUNNING"):
                    break
            
            try:
                agent_input = result.get("messages", result.get("output", {}).get("history", []))
                content = agent.inference(agent_input)
            except AgentContextLimitException:
                return TaskClientOutput(output=TaskOutput(status=SampleStatus.AGENT_CONTEXT_LIMIT, history=history))
            except Exception as e:
                return TaskClientOutput(error=TaskError.AGENT_FAILED.value, info=str(e), output=TaskOutput(status=SampleStatus.TASK_ERROR, history=history))
            
            history.append(ChatHistoryItem(role="agent", content=content or ""))
            
            try:
                response = requests.post(
                    self.controller_address + "/interact",
                    json={"session_id": sid, "agent_response": {"content": content, "status": "normal"}},
                    headers={"Session_id": str(sid)}
                )
            except Exception as e:
                return TaskClientOutput(error=TaskError.NETWORK_ERROR.value, info=str(e), output=TaskOutput(status=SampleStatus.RUNNING, history=history))
            
            if response.status_code != 200:
                return TaskClientOutput(error=TaskError.INTERACT_FAILED.value, info=response.text, output=TaskOutput(status=SampleStatus.RUNNING, history=history))
            
            result = response.json()
        
        if "output" in result:
            return TaskClientOutput(output=result["output"])
        return TaskClientOutput(output=TaskOutput(status=SampleStatus.COMPLETED, history=history, result=result.get("result")))

    def calculate_overall(self, results: List[TaskOutput]) -> JSONSerializable:
        statistics = {s: 0 for s in SampleStatus}
        for result in results:
            statistics[SampleStatus(result.status)] += 1
        for s in SampleStatus:
            statistics[s] /= len(results)
        statistics["average_history_length"] = sum(
            [len(result.history) for result in results]
        ) / len(results)
        statistics["max_history_length"] = max(
            [len(result.history) for result in results]
        )
        statistics["min_history_length"] = min(
            [len(result.history) for result in results]
        )
        ret = {
            "total": len(results),
            "validation": statistics,
        }
        res = requests.post(
            self.controller_address + "/calculate_overall",
            json=CalculateOverallRequest(name=self.name, results=results).dict(),
        )
        if res.status_code != 200:
            raise TaskNetworkException(res.text)
        ret["custom"] = res.json()
        return ret
