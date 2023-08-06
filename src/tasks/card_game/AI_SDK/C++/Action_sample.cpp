#include "Action.hpp"
#include <algorithm>

std::vector<int> AI::Pick(Game game)
{
    // TODO: fill your code
    std::vector<int> remain_fishes = get_my_remain_fishes();
    std::vector<int> pickfish;
    pickfish.clear();
    for(int i = 0; i < 4; i ++) pickfish.push_back(remain_fishes[i] == 12 ? 13 : remain_fishes[i]);
    return pickfish;
}

std::pair<int, int> AI::Assert(Game game)
{
    // TODO: fill your code
    return std::make_pair(-1, -1);
}

Action AI::Act(Game game)
{
    // TODO: fill your code
    Action action(game);
    int my_pos = (get_my_living_fishes())[0];
    action.set_action_fish(my_pos);
    auto_valid_action(my_pos, &action);
    return action;
}