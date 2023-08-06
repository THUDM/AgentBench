from typing import List
import os
import json
import sys
import time
import re
import math
import random
import datetime
import argparse
import requests

from dataclass_wizard import YAMLWizard
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Callable


class SessionExeption(Exception):
    pass

class Session:
    def __init__(self, model_inference, history=None) -> None:
        self.history: list[dict] = history or []
        self.exception_raised = False
        self.model_inference = self.wrap_inference(model_inference)

    def inject(self, message: dict) -> None:
        assert isinstance(message, dict)
        assert "role" in message and "content" in message
        assert isinstance(message["role"], str)
        assert isinstance(message["content"], str)
        assert message["role"] in ["user", "agent"]
        self.history.append(message)

    def action(self, extend_messages: List[dict] = None) -> str:
        extend = []
        if extend_messages:
            if isinstance(extend_messages, list):
                extend.extend(extend_messages)
            elif isinstance(extend_messages, dict):
                extend.append(extend_messages)
            else:
                raise Exception("Invalid extend_messages")
        result = self.model_inference(self.history + extend)
        self.history.extend(extend)
        self.history.append({"role": "agent", "content": result})
        return result
    
    def _calc_segments(self, msg: str):
        segments = 0
        current_segment = ""
        inside_word = False

        for char in msg:
            if char.isalpha():
                current_segment += char
                if not inside_word:
                    inside_word = True
                if len(current_segment) >= 7:
                    segments += 1
                    current_segment = ""
                    inside_word = False
            else:
                if inside_word:
                    segments += 1
                    current_segment = ""
                    inside_word = False
                if char not in [" ", "\n"]:
                    segments += 1

        if len(current_segment) > 0:
            segments += 1

        return segments
    
    def wrap_inference(self, inference_function: Callable[[List[dict]], str]) -> Callable[[List[dict]], str]:
        def _func(history: List[dict]) -> str:
            if self.exception_raised:
                return ""
            messages = self.filter_messages(history)
            try:
                result = inference_function(messages)
            except Exception as e:
                print(e)
                import traceback
                traceback.print_exc()
                print("Warning: Exception raised during inference.")
                self.exception_raised = True
                result = ""
            return result
        return _func

    def filter_messages(self, messages: List[Dict]) -> List[Dict]:
        try:
            assert len(messages) % 2 == 1
            for idx, message in enumerate(messages):
                assert isinstance(message, dict)
                assert "role" in message and "content" in message
                assert isinstance(message["role"], str)
                assert isinstance(message["content"], str)
                assert message["role"] in ["user", "agent"]
                if idx % 2 == 0:
                    assert message["role"] == "user"
                else:
                    assert message["role"] == "agent"
        except:
            raise SessionExeption("Invalid messages")
        
        threashold_segments = 3500
        return_messages = []
        # only include the latest {threashold_segments} segments
        
        segments = self._calc_segments(messages[0]["content"])
        
        for message in messages[:0:-1]:
            segments += self._calc_segments(message["content"])
            if segments >= threashold_segments:
                break
            return_messages.append(message)
            
        if len(return_messages) > 0 and return_messages[-1]["role"] == "user":
            return_messages.pop()
        
        instruction = messages[0]["content"]
        
        omit = len(messages) - len(return_messages) - 1
        
        if omit > 0:
            instruction += f"\n\n[NOTICE] {omit} messages are omitted."
            print(f"Warning: {omit} messages are omitted.")
        
        return_messages.append({
            "role": "user",
            "content": instruction
        })
        
        return_messages.reverse()
        return return_messages
        
            

class Agent:
    def __init__(self, **configs) -> None:
        self.name = configs.pop("name", None)
        self.src = configs.pop("src", None)
        pass

    def create_session(self) -> Session:
        return Session(self.inference)

    def inference(self, history: List[dict]) -> str:
        raise NotImplementedError
