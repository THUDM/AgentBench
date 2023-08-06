from typing import List, Tuple
import time
from llm.chatgpt.main import ChatGPT
from sdk.ai_client import Action, AIClient, Game
import random


class AI(AIClient):
    def __init__(self) -> None:
        super().__init__()
        self.chatgpt = ChatGPT()
        self.fish_id = {"spray": 1, "flame": 2, "eel": 3, "sunfish": 4}
        self.action_type = {'normal': 0, 'active': 1}
        
    def Pick(self, game: Game) -> List[int]:
        pick_list = [1, 2, 3, 4]
        # random.shuffle(pick_list)
        return pick_list

    def Assert(self, game: Game) -> Tuple[int, int]:
        return (-1, -1)

    def Act(self, game: Game) -> Action:
        enemy_fish = [{'pos': pos, 'id': self.get_enemy_id(pos), 'hp': self.get_enemy_hp(pos), 'atk': 'unknown'} for pos in range(4)]
        
        my_fish = [{'pos': pos, 'id': abs(self.get_my_id(pos)), 'hp': self.get_my_hp(pos), 'atk': self.get_my_atk(pos)} for pos in range(4)]
        
        # ChatGPT Output
        action_success, output = self.chatgpt._act(enemy_fish, my_fish, self, game)
        if not action_success:
            raise
        
        act = Action(game)
        action_fish_id = self.fish_id[output['pick_fish']]
        for fish in my_fish:
            if fish['id'] == action_fish_id:
                action_fish_pos = fish['pos']
        action_type = self.action_type[output['action']]
        target = int(output['target_position'])
        
        act.set_action_fish(action_fish_pos)
        act.set_action_type(action_type)
        if action_type == 1 and (action_fish_id == 2 or action_fish_id == 4):
            act.set_friend_target(target)
        else:
            act.set_enemy_target(target)
        
        return act
