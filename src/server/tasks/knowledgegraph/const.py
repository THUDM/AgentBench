INSTRUCTIONS = """ 
You are an intelligent agent tasked with answering questions based on the knowledge stored in a 
knowledge base (KB). You can utilize several tools to probe the KB and retrieve relevant 
information to answer the questions posed to you.
Use the tools provided effectively to navigate through the KB, find relationships, 
attributes, and intersections where applicable, and determine the most pertinent 
information to answer the questions.
Remember:
- A variable can be an entity or a set of entities as results from previous queries.
- You should always ensure the tool used is appropriate for the question's demands and 
follow the logical order where necessary (e.g., fetch relations before finding neighbors).
- After a variable is produced along the process, you need to judge whether a variable is 
the final answer to the question. Each variable is represented as an id starting from 0. 
For example, #0 is the first variable, #1 is the second variable, and so on.
- Once you identify the final answer to the question, respond with 'Final Answer: #id' 
where id is the identifier of the variable you determine to be the final answer. For 
example, if you think #3 is the final answer, you MUST respond with 'Final Answer: #3'. Do
not call tools regarding the commission of final answer!!!
- You need to execute one action at a time and can perform a maximum of {max_round} actions to find
the answer.
- You should use the supplied tools unless the final answer is identifies.
Your thoughtful application of these tools and careful consideration of the interactions 
will guide you to the correct answers.
Note that you must finish the task in {max_round} rounds! Arrange your attempts according to it!
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_relations",
            "description": "Fetches all relations associated with a given entity or variable, which helps in navigating the Knowledge Base (KB) to find useful connections.",
            "parameters": {
                "type": "object",
                "properties": {
                    "variable": {
                        "type": "string",
                        "description": "The entity or variable whose relations are to be fetched. Should be an existing entity or a result of a previous query."
                    }
                },
                "required": [
                    "variable"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_neighbors",
            "description": "Returns all entities connected to a given variable through a specified relation, can only be used after identifying valid relations with get_relations().",
            "parameters": {
                "type": "object",
                "properties": {
                    "variable": {
                        "type": "string",
                        "description": "The subject entity or variable to find neighbors for."
                    },
                    "relation": {
                        "type": "string",
                        "description": "The relationship through which neighbors are connected to the subject."
                    }
                },
                "required": [
                    "variable",
                    "relation"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "intersection",
            "description": "Computes the intersection of two sets of entities or variables of the same type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "variable1": {
                        "type": "string",
                        "description": "The first set of entities or a variable."
                    },
                    "variable2": {
                        "type": "string",
                        "description": "The second set of entities or a variable."
                    }
                },
                "required": [
                    "variable1",
                    "variable2"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_attributes",
            "description": "Retrieves all numerical attributes of a given variable, especially valuable when seeking for entities with extreme attributes (max or min).",
            "parameters": {
                "type": "object",
                "properties": {
                    "variable": {
                        "type": "string",
                        "description": "The variable whose numerical attributes are to be fetched."
                    }
                },
                "required": [
                    "variable"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "argmax",
            "description": "Finds the entity with the maximum value of the specified attribute, can be used after identifying valid attributes with get_attributes().",
            "parameters": {
                "type": "object",
                "properties": {
                    "variable": {
                        "type": "string",
                        "description": "The variable or set of entities among which to find the maximum."
                    },
                    "attribute": {
                        "type": "string",
                        "description": "The attribute to maximize over the entities."
                    }
                },
                "required": [
                    "variable",
                    "attribute"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "argmin",
            "description": "Finds the entity with the minimum value of the specified attribute, can be used after identifying valid attributes with get_attributes().",
            "parameters": {
                "type": "object",
                "properties": {
                    "variable": {
                        "type": "string",
                        "description": "The variable or set of entities among which to find the minimum."
                    },
                    "attribute": {
                        "type": "string",
                        "description": "The attribute to minimize over the entities."
                    }
                },
                "required": [
                    "variable",
                    "attribute"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "count",
            "description": "Counts the number of entities within a given variable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "variable": {
                        "type": "string",
                        "description": "The variable or set of entities to count."
                    }
                },
                "required": [
                    "variable"
                ],
                "additionalProperties": False
            }
        }
    }
]

TOOLS_PARAM_ORDER = {
    "get_relations": ["variable"],
    "get_neighbors": ["variable", "relation"],
    "intersection": ["variable1", "variable2"],
    "get_attributes": ["variable"],
    "argmax": ["variable", "attribute"],
    "argmin": ["variable", "attribute"],
    "count": ["variable"]
}

ONE_SHOT = [
    {
        "role": "user",
        "content": "Question: the bipropellant rocket engine with kerosene and gas-generator cycle is designed by who? \nEntities: [Gas-generator cycle, Kerosene]"
    },
    {
        "role": "assistant",
        "content": "Thought: I need to first find engines with gas-generator cycle. To achieve this, I will query the KB to find relations connected to the entity 'Gas-generator cycle' and see if any of them can help me find the answer.",
        'tool_calls': [{
            'function': {
                'arguments': '{"variable":"Gas-generator cycle"}',
                'name': 'get_relations'
            },
            'id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
            'type': 'function'
        }]
    },
    {
        'role': 'tool',
        'tool_call_id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
        'content': 'Observation: [spaceflight.rocket_engine_cycle.rocket_engines, spaceflight.satellite.orbiting, spaceflight.rocket_stage.fuel, spaceflight.satellite_manufacturer.spacecraft_manufactured, automotive.fuel.engines]'
    },
    {
        "role": "assistant",
        "content": "Thought: From the above relations, I might use spaceflight.rocket_engine_cycle.rocket_engines to find the engines of Gas-generator cycle.",
        'tool_calls': [{
            'function': {
                'arguments': '{"variable":"Gas-generator cycle", "relation": "spaceflight.rocket_engine_cycle.rocket_engines}"}',
                'name': 'get_neighbors'
            },
            'id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
            'type': 'function'
        }]
    },
    {
        'role': 'tool',
        'tool_call_id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
        'content': 'Observation: variable #0, which are instances of spaceflight.bipropellant_rocket_engine'
    },
    {
        "role": "assistant",
        "content": "Thought: I also need to find engines with kerosene. To achieve this, I will query the KB to find relations connected to the entity 'Kerosene",
        'tool_calls': [{
            'function': {
                'arguments': '{"variable":"Kerosene"}',
                'name': 'get_relations'
            },
            'id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
            'type': 'function'
        }]
    },
    {
        'role': 'tool',
        'tool_call_id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
        'content': 'Observation: [spaceflight.satellite_manufacturer.spacecraft_manufactured, automotive.fuel.engines, spaceflight.rocket_engine_cycle.rocket_engines]'
    },
    {
        "role": "assistant",
        "content": "Thought: From the above relations, I might use spaceflight.rocket_engine_cycle.rocket_engines to find engines with kerosene cycle.",
        'tool_calls': [{
            'function': {
                'arguments': '{"variable":"Kerosene", "relation": "spaceflight.rocket_engine_cycle.rocket_engines}"}',
                'name': 'get_neighbors'
            },
            'id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
            'type': 'function'
        }]
    },
    {
        'role': 'tool',
        'tool_call_id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
        'content': 'Observation: variable #1, which are instances of spaceflight.bipropellant_rocket_engine'
    },
    {
        "role": "assistant",
        "content": "Thought: From the above relations, I might use spaceflight.rocket_engine_cycle.rocket_engines to find engines with kerosene cycle.",
        'tool_calls': [{
            'function': {
                'arguments': '{"variable1":"#0", "variable2": "#2"}',
                'name': 'intersection'
            },
            'id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
            'type': 'function'
        }]
    },
    {
        'role': 'tool',
        'tool_call_id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
        'content': 'Observation: variable #2, which are instances of spaceflight.bipropellant_rocket_engine'
    },
    {
        "role": "assistant",
        "content": "Thought: From the above relations, I might use spaceflight.rocket_engine.designed_by to find the designer of the engines.",
        'tool_calls': [{
            'function': {
                'arguments': '{"variable":"#2", "relation": "spaceflight.rocket_engine.designed_by"}',
                'name': 'get_neighbors'
            },
            'id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
            'type': 'function'
        }]
    },
    {
        'role': 'tool',
        'tool_call_id': 'call_bl80SGcnZhRLsKtoFIUNR80D',
        'content': 'Observation: variable #3, which are instances of pspaceflight.rocket_engine_designer'
    },
    {
        "role": "assistant",
        "content": "Thought: #3 is the final answer to the question, which represents the target rocket engine designer. Final Answer: #3"
    }
]
