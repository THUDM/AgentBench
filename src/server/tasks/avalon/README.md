# AvalonBench

## Quick Start

### Prepare Configs

1. Move `./config/test_avalon.yaml` to `/configs/assignments/test_avalon.yaml`
2. Move `./config/avalon.yaml` to `/configs/tasks/avalon.yaml`
3. Add `- avalon.yaml` under `import:` in `/configs/tasks/task_assembly.yaml`

### Start the task server and the assigner

Go back to the root dir, and start the task server (3 is the number of worker)
```bash
python -m src.start_task -a --start avalon-dev 3
```
Start the assigner
```bash
python -m src.assigner --config ./configs/assignments/test_avalon.yaml
```