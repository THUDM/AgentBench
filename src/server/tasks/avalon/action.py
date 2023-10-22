import openai
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
# from .utils import openai_wrapper
from .prompts import CHECK_CHOOSE_TEAM_PROMPT, CHECK_VOTE_ON_QUEST_PROMPT, CHECK_VOTE_ON_TEAM_PROMPT, CHECK_ASSASSINATE_PROMPT, CHECK_BELIEVED_SIDES_PROMPT
# from langchain.chat_models import ChatOpenAI
import numpy as np
# from ...task import logger

# from ...tasks.avalon.arguments import args

from src.typings import (
    ChatHistoryItem,
)

def openai_wrapper(messages, temperature=0.1, **kwargs):
    executed = False
    while not executed:
        try:
            print(messages)
            result = openai.ChatCompletion.create(
                            messages=messages,
                            temperature=temperature,
                            **kwargs
            )
            executed = True
        except Exception as e:
            print(e)
            print("Sleep for 5 seconds zzZ")
            time.sleep(5)

    return result

class AvalonAction:
    def __init__(self, api_args=None, **config):
        # self.player_id = config.pop("id")
        # self.name = config.pop("name")

        self.agent_summary = "full-history"

        if not api_args:
            api_args = {}
        print("api_args={}".format(api_args))
        print("config={}".format(config))
        
        api_args = deepcopy(api_args)
        api_key = api_args.pop("key", None) or os.getenv('OPENAI_API_KEY')
        api_args["model"] = api_args.pop("model", None)
        api_args["api_key"] = api_key
        if not api_key:
            raise ValueError("OpenAI API key is required, please assign api_args.key or set OPENAI_API_KEY environment variable.")
        os.environ['OPENAI_API_KEY'] = api_key
        print("OpenAI API key={}".format(openai.api_key))
        api_base = api_args.pop("base", None) or os.getenv('OPENAI_API_BASE')
        if api_base:
            os.environ['OPENAI_API_BASE'] = api_base
        print("openai.api_base={}".format(openai.api_base))
        if not api_args["model"]:
            raise ValueError("OpenAI model is required, please assign api_args.model.")
        self.api_args = api_args


    def get_vote_result(self, message):
        answer = openai_wrapper(
            messages=[{'role':'user', 'content':message,}],
            temperature=0,
            **self.api_args
        )

        answer = answer["choices"][0]["message"]["content"]

        match_vote = "Yes|No"
        vote_result = []
        
        vote_result = re.findall(match_vote, answer)

        result = '' if len(vote_result) == 0 else vote_result[-1]

        # assert result in ['Yes', 'No']
        print(result)



        return result

    def get_team_result(self, message):
        # answer = wrap_langchain(message)

        answer = openai_wrapper(
            messages=[{'role':'user', 'content':message}],
            temperature=0,
            **self.api_args
        )

        answer = answer["choices"][0]["message"]["content"]

        match_num = r"\d+"
        player_list = []
        
        player_list = re.findall(match_num, answer)

        player_list = [int(id) for id in player_list]

        return player_list
    
    def get_assassination_result(self, message):
        answer = openai_wrapper(
            messages=[{'role':'user', 'content':message}],
            temperature=0,
            **self.api_args
        )

        answer = answer["choices"][0]["message"]["content"]  

        match_num = r"\d+"
        player_id = []
            
        player_id = re.findall(match_num, str(message)+str(answer)) 

        player_id = int(player_id[-1])

        return player_id
    
    def get_believed_player_sides(self, message):
        answer = openai_wrapper(
            messages=[{'role':'user', 'content':message}],
            temperature=0,
            **self.api_args
        )

        answer = answer["choices"][0]["message"]["content"]

        scores = eval(answer.split("Answer: ")[-1])

        return scores


    def inference(self, history: List[dict]) -> str:
        """
        Summarize-then-action
        """
        # logger.info("Current History:")
        # logger.info(str(history))
        temperature = 0.1
        mode = history[-1]["mode"]
        assassin_history = history[-1].pop("assassin_history", None)
        role_name = None if "role_name" not in history[-1] else history[-1]["role_name"]
        team_size = None if "team_size" not in history[-1] else history[-1]["team_size"]
        # history_pointer = history
        history = json.loads(json.dumps(history))
        filtered_history = []
        # idx = 0
        # while idx < len(history):
        #     h = history[idx]

        # if args.benchmark_assassination:
        #     assert assassin_history is not None
        #     history = eval(assassin_history)
        #     temperature = args.temperature

        last_discuss = False
        for h in history:
            h_mode = h.pop("mode", None)
            h.pop("team_size", None)
            h.pop("side", None)
            h.pop("seed", None)
            h.pop("role_name", None)
            h.pop("naive_result", None)
            if h['role'] == 'agent':
                h['role'] = 'assistant'

            
        summary = []

        """
        Action
        """
        if mode == 'system':
            input_messages = history
        else:
            action_prompt = {
                "role": "user",
                "content": history[-1]['content']
            }
            input_messages = history[:-1] + [action_prompt]

        # print(system_prompts)
        # print(action_prompt)
        result_dict = {
            "No": 0,
            "Yes": 1
        }

        if mode == 'system':

            resp = openai_wrapper(
                messages=input_messages,
                temperature=0.1,
                **self.api_args
            )
            resp = resp["choices"][0]["message"]["content"]

            result = resp
            return_resp = resp
        elif mode in ["choose_quest_team_action", "vote_on_team", "vote_on_mission", "assassination", "get_believed_sides"]:

            resp = openai_wrapper(
                messages=input_messages,
                temperature=temperature,
                **self.api_args
            )
            resp = resp["choices"][0]["message"]["content"]
            result = resp
            return_resp = resp
            if mode == "choose_quest_team_action":
                result = self.get_team_result(resp + '\n\n' + CHECK_CHOOSE_TEAM_PROMPT)
                if len(result) != team_size:
                    # logger.warning(f"Wrong team size {len(result)}. The correct team size should be {team_size}.")
                    wrong_result = {
                        "role": "assistant",
                        "content": resp
                    }
                    warning_prompt = {
                        "role": "user",
                        "content": f"You should choose a team of size {team_size}, instead of size {len(result)} as you did."
                    }
                    resp = openai_wrapper(
                        messages=input_messages+[wrong_result]+[warning_prompt],
                        temperature=0.1,
                        **self.api_args
                    )
                    resp = resp["choices"][0]["message"]["content"]
                    result = resp
                    return_resp = resp

                    result = self.get_team_result(resp + '\n\n' + CHECK_CHOOSE_TEAM_PROMPT)
            elif mode == "vote_on_team":
                result = self.get_vote_result(resp + '\n\n' + CHECK_VOTE_ON_TEAM_PROMPT)
                if result not in ["No", "Yes"]:
                    # logger.warning(f"Error from vote on team")
                    wrong_result = {
                        "role": "assistant",
                        "content": resp
                    }
                    warning_prompt = {
                        "role": "user",
                        "content": f"You should output Yes or No to vote on the team."
                    }
                    resp = openai_wrapper(
                        messages=input_messages+[wrong_result]+[warning_prompt],
                        temperature=0.1,
                        **self.api_args
                    )
                    resp = resp["choices"][0]["message"]["content"]
                    result = resp
                    return_resp = resp

                    result = self.get_vote_result(resp + '\n\n' + CHECK_VOTE_ON_TEAM_PROMPT)
                result = result_dict[result]
            elif mode == "vote_on_mission":
                result = self.get_vote_result(resp + '\n\n' + CHECK_VOTE_ON_QUEST_PROMPT)
                if result not in ["No", "Yes"]:
                    # logger.warning(f"Error from vote on mission")
                    wrong_result = {
                        "role": "assistant",
                        "content": resp
                    }
                    warning_prompt = {
                        "role": "user",
                        "content": f"You should output Yes or No to vote on the quest."
                    }
                    resp = openai_wrapper(
                        messages=input_messages+[wrong_result]+[warning_prompt],
                        temperature=0.1,
                        **self.api_args
                    )
                    resp = resp["choices"][0]["message"]["content"]
                    result = resp
                    return_resp = resp

                    result = self.get_vote_result(resp + '\n\n' + CHECK_VOTE_ON_QUEST_PROMPT)
                result = result_dict[result]
            elif mode == "assassination":
                result = self.get_assassination_result(resp + '\n\n' + CHECK_ASSASSINATE_PROMPT)
            elif mode == "get_believed_sides":
                result = []
                scores = self.get_believed_player_sides(resp + '\n\n' + CHECK_BELIEVED_SIDES_PROMPT)
                for i in range(5):
                    result.append(scores[i])
        elif mode == "summarize":
            """
            Summarize
            """
            if self.agent_summary == "full-history":
                summary_prompt = {
                    "role": "user",
                    "content": "Please summarize the history. Try to keep all the useful information, including your identification and your observations of the game."
                }
                summary_result = openai_wrapper(
                    messages=history[1:-1] + [summary_prompt],
                    temperature=0.1,
                    **self.api_args
                )
                summary_result = summary_result["choices"][0]["message"]["content"]
                summary.append({
                    "role": "assistant",
                    "content": "Summary of previous information:\n" + summary_result,
                })
            elif self.agent_summary == "10-last":
                summary = history[-11:-1]
            else:
                raise NotImplementedError(
                    "Value for `agent_summary` should be either `full-history` or `10-last`"
                )
            result = summary
            return_resp = summary
        elif mode == "discuss_on_team" or mode == "choose_quest_team_discussion":
            resp = openai_wrapper(
                messages=[history[0]] + summary + [history[-1]],
                temperature=0.1,
                **self.api_args
            )

            resp = resp["choices"][0]["message"]["content"]
            result = resp
            return_resp = resp
        print(result)



        return result, summary, return_resp