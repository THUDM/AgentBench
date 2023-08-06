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
        random.shuffle(pick_list)
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
        if self.get_enemy_id(fish) != -1:
            return
        if type == 1:
            #assert self.to_assert[fish]['skill'] != 1 - val
            self.to_assert[fish]['skill'] = val
        elif type == 0:
            #assert self.to_assert[fish]['passive'] != 1 - val
            self.to_assert[fish]['passive'] = val

    def ass(self, fish, type):
        self.last_fish = fish
        self.last_type = type
        return (fish, type)
    
    def Assert(self, game: Game) -> Tuple[int, int]:
        if self.stage == 1:
            return (-1, -1)
        else:
            # 如果在需要 assert 的列表中
            enemy_action = game.enemy_action
            my_action = game.my_action
            my_assert = game.my_assert
            if my_assert.assertResult == False:
                self.has_failed[self.last_fish][self.last_type] = True
                
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
                for _pos, _type in l:
                    #with open(f'/workspace/hanyu/dhl/AquaWarAI/AI_SDK/Python/baseline2.jsonl', 'a+') as f:
                    #    f.write(str(_pos) + ' ' + str(_type) + '\n')
                    #    f.write(str(self.passive_type[str(_type)]) + '\n')
                        
                    if self.passive_type[str(_type)] == 'Counter':
                        self.add_possible(_pos, 0, 0)
                    elif self.passive_type[str(_type)] == 'Deflect':
                        self.add_possible(_pos, 0, 1)
                    else:
                        raise
               
            
            # 如果完全确定了         
            for i in range(4):
                if self.get_enemy_id(i) == -1 and live_enemy.count(i):
                    if self.to_assert[i]["skill"] != -1 and self.to_assert[i]["passive"] != -1:
                        return self.ass(i, self.to_assert[i]["skill"] + self.to_assert[i]["passive"] * 2 + 1)
                
            for i in range(4):
                if self.get_enemy_id(i) == -1 and live_enemy.count(i):
                    for k in range(2):
                        if self.to_assert[i]["skill"] != -1 and self.has_failed[i][self.to_assert[i]["skill"] + k * 2 + 1] == False:
                            return self.ass(i, self.to_assert[i]["skill"] + k * 2 + 1)
            
            for i in range(4):
                if self.get_enemy_id(i) == -1 and live_enemy.count(i):
                    for k in range(2):
                        if self.to_assert[i]["passive"] != -1 and self.has_failed[i][k + self.to_assert[i]["passive"] * 2 + 1] == False:
                            return self.ass(i, k + self.to_assert[i]["passive"] * 2 + 1)
                
            # 在剩下的鱼中随机选择一个乱猜
            know_pos, know_type = [0, 1, 2, 3], [1, 2, 3, 4]
            for i in range(4):
                if self.get_enemy_id(i) != -1 or live_enemy.count(i) == 0: # 如果已经确定了那么就删掉
                    know_pos.remove(i)
                    if self.get_enemy_id(i) != -1:
                        know_type.remove(self.get_enemy_id(i))
            if len(know_pos) == 0:
                return (-1, -1)
            else:
                return self.ass(random.choice(know_pos), random.choice(know_type))
        
#策略 选择敌方
    def Act(self, game: Game) -> Action:
        action = Action(game)
        
        enemy_action_fish_atk = game.enemy_action.enemy_expected_injury[0]
        enemy_action_fish = game.enemy_action.action_fish
        # self.enemy_atk_record[enemy_action_fish] = enemy_action_fish_atk
        
        # 如果友方可以致命一击普通攻击敌方，选择直接攻击
        my_alive = self.get_my_living_fishes()
        enemy_alive = self.get_enemy_living_fishes()
        max_atk_pos = -1
        max_atk = 0
        for my_pos in my_alive:
            if max_atk < self.get_my_atk(my_pos):
                max_atk = self.get_my_atk(my_pos)
                max_atk_pos = my_pos
            
        enemy_pos = self.get_lowest_health_enemy()
        normal_atk = self.get_my_atk(max_atk_pos) * 0.5
        if normal_atk >= self.get_enemy_hp(enemy_pos) and self.get_enemy_hp(enemy_pos) > 70:
            action.set_action_fish(max_atk_pos)
            action.set_action_type(0)
            action.set_enemy_target(enemy_pos)
            return action
        
        # 如果可以使用 aoe
        if len(enemy_alive) >= 2:
            for fish in my_alive:
                if self.get_my_id(fish) == 1 or self.get_my_id(fish) == 3:
                    action.set_action_fish(fish)
                    action.set_action_type(1)
                    action.set_enemy_target(0)
                    return action
        
        action.set_action_fish(max_atk_pos)
        action.set_action_type(0)
        
        # 攻击上一轮攻击我方的鱼
        if enemy_action_fish in enemy_alive:
            action.set_enemy_target(enemy_action_fish)
        else:
            action.set_enemy_target(enemy_alive[0])
        
        # 否则攻击敌方攻击力最高的
        # target = 0
        # target_atk = -1
        # for fish in enemy_alive:
        #     if self.enemy_atk_record[fish] > target_atk:
        #         target = fish
        #         target_atk = self.enemy_atk_record[fish]
        
        # action.set_enemy_target(target)
        
        return action