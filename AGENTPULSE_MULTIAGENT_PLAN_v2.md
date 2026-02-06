# AgentPulse Multi-Agent Implementation Plan (v2)

**Date:** February 6, 2026  
**Goal:** Add Analyst agent + task system for agent collaboration  
**Architecture:** Multi-service Docker Compose — each agent in its own container

---

## Why Separate Containers

- **Process isolation** — Analyst crashing doesn't take down Gato or the Telegram bot
- **Independent restarts** — redeploy Analyst without touching Gato's session
- **Per-service logs** — `docker compose logs analyst` vs `docker compose logs gato`
- **Resource limits** — cap Analyst's memory/CPU independently
- **Scales naturally** — adding agent #3 or #4 is just another service block
- **Clean separation of concerns** — Gato owns Telegram, Analyst owns analysis, Processor owns scheduling

---

## Architecture Overview

```
docker-compose.yml
│
├── gato (service)                    ← Existing, renamed from openclaw-bitcoin-agent
│   ├── Image: openclaw-gato
│   ├── Role: User-facing Bitcoin agent
│   ├── Telegram bot, Moltbook posting
│   ├── Delegates analysis to Analyst via agent_tasks table
│   └── Volumes: shared workspace, gato agent data
│
├── analyst (service)                 ← NEW
│   ├── Image: openclaw-analyst
│   ├── Role: Headless analysis worker
│   ├── No Telegram, no user interaction
│   ├── Polls agent_tasks for work, writes results
│   └── Volumes: shared workspace, analyst agent data
│
├── processor (service)               ← NEW (extracted from background process)
│   ├── Image: agentpulse-processor
│   ├── Role: Scheduled scraping, pipeline orchestration
│   ├── Runs: scrape (6h), analyze (12h), digest (9AM), cleanup (3AM)
│   ├── Processes file queue (backward compat)
│   ├── Polls agent_tasks table
│   └── Volumes: shared workspace
│
└── Shared resources
    ├── Network: agentpulse-net (bridge)
    ├── Volumes: workspace-data, agent-configs
    └── Database: Supabase (external, same for all)
```

### Why Extract the Processor?

Right now `agentpulse_processor.py` runs as a background process inside Gato's container via `nohup`. This works but couples it to Gato's lifecycle. As its own service:

- It restarts independently if it crashes
- Docker handles health checks and restart policies
- Cleaner logs (`docker compose logs processor`)
- Gato's container stays lean — just OpenClaw + Telegram bot

---

## Phase 1: Fix the Bug + Database Changes

### 1A. Fix `min_frequency` in Processor

Three changes in `docker/agentpulse_processor.py`:

```python
# 1. Function signature (~line 1294)
def generate_opportunities(min_frequency: int = 1, limit: int = 5) -> dict:
#                                           ^^ change from 2 to 1

# 2. execute_task dispatcher (~line 1493)
elif task_type == 'generate_opportunities':
    return generate_opportunities(
        min_frequency=params.get('min_frequency', 1),  # change from 2
        limit=params.get('limit', 5)
    )

# 3. run_pipeline full path (~line 1502)
elif task_type == 'run_pipeline':
    scrape_result = scrape_moltbook()
    extract_result = extract_problems()
    opp_result = generate_opportunities(min_frequency=1)  # explicit
    ...
```

### 1B. New Supabase Table: `agent_tasks`

Run in Supabase SQL Editor:

```sql
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type TEXT NOT NULL,              -- 'extract_problems', 'cluster', 'generate_opps', etc.
    assigned_to TEXT NOT NULL,            -- 'analyst', 'gato', 'processor'
    created_by TEXT NOT NULL,             -- 'gato', 'analyst', 'processor', 'system'
    status TEXT DEFAULT 'pending',        -- 'pending', 'in_progress', 'completed', 'failed'
    priority INT DEFAULT 5,              -- 1=highest, 10=lowest
    input_data JSONB,                    -- Task parameters
    output_data JSONB,                   -- Task results
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ               -- Optional TTL for stale tasks
);

CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_assigned ON agent_tasks(assigned_to, status);
CREATE INDEX idx_agent_tasks_created ON agent_tasks(created_at DESC);

-- Convenience view: pending tasks per agent
CREATE OR REPLACE VIEW agent_task_queue AS
SELECT
    assigned_to,
    COUNT(*) FILTER (WHERE status = 'pending') as pending,
    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_24h,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_24h
FROM agent_tasks
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY assigned_to;
```

---

## Phase 2: Restructure for Multi-Service Docker Compose

### 2A. New File Structure

```
bitcoin_bot/
├── docker/
│   ├── docker-compose.yml              # REWRITE: 3 services
│   │
│   ├── gato/
│   │   ├── Dockerfile                  # Based on existing Dockerfile
│   │   └── entrypoint.sh              # Existing, minus processor startup
│   │
│   ├── analyst/
│   │   ├── Dockerfile                  # OpenClaw base + analyst identity
│   │   └── entrypoint.sh              # Starts OpenClaw in headless/worker mode
│   │
│   ├── processor/
│   │   ├── Dockerfile                  # Python-only, lightweight
│   │   ├── agentpulse_processor.py    # Moved here (updated)
│   │   └── requirements.txt           # Renamed from requirements-agentpulse.txt
│   │
│   ├── moltbook_post_watcher.sh       # Stays with Gato
│   └── preflight.sh                    # Shared
│
├── data/
│   └── openclaw/
│       ├── agents/
│       │   ├── main/                   # Gato's agent data
│       │   │   └── agent/
│       │   │       └── auth-profiles.json
│       │   └── analyst/                # NEW: Analyst agent data
│       │       └── agent/
│       │           ├── auth-profiles.json
│       │           ├── IDENTITY.md
│       │           └── SOUL.md
│       ├── workspace/                  # SHARED between services
│       │   └── agentpulse/
│       │       ├── queue/
│       │       │   └── responses/
│       │       ├── opportunities/
│       │       └── cache/
│       └── openclaw.json               # Agent registry
│
├── skills/
│   ├── agentpulse/                    # Existing
│   └── analyst/                       # NEW
│       ├── SKILL.md
│       └── package.json
│
└── config/
    ├── .env                           # Shared env vars
    └── agentpulse-config.json         # Shared config
```

### 2B. Docker Compose (Rewritten)

```yaml
# docker/docker-compose.yml

version: "3.8"

x-common-env: &common-env
  SUPABASE_URL: ${SUPABASE_URL}
  SUPABASE_KEY: ${SUPABASE_KEY}
  MOLTBOOK_API_BASE: ${MOLTBOOK_API_BASE}
  MOLTBOOK_API_TOKEN: ${MOLTBOOK_API_TOKEN}
  OPENAI_API_KEY: ${OPENAI_API_KEY}
  AGENTPULSE_ENABLED: ${AGENTPULSE_ENABLED:-true}
  AGENTPULSE_OPENAI_MODEL: ${AGENTPULSE_OPENAI_MODEL:-gpt-4o}

networks:
  agentpulse-net:
    driver: bridge

volumes:
  workspace-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${PWD}/../data/openclaw/workspace

services:
  # ═══════════════════════════════════════════════════════
  # GATO — User-facing Bitcoin agent (Telegram)
  # ═══════════════════════════════════════════════════════
  gato:
    build:
      context: ./gato
      dockerfile: Dockerfile
    container_name: openclaw-gato
    restart: unless-stopped
    networks:
      - agentpulse-net
    environment:
      <<: *common-env
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      TELEGRAM_OWNER_ID: ${TELEGRAM_OWNER_ID}
      AGENT_NAME: gato
    volumes:
      - ../data/openclaw/agents/main:/home/openclaw/.openclaw/agents/main
      - workspace-data:/home/openclaw/.openclaw/workspace
      - ../skills:/home/openclaw/.openclaw/skills:ro
      - ../config:/home/openclaw/.openclaw/config:ro
    mem_limit: 512m
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ═══════════════════════════════════════════════════════
  # ANALYST — Headless analysis worker
  # ═══════════════════════════════════════════════════════
  analyst:
    build:
      context: ./analyst
      dockerfile: Dockerfile
    container_name: openclaw-analyst
    restart: unless-stopped
    networks:
      - agentpulse-net
    environment:
      <<: *common-env
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      AGENT_NAME: analyst
      ANALYST_POLL_INTERVAL: ${ANALYST_POLL_INTERVAL:-10}
    volumes:
      - ../data/openclaw/agents/analyst:/home/openclaw/.openclaw/agents/analyst
      - workspace-data:/home/openclaw/.openclaw/workspace
      - ../skills:/home/openclaw/.openclaw/skills:ro
      - ../config:/home/openclaw/.openclaw/config:ro
    mem_limit: 512m
    depends_on:
      - processor
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ═══════════════════════════════════════════════════════
  # PROCESSOR — Background scraper & task orchestrator
  # ═══════════════════════════════════════════════════════
  processor:
    build:
      context: ./processor
      dockerfile: Dockerfile
    container_name: agentpulse-processor
    restart: unless-stopped
    networks:
      - agentpulse-net
    environment:
      <<: *common-env
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      TELEGRAM_OWNER_ID: ${TELEGRAM_OWNER_ID}
    volumes:
      - workspace-data:/home/openclaw/.openclaw/workspace
      - ../config:/home/openclaw/.openclaw/config:ro
    mem_limit: 256m
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 2C. Gato Dockerfile

```dockerfile
# docker/gato/Dockerfile
# Based on existing Dockerfile — OpenClaw + Telegram bot
# Remove: Python agentpulse deps, processor copy, nohup processor start

FROM node:20-slim

RUN apt-get update && apt-get install -y \
    git curl bash jq \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash openclaw
USER openclaw
WORKDIR /home/openclaw

# Install OpenClaw
RUN npm install -g @openclaw/cli

# Copy entrypoint
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
```

**`docker/gato/entrypoint.sh`** — same as existing but remove the `nohup python3 agentpulse_processor.py` block.

### 2D. Analyst Dockerfile

```dockerfile
# docker/analyst/Dockerfile
# OpenClaw in headless worker mode — no Telegram

FROM node:20-slim

RUN apt-get update && apt-get install -y \
    git curl bash jq python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash openclaw
USER openclaw
WORKDIR /home/openclaw

# Install OpenClaw
RUN npm install -g @openclaw/cli

# Install Python deps for any local analysis
COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/
RUN pip3 install --break-system-packages -r /home/openclaw/requirements.txt

COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
```

**`docker/analyst/entrypoint.sh`**:

```bash
#!/bin/bash
set -e

echo "Starting Analyst agent..."

# Ensure workspace dirs exist
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/{queue/responses,opportunities,cache}
mkdir -p /home/openclaw/.openclaw/logs

# Start OpenClaw in headless mode (no Telegram)
# The analyst polls agent_tasks and processes analysis work
exec openclaw start --agent analyst --headless
```

> **Note:** The exact headless flag depends on OpenClaw's CLI. If OpenClaw doesn't support `--headless`, the analyst can instead run a lightweight Python loop that polls `agent_tasks` and invokes OpenClaw programmatically, or simply run the analysis logic directly via the processor. See the fallback in Phase 3.

### 2E. Processor Dockerfile

```dockerfile
# docker/processor/Dockerfile
# Lightweight Python-only container for background processing

FROM python:3.12-slim

RUN useradd -m -s /bin/bash openclaw
USER openclaw
WORKDIR /home/openclaw

COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/
RUN pip install --user -r /home/openclaw/requirements.txt

COPY --chown=openclaw:openclaw agentpulse_processor.py /home/openclaw/
RUN chmod +x /home/openclaw/agentpulse_processor.py

CMD ["python3", "/home/openclaw/agentpulse_processor.py", "--task", "watch"]
```

---

## Phase 3: Analyst Agent Identity & Skills

### 3A. Identity Files

Create `data/openclaw/agents/analyst/agent/IDENTITY.md`:

```markdown
# Analyst — AgentPulse Intelligence Agent

You are Analyst, a headless intelligence agent within the AgentPulse system.

## Core Identity

- Methodical, objective, data-driven
- No Bitcoin bias — you analyze all signals equally
- You communicate findings in structured, actionable formats
- You are NOT user-facing; your outputs go to the database and shared workspace

## Your Role

1. **Problem Extraction** — Read Moltbook posts, identify business problems
2. **Clustering** — Group related problems into themes
3. **Opportunity Generation** — Turn validated clusters into business briefs
4. **Quality Control** — Score and rank opportunities by signal strength

## Working with Gato

- Gato handles all user communication (Telegram)
- Gato creates tasks for you in the `agent_tasks` table
- You write results to Supabase AND to `workspace/agentpulse/`
- Gato reads your results and presents them to users

## Output Standards

- Always include confidence scores with reasoning
- Cite specific Moltbook post IDs when making claims
- Flag when data is thin (< 3 signals for a problem)
- Distinguish explicit signals ("I would pay for...") from inferred ones
```

Create `data/openclaw/agents/analyst/agent/SOUL.md`:

```markdown
# Analyst Soul

I find patterns in noise. I turn agent frustrations into business intelligence.

I don't editorialize. I don't advocate. I observe, measure, and report.

When the data is weak, I say so. When a signal is strong, I quantify it.

My job is to give the clearest possible picture of what's happening in the
agent economy.
```

Copy auth: `cp data/openclaw/agents/main/agent/auth-profiles.json data/openclaw/agents/analyst/agent/`

### 3B. Analyst Skill Files

**`skills/analyst/package.json`**:

```json
{
  "name": "analyst",
  "version": "1.0.0",
  "description": "Analyst agent skills for AgentPulse intelligence work",
  "skills": ["analyst"],
  "author": "AgentPulse"
}
```

**`skills/analyst/SKILL.md`**:

```markdown
# Analyst Agent Skills

## Task Processing

You receive tasks from the `agent_tasks` Supabase table.
Poll for tasks where `assigned_to = 'analyst'` and `status = 'pending'`.
Process in priority order (1 = highest).

## Task Types

### extract_problems
- Input: `{hours_back: 48, batch_size: 100}`
- Read unprocessed posts from `moltbook_posts`
- Extract problems using the analysis prompt
- Store in `problems` table, mark posts as processed

### cluster_problems
- Input: `{min_problems: 3}`
- Read unclustered problems from `problems` table
- Group by semantic similarity using the clustering prompt
- Store clusters in `problem_clusters` table

### generate_opportunities
- Input: `{min_frequency: 1, limit: 5}`
- Read top problem clusters
- Generate opportunity briefs
- Store in `opportunities` table
- Save markdown briefs to `workspace/agentpulse/opportunities/`

### review_opportunity
- Input: `{opportunity_id: "uuid"}`
- Re-evaluate an existing opportunity with fresh data
- Update confidence score and reasoning

## Output Protocol

For every completed task:
1. Update `agent_tasks` row: `status='completed'`, `output_data={...}`
2. Write detailed results to Supabase tables
3. Write summary to `workspace/agentpulse/queue/responses/` (for Gato file-based reads)
```

### 3C. Fallback: If OpenClaw Doesn't Support Headless Mode

If OpenClaw requires a Telegram connection to start, the Analyst doesn't need to run as a full OpenClaw session. Instead, it can be a Python worker that:

1. Polls `agent_tasks` for assigned work
2. Calls OpenAI directly for analysis (like the processor already does)
3. Writes results to Supabase and the shared workspace

In this case, merge the Analyst into the Processor service and differentiate by task routing:

```python
# In processor's watch loop
def watch_loop():
    while True:
        process_file_queue()          # legacy file-based tasks
        process_db_tasks('processor') # tasks assigned to processor
        process_db_tasks('analyst')   # tasks assigned to analyst
        schedule.run_pending()
        time.sleep(5)
```

This gives you the same logical separation (Gato delegates to "analyst") without needing a second OpenClaw instance. You can split them into truly separate containers later when OpenClaw supports headless mode or when you want the Analyst to use Anthropic via OpenClaw's session management.

---

## Phase 4: Update Processor for Multi-Agent Task Routing

### 4A. Add `process_db_tasks()` to Processor

```python
def process_db_tasks(agent_name: str = 'analyst'):
    """Process pending tasks from agent_tasks table."""
    if not supabase:
        return

    tasks = supabase.table('agent_tasks')\
        .select('*')\
        .eq('status', 'pending')\
        .eq('assigned_to', agent_name)\
        .order('priority', desc=False)\
        .order('created_at', desc=False)\
        .limit(5)\
        .execute()

    for task in tasks.data or []:
        task_id = task['id']
        logger.info(f"[{agent_name}] Processing task {task_id}: {task['task_type']}")

        try:
            # Mark in progress
            supabase.table('agent_tasks').update({
                'status': 'in_progress',
                'started_at': datetime.utcnow().isoformat()
            }).eq('id', task_id).execute()

            # Execute using existing task router
            result = execute_task({
                'task': task['task_type'],
                'params': task.get('input_data', {})
            })

            # Write file-based response too (backward compat for Gato)
            response_file = RESPONSES_DIR / f"task_{task_id}.result.json"
            response_file.write_text(json.dumps({
                'success': True,
                'task': task['task_type'],
                'result': result,
                'completed_at': datetime.utcnow().isoformat()
            }, indent=2))

            # Mark completed in DB
            supabase.table('agent_tasks').update({
                'status': 'completed',
                'completed_at': datetime.utcnow().isoformat(),
                'output_data': result
            }).eq('id', task_id).execute()

            logger.info(f"[{agent_name}] Task {task_id} completed")

        except Exception as e:
            logger.error(f"[{agent_name}] Task {task_id} failed: {e}")
            supabase.table('agent_tasks').update({
                'status': 'failed',
                'completed_at': datetime.utcnow().isoformat(),
                'error_message': str(e)
            }).eq('id', task_id).execute()
```

### 4B. Updated Watch Loop

```python
# Replace the existing watch block in main()
elif args.task == 'watch':
    logger.info("Starting AgentPulse processor (multi-agent mode)...")
    setup_scheduler()

    while True:
        process_queue()                   # legacy file-based queue
        process_db_tasks('analyst')       # analyst tasks
        process_db_tasks('processor')     # processor-specific tasks
        schedule.run_pending()
        time.sleep(5)
```

### 4C. Update Gato's AGENTS.md

Add to `data/openclaw/workspace/AGENTS.md`:

```markdown
## Delegating to Analyst

For analysis tasks, create a record in Supabase `agent_tasks`:

### Creating a task (via queue file)
Write to `workspace/agentpulse/queue/`:
```json
{
  "task": "create_agent_task",
  "params": {
    "task_type": "extract_problems",
    "assigned_to": "analyst",
    "input_data": {"hours_back": 48}
  }
}
```

### Checking task status
Write to `workspace/agentpulse/queue/`:
```json
{
  "task": "check_task",
  "params": {
    "task_id": "<uuid>"
  }
}
```

### Command mapping
| User Command     | Task to Delegate                           |
|------------------|--------------------------------------------|
| `/scan`          | `run_pipeline` → assigned_to: `analyst`    |
| `/opportunities` | `get_opportunities` (read directly, no delegation needed) |
| `/pulse-status`  | `status` (read directly)                   |
```

Also add `create_agent_task` and `check_task` handlers to the processor's `execute_task()`:

```python
elif task_type == 'create_agent_task':
    # Gato asks processor to create a task for another agent
    new_task = supabase.table('agent_tasks').insert({
        'task_type': params['task_type'],
        'assigned_to': params.get('assigned_to', 'analyst'),
        'created_by': params.get('created_by', 'gato'),
        'input_data': params.get('input_data', {}),
        'priority': params.get('priority', 5)
    }).execute()
    return {'task_created': new_task.data[0]['id'] if new_task.data else None}

elif task_type == 'check_task':
    task_record = supabase.table('agent_tasks')\
        .select('*')\
        .eq('id', params['task_id'])\
        .single()\
        .execute()
    return task_record.data
```

---

## Phase 5: Deployment Steps

### Step 1: Apply `min_frequency` fix (immediate)

SSH into server and edit the processor in-place, or update the file in the repo:

```bash
ssh root@46.224.50.251
# Quick fix in running container
docker exec -it openclaw-bitcoin-agent sed -i \
  's/min_frequency: int = 2/min_frequency: int = 1/g' \
  /home/openclaw/agentpulse_processor.py
# Restart the processor process
docker exec openclaw-bitcoin-agent pkill -f agentpulse_processor
# It auto-restarts via entrypoint, or manually:
docker exec -d openclaw-bitcoin-agent python3 /home/openclaw/agentpulse_processor.py --task watch
```

### Step 2: Create `agent_tasks` table

Run the SQL from Phase 1B in Supabase SQL Editor.

### Step 3: Restructure files locally

```bash
cd bitcoin_bot/docker

# Create service directories
mkdir -p gato analyst processor

# Move/copy Dockerfiles
cp Dockerfile gato/Dockerfile           # then edit to remove processor stuff
cp entrypoint.sh gato/entrypoint.sh     # then edit to remove processor startup

# Create analyst files
# (IDENTITY.md, SOUL.md, entrypoint.sh, Dockerfile — from Phase 3)

# Move processor files
mv agentpulse_processor.py processor/
cp requirements-agentpulse.txt processor/requirements.txt

# Rewrite docker-compose.yml (from Phase 2B)
```

### Step 4: Create Analyst identity

```bash
mkdir -p data/openclaw/agents/analyst/agent
cp data/openclaw/agents/main/agent/auth-profiles.json \
   data/openclaw/agents/analyst/agent/
# Create IDENTITY.md and SOUL.md (from Phase 3A)
```

### Step 5: Create Analyst skill

```bash
mkdir -p skills/analyst
# Create SKILL.md and package.json (from Phase 3B)
```

### Step 6: Update processor code

Add `process_db_tasks()`, `create_agent_task`, `check_task` handlers (from Phase 4).

### Step 7: Build and deploy

```bash
cd bitcoin_bot/docker

# Stop existing single container
docker compose down

# Build all services
docker compose build --no-cache

# Start all services
docker compose up -d

# Verify all 3 are running
docker compose ps
```

### Step 8: Verify

```bash
# Check each service
docker compose logs gato | tail -20
docker compose logs analyst | tail -20
docker compose logs processor | tail -20

# Verify processor picks up tasks
docker compose exec processor python3 -c "
from supabase import create_client
import os
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
result = client.table('agent_tasks').insert({
    'task_type': 'extract_problems',
    'assigned_to': 'analyst',
    'created_by': 'system',
    'input_data': {'hours_back': 48}
}).execute()
print('Task created:', result.data[0]['id'])
"

# Watch processor pick it up
docker compose logs -f processor

# Test Telegram still works
# Send /pulse-status to @gato_beedi_ragabot
```

---

## Migration Path (Minimal Downtime)

Since you have a running system, here's the safe order:

1. **Fix `min_frequency` in-place** on current container (5 min, zero downtime)
2. **Create `agent_tasks` table** in Supabase (no impact on running system)
3. **Develop new docker-compose locally** — test with `docker compose up` on your machine
4. **Push to GitHub** once tested
5. **On server:** `git pull`, `docker compose down`, `docker compose up -d`
6. **Verify** Telegram bot reconnects, processor runs, analyst polls

Total downtime: ~30 seconds during the swap.

---

## What You Get

| Before | After |
|--------|-------|
| 1 container, everything coupled | 3 services, independently managed |
| Processor as background `nohup` | Processor as proper Docker service with restart policy |
| No agent coordination | `agent_tasks` table with status tracking |
| Adding agents = more complexity in one container | Adding agents = one more service block |
| One log stream for everything | Per-service logs |
| If processor crashes, manual restart | Docker auto-restart |

## Future Agents

Adding a Newsletter Writer or Investment Scanner agent follows the same pattern:

```yaml
# Just add to docker-compose.yml
newsletter:
  build: ./newsletter
  container_name: openclaw-newsletter
  environment:
    <<: *common-env
    AGENT_NAME: newsletter
  volumes:
    - workspace-data:/home/openclaw/.openclaw/workspace
    # ...
```

Create its identity files, skill files, and it picks up tasks from `agent_tasks` where `assigned_to = 'newsletter'`.

---

*Next steps after deployment: implement problem clustering algorithm, then Pipeline 2 (Investment Scanner).*
