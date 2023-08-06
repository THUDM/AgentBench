from .example_task import ExampleTask
from .composite_task import CompositeTask
try: from .card_game import CardGame
except: print("> [Warning] CardGame task not available")
try: from .os_interaction import OSInteraction
except: print("> [Warning] OSInteraction task not available")
try: from .alfworld import ALFWorld
except: print("> [Warning] ALFWorld task not available")
try: from .dbbench import DBBench
except: print("> [Warning] DBBench task not available")
try:
    from .webshop_docker import WebShop
except:
    try:
        from .webshop import WebShop
    except:
        print("> [Warning] WebShop task not available")
try: from .lateralthinkingpuzzle import LateralThinkingPuzzle
except: print("> [Warning] LateralThinkingPuzzle task not available")
try: from .lateralthinkingpuzzle_zh import LateralThinkingPuzzle_zh
except: print("> [Warning] LateralThinkingPuzzle_zh task not available")
try: from .mind2web import Mind2Web
except: print("> [Warning] Mind2Web task not available")
try: from .knowledgegraph import KnowledgeGraph
except: print("> [Warning] KnowledgeGraph task not available")
