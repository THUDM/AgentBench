import requests
import os, json, sys, time, re, math, random, datetime, argparse, requests
from typing import List, Dict, Any, Union

from fastchat.model.model_adapter import get_conversation_template
from src.agent import Agent

# import TimeoutException
from requests.exceptions import Timeout, ConnectionError


class Prompter:
    @staticmethod
    def get_prompter(prompter_name: Union[str, None]):
        # check if prompter_name is a method and its variable
        if not prompter_name:
            return None
        if hasattr(Prompter, prompter_name) and callable(getattr(Prompter, prompter_name)):
            return getattr(Prompter, prompter_name)
    
    @staticmethod
    def claude(messages: List[Dict[str, str]]):
        prompt = ""
        role_dict = {
            "user": "Human",
            "agent": "Assistant",
        }
        for item in messages:
            prompt += f"{role_dict[item['role']]}: {item['content']}\n\n"
        prompt += "Assistant:"
        return {"prompt": prompt}

    @staticmethod
    def openchat_v3_1(messages: List[Dict[str, str]]):
        prompt = "Assistant is GPT4<|end_of_turn|>"
        role_dict = {
            "user": "User: {content}<|end_of_turn|>",
            "agent": "Assistant: {content}<|end_of_turn|>",
        }
        for item in messages:
            prompt += role_dict[item['role']].format(content=item['content'])
        prompt += "Assistant:"
        return {"prompt": prompt}
    
    @staticmethod
    def openchat_v3_2(messages: List[Dict[str, str]]):
        prompt = ""
        role_dict = {
            "user": "GPT4 User: {content}<|end_of_turn|>",
            "agent": "GPT4 Assistant: {content}<|end_of_turn|>",
        }
        for item in messages:
            prompt += role_dict[item['role']].format(content=item['content'])
        prompt += "GPT4 Assistant:"
        return {"prompt": prompt}

class FastChatAgent(Agent):

    def __init__(self, model_name, controller_address=None, worker_address=None, temperature=0, max_new_tokens=32, top_p=0, prompter=None, args=None, **kwargs) -> None:
        if controller_address is None and worker_address is None:
            raise ValueError("Either controller_address or worker_address must be specified.")
        self.controller_address = controller_address
        self.worker_address = worker_address
        self.model_name = model_name
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.top_p = top_p
        self.prompter = Prompter.get_prompter(prompter)
        self.args = args or {}
        print(self.max_new_tokens)
        super().__init__(**kwargs)

    def inference(self, history: List[dict]) -> str:
        if self.worker_address:
            worker_addr = self.worker_address
        else:
            controller_addr = self.controller_address
            worker_addr = controller_addr
        if worker_addr == "":
            return
        gen_params = {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_new_tokens": self.max_new_tokens,
            "echo": False,
            "top_p": self.top_p,
            **self.args
        }
        if self.prompter:
            prompt = self.prompter(history)
            gen_params.update(prompt)
        else:
            conv = get_conversation_template(self.model_name)
            for history_item in history:
                role = history_item["role"]
                content = history_item["content"]
                if role == "user":
                    conv.append_message(conv.roles[0], content)
                elif role == "agent":
                    conv.append_message(conv.roles[1], content)
                else:
                    raise ValueError(f"Unknown role: {role}")
            conv.append_message(conv.roles[1], None)
            prompt = conv.get_prompt()
            gen_params.update({
                "prompt": prompt,
                "stop": conv.stop_str,
                "stop_token_ids": conv.stop_token_ids,
            })
        headers = {"User-Agent": "FastChat Client"}
        for _ in range(3):
            try:
                response = requests.post(
                    controller_addr + "/worker_generate_stream",
                    headers=headers,
                    json=gen_params,
                    stream=True,
                    timeout=120,
                )
                text = ""
                for line in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
                    if line:
                        text = json.loads(line)["text"]
                return text
            # if timeout or connection error, retry
            except Timeout: 
                print("Timeout, retrying...")
            except ConnectionError:
                print("Connection error, retrying...")
            time.sleep(5)
        else:
            raise Exception("Timeout after 3 retries.")

