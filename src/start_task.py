"""Start task workers from a YAML config.

This module is referenced by the README/docs as:

  python -m src.start_task -a

It existed in earlier AgentBench versions; some users reported it missing on the
current main branch (see issue #212).

The script reads `configs/start_task.yaml` by default and starts one or more
`src.server.task_worker` processes, optionally auto-starting the task_controller.

Note: Many AgentBench tasks run workers inside Docker containers; this script
will use the task definition's `docker.image` when present.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from urllib.parse import urlparse

import requests

from src.configs import ConfigLoader


def _project_root() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _start_worker(name: str, port: int, controller: str, definition: dict) -> None:
    conf = definition[name]

    # If a docker image is specified, run the worker in a container.
    if "docker" in conf and isinstance(conf["docker"], dict) and "image" in conf["docker"]:
        docker = conf["docker"]
        project_root = _project_root()
        subprocess.Popen(
            [
                "docker",
                "run",
                "--rm",
                "-p",
                f"{port}:{port}",
                "--add-host",
                "host.docker.internal:host-gateway",
                "-v",
                f"{project_root}:/root/workspace",
                "-w",
                "/root/workspace",
                docker["image"],
                "bash",
                "-c",
                docker.get("command", "")
                + " "
                + (
                    f"python -m src.server.task_worker {name}"
                    f" --self http://localhost:{port}/api"
                    f" --port {port}"
                    f" --controller {controller.replace('localhost', 'host.docker.internal')}"
                ),
            ]
        )
        return

    # Otherwise, run the worker on the host python.
    subprocess.Popen(
        [
            "python",
            "-m",
            "src.server.task_worker",
            name,
            "--self",
            f"http://localhost:{port}/api",
            "--port",
            str(port),
            "--controller",
            controller,
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        help="Config file to load",
        default="configs/start_task.yaml",
    )
    parser.add_argument(
        "--start",
        "-s",
        dest="start",
        type=str,
        nargs="*",
        help="name num_worker name num_worker ...",
    )
    parser.add_argument(
        "--controller",
        "-l",
        dest="controller_addr",
        default="",
        help="Explicit controller address (e.g. http://localhost:5000/api)",
    )
    parser.add_argument(
        "--auto-controller",
        "-a",
        dest="auto_controller",
        action="store_true",
        help="Auto-start task_controller if not running",
    )
    parser.add_argument(
        "--base-port",
        "-p",
        dest="port",
        type=int,
        default=5001,
        help="Base port for task workers (workers increment ports sequentially)",
    )

    args = parser.parse_args()

    config = ConfigLoader().load_from(args.config)

    # Auto-start controller if requested.
    if args.auto_controller:
        # If config specifies a controller, start it on that port if it doesn't respond.
        if "controller" in config:
            try:
                requests.get(config["controller"] + "/list_workers", timeout=2)
            except Exception:
                print("Specified controller not responding, trying to start a new one")
                o = urlparse(config["controller"])
                subprocess.Popen(
                    [
                        "python",
                        "-m",
                        "src.server.task_controller",
                        "--port",
                        str(o.port),
                    ]
                )
        else:
            subprocess.Popen(["python", "-m", "src.server.task_controller", "--port", "5000"])

        # Wait briefly for controller to come up.
        for _ in range(10):
            try:
                requests.get("http://localhost:5000/api/list_workers", timeout=2)
                break
            except Exception:
                print("Waiting for controller to start...")
                time.sleep(0.5)
        else:
            raise RuntimeError("Controller failed to start")

    # Determine controller address.
    if args.controller_addr:
        controller_addr = args.controller_addr
    elif "controller" in config:
        controller_addr = config["controller"]
    else:
        controller_addr = "http://localhost:5000/api"

    base_port = args.port

    # Start from config unless overridden by --start.
    if "start" in config and not args.start:
        for key, val in config.get("start", {}).items():
            for _ in range(int(val)):
                _start_worker(key, base_port, controller_addr, config["definition"])
                base_port += 1

    # Parse --start overrides.
    n = len(args.start) if args.start else 0
    if n % 2 != 0:
        raise ValueError(
            "--start argument should strictly follow the format: name1 num1 name2 num2 ..."
        )
    for i in range(0, n, 2):
        name = args.start[i]
        num = int(args.start[i + 1])
        for _ in range(num):
            _start_worker(name, base_port, controller_addr, config["definition"])
            base_port += 1

    # Keep the main process alive so Ctrl+C stops the stack.
    while True:
        input()


if __name__ == "__main__":
    main()
