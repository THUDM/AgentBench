from typing import List, Tuple
import time, requests, json, re, random
from sdk.ai_client import Action, AIClient, Game
from prompt.en import ACTION_DESCRIPTION, GUESS_DESCRIPTION

class Agent(AIClient):
    def __init__(self, client, stage, order, save_dir) -> None:
        super().__init__()
        
        self.client = client
        self.stage = stage
        self.order = order
        self.save_dir = save_dir
        
        self.history = []
        self.assert_history = []
        
        self.name_to_id = {"spray": 1, "flame": 2, "eel": 3, "sunfish": 4, "0": 1, "1": 2, "2": 3, "3": 4}
        self.id_to_name = ["", "spray", "flame", "eel", "sunfish", "unknown"]
        self.action_type = {'normal': 0, 'active': 1}
        self.skill_type = {'skill_type.aoe': 'AOE', 'skill_type.infight': 'Infight', 'skill_type.normalattack': 'Normal'}
        self.passive_type = {'passive_type.counter': 'Counter', 'passive_type.deflect': 'Deflect'}
        
    def Pick(self, game: Game) -> List[int]:
        pick_list = [1, 2, 3, 4]
        # random.shuffle(pick_list)
        
        self.name_to_pos = {"spray": 0, "flame": 1, "eel": 2, "sunfish": 3, "0": 0, "1": 1, "2": 2, "3": 3}
        self.pos_to_name = ["spray", "flame", "eel", "sunfish"]
        
        return pick_list

    def _guess_verify(self, move):
        try:
            move['target_position'] = str(move['target_position'])
            target_position = move['target_position']
            guess_type = move['guess_type']

            # verify output
            assert guess_type in ['spray', 'flame', 'eel', 'sunfish']
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
                    'ACTION_FISH': str(enemy_action.action_fish), 
                    'ATK': str(enemy_action.enemy_expected_injury[0]),
                    'TARGET': str(self._non_zero_indexes(enemy_action.enemy_targets)), 
                    'SKILL_TYPE': self.skill_type[str(enemy_action.type)]
                }
            else:
                enemy_action_str = {
                    'ACTION_FISH': 'None', 
                    'ATK': 'None', 
                    'TARGET': 'None',
                    'SKILL_TYPE': 'None'
                }
            
            trigger_passive = {}
            for _pos, _type in zip(my_action.enemy_passives_id, my_action.enemy_types):
                trigger_passive['Position: ' + str(_pos)] = self.passive_type[str(_type)]
                
            for _pos, _type in zip(enemy_action.friend_passives_id, enemy_action.friend_types):
                trigger_passive['Position: ' + str(_pos)] = self.passive_type[str(_type)]
            
            live_enemy = self.get_enemy_living_fishes()
            live_enemy.sort()
            live_enemy = [str(i) for i in live_enemy]
            
            prompt = f'Previous Guess: {my_assert.assertResult}\nLive Enemy Fish: {live_enemy}\nEnemy\'s previous action: {enemy_action_str}\nEnemy\'s previous triggered passive ability: {json.dumps(trigger_passive, ensure_ascii=False)}\n\nPlease output your guess.'
            
            output = self.client.llm_call(history, prompt, system)
            
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
        
        enemy_fish = [{'pos': pos, 'id': self.get_enemy_id(pos), 'hp': self.get_enemy_hp(pos), 'atk': 'unknown'} for pos in range(4)]
        
        state = {"You": [], "Enemy": []} 
        for fish in my_fish:
            x = {}
            x["ID"] = self.id_to_name[fish["id"]]
            x["POSITION"] = str(fish["pos"])
            x["HP"] = str(fish["hp"])
            x["ATK"] = str(fish["atk"])
            state["You"].append(x)
        
        for fish in enemy_fish:
            x = {}
            x["ID"] = self.id_to_name[fish["id"]]
            x["POSITION"] = str(fish["pos"])
            x["HP"] = str(fish["hp"])
            x["ATK"] = str(fish["atk"])
            state["Enemy"].append(x)
        
        return json.dumps(state, ensure_ascii=False)
        
    def _move_verfiy(self, move):
        try:
            pick_fish = move['pick_fish']
            action = move['action']
            assert action in ['normal', 'active']
            
            move['target_position'] = str(move['target_position'])
            # if aoe, choose 0 position
            if (pick_fish == 'spray' or pick_fish == 'eel') and action == 'active':
                move['target_position'] = '0'
            else:
                assert int(move['target_position']) in self.get_enemy_living_fishes()
                
            target_position = move['target_position']
            
            # verify if choose dead fish
            assert self.name_to_pos[pick_fish] in self.get_my_living_fishes()
            
            # verify if use skill on its self or dead fish
            dead_fish = [i for i in range(4) if i not in self.get_my_living_fishes()]
            assert not(pick_fish == 'flame' and action == 'active' and int(target_position) in [self.name_to_pos[pick_fish]] + dead_fish)
            assert not(pick_fish == 'sunfish' and action == 'active' and int(target_position) in [self.name_to_pos[pick_fish]] + dead_fish)
            
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
        for ix in range(5):
            system = ACTION_DESCRIPTION[self.stage]
            history = self.history[-2:]
            
            enemy_action = game.enemy_action
            my_action = game.my_action
            
            if enemy_action.action_fish != -1:
                enemy_action_str = {'ACTION_FISH': str(enemy_action.action_fish), 'ATK': str(enemy_action.enemy_expected_injury[0]), 'TARGET': str(self._non_zero_indexes(enemy_action.enemy_targets))}
            else:
                enemy_action_str = {'ACTION_FISH': 'None', 'ATK': 'None', 'TARGET': 'None'}
            
            if my_action.action_fish != -1:
                my_action_str = {'ACTION_FISH': str(my_action.action_fish), 'ATK': str(my_action.enemy_expected_injury[0]), 'TARGET': str(self._non_zero_indexes(my_action.enemy_targets))}
            else:
                my_action_str = {'ACTION_FISH': 'None', 'ATK': 'None', 'TARGET': 'None'}
            
            current_state = self._get_current_state(game)
            prompt = f'Following is the current game state:\n{current_state}\n\nYour previous action: {my_action_str}\nEnemy\'s previous action: {enemy_action_str}\n\nPlease Output your next action.'
            
            output = self.client.llm_call(history, prompt, system)
            
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
                    if action_type == 1 and (pick_fish == 'flame' or pick_fish == 'sunfish'):
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
        #if not action_success:
        #    raise
        
        return act

