from __future__ import annotations
from dataclass_wizard import YAMLWizard
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, Tuple, Callable, Type, TypeVar
from src.agent import Agent
from src.task import Task


@dataclass
class YAMLConfig(YAMLWizard):
    module: str = None  # Agent module
    parameters: dict = field(default_factory=dict)  # Agent parameters

    def create(self) -> Union[Agent, Task]:
        path = ".".join(self.module.split(".")[:-1])
        mod = __import__(path, fromlist=[self.module.split(".")[-1]])
        # print(mod)
        return getattr(mod, self.module.split(".")[-1])(**self.parameters)

    @classmethod
    def init_from_yaml(cls, yaml_path: str, update_parameters: Union[None, Dict] = None):
        config = cls.from_yaml_file(yaml_path)
        if update_parameters:
            config.parameters.update(update_parameters)
        # print(config.module)
        config.parameters["src"] = yaml_path
        return config

    @classmethod
    def create_from_yaml(cls, yaml_path: str, update_parameters: Union[None, Dict] = None) -> Union[Agent, Task]:
        config = cls.from_yaml_file(yaml_path)
        if update_parameters:
            config.parameters.update(update_parameters)
        # print(config.module)
        config.parameters["src"] = yaml_path
        return config.create()

