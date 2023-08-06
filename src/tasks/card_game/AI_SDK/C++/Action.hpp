#pragma once

#include "sdk/ai_client.hpp"

class AI : public AIClient
{

private:
    bool attacked;
    int try_type;
    int try_pos;
    bool is_inited = false;
    bool *is_exposed;
    int *pickfish;

public:
    AI()
    {
        is_exposed = new bool[12];
        pickfish = new int[4];
    }
    ~AI()
    {
        delete[] is_exposed;
        delete[] pickfish;
    }

    std::vector<int> Pick(Game game);
    std::pair<int, int> Assert(Game game);
    Action Act(Game game);
};