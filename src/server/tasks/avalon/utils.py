import re

def get_vote_result(answer):
    match_vote = "Yes|No"
    vote_result = []
    
    vote_result = re.findall(match_vote, answer)

    result = '' if len(vote_result) == 0 else vote_result[-1]

    return result

def get_team_result(answer):
    match_num = r"\d+"
    player_list = []
    
    player_list = re.findall(match_num, answer)

    player_list = [int(id) for id in player_list]

    return player_list

def get_assassination_result(message, answer): 
    match_num = r"\d+"
    player_id = []
        
    player_id = re.findall(match_num, str(message)+str(answer)) 

    player_id = int(player_id[-1])

    return player_id

def get_believed_player_sides(answer):
    scores = eval(answer.split("Answer: ")[-1])

    return scores

def verbalize_team_result(votes, outcome):
    verbal_vote = {
        0: "reject",
        1: "approve"
    }
    verbalized_result = ""
    if outcome == True:
        verbalized_result = "The team is approved."
    elif outcome == False:
        verbalized_result = "The team is rejected."
    else:
        raise ValueError("Invalid outcome %s" % outcome)
    
    for idx, vote in enumerate(votes):
        verbalized_result += " Player %d voted %s." % (idx, verbal_vote[vote])
    
    return verbalized_result

def verbalize_mission_result(team, outcome):
    verbalized_result = ""
    if outcome == True:
        verbalized_result = "The mission succeeded."
    elif outcome == False:
        verbalized_result = "The mission failed."
    else:
        raise ValueError("Invalid outcome %s" % outcome)
    
    verbalized_result += " The team is %s, which contains" % str(team)
    for member in team:
        verbalized_result += " Player %s" % str(member)

    return verbalized_result