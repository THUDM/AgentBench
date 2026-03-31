"""AG2 multi-agent client for AgentBench evaluation.

Uses AG2 (formerly AutoGen) framework to handle benchmark tasks
via multi-agent conversation with tool-augmented agents.

AG2: https://ag2.ai — 500K+ monthly PyPI downloads, 4,300+ GitHub stars.
"""

import os
import logging
from typing import List

try:
    from autogen import AssistantAgent, UserProxyAgent, LLMConfig
except ImportError:
    raise ImportError(
        "AG2 is not installed. It requires a separate environment "
        "(Python >=3.10, pydantic >=2.6.1). Install with:\n"
        "  pip install -r requirements-ag2.txt\n"
        "See requirements-ag2.txt for details."
    )

from src.client.agent import AgentClient

logger = logging.getLogger(__name__)


class AG2Agent(AgentClient):
    """AgentBench client powered by AG2 multi-agent framework.

    Wraps AG2's AssistantAgent + UserProxyAgent into the AgentClient
    interface expected by AgentBench. Each call to `inference()` runs
    a single-turn agent conversation and returns the assistant's response.

    Args:
        model: Model name (e.g., "gpt-4o-mini", "gpt-4").
        api_key: API key for the model provider.
        api_type: Provider type ("openai", "anthropic", "google", etc.).
        system_message: System prompt for the assistant agent.
        max_tokens: Maximum tokens for model responses.
        temperature: Sampling temperature.
        max_turns: Maximum conversation turns per inference call.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str = None,
        api_type: str = "openai",
        system_message: str = "You are a helpful AI assistant that solves tasks step by step.",
        max_tokens: int = 512,
        temperature: float = 0,
        max_turns: int = 1,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.api_type = api_type
        self.system_message = system_message
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_turns = max_turns

        # Build LLM config — AG2 0.11.4 accepts config dicts as positional args
        config_entry = {
            "model": self.model,
            "api_key": self.api_key,
            "api_type": self.api_type,
        }

        self._llm_config = LLMConfig(
            config_entry,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # Create agents
        self._assistant = AssistantAgent(
            name="bench_assistant",
            system_message=self.system_message,
            llm_config=self._llm_config,
        )

        self._user_proxy = UserProxyAgent(
            name="bench_evaluator",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            code_execution_config=False,
        )

    def inference(self, history: List[dict]) -> str:
        """Run AG2 agent inference on the given conversation history.

        Converts AgentBench history format to a single prompt,
        runs the AG2 agent pair, and extracts the response.

        Args:
            history: List of message dicts from the benchmark environment.
                     Each dict typically has "role" and "content" keys.

        Returns:
            The assistant's response string.
        """
        # Reset agents for clean state
        self._assistant.reset()
        self._user_proxy.reset()

        # Build prompt from history
        # AgentBench passes history as a list of {"role": ..., "content": ...}
        # We concatenate into a single prompt for the AG2 conversation
        prompt_parts = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                # System messages are part of context, prepend them
                prompt_parts.insert(0, f"[System]: {content}")
            else:
                prompt_parts.append(content)

        prompt = "\n\n".join(prompt_parts)

        try:
            run_response = self._user_proxy.run(
                self._assistant,
                message=prompt,
            )
            # process() drives the conversation but returns None;
            # the actual chat history lives on the agent objects.
            run_response.process()

            # Extract first assistant reply from the assistant's chat log
            chat_messages = self._assistant.chat_messages
            if chat_messages:
                # chat_messages is a defaultdict keyed by the other agent
                history = list(chat_messages.values())[0]
                for msg in history:
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "").strip()
                        if content:
                            return content

            logger.warning("AG2 agent returned empty chat history")
            return ""

        except Exception as e:
            logger.error(f"AG2 inference error: {e}")
            return f"Error: {str(e)}"


class AG2GroupChatAgent(AgentClient):
    """AgentBench client using AG2 GroupChat with multiple specialized agents.

    Demonstrates AG2's multi-agent capability within the AgentBench framework.
    Uses a Planner + Executor pattern for complex reasoning tasks.

    Args:
        model: Model name.
        api_key: API key.
        api_type: Provider type.
        max_tokens: Maximum tokens per response.
        temperature: Sampling temperature.
        max_rounds: Maximum GroupChat rounds.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str = None,
        api_type: str = "openai",
        max_tokens: int = 512,
        temperature: float = 0,
        max_rounds: int = 4,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

        config_entry = {
            "model": model,
            "api_key": self.api_key,
            "api_type": api_type,
        }

        self._llm_config = LLMConfig(
            config_entry,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._max_rounds = max_rounds

        from autogen import GroupChat, GroupChatManager

        # Specialized agents
        self._planner = AssistantAgent(
            name="Planner",
            system_message=(
                "You are a planning specialist. Analyze the task, break it down "
                "into steps, and propose a clear action plan. Be concise."
            ),
            llm_config=self._llm_config,
        )

        self._executor = AssistantAgent(
            name="Executor",
            system_message=(
                "You are an execution specialist. Follow the plan and produce "
                "the final answer. Output only the answer, no explanation."
            ),
            llm_config=self._llm_config,
        )

        self._user_proxy = UserProxyAgent(
            name="Evaluator",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            code_execution_config=False,
        )

        self._group_chat = GroupChat(
            agents=[self._user_proxy, self._planner, self._executor],
            messages=[],
            max_round=self._max_rounds,
            speaker_selection_method="auto",
        )

        self._manager = GroupChatManager(
            groupchat=self._group_chat,
            llm_config=self._llm_config,
        )

    def inference(self, history: List[dict]) -> str:
        """Run GroupChat inference on the given conversation history.

        Args:
            history: List of message dicts from the benchmark environment.

        Returns:
            The final agent response string.
        """
        # Reset all agents
        self._planner.reset()
        self._executor.reset()
        self._user_proxy.reset()
        self._group_chat.messages.clear()

        # Build prompt
        prompt_parts = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.insert(0, f"[System]: {content}")
            else:
                prompt_parts.append(content)

        prompt = "\n\n".join(prompt_parts)

        try:
            run_response = self._user_proxy.run(
                self._manager,
                message=prompt,
            )
            run_response.process()

            # GroupChat history is stored in group_chat.messages
            for msg in reversed(self._group_chat.messages):
                role = msg.get("role", "")
                content = msg.get("content", "").strip()
                if role != "user" and content:
                    return content

            return ""

        except Exception as e:
            logger.error(f"AG2 GroupChat inference error: {e}")
            return f"Error: {str(e)}"
