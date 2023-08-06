from typing import List, Tuple
import random

from sdk.ai_client import Action, AIClient, Game
from random import randint


class AI(AIClient):
    def __init__(self, stage) -> None:
        super().__init__()
        self.stage = stage
        # self.enemy_atk_record = [0, 0, 0, 0]
        self.has_failed = [[False for i in range(5)] for j in range(4)]
        self.last_fish = -1
        self.last_type = -1
        self.skill_type = {'skill_type.aoe': 'AOE', 'skill_type.infight': 'Infight', 'skill_type.normalattack': 'Normal'}
        self.passive_type = {'passive_type.counter': 'Counter', 'passive_type.deflect': 'Deflect'}
        self.to_assert = {0: {"skill":-1, "passive":-1}, 1: {"skill":-1, "passive":-1}, 2: {"skill":-1, "passive":-1}, 3: {"skill":-1, "passive":-1}}

    def Pick(self, game: Game) -> List[int]:
        pick_list = [1, 2, 3, 4]
        #random.shuffle(pick_list)
        return pick_list
    
    def _non_zero_indexes(self, lst):
        result = []
        for i in range(len(lst)):
            if lst[i] != 0:
                result.append(i)
        return result
    # skill : 0 : aoe, 1 : infight
    # passive : 0 : counter, 1 : deflect
    def add_possible(self, fish, type, val):
        #with open(f'passive.jsonl', 'a+') as f:
        #    f.write(str(fish) + " " + str(val) + "\n")
        if self.get_enemy_id(fish) != -1:
            return
        if type == 1:
            #assert self.to_assert[fish]['skill'] != 1 - val
            self.to_assert[fish]['skill'] = val
        elif type == 0:
            #assert self.to_assert[fish]['passive'] != 1 - val
            self.to_assert[fish]['passive'] = val

    def ass(self, fish, type):
        last_fist = fish
        last_type = type
        return (fish, type)
    
    def Assert(self, game: Game) -> Tuple[int, int]:
        if self.stage == 1:
            return (-1, -1)
        else:
            # 如果在需要 assert 的列表中
            enemy_action = game.enemy_action
            my_action = game.my_action
            my_assert = game.my_assert
            
            live_enemy = self.get_enemy_living_fishes()
            live_enemy.sort()
            
            # 如果上次行动的鱼其实是未知的
            if self.get_enemy_id(enemy_action.action_fish) == -1:
                # 如果返回目标很多 代表有 aoe
                if enemy_action.is_skill == True:
                    target = self._non_zero_indexes(enemy_action.enemy_targets)
                    if enemy_action.num_friend_injury >= 1:
                        self.add_possible(enemy_action.action_fish, 1, 1)
                    else:
                        self.add_possible(enemy_action.action_fish, 1, 0)

                # 判断可能的被动
                l = zip(enemy_action.friend_passives_id + my_action.enemy_passives_id, enemy_action.friend_types + my_action.enemy_types)
                with open(f'/workspace/hanyu/dhl/AquaWarAI/AI_SDK/Python/zip.jsonl', 'a+') as f:
                    
                    for _pos, _type in l:
                        f.write(str(_pos) + " " + str(_type) + '\n')
                for _pos, _type in l:
                        
                    if self.passive_type[str(_type)] == 'Counter':
                        self.add_possible(_pos, 0, 0)
                    elif self.passive_type[str(_type)] == 'Deflect':
                        self.add_possible(_pos, 0, 1)
                    else:
                        raise
            return (-1, -1)
            
        
#策略 选择敌方
    def Act(self, game: Game) -> Action:
        action = Action(game)
        
        action.set_action_fish(0)
        action.set_action_type(0)
        action.set_enemy_target(0)
        return action