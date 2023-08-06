from src.agent import Agent
from typing import List, Dict, Any, Optional, Union, Tuple, Callable, Type, TypeVar
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


class DoNothingAgent(Agent):
    """This agent is a test agent, which does nothing. (return empty string for each action)"""

    def __init__(self, sleep=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.sleep = sleep

    def inference(self, history: List[dict]) -> str:
        if self.sleep:
            time.sleep(self.sleep)
        return "AAAAA"
