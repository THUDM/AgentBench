import sys
import types
from unittest import mock
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, ".")

if "fastchat" not in sys.modules:
    _fc = types.ModuleType("fastchat")
    _fc_model = types.ModuleType("fastchat.model")
    _fc_adapter = types.ModuleType("fastchat.model.model_adapter")
    _fc_adapter.get_conversation_template = MagicMock()
    _fc.model = _fc_model
    _fc_model.model_adapter = _fc_adapter
    sys.modules.update({"fastchat": _fc, "fastchat.model": _fc_model, "fastchat.model.model_adapter": _fc_adapter})

from src.client.agents.litellm_agent import LiteLLMAgent
from src.typings import AgentContextLimitException


def _mock_resp(content="Hello!"):
    msg = MagicMock(); msg.content = content
    choice = MagicMock(); choice.message = msg
    resp = MagicMock(); resp.choices = [choice]
    return resp


def _run_inference(agent, history, response):
    fake = types.ModuleType("litellm")
    fake.completion = MagicMock(return_value=response)
    with mock.patch.dict(sys.modules, {"litellm": fake}):
        result = agent.inference(history)
    return result, fake.completion


def _run_inference_error(agent, history, error):
    fake = types.ModuleType("litellm")
    fake.completion = MagicMock(side_effect=error)
    with mock.patch.dict(sys.modules, {"litellm": fake}):
        with mock.patch("src.client.agents.litellm_agent.time.sleep"):
            try:
                agent.inference(history)
                return None, fake.completion
            except Exception as e:
                return e, fake.completion


class TestInit:
    def test_default(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        assert a.model == "openai/gpt-4o"
        assert a.model_name == "openai/gpt-4o"
        assert a.api_key is None
        assert a.api_args == {}

    def test_with_params(self):
        a = LiteLLMAgent(model="anthropic/claude-sonnet-4-20250514", api_key="sk-test", api_args={"temperature": 0.7})
        assert a.api_key == "sk-test"
        assert a.api_args["temperature"] == 0.7

    def test_model_required(self):
        with pytest.raises(ValueError):
            LiteLLMAgent(model=None)


class TestInference:
    def test_basic_completion(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        result, comp = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp("42"))
        assert result == "42"
        comp.assert_called_once()

    def test_role_mapping(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        history = [
            {"role": "user", "content": "hi"},
            {"role": "agent", "content": "hello"},
            {"role": "user", "content": "bye"},
        ]
        _, comp = _run_inference(a, history, _mock_resp("ok"))
        msgs = comp.call_args.kwargs["messages"]
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[2]["role"] == "user"

    def test_drop_params(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        _, comp = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp())
        assert comp.call_args.kwargs["drop_params"] is True

    def test_api_key_forwarded(self):
        a = LiteLLMAgent(model="openai/gpt-4o", api_key="sk-test")
        _, comp = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp())
        assert comp.call_args.kwargs["api_key"] == "sk-test"

    def test_api_key_omitted(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        _, comp = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp())
        assert "api_key" not in comp.call_args.kwargs

    def test_api_args_forwarded(self):
        a = LiteLLMAgent(model="openai/gpt-4o", api_args={"temperature": 0.5, "max_tokens": 100})
        _, comp = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp())
        assert comp.call_args.kwargs["temperature"] == 0.5
        assert comp.call_args.kwargs["max_tokens"] == 100

    def test_api_base_forwarded(self):
        a = LiteLLMAgent(model="openai/gpt-4o", api_base="https://proxy.local")
        _, comp = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp())
        assert comp.call_args.kwargs["api_base"] == "https://proxy.local"

    def test_model_forwarded(self):
        a = LiteLLMAgent(model="anthropic/claude-sonnet-4-20250514")
        _, comp = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp())
        assert comp.call_args.kwargs["model"] == "anthropic/claude-sonnet-4-20250514"

    def test_none_content_returns_empty_string(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        result, _ = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp(content=None))
        assert result == ""

    def test_empty_string_content(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        result, _ = _run_inference(a, [{"role": "user", "content": "hi"}], _mock_resp(content=""))
        assert result == ""


class TestRetryAndErrors:
    def test_retries_3_times_then_raises(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        exc, comp = _run_inference_error(
            a, [{"role": "user", "content": "hi"}], RuntimeError("transient")
        )
        assert comp.call_count == 3
        assert "Failed after 3 attempts" in str(exc)

    def test_context_limit_raises_immediately(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        exc, comp = _run_inference_error(
            a, [{"role": "user", "content": "hi"}],
            RuntimeError("prompt is too long, exceeds context token limit"),
        )
        assert isinstance(exc, AgentContextLimitException)
        assert comp.call_count == 1

    def test_auth_error_not_retried(self):
        auth_exc = type("AuthenticationError", (Exception,), {})("bad key")
        auth_exc.__class__.__module__ = "litellm.exceptions"
        auth_exc.__class__.__qualname__ = "AuthenticationError"
        a = LiteLLMAgent(model="openai/gpt-4o")
        exc, comp = _run_inference_error(
            a, [{"role": "user", "content": "hi"}], auth_exc,
        )
        assert comp.call_count == 1
        assert "bad key" in str(exc)

    def test_rate_limit_not_misclassified_as_context_limit(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        exc, comp = _run_inference_error(
            a, [{"role": "user", "content": "hi"}],
            RuntimeError("Rate limit exceeded, please retry"),
        )
        assert not isinstance(exc, AgentContextLimitException)
        assert comp.call_count == 3


class TestRegistration:
    def test_importable(self):
        from src.client.agents import LiteLLMAgent as Imported
        assert Imported is LiteLLMAgent

    def test_subclass(self):
        from src.client.agent import AgentClient
        assert issubclass(LiteLLMAgent, AgentClient)

    def test_instance_factory(self):
        from src.typings import InstanceFactory
        factory = InstanceFactory(
            module="src.client.agents.litellm_agent.LiteLLMAgent",
            parameters={"model": "openai/gpt-4o"},
        )
        agent = factory.create()
        assert isinstance(agent, LiteLLMAgent)
        assert agent.model == "openai/gpt-4o"

    def test_model_name_attribute(self):
        a = LiteLLMAgent(model="openai/gpt-4o")
        assert a.model_name == "openai/gpt-4o"
