import socket
import sys
import time
from typing import Optional

import docker
import mysql.connector
from docker.models import containers
import random


class Container:
    port = 13000

    def __init__(self, volume: str = None, init_file: str = None, image: str = "mysql"):
        self.deleted = False
        self.image = image
        self.client = docker.from_env()
        password = "password"
        # print("trying port", file=sys.stderr)
        p = Container.port + random.randint(0, 10000)
        while self.is_port_open(p):
            p += random.randint(0, 20)
        self.port = p
        # print("port decided", self.port, file=sys.stderr)
        if volume:
            self.container: containers.Container = \
                self.client.containers.run(image,
                                           name=f"mysql_{self.port}",
                                           environment={
                                               "MYSQL_ROOT_PASSWORD": password,
                                               # "MYSQL_DATABASE": database
                                           },
                                           ports={"3306": self.port},
                                           volumes={volume: {"bind": "/var/lib/mysql", "mode": "rw"}},
                                           detach=True, tty=True,
                                           stdin_open=True, remove=True)
        else:
            self.container: containers.Container = \
                self.client.containers.run(image,
                                           name=f"mysql_{self.port}",
                                           environment={
                                               "MYSQL_ROOT_PASSWORD": password,
                                               # "MYSQL_DATABASE": database
                                           },
                                           ports={"3306": self.port},
                                           detach=True, tty=True,
                                           stdin_open=True, remove=True)
        Container.port += 1

        time.sleep(1)

        retry = 0
        while True:
            try:
                self.conn = mysql.connector.connect(
                    host="127.0.0.1",
                    user="root",
                    password="password",
                    port=self.port,
                    # database=database
                    pool_reset_session=True,
                )
            except mysql.connector.errors.OperationalError:
                # print("sleep", file=sys.stderr)
                time.sleep(1)
            except mysql.connector.InterfaceError:
                if retry > 10:
                    raise
                time.sleep(5)
            else:
                break
            retry += 1

        # self.conn.autocommit = True

        if init_file:
            # print(f"Initializing container with {init_file}")
            with open(init_file) as f:
                data = f.read()
            for sql in data.split("\n\n"):
                try:
                    self.execute(sql, verbose=False)
                except Exception as e:
                    raise
                    # print(e)

    def delete(self):
        # self.conn.close()
        self.container.stop()
        self.deleted = True

    def __del__(self):
        try:
            if not self.deleted:
                self.delete()
        except:
            pass

    def execute(self, sql: str, database: str = None, truncate: bool = True, verbose: bool = True,
                no_except: bool = False) -> Optional[str]:
        if verbose:
            # print("== EXECUTING ==")
            if len(sql) < 300:
                pass
                # print(sql)
        self.conn.reconnect()
        try:
            with self.conn.cursor() as cursor:
                if database:
                    cursor.execute(f"use `{database}`;")
                    cursor.fetchall()
                cursor.execute(sql, multi=True)
                result = cursor.fetchall()
                result = str(result)
            self.conn.commit()
        except Exception as e:
            if no_except:
                raise
            result = str(e)
        if verbose:
            if len(result) < 200:
                pass
                # print(result)
            else:
                pass
                # print("len result:", len(result))
        if len(result) > 800 and truncate:
            result = result[:800] + "[TRUNCATED]"
        if not sql.lower().startswith("select"):
            pass  # IMPORTANT: if `execute` is called in a high rate, here must wait for the transaction
            # time.sleep(0.5)     # insure transaction is done
        return result

    def is_port_open(self, port) -> bool:
        try:
            self.client.containers.get(f"mysql_{port}")
            return True
        except Exception:
            pass
        # Create a socket object
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Try to connect to the specified port
            sock.connect(('localhost', port))
            # If the connection succeeds, the port is occupied
            return True
        except ConnectionRefusedError:
            # If the connection is refused, the port is not occupied
            return False
        finally:
            # Close the socket
            sock.close()
