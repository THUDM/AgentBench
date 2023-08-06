import sys
from client import Client
import json

if __name__ == "__main__":
    language = sys.argv[1]
    stage = int(sys.argv[2])
    order = int(sys.argv[3])
    save_dir = sys.argv[4]
    port = int(sys.argv[5])
    client = Client(port=port)
    if language == 'en':
        from AI_En import Agent
        myAI = Agent(client, stage, order, save_dir)
    else:
        from AI_Cn import Agent
        myAI = Agent(client, stage, order, save_dir)
    
    myAI.run()
    client.quit()