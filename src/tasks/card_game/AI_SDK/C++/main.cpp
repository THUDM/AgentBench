#include "Action.hpp"

int main()
{
    AI *myAI = new AI();
    myAI->run();
    delete (myAI);
    return 0;
}