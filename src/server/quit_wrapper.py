
from typing import Union

class QuitWrapper(object):

    def __init__(self, environment): 
        self.env = environment
        self.quit = False # tracks whether the env has been quit
        
    def reset(self):
        self.quit = False
        return self.env.reset()

    def add_quit_to_info(self, info: Union[dict, None], quit: bool):
        if info is not None:
            info['quit'] = quit
        else:
            info = {'quit': quit}
        return info
    
    def step(self, action):
        observation, reward, done, info = self.env.step(action)
        
        if action == 'quit': 
            self.quit = True
        
        if isinstance(action, list): # some environments take an action list
            if action[0] == 'quit':
                self.quit = True
            
        if self.quit:
            observation = 'Ending game due to quit action'
            done = True
            reward = 0
        
        info = self.add_quit_to_info(info, self.quit)

        return observation, reward, done, info
