#!/bin/bash

IP=$(hostname -i)

exec python -m agentrl.worker --self "http://${IP}:5021/api" "$@"
