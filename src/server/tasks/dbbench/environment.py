from typing import List

from agentrl.worker.environment import EnvironmentDelegation

TYPE_MYSQL = 'mysql'
TYPE_SQLITE = 'sqlite'


class DBBenchEnvironmentDelegation(EnvironmentDelegation):

    def __init__(self, password: str = 'password'):
        super().__init__('dbbench')
        self.password = password

    def get_subtypes(self) -> List[str]:
        return [TYPE_MYSQL]

    async def create_docker_container(self, attrs: dict, subtype: str) -> dict:
        if subtype == TYPE_MYSQL:
            attrs['Image'] = 'docker.io/library/mysql:8'
            attrs['Env']['MYSQL_ROOT_PASSWORD'] = self.password
            attrs['ExposedPorts'] = {
                '3306/tcp': {}
            }
            attrs['HostConfig']['Ulimits'] = [{
                'Name': 'nofile',
                'Soft': 65536,
                'Hard': 65536
            }]
            attrs['HostConfig']['Tmpfs'] = {
                '/var/lib/mysql': 'rw,uid=999,gid=999,mode=1750'
            }
            attrs['Cmd'] = [
                '--max_connections=2000',
                '--thread_cache_size=512',
                '--innodb_buffer_pool_size=32G',
                '--innodb_buffer_pool_instances=4',
                '--innodb_file_per_table=1',
                '--innodb_log_file_size=1G',
                '--innodb_log_buffer_size=64M',
                '--innodb_flush_log_at_trx_commit=0',
                '--innodb_io_capacity=10000',
                '--innodb_io_capacity_max=20000',
                '--table_open_cache=10000',
                '--table_definition_cache=4096',
                '--wait_timeout=600',
                '--interactive_timeout=600',
                '--connect_timeout=10',
                '--skip-name-resolve',
                '--performance_schema=ON'
            ]
            attrs['Healthcheck'] = {
                'Test': ['CMD', 'mysqladmin', 'ping', '-h', 'localhost', '-u', 'root', f'-p{self.password}'],
                'Interval': 10 * 1000 * 1000 * 1000,  # 10 seconds
                'Timeout': 5 * 1000 * 1000 * 1000,  # 5 seconds
                'StartPeriod': 30 * 1000 * 1000 * 1000,  # 30 seconds
                'StartInterval': 1 * 1000 * 1000 * 1000,  # 1 second
            }

        return attrs

    def get_concurrency_limit(self, subtype: str) -> int:
        return 64

    def get_reuse_limit(self, subtype: str) -> int:
        return 1024
