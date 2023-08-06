from typing import List, Tuple

from sdk.ai_client import Action, AIClient, Game


class AI(AIClient):
    def __init__(self) -> None:
        super().__init__()
        self.__attacked: bool = False
        self.__try_type: int = -1
        self.__try_pos: int = -1
        self.__is_inited: bool = False
        self.__is_exposed: List[bool] = [False for _ in range(12)]
        self.__pickfish: List[int] = [-1 for _ in range(4)]

    def Pick(self, game: Game) -> List[int]:
        return [1, 2, 3, 4]

    def Assert(self, game: Game) -> Tuple[int, int]:
        return (-1, -1)

    def Act(self, game: Game) -> Action:
        action = Action(game)
        if 0 in self.get_my_living_fishes():
            action.set_action_fish(0)
            action.set_action_type(1)
            action.set_enemy_target(0)
        else:
            action.set_action_fish(2)
            action.set_action_type(1)
            action.set_enemy_target(0)
        

        return action


if __name__ == "__main__":
    myAI = AI()
    myAI.run()

