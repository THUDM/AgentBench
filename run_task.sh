#!/bin/bash
# AgentBench Task Runner
# Usage: ./run_task.sh <task_name>
# Example: ./run_task.sh alfworld-std

TASK=${1:-alfworld-std}

echo "=========================================="
echo "AgentBench Task Runner"
echo "=========================================="
echo "Task: $TASK"
echo ""

# Map task names to docker service names
case $TASK in
    alfworld-std|alfworld)
        SERVICE="alfworld-std"
        TASK_NAME="alfworld-std"
        ;;
    dbbench-std|dbbench|db)
        SERVICE="dbbench-std"
        TASK_NAME="dbbench-std"
        ;;
    os-std|os|os_interaction)
        SERVICE="os_interaction-std"
        TASK_NAME="os-std"
        ;;
    kg-std|kg|knowledgegraph)
        SERVICE="knowledgegraph-std"
        TASK_NAME="kg-std"
        echo "WARNING: kg-std requires freebase data. See README for setup."
        ;;
    webshop-std|webshop)
        SERVICE="webshop-std"
        TASK_NAME="webshop-std"
        echo "WARNING: webshop requires ~16GB RAM"
        ;;
    *)
        echo "Unknown task: $TASK"
        echo ""
        echo "Available tasks:"
        echo "  alfworld-std  - House-holding tasks (ALFWorld)"
        echo "  dbbench-std   - Database tasks"
        echo "  os-std        - OS interaction tasks"
        echo "  kg-std        - Knowledge graph tasks (requires freebase)"
        echo "  webshop-std   - Web shopping tasks (requires ~16GB RAM)"
        exit 1
        ;;
esac

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Step 1: Updating config to use $TASK_NAME..."
# Update the default.yaml to use the selected task
sed -i "s/^      - alfworld-std/      # - alfworld-std/" configs/assignments/default.yaml
sed -i "s/^      - dbbench-std/      # - dbbench-std/" configs/assignments/default.yaml
sed -i "s/^      - os-std/      # - os-std/" configs/assignments/default.yaml
sed -i "s/^      - kg-std/      # - kg-std/" configs/assignments/default.yaml
sed -i "s/^      - webshop-std/      # - webshop-std/" configs/assignments/default.yaml
sed -i "s/^      # - $TASK_NAME/      - $TASK_NAME/" configs/assignments/default.yaml

echo "Step 2: Starting Docker services..."
cd extra
docker compose up -d controller redis $SERVICE

echo ""
echo "Step 3: Waiting for services to start (15 seconds)..."
sleep 15

echo ""
echo "Step 4: Checking worker registration..."
curl -s http://localhost:5020/api/list_workers | python3 -m json.tool 2>/dev/null || curl -s http://localhost:5020/api/list_workers

echo ""
echo "=========================================="
echo "Ready to run! Execute:"
echo "  cd $SCRIPT_DIR"
echo "  source venv/bin/activate"
echo "  python -m src.assigner"
echo "=========================================="

