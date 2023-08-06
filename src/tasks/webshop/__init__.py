import re
import sys
from os.path import dirname, realpath

sys.path.append(dirname(realpath(__file__)))

import multiprocess as mp
from typing import Dict, Callable, List

from src.task import Task, Dataset, DataPiece, Session
from .web_agent_site.envs.web_agent_text_env import WebAgentTextEnv

prompt: str = """
You are web shopping.
I will give you instructions about what to do.
You have to follow the instructions.
Every round I will give you an observation and a list of available actions, \
you have to respond an action based on the state and instruction.
You can use search action if search is available.
You can click one of the buttons in clickables.
An action should be of the following structure:
search[keywords]
click[value]
If the action is not valid, perform nothing.
Keywords in search are up to you, but the value in click must be a value in the list of available actions.
Remember that your keywords in search should be carefully designed.
Your response should use the following format:

Thought:
I think ...

Action:
click[something]
"""


def predict(receiver):
    env = WebAgentTextEnv(observation_mode="text", human_goals=True)
    while True:
        data_item, session, sender = receiver.recv()
        history = []
        env.reset(data_item)
        session.inject({"role": "user", "content": prompt})
        session.inject({"role": "agent", "content": "Ok."})

        # one shot

        session.inject({'role': 'user', 'content': 'Observation:\n"WebShop [SEP] Instruction: [SEP] i need a long lasting 6.76 fl oz bottle of l\'eau d\'issey, and price lower than 100.00 dollars [SEP] Search"\n\nAvailable Actions:\n{"has_search_bar": true, "clickables": ["..."]}'})
        session.inject({'role': 'agent', 'content': 'Thought:\nI think I should use the search bar to look for the product I need.\n\nAction:\nsearch[l\'eau d\'issey 6.76 fl oz bottle price < 100.00]'})
        session.inject({'role': 'user', 'content': 'Observation:\n"Instruction: [SEP] i need a long lasting 6.76 fl oz bottle of l\'eau d\'issey, and price lower than 100.00 dollars [SEP] Back to Search [SEP] Page 1 (Total results: 50) [SEP] Next > [SEP] B000VOHH8I [SEP] L\'eau D\'issey By Issey Miyake for MenEau De Toilette Spray, 6.7 Fl Oz Bottle [SEP] $64.98 [SEP] B000MJZOPK [SEP] L\'eau d\'Issey by Issey Miyake for Women 3.3 oz Eau de Toilette Spray [SEP] $49.98 [SEP] B0012S249E [SEP] L\'eau D\'issey By Issey Miyake For Women. Shower Cream 6.7-Ounces [SEP] $31.36 [SEP] B01H8PGKZS [SEP] L\'eau D\'Issey FOR MEN by Issey Miyake - 6.7 oz EDT Spray [SEP] $67.97 [SEP] B00G3C8FHE [SEP] L\'Eau d\'Issey pour Homme - Eau de Toilette 4.2 fl oz [SEP] $51.25 [SEP] B000R94HRG [SEP] Issey Miyake L\'Eau D\'Issey Pour Homme Eau De Toilette Natural Spray [SEP] $44.99 [SEP] B000C214CO [SEP] Issey Miyake L\'eau D\'issey Eau de Toilette Spray for Men, 4.2 Fl Oz [SEP] $53.99 [SEP] B0018SBRDC [SEP] Issey Miyake L\'eau d\'Issey for Women EDT, White, 0.84 Fl Oz [SEP] $27.04 [SEP] B000XEAZ9Y [SEP] L\'eau De Issey By Issey Miyake For Men. Eau De Toilette Spray 6.7 Fl Oz [SEP] $67.08 [SEP] B079HZR2RX [SEP] L\'eau d\'Issey Pure by Issey Miyake for Women 3.0 oz Nectar de Parfum Spray [SEP] $71.49"\n\nAvailable Actions:\n{"has_search_bar": false, "clickables": ["...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "..."]}'})
        session.inject({'role': 'agent', 'content': 'Thought:\nI think I should click on the product I need, which is B000VOHH8I.\n\nAction:\nclick[B000VOHH8I]'})
        session.inject({'role': 'user', 'content': 'Observation:\n"Instruction: [SEP] i need a long lasting 6.76 fl oz bottle of l\'eau d\'issey, and price lower than 100.00 dollars [SEP] Back to Search [SEP] < Prev [SEP] size [SEP] 2.5 fl oz [SEP] 6.76 fl oz (pack of 1) [SEP] L\'eau D\'issey By Issey Miyake for MenEau De Toilette Spray, 6.7 Fl Oz Bottle [SEP] Price: $64.98 [SEP] Rating: N.A. [SEP] Description [SEP] Features [SEP] Reviews [SEP] Buy Now"\n\nAvailable Actions:\n{"has_search_bar": false, "clickables": ["...", "...", "...", "...", "...", "...", "...", "..."]}'})
        session.inject({'role': 'agent', 'content': 'Thought:\nI think I should click on the \'6.76 fl oz (pack of 1)\' option to select the size I need.\n\nAction:\nclick[6.76 fl oz (pack of 1)]'})
        session.inject({'role': 'user', 'content': 'Observation:\n"Instruction: [SEP] i need a long lasting 6.76 fl oz bottle of l\'eau d\'issey, and price lower than 100.00 dollars [SEP] Back to Search [SEP] < Prev [SEP] size [SEP] 2.5 fl oz [SEP] 6.76 fl oz (pack of 1) [SEP] L\'eau D\'issey By Issey Miyake for MenEau De Toilette Spray, 6.7 Fl Oz Bottle [SEP] Price: $64.98 [SEP] Rating: N.A. [SEP] Description [SEP] Features [SEP] Reviews [SEP] Buy Now"\n\nAvailable Actions:\n{"has_search_bar": false, "clickables": ["...", "...", "...", "...", "...", "...", "...", "..."]}'})
        session.inject({'role': 'agent', 'content': 'Thought:\nI think I should click on the \'Buy Now\' button to purchase the product.\n\nAction:\nclick[Buy Now]'})

        observation = env.observation
        reward = 0
        format_fail = False
        for j in range(10):
            available_actions = env.get_available_actions()
            session.inject({"role": "user", "content": f"Observation:\n{observation}\n\n"
                                                       f"Available Actions:\n{available_actions}"})
            response = session.action()
            try:
                action = re.search(r"[Aa]ction: *\n *((search|click)\[.+?])", response).group(1)
            except:
                format_fail = True
                action = None
            history.append({"observation": observation, "available_actions": available_actions,
                            "response": response, "action": action})
            if not action:
                reward = 0
                break
            observation, reward, done, info = env.step(action)
            history[-1]["reward"] = reward
            history[-1]["done"] = done
            if done:
                break
        sender.send({
            "history": history,
            "reward": reward,
            "format_fail": format_fail
        })


class WebShop(Task[int, Dict, None]):
    def __init__(self, **configs):
        super().__init__(**configs)
        self.ranging = (configs.pop("start", 0), configs.pop("end", 500))
        self.num_envs = min(self.workers, configs.pop("num_envs", 1))
        self.processes = []
        ctx = mp.get_context('spawn')
        for i in range(self.num_envs):
            receiver, sender = ctx.Pipe(False)
            p = ctx.Process(target=predict, args=(receiver,))
            p.start()
            self.processes.append((sender, ctx.Lock(), p))

    def get_data(self) -> Dataset[int, None]:
        dataset = Dataset()
        for i in range(*self.ranging):
            dataset.append(DataPiece(i, None))
        return dataset

    def predict_single(self, session: Session, data_item: Dict) -> Dict[str, None]:
        ctx = mp.get_context('spawn')
        receiver, sender = ctx.Pipe(False)
        i = 0
        while True:
            if self.processes[i][1].acquire(timeout=0.2):
                break
            i += 1
            i %= self.num_envs
        self.processes[i][0].send((data_item, session, sender))
        ret = receiver.recv()
        self.processes[i][1].release()
        return ret

    @property
    def metrics(self) -> Dict[str, Callable[[List[Dict], List[None]], float]]:
        def factory(key):
            def f(output, target):
                output = [x for x in output if x]
                if key == "history":
                    return sum([len(x[key]) for x in output]) / len(output) if len(output) > 0 else 0
                return sum([x[key] for x in output]) / len(output) if len(output) > 0 else 0

            return f

        return {
            "reward": factory("reward"),
            "format_fail_rate": factory("format_fail"),
            "average_round": factory("history"),
        }

    def release(self):
        for _, _, p in self.processes:
            p.terminate()
            p.join()
