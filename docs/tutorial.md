![](../assets/logo.png)

<h1 align="center">Tutorial for AgentBench</h1>

# How to Start Evaluation

We provide two ways to start evaluation. 

## Method I: Perform Evaluation Directly

You can use the `eval.py` to directly perform evaluation. The usage of this script is as follows.

```bash
python eval.py \
    --task <TASK_CONFIG_PATH> \
    --agent <AGENT_CONFIG_PATH> \
    --output <OUTPUT_DIRECTORY> \
    --workers <NUMBER_OF_WORKERS> 
```

Arguments:

- `task`: The path of the task configuration file.
- `agent`: The path of the agent configuration file.
- `output`: Optional. The path of the output directory. 
- `workers`: Optional. The number of workers. This will override the worker configuration in the specified task file. 


## Method II: Create Assignments

### Step 1. Write an assignment file (Recommended in `configs/assigments`).

You can see the [How to Write Configurations](#how-to-write-configurations) section for more detailed information. You can also see the [Example Section](#examples) or [Assignment Directory](../configs/assignments) for examples.

### Step 2. Create an Assignment

You can use the `create_assignment.py` to create an assignment. The usage of this script is as follows.

```bash
python create_assignment.py \
    --assignment <ASSIGNMENT_CONFIG_PATH> 
```

Arguments:

- `assignment`: The path of the assignment configuration file.

### Step 3. Run the Assignment

After running `create_assignment.py` script, you will get a bash script in the `.assigments` directory. You can run this bash script to start evaluation.

```bash
bash <ASSIGNMENT_PATH>
```

# How to Write Configurations

## Introduction

We use `YAML` as the configuration file format. The structures of our configurations are shown in the following list.

- `Instance: object`
    - Properties:
        - `module: string` (The class of the instance related to the root directory of this project)
        - `parameters: dict` (The parameters of the instance)
    - Grammar Sugar:
        - Inherit configurations from another file
            - Method 1: import a configuration and override some properties.
                - `from: str`
                - Example:
                    ```yaml
                    Instance:
                        from: <file-path>
                        parameters:
                            max_new_tokens: 128
                    ```
            - Method 2: Simply import a configuration file.
                - `str`
                - Example:
                    ```yaml
                    Instance: <file-path>
                    ```
            - More detailed examples can be found in the [Example Section](#examples).
- `Agent: Instance`
- `Task: Instance`
    - Properties:
        - `docker_image: string` (Optional. The docker image of the task)
- `Assigment: object`
    - Properties:
        - `agent: Agent` (The agent of the assignment)
        - `task: Task` (The task of the assignment)
        - `output: string` (The parameters of the assignment)

## Constructure of Assigments

When you want to create an assignments file, you should write an assignment file. The structure of the assignment file is shown in the following list.

- `default: Assignment` (Optional. The default assignment configuration. Each of the following assignments will inherit the properties of this object if not specified)
- `assignments: List[Assignment]` (The list of assignments)

## Examples

### Example 1: Evaluation an Agent on Multiple Tasks

```yaml
default:
    agent: <YOUR AGENT PATH>
    task:
        parameters:
        workers: 15
assignments:
    - task: "configs/tasks/os_interaction/dev.yaml"
    - task:
        from: "configs/tasks/dbbench/dev.yaml"
        parameters:
            workers: 10
    - task: "configs/tasks/lateralthinkingpuzzle/dev.yaml"
    - task: "configs/tasks/lateralthinkingpuzzle_zh/dev.yaml"
    - task: "configs/tasks/knowledgegraph/dev.yaml"
    - task: "configs/tasks/alfworld/dev.yaml"
    - task: "configs/tasks/mind2web/dev.yaml"
    - task:
        from: "configs/tasks/webshop/dev.yaml"
        parameters:
            workers: 6
    - task: "configs/tasks/card_game/dev.yaml"
```

### Example 2: Evaluate Multiple Agents on a Task

```yaml
default:
    task: "configs/tasks/os_interaction/dev.yaml"
assignments:
    - agent: <YOUR AGENT1 PATH>
    - agent:
        from: <YOUR AGENT2 PATH>
        parameters:
            max_new_tokens: 128
```

### Example 3: Compose Multiple Assignments

```yaml
assignments:
    - task: "configs/tasks/os_interaction/dev.yaml"
      agent: <YOUR AGENT1 PATH>
    - task: "configs/tasks/dbbench/dev.yaml"
      agent: <YOUR AGENT2 PATH>
```

# How to Create Your Agent

## Recommand Way

We recommend that you deploy your agent as an HTTP service first (you may refer to [OpenAI](https://platform.openai.com/docs/api-reference) or [FastChat](https://github.com/lm-sys/FastChat)). Then you can simply write a configuration file to specify your agent like this:

```yaml
module: src.agents.HTTPAgent
parameters:
    name: "YOUR_AGENT_NAME" # Necessary
    url: https://api.openai.com/v1/chat/completions
    headers: # header dict pairs that your server needs
        Content-Type: application/json
    body: # body dict pairs that your server needs
        Key1: Value1
        Key2: Value2
    prompter:
        name: role_content_dict
        args:
            agent_role: assistant
```

Parameters for `prompter`: (Refer to `src/agents/http_agent.py`)

- `role_content_dict` (besides `body` field specified in your configuration file, a dict filed will be added to the body dict.)
    ```yaml
    name: role_content_dict
    args:
        message_key: messages   # the key of the message list in the body dict
        role_key: role          # the key of the role in each message dict
        content_key: content    # the key of the content in each message dict
        user_role: user         # the value of role field for the user
        agent_role: assistant   # the value of role field for the agent
    ```
- `prompt_string` (besides `body` field specified in your configuration file, a string filed will be added to the body dict.)
    ```yaml
    name: prompt_string
    args:
        prefix: ""                            # The prefix of the prompt
        suffix: "AGENT:"                      # The suffix of the prompt
        user_format: "USER: {content}\n\n"    # The format of the user message, {content} represents the real content
        agent_format: "AGENT: {content}\n\n"  # The format of the agent message, {content} represents the real content
        prompt_key: "prompt"                  # The key of the prompt in the body dict
    ```


## Alternative Way

Alternatively, you can implement your own agent by inheriting the [`Agent` class](../src/agent.py) and override the `inference` method.

### Step 1. Create a file named `your_own_agent.py` in the `src/agents` folder. Write the following code in the file:

```python
from typing import List
from src.agent import Agent

class YourOwnAgent(Agent):
    """This agent is a test agent, which does nothing. (return empty string for each action)"""

    def __init__(self, **kwargs) -> None:
        # load your model here
        super().__init__(**kwargs)

    def inference(self, history: List[dict]) -> str:
        """Inference with the given history. History is composed of a list of dict, each dict:
        {
            "role": str, # the role of the message, "user" or "agent" only
            "content": str, # the text of the message
        }
        """

        # Finally return a string as the output
        return "AAAAA"
```


### Step 2. Add an import statement in `src/agents/__init__.py`:

```python
from .your_own_agent import YourOwnAgent
```

### Step 3. Implement the config file `configs/agents/your_own_agent.yaml`:

```yaml
module: "src.agents.YourOwnAgent" # The module path to your agent class
parameters:
    name: "Your Agent Name"
    key1: value1 # The parameters fed into the constructor of your agent class
    key2: value2 # The parameters fed into the constructor of your agent class
```

# How to Create Your Task

## Implement a task class

Create a folder `src/tasks/<your_task>`.

Create a file `src/tasks/<your_task>/task.py` to override the following methods: (You can refer to src.tasks.OSInteraction)

```python
from src.task import Task

class YourOwnTask(Task):
    def __init__(self, **config):
        # Pop the neccessary parameters from config
        super().__init__(**config)

    @property
    def metrics(self): # Change the metrics if necessary
        return {"EM": lambda outputs, targets: len([1 for o, t in zip(outputs, targets) if o == t]) / min(len(outputs), len(targets))}

    def get_data(self): # return Dataset(Generic[T_INPUT, T_TARGET], List[DataPiece[T_INPUT, T_TARGET]]), T_INPUT and T_TARGET need to be json serializable
        raise NotImplementedError

    def predict_single(self, session, data_item): # return OUTPUT object, need to be json serializable
        raise NotImplementedError
```

Create a file `src/tasks/<your_task>/__init__.py` and write the following code:

```python
from .task import YourOwnTask
```

Import your task in `src/tasks/__init__.py`:

```python
from .<your_task> import YourOwnTask
```

## Put your data if necessary

Put your data in `data/<your_task>/*`.

## Create a task configuration file (YAML)

Create a file `configs/tasks/<your_task>.yaml` to specify your task's configuration:

```yaml
module: "src.tasks.YourOwnTask"
parameters:
    name: "your_task" # Necessary
    key: value # the parameters in YourOwnTask's constructor
    key2: value2 # the parameters in YourOwnTask's constructor
```

## Execute Unit Test with DoNothingAgent

Run the following command to test your task:

```
python eval.py --task configs/tasks/<your_task>.yaml --agent configs/agents/do_nothing.yaml --workers 30
```

Check your output in `output/<timestamp>/<your_task>`.

# How to Run All tasks in AgentBench

## 1. Prepare the Environment

### Step 1. Prepare all the Requirements described in [README.md](../README.md#quick-start).

### Step 2. Prepare Docker Environment

Some of the tasks in AgentBench are evaluated in docker containers, you need to install docker first. You can refer to [Install Docker](https://docs.docker.com/engine/install/) for more detailed information.

And then, run `docker --version` and `docker ps` to verify that you have successfully installed docker.

After that, you can run the following command to build all of the docker image:

```bash
bash scripts/build_docker.sh
```

### Step 3. Prepare the Requirements for Each Task

For OS, DB, KG, you need to build the requirements outside the docker container. 
For LTP, you need to configure your [`gpt-3.5-turbo` Agent](../configs/agents/api_agents/gpt-3.5-turbo.yaml) as a host.

**Task: Operating System**

Install requirements.

```bash
pip install -r src/tasks/os_interaction/requirements.txt
```

Create local images. This process may takes 5 ~ 10 minutes.

```bash
python src/tasks/os_interaction/images.py build -c configs/tasks/os_interaction/dev.yaml -r .
```

Run the following command to verify that you have successfully prepared the requirements.

```bash
python eval.py \
    --task configs/tasks/os_interaction/dev.yaml \
    --agent configs/agents/do_nothing.yaml \
    --workers 30
```

**Task: DataBase**

Prepare `mysql` image.

```bash
docker pull mysql
```

Make sure you have already installed global requirements.
```bash
pip install -r src/tasks/dbbench/requirements.txt
```

Run the following command to verify that you have successfully prepared the requirements. To avoid docker crash, we do not recommend run with too many workers.

```bash
python eval.py \
    --task configs/tasks/dbbench/dev.yaml \
    --agent configs/agents/do_nothing.yaml \
    --workers 5
```

**Task: Knowledge Graph**

Follow [Freebase Setup](https://github.com/dki-lab/Freebase-Setup) to start your own Virtuoso server. Then replace `sparql_url` with the link to your own server in the [config files](../configs/tasks/knowledgegraph). (**Caveat:** You may try the default `sparql_url` without touching this, but it is not always guaranteed that our Virtuoso server is active.)

Install necessary Python packages.

```bash
pip install -r src/tasks/knowledgegraph/requirements.txt
```

Run the following command to verify that you have successfully prepared the requirements.

```bash
python eval.py \
    --task configs/tasks/knowledgegraph/dev.yaml \
    --agent configs/agents/do_nothing.yaml \
    --workers 30
```

## 2. Implement Your Agent

You can refer to [How to Create Your Agent](#how-to-create-your-agent) for detailed information.

## 3. Create an Assignment and Run it!

Replace the agent config in [assignment file](../configs/assignments/dev.yaml).

```yaml
default:
    agent: "PUT YOUR AGENT CONFIG HERE"
    task:
        parameters:
        workers: 15
assignments:
    - task: "configs/tasks/os_interaction/dev.yaml"
    - task:
        from: "configs/tasks/dbbench/dev.yaml"
        parameters:
            workers: 10
    - task: "configs/tasks/lateralthinkingpuzzle/dev.yaml"
    - task: "configs/tasks/lateralthinkingpuzzle_zh/dev.yaml"
    - task: "configs/tasks/knowledgegraph/dev.yaml"
    - task: "configs/tasks/alfworld/dev.yaml"
    - task: "configs/tasks/mind2web/dev.yaml"
    - task:
        from: "configs/tasks/webshop/dev.yaml"
        parameters:
            workers: 6
    - task: "configs/tasks/card_game/dev.yaml"
```

After that, run the following code.

```bash
python create_assignment.py \
    --assignment configs/assignments/dev.yaml
```

And then, the start command of evaluation will be displayed in the output, just run it!

Finally, check Your Results in `outputs` folder.
