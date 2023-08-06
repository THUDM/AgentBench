from typing import List, Tuple
import random

from sdk.ai_client import Action, AIClient, Game
from random import randint


class AI(AIClient):
    def __init__(self, stage) -> None:
        super().__init__()
        self.stage = stage

    def Pick(self, game: Game) -> List[int]:
        pick_list = [1, 2, 3, 4]
        random.shuffle(pick_list)
        return pick_list

    def Assert(self, game: Game) -> Tuple[int, int]:
        if self.stage == 1:
            return (-1, -1)
        else:
            return (self.get_enemy_living_fishes()[0], randint(1, 4))

    def Act(self, game: Game) -> Action:
        action = Action(game)
        my_pos: int = self.get_my_living_fishes()[0]
        action.set_action_fish(my_pos)
        return self.auto_valid_action(my_pos, action)
