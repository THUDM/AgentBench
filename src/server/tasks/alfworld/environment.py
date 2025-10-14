import logging
import threading

from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv


class AlfworldEnvWrapper:

    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.lock = threading.Lock()  # lock is used to prevent parallel execution, which might bring exceptions

    def create_env(self, data_item: str):
        with self.lock:
            self.logger.info('initializing alfworld environment')
            alf_env = SingleAlfredTWEnv(self.config, data_item)
            return alf_env.init_env(batch_size=1)

    def reset_env(self, env):
        with self.lock:
            self.logger.info('resetting alfworld environment')
            return env.reset()

    def step_env(self, env, action):
        with self.lock:
            return env.step([action])

    def close_env(self, env):
        with self.lock:
            self.logger.info('closing alfworld environment')
            try:
                env.close()
            except Exception:
                self.logger.warning('error closing alfworld environment', exc_info=True)


class SingleAlfredTWEnv(AlfredTWEnv):

    def __init__(self, config, game_files, train_eval='eval_out_of_distribution'):
        self.config = config
        self.train_eval = train_eval

        self.goal_desc_human_anns_prob = self.config['env']['goal_desc_human_anns_prob']
        self.get_game_logic()
        # self.gen_game_files(regen_game_files=self.config['env']['regen_game_files'])

        self.random_seed = 42

        self.game_files = [game_files]
        self.num_games = 1


def get_all_game_files(config, split='eval_out_of_distribution'):
    env = AlfredTWEnv(config, train_eval=split)
    game_files = env.game_files
    del env
    return game_files
