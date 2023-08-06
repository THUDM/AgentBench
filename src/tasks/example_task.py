from src.task import Task, Dataset, DataPiece, Session
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


class ExampleTask(Task[str, str, str]):
    def __init__(self, **configs):
        self.count = configs.pop("count", 10)
        self.range_min = configs.pop("range_min", 0)
        self.range_max = configs.pop("range_max", 100)
        super().__init__(**configs)

    def get_data(self) -> Dataset[str, str]:
        data = Dataset()
        for _ in range(self.count):
            x = random.randint(self.range_min, self.range_max)
            y = random.randint(self.range_min, self.range_max)
            data.append(DataPiece("Your answer should only contain the integer number (without comma), for example, for a question 'what is the answer of 5000 + 5000?', your should print only '10000'. Now, answer the question: What is the answer of {} + {}?".format(x, y), str(x + y)))
        return data

    def predict_single(self, session: Session, data_item: str) -> str:
        return session.action({"role": "user", "content": data_item})
