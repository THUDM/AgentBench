import json

action_format = {
    "pick_fish": "pick an alive fish",
    "action": "choose from [normal, active]",
    "target_position": "target's position, you must choose from [0,3]"
}

guess_format = {
    "guess_type": "the enemy's fish type you may guess",
    "target_position": "guess target's position, you must choose from [0,3]"
}

fish_description = {
    "spray": {
        "passive": r"Counter: Deals 30 damage to attacker when a teammate's health is below 30%",
        "active": r"AOE: Attacks all enemies for 35% of its attack points."
    },
    "flame": {
        "passive": r"Counter: Deals 30 damage to attacker when a teammate's health is below 30%. ",
        "active": r"Infight: Attacks one alive teammate for 75 damage and increases your own attack points by 140. Notice! You can't attack yourself or dead teamate!"
    },
    "eel": {
        "passive": r"Deflect: Distributes 70% damage to teammates and takes 30% when attacked. Gains 40 attack points after taking 200 damage accumulated. ",
        "active": r"AOE: Attacks all enemies for 35% of your attack points."
    },
    "sunfish": {
        "passive": r"Deflect: Distributes 70% damage to teammates and takes 30% when attacked. Gains 40 attack points after taking 200 damage accumulated. ",
        "active": r"Infight: Attacks one alive teammate for 75 damage and increases your own attack points by 140. Notice! You can't attack yourself or dead teamate!"
    }
}

ACTION_PROMPT = """This is a two-player battle game with four pet fish on each team.
Each fish has its 400 initial health, 200 attack power, active ability, and passive ability.
You can choose a live fish to use its active skill or normal attack on an enemy fish each round.
When the conditions are met, the fish's passive ability will automatically trigger, regardless of whether it is chosen.
%s
The victory condition is to have more fish alive at the end of the game.

The following are the four types of the pet fish:
%s

Play the game with me. In each round, you should output your thinking process, and return your move with following json format:
%s

Notice! You must return your move in each round. Otherwise, you will be considered defeated."""

GUESS_RULE = """Your fish's identity is initially hidden. The enemy can guess one of your fish's identity in each round. If the enemy guesses right, your fish's identity is revealed, and each of your fish will get 50 damage."""

GUESS_PROMPT = """This is a two-player battle game with four pet fish in each team.
Each fish has its initial health, attack power, active ability, and passive ability.
All fish\'s identities are initially hidden. You should guess one of the enemy fish\'s identities in each round. If you guess right, the enemy fish\'s identity is revealed, and each of the enemy's fish will get 50 damage. You can only guess the identity of the live fish.
The victory condition is to have more fish alive at the end of the game.

The following are the four types of the pet fish:
%s

Play the game with me. In each round, you should output your thinking process, and return your move with following json format:
%s

Notice! You must return your move in each round. Otherwise, you will be considered defeated."""


ACTION_DESCRIPTION = {
    1: ACTION_PROMPT % ('', fish_description, action_format),
    2: ACTION_PROMPT % (GUESS_RULE, fish_description, action_format)
}

GUESS_DESCRIPTION = {
    2: GUESS_PROMPT % (fish_description, guess_format),
}