# import random
import numpy as np

class AvalonConfig():
    '''
    Avalon game configuration
    '''

    # usage: creationAndQuests[num_players][[num_good, num_evil], [num_players_for_quest], [num_fails_for_quest]]
    QUEST_PRESET      = {5 : [[3,2] , [2,3,2,3,3], [1,1,1,1,1], ] , 
                         6 : [[4,2] , [2,3,4,3,4], [1,1,1,1,1],] , 
                         7 : [[4,3] , [2,3,3,4,4], [1,1,1,2,1],] , 
                         8 : [[5,3] , [3,4,4,5,5], [1,1,1,2,1],] , 
                         9 : [[6,3] , [3,4,4,5,5], [1,1,1,2,1],] , 
                         10 : [[6,4] , [3,4,4,5,5], [1,1,1,2,1],]}
    
    MAX_ROUNDS = 5
    PHASES = {0 : "Team Selection", 1 : "Team Voting", 2 : "Quest Voting", 3 : "Assassination"}
    ROLES = {0 : "Merlin", 1 : "Percival", 2 : "Morgana", 3 : "Mordred", 4 : "Oberon", 5 : "Servant", 6 : "Minion", 7 : "Assassin"}

    def __init__(self, num_players, merlin = True, percival = False, morgana = False, mordred = False, oberon = False) -> None:
        '''
        num_players: number of players in the game
        merlin: whether Merlin is in the game
        percival: whether Percival is in the game
        morgana: whether Morgana is in the game
        mordred: whether Mordred is in the game
        oberon: whether Oberon is in the game
        '''
        self.num_players = num_players
        self.merlin = merlin
        self.percival = percival
        self.morgana = morgana
        self.mordred = mordred
        self.oberon = oberon

        # load game presets
        self.num_evil = self.QUEST_PRESET[num_players][0][1]
        self.num_good = num_players - self.num_evil
        self.num_players_for_quest = self.QUEST_PRESET[num_players][1]
        self.num_fails_for_quest = self.QUEST_PRESET[num_players][2]

        np.random.seed(0)
    
class AvalonGameEnvironment():
    
    '''
    Avalon game environment, call methods to access environment
    '''
    def __init__(self, config: AvalonConfig) -> None:
        '''
        num_players: number of players in the game
        merlin: whether Merlin is in the game
        percival: whether Percival is in the game
        morgana: whether Morgana is in the game
        mordred: whether Mordred is in the game
        oberon: whether Oberon is in the game
        '''
        self.num_players = config.num_players
        self.merlin = config.merlin
        self.percival = config.percival
        self.morgana = config.morgana
        self.mordred = config.mordred
        self.oberon = config.oberon

        # load game presets
        self.num_evil = config.num_evil
        self.num_good = config.num_good
        self.num_players_for_quest = config.num_players_for_quest
        self.num_fails_for_quest = config.num_fails_for_quest

        self.config = config
        
        # np.random.seed(0)
        # initialize game
        self.reset()

    def reset(self):
        '''
        Reset game environment
        '''

        # reset game trackers
        self.round = 0
        self.quest = 0
        self.phase = 0
        self.turn = 0
        self.done = False
        self.good_victory = False
        self.quest_leader = np.random.randint(0, self.num_players - 1)

        self.quest_results = []
        self.quest_team = []
        self.team_votes = []
        self.quest_votes = []

        # reassign roles
        return self.assign_roles()
    
    def assign_roles(self):
        '''
        assigns roles to players
        '''
        self.roles = np.full(self.num_players, 5)
        self.is_good = np.full(self.num_players, True)

        # choose num_evil players to be evil
        evil_players = np.random.choice(range(self.num_players), self.num_evil, replace = False)
        self.is_good[evil_players] = False

        # create evil roles
        evil_roles = [7]
        if self.morgana:
            evil_roles.append(2)
        if self.mordred:
            evil_roles.append(3)
        if self.oberon:
            evil_roles.append(4)
        
        # fill rest of evil roles with 6
        evil_roles += [6] * (self.num_evil - len(evil_roles))

        # assign evil roles randomly
        self.roles[evil_players] = np.random.choice(evil_roles, self.num_evil, replace = False)

        # create good roles
        good_roles = []
        if self.merlin:
            good_roles.append(0)
        if self.percival:
            good_roles.append(1)

        # fill rest of good roles with 5
        good_roles += [5] * (self.num_good - len(good_roles))

        # assign good roles randomly
        good_players = np.where(self.is_good)[0]
        self.roles[good_players] = np.random.choice(good_roles, self.num_good, replace = False)

        # return list of role names
        return [self.config.ROLES[role] for role in self.roles]

    def get_role(self, player):
        '''
        returns tuple of role index, role name, and whether player is good
        '''
        return (self.roles[player], self.ROLES[self.roles[player]], self.is_good[player])
    
    def get_roles(self):
        '''
        returns list of tuples of role index, role name, and whether player is good
        '''
        return [(role, self.config.ROLES[role], self.is_good[player]) for player, role in enumerate(self.roles)]
    
    def get_partial_sides(self, player):
        '''
        returns list of the sides of other players that player knows
        '''
        
        # if player is Merlin or evil, return all sides
        if self.roles[player] == 0 or not self.is_good[player]:
            return self.is_good
        # otherwise return list of -1 for unknown
        else:
            return [-1 if i != player else 1 for i in range(self.num_players)]
    
    def get_phase(self):
        '''
        returns tuple of phase index and phase name
        '''
        return (self.phase, self.config.PHASES[self.phase])
    
    def get_quest_leader(self):
        '''
        returns quest leader
        '''
        return self.quest_leader
    
    def get_team_size(self):
        '''
        returns team size
        '''
        return self.num_players_for_quest[self.turn]
    
    def choose_quest_team(self, team: frozenset, leader):
        '''
        chooses quest team
        team: list of players on team
        returns: (next phase, whether game is done, next quest leader)
        '''
        # check if game ended or not
        if self.done:
            raise ValueError("Game ended")

        # check if it is team selection phase. if not, raise error
        if self.phase != 0:
            raise ValueError("Not in team selection phase")

        # check if team size is valid
        # if np.sum(team) != self.num_players_for_quest[self.round]:
        #     raise ValueError("Invalid team size")

        if len(team) != self.num_players_for_quest[self.turn]:
            raise ValueError("Invalid team size")

        # check if leader is quest leader
        if leader != self.quest_leader:
            raise ValueError("Not quest leader")

        self.quest_team = team

        # move to next phase
        self.phase += 1
        self.quest_leader = (self.quest_leader + 1) % self.num_players

        return (self.phase, self.done, self.quest_leader)
    
    def get_current_quest_team(self):
        '''
        returns list of players on quest team
        '''
        return self.quest_team

    def vote_on_team(self, votes):
        '''
        votes on quest team: list, 0 for reject, 1 for accept
        returns (next phase, whether game is done, whether team is accepted)
        '''
        # check if game ended or not
        if self.done:
            raise ValueError("Game ended")

        # check if it is team voting phase. if not, raise error
        if self.phase != 1:
            raise ValueError("Not in team voting phase")

        # check if votes is valid
        if len(votes) != self.num_players:
            raise ValueError("Invalid number of votes")

        self.team_votes = votes

        # if this is the MAX_ROUNDS round, then team automatically passes
        if self.round == self.config.MAX_ROUNDS -1:
            self.phase += 1
            self.round = 0
            return (self.phase, self.done, True)

        # if strict majority accepts, move to next phase. Otherwise back to team selection
        if sum(votes) > self.num_players / 2:
            self.phase += 1
            self.round = 0
            return (self.phase, self.done, True)
        else:
            self.phase = 0
            self.round += 1
            return (self.phase, self.done, False)
        
    def get_quest_team_votes(self):
        '''
        returns list of votes on quest team
        '''
        return self.quest_team_votes
    
    def vote_on_quest(self, votes):
        '''
        votes on quest: list, 0 for fail, 1 for pass
        returns: (next phase, whether game is done, whether the quest succeeded, number of fails)
        '''
        # check if game ended or not
        if self.done:
            raise ValueError("Game ended")

        # check if it is quest voting phase. if not, raise error
        if self.phase != 2:
            raise ValueError("Not in quest voting phase")

        # check if votes is valid
        if len(votes) != self.num_players_for_quest[self.turn]:
            raise ValueError("Invalid number of votes")

        self.quest_votes = votes

        num_fails = len(votes) - sum(votes)

        # if number of fails is greater to or equal to number of fails allowed, quest fails
        if (num_fails) >= self.num_fails_for_quest[self.turn]:
            
            self.quest_results.append(False)
            self.turn += 1

            # end game if 3 quests failed. Otherwise go to team selection phase
            if len(self.quest_results) - sum(self.quest_results) == 3:
                self.done = True
                self.good_victory = False
                return (self.phase, self.done, False, num_fails)
            else:
                self.phase = 0
                return (self.phase, self.done, False, num_fails)

        else:
            self.quest_results.append(True)
            self.turn += 1

            # go to assassination phase if 3 quests succeeded. Otherwise go to team selection phase
            if sum(self.quest_results) == 3:
                self.phase += 1
            else:
                self.phase = 0
            return (self.phase, self.done, True, num_fails)
        
    def get_assassin(self):
        '''
        returns assassin
        '''
        return np.where(self.roles == 7)[0][0]
        
    def choose_assassination_target(self, player, target):
        '''
        chooses assassination target
        returns: (next phase, whether game is done, whether good wins)
        game ends
        '''
        # check if game ended or not
        if self.done:
            raise ValueError("Game ended")

        # check if it is assassination phase. if not, raise error
        if self.phase != 3:
            raise ValueError("Not in assassination phase")

        # check if player is assassin
        if self.roles[player] != 7:
            raise ValueError("Not assassin")

        # check if player is good
        if self.is_good[player]:
            raise ValueError("Assassin cannot be good")

        self.done = True

        # check if target is merlin
        if self.roles[target] == 0:
            self.good_victory = False
            return (self.phase, self.done, False)
        
        # check if at least 3 successfuel quests
        if sum(self.quest_results) >= 3:
            self.good_victory = True
            return (self.phase, self.done, True)
        
        # otherwise evil wins
        self.good_victory = False
        return (self.phase, self.done, False)




        
    

        





