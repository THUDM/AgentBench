from typing import List, Tuple
import time, requests, json, re, random
from sdk.ai_client import Action, AIClient, Game

from models import model_call
from prompt.cn import ACTION_DESCRIPTION, GUESS_DESCRIPTION


class Agent(AIClient):
    def __init__(self, model, stage, order, save_dir) -> None:
        super().__init__()
        self.model = model_call[model]
        self.stage = stage
        self.order = order
        self.save_dir = save_dir
        
        self.history = []
        self.assert_history = []
        
        self.name_to_id = {"射水鱼": 1, "喷火鱼": 2, "电鳗": 3, "翻车鱼": 4, "0": 1, "1": 2, "2": 3, "3": 4}
        self.id_to_name = ["", "射水鱼", "喷火鱼", "电鳗", "翻车鱼", "未知"]
        self.action_type = {'normal': 0, 'active': 1}
        self.skill_type = {'skill_type.aoe': '范围伤害', 'skill_type.infight': '内斗', 'skill_type.normalattack': 'normal'}
        self.passive_type = {'passive_type.counter': '反弹', 'passive_type.deflect': '伤害转移'}
        self.assert_to_success =  {True : "成功", False : "失败"}
        
        # refresh the record file
        # open(f'/workspace/hanyu/dhl/AquaWarAI/AI_SDK/Python/thinking_process_{self.order}.jsonl', 'w').close()
        # open(f'/workspace/hanyu/dhl/AquaWarAI/AI_SDK/Python/guess_process_{self.order}.jsonl', 'w').close()
        
    def Pick(self, game: Game) -> List[int]:
        pick_list = [1, 2, 3, 4]
        # random.shuffle(pick_list)
        
        self.name_to_pos = {"射水鱼": 0, "喷火鱼": 1, "电鳗": 2, "翻车鱼": 3, "0": 1, "1": 2, "2": 3, "3": 4}
        self.pos_to_name = ["射水鱼", "喷火鱼", "电鳗", "翻车鱼"]
        
        return pick_list

    def _guess_verify(self, move):
        try:
            move['target_position'] = str(move['target_position'])
            target_position = move['target_position']
            guess_type = move['guess_type']

            # verify output
            assert guess_type in ['射水鱼', '喷火鱼', '电鳗', '翻车鱼']
            assert target_position in ['0', '1', '2', '3']
            assert int(target_position) in self.get_enemy_living_fishes()

            return True
        
        except:
            return False
    
    def _decode_guess(self, output):
        pattern = r"\{[\w\W]*?\}"
        results = [res.replace('\'', '"') for res in re.findall(pattern, output)]

        if results:
            for res in results:
                try:
                    move = json.loads(res)
                except:
                    continue
                
                if self._guess_verify(move):
                    # self.debug_msg(str(output))
                    # self.debug_msg(str(move))
                    return True, move
        
        return False, {}
    
    # 取出目标的position list
    def _non_zero_indexes(self, lst):
        result = []
        for i in range(len(lst)):
            if lst[i] != 0:
                result.append(i)
        return result
    
    def _guess(self, game):
        for ix in range(5):
            system = GUESS_DESCRIPTION[self.stage]
            history = self.assert_history[-3:]
            
            enemy_action = game.enemy_action
            my_action = game.my_action
            my_assert = game.my_assert
            
            if enemy_action.action_fish != -1:
                enemy_action_str = {
                    '行动的鱼': str(enemy_action.action_fish), 
                    '攻击力': str(enemy_action.enemy_expected_injury[0]),
                    '目标': str(self._non_zero_indexes(enemy_action.enemy_targets)), 
                    '技能种类': self.skill_type[str(enemy_action.type)]
                }
            else:
                enemy_action_str = {
                    '行动的鱼': '无', 
                    '攻击力': '无', 
                    '目标': '无',
                    '技能种类': '无'
                }
            
            trigger_passive = {}
            for _pos, _type in zip(my_action.enemy_passives_id, my_action.enemy_types):
                trigger_passive['位置：' + str(_pos)] = self.passive_type[str(_type)]
                
            for _pos, _type in zip(enemy_action.friend_passives_id, enemy_action.friend_types):
                trigger_passive['位置：' + str(_pos)] = self.passive_type[str(_type)]
            
            live_enemy = self.get_enemy_living_fishes()
            live_enemy.sort()
            live_enemy = [str(i) for i in live_enemy]
            
            prompt = f'前一次猜测结果: {self.assert_to_success[my_assert.assertResult]}\敌方当前存活的鱼: {live_enemy}\n敌方上一轮action: {enemy_action_str}\n敌方上一轮触发被动技能: {json.dumps(trigger_passive, ensure_ascii=False)}\n\n请输出你的猜测。'
            
            output = self.model(history, prompt, system)            
            
            # decode output
            success, move = self._decode_guess(output)
            if success:                    
                guess_type = self.name_to_id[move['guess_type']]
                target = int(move['target_position'])
                
                self.assert_history.append((prompt, output))
                with open(f'{self.save_dir}/guess_process_{self.order}.jsonl', 'a+') as f:
                    f.write(json.dumps({'try_times': ix, 'cot': output, 'move': move}, ensure_ascii=False) + '\n')
                
                return (target, guess_type)
                
        return (-1, -1)
    
    def Assert(self, game: Game) -> Tuple[int, int]:
        if self.stage == 1:
            return (-1, -1)
        else:
            return self._guess(game)
            
    def _get_current_state(self, game: Game):
        my_fish = [{'pos': pos, 'id': abs(self.get_my_id(pos)), 'hp': self.get_my_hp(pos), 'atk': self.get_my_atk(pos)} for pos in range(4)]
        
        enemy_fish = [{'pos': pos, 'id': self.get_enemy_id(pos), 'hp': self.get_enemy_hp(pos), 'atk': '未知'} for pos in range(4)]
        
        state = {"你": [], "敌方": []} 
        for fish in my_fish:
            x = {}
            x["ID"] = self.id_to_name[fish["id"]]
            x["位置"] = str(fish["pos"])
            x["血量"] = str(fish["hp"])
            x["攻击力"] = str(fish["atk"])
            state["你"].append(x)
        
        for fish in enemy_fish:
            x = {}
            x["ID"] = self.id_to_name[fish["id"]]
            x["位置"] = str(fish["pos"])
            x["血量"] = str(fish["hp"])
            x["攻击力"] = str(fish["atk"])
            state["敌方"].append(x)
        
        return json.dumps(state, ensure_ascii=False)
        
    def _move_verfiy(self, move):
        try:
            pick_fish = move['pick_fish']
            action = move['action']
            assert action in ['normal', 'active']
            
            move['target_position'] = str(move['target_position'])
            # if aoe, choose 0 position
            if (pick_fish == '射水鱼' or pick_fish == '电鳗') and action == 'active':
                move['target_position'] = '0'
            else:
                assert int(move['target_position']) in self.get_enemy_living_fishes()
                
            target_position = move['target_position']
            
            # verify if choose dead fish
            assert self.name_to_pos[pick_fish] in self.get_my_living_fishes()
            
            # verify if use skill on its self or dead fish
            dead_fish = [i for i in range(4) if i not in self.get_my_living_fishes()]
            assert not(pick_fish == '喷火鱼' and action == 'active' and int(target_position) in [self.name_to_pos[pick_fish]] + dead_fish)
            assert not(pick_fish == '翻车鱼' and action == 'active' and int(target_position) in [self.name_to_pos[pick_fish]] + dead_fish)
            
            return True

        except:
            return False
    
    def _decode_move(self, output):
        pattern = r"\{[\w\W]*?\}"
        results = [res.replace('\'', '"') for res in re.findall(pattern, output)]

        if results:
            for res in results:
                try:
                    move = json.loads(res)
                except:
                    continue
                
                if self._move_verfiy(move):
                    # self.debug_msg(str(output))
                    # self.debug_msg(str(move))
                    return True, move
        
        return False, {}
    
    def _decide(self, game):
        for ix in range(10):
            system = ACTION_DESCRIPTION[self.stage]
            history = self.history[-2:]
            
            enemy_action = game.enemy_action
            my_action = game.my_action
            
            if enemy_action.action_fish != -1:
                enemy_action_str = {'行动的鱼': str(enemy_action.action_fish), '攻击力': str(enemy_action.enemy_expected_injury[0]), '目标': str(self._non_zero_indexes(enemy_action.enemy_targets))}
            else:
                enemy_action_str = {'行动的鱼': '无', '攻击力': '无', '目标': '无'}
            
            if my_action.action_fish != -1:
                my_action_str = {'行动的鱼': str(my_action.action_fish), '攻击力': str(my_action.enemy_expected_injury[0]), '目标': str(self._non_zero_indexes(my_action.enemy_targets))}
            else:
                my_action_str = {'行动的鱼': '无', '攻击力': '无', '目标': '无'}
            
            current_state = self._get_current_state(game)
            prompt = f'以下是当前游戏状态:\n{current_state}\n\n你上回合的action: {my_action_str}\n敌方上回合的action: {enemy_action_str}\n\n请输出你的下一个action。'
            
            with open(f'{self.save_dir}/prompt_output{self.order}.jsonl', 'a+') as f:
                f.write(prompt + '\n')
                
            output = self.model(history, prompt, system)      
            with open(f'{self.save_dir}/prompt_output{self.order}.jsonl', 'a+') as f:
                f.write(output + '\n')      
            
            # decode output
            success, move = self._decode_move(output)
            if success:                    
                act = Action(game)
                pick_fish = move['pick_fish']
                action_fish_pos = self.name_to_pos[pick_fish]
                action_fish_id = self.name_to_id[pick_fish]
                action_type = self.action_type[move['action']]
                target = int(move['target_position'])
                
                try:
                    assert act.set_action_fish(action_fish_pos) == 6
                    assert act.set_action_type(action_type) == 6
                    
                    # active skill is used on ally
                    if action_type == 1 and (pick_fish == '喷火鱼' or pick_fish == '翻车鱼'):
                        assert act.set_friend_target(target) == 6
                    else:
                        assert act.set_enemy_target(target) == 6
                except:
                    continue
                
                self.history.append((prompt, output))
                with open(f'{self.save_dir}/thinking_process_{self.order}.jsonl', 'a+') as f:
                    f.write(json.dumps({'try_times': ix, 'cot': output, 'move': move}, ensure_ascii=False) + '\n')
                
                return True, act
                
        return False, ''
    
    def Act(self, game: Game) -> Action:
        
        # ChatGPT Output
        action_success, act = self._decide(game)
        if not action_success:
            raise
        
        return act