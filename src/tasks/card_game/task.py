from typing import Any, Dict
from src.agent import Agent, Session
from src.task import Task, DataPiece, Dataset
from .judger.run_all import get_llm
from .server import Server
from .utils import run_cmd
from .judger.cal_metric import calculate
import socket
import os
import json
import time
import threading
import random
import string
import shutil

class CardGame(Task):
    def __init__(self, **kwargs):
        self.port = kwargs.pop("port", 12345)
        self.test_time = kwargs.pop("test_time", 1)
        self.root_dir = "./src/tasks/card_game"
        self.cache_dir = "./data/card_game/.cache"
        self.server = Server(port=self.port, workers=kwargs["workers"])
        self.port = self.server.port
        super().__init__(**kwargs)
        
    @property
    def metrics(self) -> Dict:
        return {
            "score": self._cal_metric,
        }
        
    def _cal_metric(self, prediction, target):
        win_round = 0 
        total_round = 0
        for dict in prediction:
            x = dict["meta"]
            for (key, val) in x.items():
                win_round += val["win_round"]
                total_round += val["test_times"]
        if total_round == 0:
            return {"win_round": win_round, "total_round": total_round, "win_rate": float("nan")}
        else:
            return {"win_round": win_round, "total_round": total_round, "win_rate": win_round / total_round}

    def _random_string(self, length):
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=length))
    
    def _delete_dir(self, directory):
        try:
            shutil.rmtree(directory)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (directory, e))
    
    # run for one round
    def get_data(self) -> Dataset[Dict, Dict]:
        ret = Dataset()
        for stage in [2]:
            for base in ["baseline1", "baseline2"]:
                for agent in [0, 1]:
                    for i in range(self.test_time):
                        ret.append(DataPiece({
                        "stage" : stage,
                        "base" : base,  
                        "agent" : agent
                        }, None))
        return ret
         
    def predict_single(self, session: Session, data_item: Dict) -> Dict:
        location = {
            'ai': f'python+{self.root_dir}/AI_SDK/Python/main.py+en+%d+%d+%s+%d',
            'baseline1': f'python+{self.root_dir}/AI_SDK/Python/basline1.py+%d+%d+%s',
            'baseline2': f'python+{self.root_dir}/AI_SDK/Python/basline2.py+%d+%d+%s',
        }
        # a round consist of 50 subrounds
        folder = self._random_string(16)
        total = {}
        
        stage = data_item["stage"]
        base = data_item["base"]
        agent = data_item["agent"]
        if agent == 0:
            result_dir = f'{self.cache_dir}/result/{folder}_{stage}_ai_{base}'
        else:
            result_dir = f'{self.cache_dir}/result/{folder}_{stage}_{base}_ai'
        stamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(int(time.time())))
        save_dir = f'{result_dir}/{stamp}'
        os.makedirs(save_dir)

        cmd = f'python {self.root_dir}/judger/judger.py {self.root_dir}/logic/bin/main %s %s config {save_dir}/replay.json'
        
        if agent == 0:
            cmd = cmd % (location["ai"] % (stage, 0, save_dir, self.port), location[base] % (stage, 1, save_dir))
        else:
            cmd = cmd % (location[base] % (stage, 1, save_dir), location["ai"] % (stage, 0, save_dir, self.port))
        
        th = threading.Thread(target=self.server.start, args=(folder, session,))
        th.start()
        msg = run_cmd(cmd)[1]
        time.sleep(1)
        th.join()
        current_log = self.server.log[folder]
        
        if agent == 0:
            meta = {'ai1': "ai", 'ai2': base}
        else:
            meta = {'ai1': base, 'ai2': "ai"}
                
        if "\"0\" : 0" in msg:
            meta['winner'] = '1'
        else:
            meta['winner'] = '0'
        
        with open(save_dir + '/meta.json', 'w') as f:
            f.write(json.dumps(meta))     
        ret = calculate(result_dir=result_dir, agent=agent) 
        total[result_dir] = ret
        
        self._delete_dir(result_dir)

        return {"meta": total, "game": current_log, "state": meta, "folder": folder}