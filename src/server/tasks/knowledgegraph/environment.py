from typing import Optional, Union, List

from agentrl.worker.environment import EnvironmentDelegation

ENV_SUBTYPE = 'kg'
IMAGE = 'freebase:latest'


class KnowledgeGraphEnvironmentDelegation(EnvironmentDelegation):

    def __init__(self, database_file: Optional[str] = None):
        super().__init__('knowledgegraph')
        self.database_file = database_file

    def get_subtypes(self) -> List[str]:
        return [ENV_SUBTYPE]

    def get_service_port(self, subtype: str) -> Optional[Union[int, List[int]]]:
        return 3001

    def get_reuse_limit(self, subtype: str) -> int:
        return 0

    def get_concurrency_limit(self, subtype: str) -> int:
        return 0

    async def create_docker_container(self, attrs: dict, subtype: str) -> dict:
        assert self.database_file, 'database file path must be provided'

        attrs['Image'] = IMAGE

        attrs['HostConfig']['Binds'] = [
            f'{self.database_file}:/database/virtuoso.db:ro'
        ]

        return attrs
