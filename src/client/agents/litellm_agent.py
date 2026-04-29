import time
from typing import Any, Dict, List

from src.typings import AgentClientException, AgentContextLimitException
from .http_agent import check_context_limit
from ..agent import AgentClient


class LiteLLMAgent(AgentClient):
    """Agent client that routes to 100+ LLM providers via LiteLLM.

    Model names use LiteLLM format: "provider/model-name", e.g.:
        anthropic/claude-sonnet-4-20250514, openai/gpt-4o,
        bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0

    Provider API keys are read from standard environment variables
    (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.).

    See https://docs.litellm.ai/docs/providers for the full list.
    """

    def __init__(self, model, api_key=None, api_base=None, api_args=None, **kwargs):
        super().__init__(**kwargs)
        if not model:
            raise ValueError("model is required (e.g. 'anthropic/claude-sonnet-4-20250514')")
        self.model = model
        self.model_name = model
        self.api_key = api_key
        self.api_base = api_base
        self.api_args = api_args or {}

    def inference(self, history: List[dict]) -> str:
        import litellm

        messages = []
        for item in history:
            role = "assistant" if item["role"] == "agent" else item["role"]
            messages.append({"role": role, "content": item["content"]})

        extra: Dict[str, Any] = {}
        if self.api_key:
            extra["api_key"] = self.api_key
        if self.api_base:
            extra["api_base"] = self.api_base

        for attempt in range(3):
            try:
                response = litellm.completion(
                    model=self.model,
                    messages=messages,
                    drop_params=True,
                    **self.api_args,
                    **extra,
                )
                return response.choices[0].message.content or ""
            except AgentClientException as e:
                raise e
            except Exception as e:
                if check_context_limit(str(e)):
                    raise AgentContextLimitException(str(e))
                qualname = f"{type(e).__module__}.{type(e).__name__}"
                if qualname in (
                    "litellm.exceptions.AuthenticationError",
                    "litellm.exceptions.BadRequestError",
                    "litellm.exceptions.NotFoundError",
                ):
                    raise
                print("Warning: ", e)
                time.sleep(attempt + 2)
        raise Exception("Failed after 3 attempts.")
