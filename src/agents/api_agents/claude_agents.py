import anthropic
from src.agent import Agent
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
from typing import List, Callable
import dataclasses
from copy import deepcopy


class Claude(Agent):
    def __init__(self, api_args=None, **config):
        if not api_args:
            api_args = {}
        api_args = deepcopy(api_args)
        self.key = api_args.pop("key", None) or os.getenv('Claude_API_KEY')
        api_args["model"] = api_args.pop("model", None)
        if not self.key:
            raise ValueError("Claude API KEY is required, please assign api_args.key or set OPENAI_API_KEY environment variable.")
        if not api_args["model"]:
            raise ValueError("Claude model is required, please assign api_args.model.")
        self.api_args = api_args
        if not self.api_args.get("stop_sequences"):
            self.api_args["stop_sequences"] = [anthropic.HUMAN_PROMPT]
        super.__init__(**config)

    def inference(self, history: List[dict]) -> str:
        prompt = ""
        for message in history:
            if message["role"] == "user":
                prompt += anthropic.HUMAN_PROMPT + message["content"]
            else:
                prompt += anthropic.AI_PROMPT + message["content"]
        prompt += anthropic.AI_PROMPT
        c = anthropic.Client(self.key)
        resp = c.completion(
            prompt=prompt,
            **self.api_args
        )
        return resp
