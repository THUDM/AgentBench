import contextlib
import time
import warnings

import requests
from urllib3.exceptions import InsecureRequestWarning

from src.typings import *
from src.utils import *
from ..agent import AgentClient

old_merge_environment_settings = requests.Session.merge_environment_settings


@contextlib.contextmanager
def no_ssl_verification():
    opened_adapters = set()

    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        # Verification happens only once per connection so we need to close
        # all the opened adapters once we're done. Otherwise, the effects of
        # verify=False persist beyond the end of this context manager.
        opened_adapters.add(self.get_adapter(url))

        settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
        settings['verify'] = False

        return settings

    requests.Session.merge_environment_settings = merge_environment_settings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', InsecureRequestWarning)
            yield
    finally:
        requests.Session.merge_environment_settings = old_merge_environment_settings

        for adapter in opened_adapters:
            try:
                adapter.close()
            except:
                pass


class Prompter:
    @staticmethod
    def get_prompter(prompter: Union[Dict[str, Any], None]):
        # check if prompter_name is a method and its variable
        if not prompter:
            return Prompter.default()
        assert isinstance(prompter, dict)
        prompter_name = prompter.get("name", None)
        prompter_args = prompter.get("args", {})
        if hasattr(Prompter, prompter_name) and callable(
            getattr(Prompter, prompter_name)
        ):
            return getattr(Prompter, prompter_name)(**prompter_args)
        return Prompter.default()

    @staticmethod
    def default():
        return Prompter.role_content_dict()

    @staticmethod
    def batched_role_content_dict(*args, **kwargs):
        base = Prompter.role_content_dict(*args, **kwargs)

        def batched(messages):
            result = base(messages)
            return {key: [result[key]] for key in result}

        return batched

    @staticmethod
    def role_content_dict(
        message_key: str = "messages",
        role_key: str = "role",
        content_key: str = "content",
        user_role: str = "user",
        agent_role: str = "agent",
    ):
        def prompter(messages: List[Dict[str, str]]):
            nonlocal message_key, role_key, content_key, user_role, agent_role
            role_dict = {
                "user": user_role,
                "agent": agent_role,
            }
            prompt = []
            for item in messages:
                prompt.append(
                    {role_key: role_dict[item["role"]], content_key: item["content"]}
                )
            return {message_key: prompt}

        return prompter

    @staticmethod
    def openai_passthrough():
        """Pass through OpenAI-format messages and tools directly."""
        def prompter(data):
            # If it's already in OpenAI format (dict with messages/tools), pass through
            if isinstance(data, dict) and "messages" in data:
                result = {"messages": data["messages"]}
                if "tools" in data:
                    result["tools"] = data["tools"]
                return result
            # Otherwise, convert from old format
            prompt = []
            for item in data:
                role = "assistant" if item.get("role") == "agent" else item.get("role", "user")
                prompt.append({"role": role, "content": item.get("content", "")})
            return {"messages": prompt}
        return prompter

    @staticmethod
    def prompt_string(
        prefix: str = "",
        suffix: str = "AGENT:",
        user_format: str = "USER: {content}\n\n",
        agent_format: str = "AGENT: {content}\n\n",
        prompt_key: str = "prompt",
    ):
        def prompter(messages: List[Dict[str, str]]):
            nonlocal prefix, suffix, user_format, agent_format, prompt_key
            prompt = prefix
            for item in messages:
                if item["role"] == "user":
                    prompt += user_format.format(content=item["content"])
                else:
                    prompt += agent_format.format(content=item["content"])
            prompt += suffix
            print(prompt)
            return {prompt_key: prompt}

        return prompter

    @staticmethod
    def claude():
        return Prompter.prompt_string(
            prefix="",
            suffix="Assistant:",
            user_format="Human: {content}\n\n",
            agent_format="Assistant: {content}\n\n",
        )

    @staticmethod
    def palm():
        def prompter(messages):
            return {"instances": [
                Prompter.role_content_dict("messages", "author", "content", "user", "bot")(messages)
            ]}
        return prompter


def check_context_limit(content: str):
    content = content.lower()
    and_words = [
        ["prompt", "context", "tokens"],
        [
            "limit",
            "exceed",
            "max",
            "long",
            "much",
            "many",
            "reach",
            "over",
            "up",
            "beyond",
        ],
    ]
    rule = AndRule(
        [
            OrRule([ContainRule(word) for word in and_words[i]])
            for i in range(len(and_words))
        ]
    )
    return rule.check(content)


class HTTPAgent(AgentClient):
    def __init__(
        self,
        url,
        proxies=None,
        body=None,
        headers=None,
        return_format="{response}",
        prompter=None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.url = url
        self.proxies = proxies or {}
        self.headers = headers or {}
        self.body = body or {}
        self.return_format = return_format
        self.prompter = Prompter.get_prompter(prompter)
        if not self.url:
            raise Exception("Please set 'url' parameter")

    def _handle_history(self, history: List[dict]) -> Dict[str, Any]:
        return self.prompter(history)

    def inference(self, history) -> str:
        for _ in range(3):
            try:
                body = self.body.copy()
                body.update(self._handle_history(history))
                with no_ssl_verification():
                    resp = requests.post(
                        self.url, json=body, headers=self.headers, proxies=self.proxies, timeout=120
                    )
                # print(resp.status_code, resp.text)
                if resp.status_code != 200:
                    # print(resp.text)
                    if check_context_limit(resp.text):
                        raise AgentContextLimitException(resp.text)
                    else:
                        raise Exception(
                            f"Invalid status code {resp.status_code}:\n\n{resp.text}"
                        )
            except AgentClientException as e:
                raise e
            except Exception as e:
                print("Warning: ", e)
                pass
            else:
                resp = resp.json()
                # Handle OpenAI chat completion format
                if self.return_format == "openai_chat":
                    if "choices" in resp and resp["choices"]:
                        message = resp["choices"][0].get("message", {})
                        # Check for tool calls first
                        if "tool_calls" in message and message["tool_calls"]:
                            tool_call = message["tool_calls"][0]
                            # Return the action from the tool call arguments
                            import json
                            try:
                                args = json.loads(tool_call["function"]["arguments"])
                                return args.get("action", "")
                            except:
                                return tool_call["function"]["arguments"]
                        # Otherwise return content
                        return message.get("content", "")
                    return ""
                return self.return_format.format(response=resp)
            time.sleep(_ + 2)
        raise Exception("Failed.")
