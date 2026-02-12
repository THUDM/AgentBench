# AgentBench Setup Guide (Azure OpenAI + WSL2)

This guide walks you through setting up and running AgentBench with Azure OpenAI on Windows using WSL2.

## Prerequisites
- Use Ubuntu
- Windows 10/11 with WSL2 enabled
- Docker Desktop for Windows with WSL2 integration enabled
- An Azure OpenAI resource with a deployed model (e.g., `gpt-4o-mini`)

---

## Step 1: Enable WSL2 Integration in Docker Desktop

1. Open **Docker Desktop**
2. Go to **Settings** → **Resources** → **WSL Integration**
3. Enable integration with your WSL2 distro (e.g., Ubuntu)
4. Click **Apply & Restart**

---

## Step 2: Clone the Repository

```bash
# In WSL2 terminal
cd ~
git clone https://github.com/Jay-Dev01/AgentBench.git
cd AgentBench
git checkout ubuntu-azure-setup
```

---

## Step 3: Set Up Python Environment

```bash
# Install Python 3.11 if not available
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 4: Configure Azure OpenAI API Key

Set your Azure OpenAI API key as an environment variable:

```bash
export AZURE_OPENAI_API_KEY="your-azure-api-key-here"
```

To make it persistent, add it to your `~/.bashrc`:

```bash
echo 'export AZURE_OPENAI_API_KEY="your-azure-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### Finding Your Azure OpenAI Credentials

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your **Azure OpenAI resource**
3. Click **Keys and Endpoint**
4. Copy **Key 1** or **Key 2**

The configuration file (`configs/agents/openai-chat.yaml`) is already set up to use:
- **Endpoint**: `https://algoverse-ab.openai.azure.com/`
- **Deployment**: `gpt-4o-mini`
- **API Version**: `2024-08-01-preview`

If your Azure resource is different, update the URL in `configs/agents/openai-chat.yaml`.

---

## Step 5: Start Docker Services

```bash
cd ~/AgentBench/extra

# Start the controller, redis, and alfworld worker
docker compose up -d controller redis alfworld-std

# Wait for services to initialize (~30-60 seconds)

# Verify services are running
docker compose ps

# Check that the worker registered
curl http://localhost:5020/api/list_workers
```

You should see output showing `alfworld-std` with workers registered.

### Verify Direct Worker Access

```bash
curl http://localhost:5021/api/get_sessions
```

This should return `[]` or a list of sessions.

---

## Step 6: Run the Benchmark

```bash
cd ~/AgentBench
source venv/bin/activate

# Make sure API key is set
echo $AZURE_OPENAI_API_KEY

# Run the assigner
python -m src.assigner
```

### Expected Output

```
TaskClient created: alfworld-std (http://localhost:5020/api)
  -> Using direct worker address: http://localhost:5021/api
Message: 109 samples remaining.
Agent "gpt-4o-mini" needs to run 1 tasks with total 109 samples:
    Task "alfworld-std": 109
Running Count: 0
Assigned gpt-4o-mini/alfworld-std#108
...
```

The benchmark will run through 109 ALFWorld tasks. Results are saved to the `outputs/` directory.

---

## Troubleshooting

### Rate Limit Errors

If you see `RateLimitReached` errors, the concurrency is set to 1 in `configs/assignments/default.yaml` to minimize this. You can:

1. Wait and retry (the error message tells you how long)
2. Increase your Azure quota at [aka.ms/oai/quotaincrease](https://aka.ms/oai/quotaincrease)

### Connection Refused

If you get connection errors:

```bash
# Check Docker services are running
docker compose ps

# Check controller logs
docker logs agentrl-controller --tail 50

# Check worker logs
docker logs agentbench-fc-alfworld-std-1 --tail 50

# Restart services
docker compose down
docker compose up -d controller redis alfworld-std
```

### Worker Not Registering

If `curl http://localhost:5020/api/list_workers` shows empty workers:

```bash
# Check worker logs for errors
docker logs agentbench-fc-alfworld-std-1 --tail 100

# Rebuild and restart
docker compose down
docker compose build alfworld-std
docker compose up -d controller redis alfworld-std
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `configs/agents/openai-chat.yaml` | Azure OpenAI endpoint and API key |
| `configs/agents/api_agents.yaml` | Agent definitions (gpt-4o-mini) |
| `configs/assignments/default.yaml` | Task assignments and concurrency |
| `configs/assignments/definition.yaml` | Controller address (port 5020) |
| `extra/docker-compose.yml` | Docker service definitions |

---

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Python        │     │   Controller     │     │   ALFWorld      │
│   Assigner      │────▶│   (port 5020)    │────▶│   Worker        │
│                 │     │                  │     │   (port 5021)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                                                 │
        │  (direct communication - bypasses controller)   │
        └─────────────────────────────────────────────────┘
        
        │
        ▼
┌─────────────────┐
│   Azure OpenAI  │
│   (gpt-4o-mini) │
└─────────────────┘
```

**Note:** The Python client talks directly to the worker (port 5021) because the controller has a bug that prevents proper `/interact` forwarding.

---

## Stopping Services

```bash
cd ~/AgentBench/extra
docker compose down
```

---

## Running Different Tasks

All tasks are pre-configured. To switch between tasks:

### Option 1: Use the run script

```bash
chmod +x run_task.sh
./run_task.sh alfworld-std   # or dbbench-std, os-std, kg-std, webshop-std
```

### Option 2: Manual setup

#### 1. Edit `configs/assignments/default.yaml`

Uncomment the task you want to run:

```yaml
    task:
      # - alfworld-std      # House-holding tasks
      - dbbench-std         # Database tasks (uncomment this one)
      # - os-std            # OS interaction tasks
      # - kg-std            # Knowledge graph tasks
      # - webshop-std       # Web shopping tasks
```

#### 2. Start the Docker service

```bash
cd ~/AgentBench/extra

# For alfworld (house-holding)
docker compose up -d controller redis alfworld-std

# For dbbench (database)
docker compose up -d controller redis dbbench-std

# For os-std (OS interaction) - requires building images first
docker compose up -d controller redis os_interaction-std

# For kg-std (knowledge graph) - requires freebase data
docker compose up -d controller redis knowledgegraph-std freebase

# For webshop (web shopping) - requires ~16GB RAM
docker compose up -d controller redis webshop-std
```

#### 3. Run the assigner

```bash
cd ~/AgentBench
source venv/bin/activate
python -m src.assigner
```

---

## Task-Specific Requirements

### OS Interaction (os-std)

Build the required Docker images first:

```bash
cd ~/AgentBench
docker build -t local-os/default -f data/os_interaction/res/dockerfiles/default data/os_interaction/res/dockerfiles
docker build -t local-os/packages -f data/os_interaction/res/dockerfiles/packages data/os_interaction/res/dockerfiles
docker build -t local-os/ubuntu -f data/os_interaction/res/dockerfiles/ubuntu data/os_interaction/res/dockerfiles
```

### Knowledge Graph (kg-std)

Requires Freebase data:

1. Download data from [Freebase-Setup](https://github.com/dki-lab/Freebase-Setup)
2. Extract and place at `./extra/virtuoso_db/virtuoso.db`
3. Start with: `docker compose up -d controller redis knowledgegraph-std freebase`

### WebShop (webshop-std)

- Requires ~16GB RAM
- Takes ~3 minutes to start
- Start with: `docker compose up -d controller redis webshop-std`

---

## Port Mapping Reference

| Task | Host Port | Worker Port |
|------|-----------|-------------|
| Controller | 5020 | 5020 |
| alfworld-std | 5021 | 5021 |
| dbbench-std | 5022 | 5021 |
| os-std | 5023 | 5021 |
| kg-std | 5024 | 5021 |
| webshop-std | 5025 | 5021 |

---

## License

Apache-2.0 - See [LICENSE](LICENSE) for details.

