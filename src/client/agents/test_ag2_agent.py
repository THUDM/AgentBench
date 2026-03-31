"""Tests for AG2 agent clients.

Covers three levels:
  1. Unit tests — class init, prompt construction, error handling.
  2. Integration tests — InstanceFactory config loading, agent registry.
  3. End-to-end tests — full TaskClient.run_sample loop with a mocked
     task server, exercising the real AG2Agent.inference() code path.
"""

import json
import os
import threading
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List
from unittest.mock import patch, MagicMock

import pytest

from src.client.agent import AgentClient
from src.client.agents.ag2_agent import AG2Agent, AG2GroupChatAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_history(*messages) -> List[dict]:
    """Build a history list from (role, content) pairs."""
    return [{"role": r, "content": c} for r, c in messages]


def _setup_ag2_mocks(mock_proxy, mock_asst, chat_messages):
    """Configure AG2 mocks so inference() can extract responses.

    AG2 0.11.4 flow:
      - user_proxy.run(assistant, message=...) -> RunResponse
      - RunResponse.process() -> None (side effect: populates agent.chat_messages)
      - Result extracted from assistant.chat_messages
    """
    mock_asst_inst = MagicMock()
    # chat_messages is defaultdict(list) keyed by other agent
    mock_asst_inst.chat_messages = defaultdict(list, {mock_proxy: chat_messages})
    mock_asst.return_value = mock_asst_inst

    mock_proxy_inst = MagicMock()
    run_response = MagicMock()
    run_response.process.return_value = None
    mock_proxy_inst.run.return_value = run_response
    mock_proxy.return_value = mock_proxy_inst

    return mock_asst_inst, mock_proxy_inst


# Decorator shorthand — mocks AG2 classes so __init__ doesn't hit real AG2
_patch_ag2 = lambda fn: (
    patch("src.client.agents.ag2_agent.LLMConfig")(
    patch("src.client.agents.ag2_agent.AssistantAgent")(
    patch("src.client.agents.ag2_agent.UserProxyAgent")(fn)))
)


# ============================================================================
# 1. Unit tests
# ============================================================================

class TestAG2AgentUnit:
    """Unit tests for AG2Agent init and prompt construction."""

    @_patch_ag2
    def test_init_default_params(self, mock_proxy, mock_asst, mock_llm):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            agent = AG2Agent()
            assert agent.model == "gpt-4o-mini"
            assert agent.api_type == "openai"
            assert agent.max_tokens == 512
            assert agent.temperature == 0
            assert agent.max_turns == 1

    @_patch_ag2
    def test_init_custom_params(self, mock_proxy, mock_asst, mock_llm):
        agent = AG2Agent(
            model="gpt-4",
            api_key="custom-key",
            api_type="openai",
            max_tokens=1024,
            temperature=0.5,
            max_turns=3,
        )
        assert agent.model == "gpt-4"
        assert agent.api_key == "custom-key"
        assert agent.max_tokens == 1024
        assert agent.temperature == 0.5
        assert agent.max_turns == 3

    @_patch_ag2
    def test_inherits_agent_client(self, mock_proxy, mock_asst, mock_llm):
        agent = AG2Agent(api_key="k")
        assert isinstance(agent, AgentClient)

    @_patch_ag2
    def test_inference_returns_assistant_content(self, mock_proxy, mock_asst, mock_llm):
        _setup_ag2_mocks(mock_proxy, mock_asst, [
            {"role": "user", "content": "hi", "name": "user"},
            {"role": "assistant", "content": "hello back", "name": "assistant"},
        ])
        agent = AG2Agent(api_key="k")
        result = agent.inference(_make_history(("user", "hi")))
        assert result == "hello back"

    @_patch_ag2
    def test_inference_skips_empty_assistant_messages(self, mock_proxy, mock_asst, mock_llm):
        """When last assistant message is empty, find previous non-empty one."""
        _setup_ag2_mocks(mock_proxy, mock_asst, [
            {"role": "user", "content": "hi", "name": "user"},
            {"role": "assistant", "content": "real answer", "name": "assistant"},
            {"role": "user", "content": "", "name": "user"},
            {"role": "assistant", "content": "", "name": "assistant"},
        ])
        agent = AG2Agent(api_key="k")
        result = agent.inference(_make_history(("user", "hi")))
        assert result == "real answer"

    @_patch_ag2
    def test_inference_empty_history_returns_empty(self, mock_proxy, mock_asst, mock_llm):
        _setup_ag2_mocks(mock_proxy, mock_asst, [])
        agent = AG2Agent(api_key="k")
        result = agent.inference([])
        assert result == ""

    @_patch_ag2
    def test_inference_handles_exception(self, mock_proxy, mock_asst, mock_llm):
        mock_proxy_inst = MagicMock()
        mock_proxy_inst.run.side_effect = RuntimeError("LLM timeout")
        mock_proxy.return_value = mock_proxy_inst

        agent = AG2Agent(api_key="k")
        result = agent.inference(_make_history(("user", "hello")))
        assert "Error" in result
        assert "LLM timeout" in result

    @_patch_ag2
    def test_inference_resets_agents_each_call(self, mock_proxy, mock_asst, mock_llm):
        mock_asst_inst, mock_proxy_inst = _setup_ag2_mocks(mock_proxy, mock_asst, [
            {"role": "assistant", "content": "ok", "name": "assistant"},
        ])

        agent = AG2Agent(api_key="k")
        agent.inference(_make_history(("user", "first")))
        agent.inference(_make_history(("user", "second")))

        assert mock_asst_inst.reset.call_count == 2
        assert mock_proxy_inst.reset.call_count == 2

    def test_prompt_construction_system_first(self):
        """System messages should be prepended to the prompt."""
        history = _make_history(
            ("user", "Turn on the light."),
            ("system", "You are in a kitchen."),
            ("user", "Look around."),
        )
        prompt_parts = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.insert(0, f"[System]: {content}")
            else:
                prompt_parts.append(content)
        prompt = "\n\n".join(prompt_parts)

        assert prompt.startswith("[System]: You are in a kitchen.")
        assert "Turn on the light." in prompt
        assert "Look around." in prompt

    def test_prompt_construction_multi_turn(self):
        """Multi-turn history concatenated properly."""
        history = _make_history(
            ("user", "What is 2+2?"),
            ("agent", "4"),
            ("user", "And 3+3?"),
        )
        prompt_parts = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.insert(0, f"[System]: {content}")
            else:
                prompt_parts.append(content)
        prompt = "\n\n".join(prompt_parts)

        assert "What is 2+2?" in prompt
        assert "4" in prompt
        assert "And 3+3?" in prompt


class TestAG2GroupChatAgentUnit:
    """Unit tests for AG2GroupChatAgent."""

    @patch("autogen.GroupChatManager")
    @patch("autogen.GroupChat")
    @_patch_ag2
    def test_init_defaults(self, mock_proxy, mock_asst, mock_llm, mock_gc, mock_gcm):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            agent = AG2GroupChatAgent()
            assert agent._max_rounds == 4
            assert isinstance(agent, AgentClient)

    @patch("autogen.GroupChatManager")
    @patch("autogen.GroupChat")
    @_patch_ag2
    def test_init_custom_rounds(self, mock_proxy, mock_asst, mock_llm, mock_gc, mock_gcm):
        agent = AG2GroupChatAgent(api_key="k", max_rounds=8)
        assert agent._max_rounds == 8

    @patch("autogen.GroupChatManager")
    @patch("autogen.GroupChat")
    @_patch_ag2
    def test_inference_returns_last_non_user(
        self, mock_proxy, mock_asst, mock_llm, mock_gc, mock_gcm
    ):
        mock_proxy_inst = MagicMock()

        def mock_run(recipient, message):
            # Simulate process() populating group_chat.messages
            agent._group_chat.messages = [
                {"role": "user", "content": "task"},
                {"role": "assistant", "content": "plan step 1"},
                {"role": "assistant", "content": "final answer"},
            ]
            run_response = MagicMock()
            run_response.process.return_value = None
            return run_response

        mock_proxy_inst.run.side_effect = mock_run
        mock_proxy.return_value = mock_proxy_inst

        agent = AG2GroupChatAgent(api_key="k")
        result = agent.inference(_make_history(("user", "solve this")))
        assert result == "final answer"


# ============================================================================
# 2. Integration tests — config loading & agent registry
# ============================================================================

class TestAG2Integration:
    """Test that AG2 agents load correctly through AgentBench's config system."""

    @_patch_ag2
    def test_instance_factory_creates_ag2_agent(self, mock_proxy, mock_asst, mock_llm):
        from src.typings import InstanceFactory

        factory = InstanceFactory(
            module="src.client.agents.AG2Agent",
            parameters={
                "model": "gpt-4o-mini",
                "api_key": "test-key-123",
                "api_type": "openai",
                "max_tokens": 256,
            },
        )
        agent = factory.create()
        assert isinstance(agent, AG2Agent)
        assert isinstance(agent, AgentClient)
        assert agent.model == "gpt-4o-mini"
        assert agent.api_key == "test-key-123"
        assert agent.max_tokens == 256

    @patch("autogen.GroupChatManager")
    @patch("autogen.GroupChat")
    @_patch_ag2
    def test_instance_factory_creates_groupchat_agent(
        self, mock_proxy, mock_asst, mock_llm, mock_gc, mock_gcm
    ):
        from src.typings import InstanceFactory

        factory = InstanceFactory(
            module="src.client.agents.AG2GroupChatAgent",
            parameters={
                "model": "gpt-4",
                "api_key": "test-key-456",
                "max_rounds": 6,
            },
        )
        agent = factory.create()
        assert isinstance(agent, AG2GroupChatAgent)
        assert isinstance(agent, AgentClient)
        assert agent._max_rounds == 6

    def test_config_loader_loads_ag2_single_yaml(self):
        from src.configs import ConfigLoader

        loader = ConfigLoader()
        config = loader.load_from("configs/agents/ag2-single.yaml")
        assert config["module"] == "src.client.agents.AG2Agent"
        assert "parameters" in config
        assert config["parameters"]["model"] == "gpt-4o-mini"
        assert config["parameters"]["api_type"] == "openai"

    def test_config_loader_loads_ag2_groupchat_yaml(self):
        from src.configs import ConfigLoader

        loader = ConfigLoader()
        config = loader.load_from("configs/agents/ag2-groupchat.yaml")
        assert config["module"] == "src.client.agents.AG2GroupChatAgent"
        assert config["parameters"]["max_rounds"] == 4

    def test_config_loader_loads_ag2_gpt4_yaml(self):
        from src.configs import ConfigLoader

        loader = ConfigLoader()
        config = loader.load_from("configs/agents/ag2-gpt4.yaml")
        assert config["parameters"]["model"] == "gpt-4"
        assert config["parameters"]["max_tokens"] == 1024

    def test_ag2_importable_from_agents_package(self):
        """Verify the agents __init__.py exports work."""
        from src.client.agents import AG2Agent as ImportedAgent
        from src.client.agents import AG2GroupChatAgent as ImportedGroupChat

        assert ImportedAgent is AG2Agent
        assert ImportedGroupChat is AG2GroupChatAgent

    @_patch_ag2
    def test_full_yaml_to_agent_pipeline(self, mock_proxy, mock_asst, mock_llm):
        """Load YAML -> InstanceFactory -> create() -> working agent."""
        from src.configs import ConfigLoader
        from src.typings import InstanceFactory

        config = ConfigLoader().load_from("configs/agents/ag2-single.yaml")
        config["parameters"]["api_key"] = "test-pipeline-key"
        factory = InstanceFactory(**config)
        agent = factory.create()

        assert isinstance(agent, AG2Agent)
        assert agent.api_key == "test-pipeline-key"
        assert agent.system_message.startswith("You are a helpful")


# ============================================================================
# 3. End-to-end test — full TaskClient.run_sample loop
# ============================================================================

class _FakeTaskHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler simulating AgentBench task controller.

    Implements the /api/start_sample and /api/interact endpoints
    so that TaskClient.run_sample() can execute a complete loop:
      1. start_sample -> RUNNING with initial history
      2. interact (agent response) -> COMPLETED with result
    """

    # Shared across requests via class variable
    interaction_count = 0
    agent_responses = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/start_sample":
            _FakeTaskHandler.interaction_count = 0
            _FakeTaskHandler.agent_responses = []
            response = {
                "session_id": 1001,
                "output": {
                    "status": "running",
                    "result": None,
                    "history": [
                        {"role": "user", "content": "You are in a dark room. What do you do?"}
                    ],
                },
            }
            self._respond(200, response)

        elif self.path == "/api/interact":
            _FakeTaskHandler.interaction_count += 1
            agent_content = body.get("agent_response", {}).get("content", "")
            _FakeTaskHandler.agent_responses.append(agent_content)

            if _FakeTaskHandler.interaction_count >= 2:
                response = {
                    "output": {
                        "status": "completed",
                        "result": {"score": 1.0, "success": True},
                        "history": [
                            {"role": "user", "content": "You are in a dark room. What do you do?"},
                            {"role": "agent", "content": _FakeTaskHandler.agent_responses[0]},
                            {"role": "user", "content": "You turned on the light. You see a key."},
                            {"role": "agent", "content": agent_content},
                        ],
                    }
                }
            else:
                response = {
                    "output": {
                        "status": "running",
                        "result": None,
                        "history": [
                            {"role": "user", "content": "You are in a dark room. What do you do?"},
                            {"role": "agent", "content": agent_content},
                            {"role": "user", "content": "You turned on the light. You see a key."},
                        ],
                    }
                }

            self._respond(200, response)

        elif self.path == "/api/cancel":
            self._respond(200, {"status": "cancelled"})

        else:
            self._respond(404, {"error": "not found"})

    def do_GET(self):
        if self.path.startswith("/api/list_workers"):
            self._respond(200, {})
        elif self.path.startswith("/api/get_indices"):
            self._respond(200, [0, 1, 2])
        else:
            self._respond(404, {})

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format, *args):
        pass  # suppress request logging during tests


@pytest.fixture(scope="class")
def fake_task_server():
    """Start a local HTTP server simulating the task controller."""
    server = HTTPServer(("127.0.0.1", 0), _FakeTaskHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/api"
    server.shutdown()


class TestAG2EndToEnd:
    """Full end-to-end test: config -> agent -> TaskClient -> fake server.

    Exercises the real code paths:
      - ConfigLoader loads YAML
      - InstanceFactory creates AG2Agent
      - TaskClient.run_sample() calls agent.inference() in a loop
      - Agent resets state between turns
      - Responses flow back through the task protocol
    """

    @_patch_ag2
    def test_full_task_loop(self, mock_proxy, mock_asst, mock_llm, fake_task_server):
        """Run a complete 2-turn task with AG2Agent through TaskClient."""
        from src.client.task import TaskClient

        call_count = [0]
        responses = [
            "I will look for a light switch.",
            "I pick up the key.",
        ]

        def mock_run(recipient, message):
            """Simulate run() — populate chat_messages as side effect."""
            resp = responses[min(call_count[0], len(responses) - 1)]
            call_count[0] += 1
            # Populate assistant's chat_messages (what real AG2 does)
            mock_asst_inst.chat_messages = defaultdict(list, {
                mock_proxy_inst: [
                    {"role": "user", "content": message, "name": "user"},
                    {"role": "assistant", "content": resp, "name": "assistant"},
                ]
            })
            run_response = MagicMock()
            run_response.process.return_value = None
            return run_response

        mock_asst_inst = MagicMock()
        mock_asst_inst.chat_messages = defaultdict(list)
        mock_asst.return_value = mock_asst_inst

        mock_proxy_inst = MagicMock()
        mock_proxy_inst.run.side_effect = mock_run
        mock_proxy.return_value = mock_proxy_inst

        from src.configs import ConfigLoader
        from src.typings import InstanceFactory

        config = ConfigLoader().load_from("configs/agents/ag2-single.yaml")
        config["parameters"]["api_key"] = "e2e-test-key"
        agent = InstanceFactory(**config).create()

        task_client = TaskClient(name="test-task", controller_address=fake_task_server)
        output = task_client.run_sample(index=0, agent=agent)

        assert output.error is None, f"Task failed: {output.error} — {output.info}"
        assert output.output is not None

        task_output = output.output
        assert task_output.status.value == "completed"
        assert task_output.result["success"] is True
        assert task_output.result["score"] == 1.0
        assert call_count[0] == 2

        agent_msgs = [m.content for m in task_output.history if m.role == "agent"]
        assert "I will look for a light switch." in agent_msgs
        assert "I pick up the key." in agent_msgs
        assert _FakeTaskHandler.interaction_count == 2

    @_patch_ag2
    def test_task_loop_agent_error_recovery(self, mock_proxy, mock_asst, mock_llm, fake_task_server):
        """Verify TaskClient handles agent errors within run_sample."""
        from src.client.task import TaskClient

        mock_proxy_inst = MagicMock()
        mock_proxy_inst.run.side_effect = RuntimeError("Model overloaded")
        mock_proxy.return_value = mock_proxy_inst

        agent = AG2Agent(api_key="e2e-test-key")
        task_client = TaskClient(name="test-task", controller_address=fake_task_server)
        output = task_client.run_sample(index=0, agent=agent)

        # Agent returns "Error: ..." string which is valid —
        # TaskClient treats any string as a valid response, pipeline doesn't crash
        assert output is not None

    @patch("autogen.GroupChatManager")
    @patch("autogen.GroupChat")
    @_patch_ag2
    def test_groupchat_in_task_loop(
        self, mock_proxy, mock_asst, mock_llm, mock_gc, mock_gcm, fake_task_server
    ):
        """Run GroupChatAgent through a full task loop."""
        from src.client.task import TaskClient

        call_count = [0]

        def mock_run(recipient, message):
            call_count[0] += 1
            # Populate group_chat.messages as side effect
            agent._group_chat.messages = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": "Planner: analyze task"},
                {"role": "assistant", "content": f"Executor: action {call_count[0]}"},
            ]
            run_response = MagicMock()
            run_response.process.return_value = None
            return run_response

        mock_proxy_inst = MagicMock()
        mock_proxy_inst.run.side_effect = mock_run
        mock_proxy.return_value = mock_proxy_inst

        agent = AG2GroupChatAgent(api_key="e2e-test-key")
        task_client = TaskClient(name="test-task", controller_address=fake_task_server)
        output = task_client.run_sample(index=0, agent=agent)

        assert output.error is None, f"Task failed: {output.error}"
        assert output.output.status.value == "completed"
        assert call_count[0] == 2
