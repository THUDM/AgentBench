from typing import Dict, List

from agentrl.worker.environment import EnvironmentDelegation


class OSEnvironmentDelegation(EnvironmentDelegation):

    def __init__(self, image_base: str):
        super().__init__('os_interaction')
        self.image_base = image_base

    def get_subtypes(self) -> List[str]:
        return ['default', 'packages', 'ubuntu']

    def is_exclusive(self, subtype: str) -> bool:
        return True

    async def create_docker_container(self, attrs: dict, subtype: str) -> dict:
        attrs['Image'] = f'{self.image_base}/{subtype}'
        attrs['User'] = 'root'
        attrs['Entrypoint'] = ['/bin/sleep']
        attrs['Cmd'] = ['infinity']
        attrs['AttachStdin'] = False
        attrs['AttachStdout'] = False
        attrs['AttachStderr'] = False
        attrs['WorkingDir'] = '/root'
        attrs['HostConfig']['Memory'] = 1024 * 1024 * 1024  # 1GB RAM
        attrs['HostConfig']['MemorySwap'] = attrs['HostConfig']['Memory']  # disable swap
        attrs['HostConfig']['NanoCpus'] = 2_000_000_000  # 2 vCPUs
        return attrs

    def get_container_images(self) -> Dict[str, str]:
        return {
            subtype: f'{self.image_base}/{subtype}'
            for subtype in self.get_subtypes()
        }
