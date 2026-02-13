# Analyst Intelligence Upgrade: Cursor Prompts

> **How to use:** Run in order. Upload `AGENTPULSE_ANALYST_INTELLIGENCE.md` as context for every prompt. Test between each.

---

## Prompt 1: Supabase Schema (Manual — SQL Editor)

Run in Supabase SQL Editor:

```sql
-- ================================================
-- ANALYST INTELLIGENCE UPGRADE — SCHEMA
-- ================================================

-- 1. Analysis runs — the Analyst's full reasoning chain
CREATE TABLE analysis_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_type TEXT NOT NULL,
    trigger TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    input_snapshot JSONB,
    reasoning_steps JSONB,
    key_findings JSONB,
    opportunities_created UUID[],
    analyst_notes TEXT,
    confidence_level TEXT,
    caveats TEXT[],
    flags TEXT[],
    previous_run_id UUID REFERENCES analysis_runs(id),
    delta_summary TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_analysis_runs_type ON analysis_runs(run_type);
CREATE INDEX idx_analysis_runs_status ON analysis_runs(status);
CREATE INDEX idx_analysis_runs_started ON analysis_runs(started_at DESC);

-- 2. Add reasoning columns to opportunities
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS analyst_reasoning TEXT;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS analyst_confidence_notes TEXT;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS signal_sources JSONB;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS last_reviewed_at TIMESTAMPTZ;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS review_count INT DEFAULT 0;

-- 3. Cross-pipeline signals
CREATE TABLE cross_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    signal_type TEXT NOT NULL,
    description TEXT NOT NULL,
    problem_cluster_id UUID REFERENCES problem_clusters(id),
    tool_name TEXT,
    opportunity_id UUID REFERENCES opportunities(id),
    strength FLOAT,
    reasoning TEXT,
    status TEXT DEFAULT 'active',
    first_detected TIMESTAMPTZ DEFAULT NOW(),
    last_confirmed TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_cross_signals_type ON cross_signals(signal_type);
CREATE INDEX idx_cross_signals_strength ON cross_signals(strength DESC);
```

**Verify:** Check Supabase Table Editor — you should see `analysis_runs` and `cross_signals` as new tables, and `opportunities` should have the new columns (`analyst_reasoning`, `signal_sources`, etc).

---

## Prompt 2: Upgrade the Analyst Container

```
Upgrade the Analyst agent container for intelligent analysis. The Analyst is changing from a label (where the Processor did the work) to a real OpenClaw agent with its own reasoning capabilities.

Reference: AGENTPULSE_ANALYST_INTELLIGENCE.md for the full architecture.

1. Update docker/analyst/Dockerfile:
   - Base image: node:22-slim (MUST be 22+, OpenClaw requires Node >= 22.12.0)
   - Install git, curl, bash, jq, python3, python3-pip
   - Create openclaw user
   - Install OpenClaw via npm
   - Install Python requirements (httpx, supabase, python-dotenv)
   - Copy analyst_poller.py AND entrypoint.sh
   - ENTRYPOINT: entrypoint.sh

2. Create docker/analyst/analyst_poller.py:
   This bridges the agent_tasks Supabase table to the file queue for the OpenClaw agent. It:
   
   POLLING:
   - Every 15 seconds, queries agent_tasks where assigned_to='analyst' AND status='pending'
   - Orders by priority ASC, created_at ASC, limit 3
   - For each task: marks as in_progress (set started_at), writes a JSON file to workspace/agentpulse/queue/ named analyst_{task_id}.json containing {task, task_id, params, created_by}
   
   RESPONSE HANDLING:
   - Watches workspace/agentpulse/queue/responses/ for analyst_*.result.json files
   - When found, reads the result and does ALL of these:
     a. If successful and result contains analysis data:
        - Insert into analysis_runs table: run_type, trigger='task', status='completed', reasoning_steps, key_findings, analyst_notes (from executive_summary), confidence_level, caveats, flags, completed_at
        - For each opportunity in result that has an 'id': update the opportunities table with confidence_score, analyst_reasoning, analyst_confidence_notes (JSON of downgrade_factors), signal_sources, last_reviewed_at, increment review_count
        - For each cross_signal in result: insert into cross_signals table with signal_type, description, strength, reasoning, problem_cluster_id, tool_name, opportunity_id
     b. Update agent_tasks row: status completed/failed, completed_at, output_data, error_message
     c. Delete the response file
   
   - Run in infinite loop with try/except so transient errors don't crash it
   - Log to stdout with timestamps

3. Update docker/analyst/entrypoint.sh:
   - Create workspace dirs: agentpulse/{queue/responses,analysis,opportunities,cache}
   - Create logs dir
   - Start analyst_poller.py in background (nohup, log to analyst-poller.log)
   - Start OpenClaw: exec openclaw start --agent analyst --headless

4. Create docker/analyst/requirements.txt:
   httpx>=0.25.0
   supabase>=2.0.0
   python-dotenv>=1.0.0

Don't modify any other services. Don't touch the Processor, Gato, or Newsletter containers.
```

**After this:**
```bash
docker compose build analyst --no-cache
docker compose up analyst -d
docker compose logs analyst | tail -30
# Should show: poller started, OpenClaw headless starting
```

---

## Prompt 3: Upgrade the Analyst Identity and Skills

```
Replace the Analyst agent's identity and skill files with the intelligence-upgraded versions.

Reference: AGENTPULSE_ANALYST_INTELLIGENCE.md — copy the FULL content from the "Analyst Identity Upgrade" and "Analyst Skill Upgrade" sections.

1. REPLACE data/openclaw/agents/analyst/agent/IDENTITY.md with the FULL content from the "Analyst Identity Upgrade" section of AGENTPULSE_ANALYST_INTELLIGENCE.md. This is a long, detailed file — do NOT shorten or summarize it. The detail is critical. It includes:
   - Core principles (evidence over intuition, reasoning is the product, connect the dots, challenge yourself, serve the operator)
   - The 6-step reasoning process (situational assessment, problem deep-dive, cross-pipeline synthesis, opportunity scoring with reasoning, self-critique, intelligence brief)
   - Working with other agents
   - Output format expectations
   - Important rules

2. REPLACE data/openclaw/agents/analyst/agent/SOUL.md with the new version from the doc. Key line: "The best intelligence analysts aren't the ones who are always right. They're the ones who know exactly how confident to be, and why."

3. REPLACE skills/analyst/SKILL.md with the full upgraded version from AGENTPULSE_ANALYST_INTELLIGENCE.md. This includes:
   - full_analysis task type with detailed input/output JSON schema
   - deep_dive task type
   - review_opportunity task type
   - compare_runs task type
   - Data access documentation (which Supabase tables it can query)
   - How to request more data from the Processor

4. Verify auth-profiles.json exists:
   data/openclaw/agents/analyst/agent/auth-profiles.json should match the main agent's. If missing, copy from data/openclaw/agents/main/agent/auth-profiles.json.

Don't modify any other files.
```

**After this:**
```bash
# Restart analyst to pick up new identity
docker compose restart analyst
docker compose logs analyst | tail -30
```

---

## Prompt 4: Update Processor for Data Package Assembly

```
Update the Processor to assemble data packages for the Analyst instead of running analysis directly.

Reference: AGENTPULSE_ANALYST_INTELLIGENCE.md, "Updated Processor" section.

Changes to docker/processor/agentpulse_processor.py:

1. ADD a new function prepare_analysis_package(hours_back=48) that:
   - Logs pipeline start
   - Queries Supabase for ALL data the Analyst needs:
     * problems: last N hours, ordered by frequency_count DESC, limit 200
     * clusters: all, ordered by opportunity_score DESC, limit 50
     * tool_mentions: last N hours, ordered by mentioned_at DESC, limit 200
     * tool_stats: all, ordered by total_mentions DESC, limit 50
     * existing_opportunities: where status='draft', ordered by confidence_score DESC, limit 20
     * previous_run: latest completed analysis_runs row (for delta comparison)
     * stats: post count in window, problem count, tools tracked, existing opportunities count
   - Assembles a data_package dict with all the above + timeframe_hours + gathered_at timestamp
   - Creates an agent_task:
     task_type='full_analysis', assigned_to='analyst', created_by='processor', priority=2, input_data=data_package
   - IMPORTANT: serialize with json.dumps(data_package, default=str) before inserting (datetimes)
   - Logs pipeline end
   - Returns {task_id, data_summary: {counts of each data type}, delegated_to: 'analyst'}

2. UPDATE the run_pipeline task in execute_task():
   Change from running analysis directly to:
   - scrape_result = scrape_moltbook()
   - extract_result = extract_problems()
   - tool_result = extract_tool_mentions()
   - cluster_result = cluster_problems()
   - analysis_result = prepare_analysis_package()  ← delegates to Analyst
   Return all results.
   
   KEEP the old generate_opportunities() function as a fallback — don't delete it.
   Just don't call it from run_pipeline anymore. It stays available as a standalone task
   in case the Analyst is down.

3. ADD 'prepare_analysis' as a task type in execute_task():
   elif task_type == 'prepare_analysis':
       return prepare_analysis_package(hours_back=params.get('hours_back', 48))

4. ADD 'prepare_analysis' to the argparse --task choices.

5. UPDATE the scheduled analysis in setup_scheduler():
   The scheduled_analyze() function should now call prepare_analysis_package()
   instead of (or in addition to) the old extract + generate flow.
   Keep the old extract_problems() and cluster_problems() as part of the scheduled flow
   since the Analyst needs that data to already exist.
   New flow: extract_problems() → cluster_problems() → extract_tool_mentions() → prepare_analysis_package()

Don't delete any existing functions — the old generate_opportunities() stays as a fallback.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d

# Test the new flow
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_analysis

# Check Supabase:
# - agent_tasks should have a row: task_type='full_analysis', assigned_to='analyst'
# - Wait 15-30 seconds for the analyst poller to pick it up
docker compose logs analyst | tail -30

# Check if analysis_runs gets populated
# (may take a minute or two for the Analyst to complete reasoning)
```

---

## Prompt 5: Wire New Commands to Gato

```
Update Gato's instruction files for the Analyst intelligence upgrade. The Analyst now returns richer output with reasoning chains.

1. Update data/openclaw/workspace/AGENTS.md — add new commands:

   - /analysis → write {"task":"get_latest_analysis","params":{}} to the queue. Display the executive summary, key findings, and confidence level. If the analysis has caveats, show them.

   - /signals → write {"task":"get_cross_signals","params":{"limit":10}} to the queue. Display cross-pipeline signals with their strength and reasoning.

   - /deep-dive [topic] → Delegate to Analyst: write {"task":"create_agent_task","params":{"task_type":"deep_dive","assigned_to":"analyst","created_by":"gato","input_data":{"topic":"<user's topic>"}}} to the queue. Tell user "Analyst is diving deep into [topic]..."

   - /review [opportunity name] → Delegate to Analyst: write {"task":"create_agent_task","params":{"task_type":"review_opportunity","assigned_to":"analyst","created_by":"gato","input_data":{"opportunity_title":"<name>"}}} to the queue. Tell user "Analyst is reviewing [name]..."

   Also update the /scan description: when results come back, present the Analyst's executive summary and key findings (not just raw opportunity list). Include the confidence level and any caveats.

2. Update skills/agentpulse/SKILL.md — add to the commands table:
   | /analysis | Show latest Analyst intelligence brief |
   | /signals | Show cross-pipeline signals |
   | /deep-dive [topic] | Analyst deep-dive on a specific topic |
   | /review [opp] | Analyst re-evaluation of an opportunity |

   Add an "Analyst Intelligence" section explaining:
   - The Analyst now runs multi-step reasoning instead of fixed pipelines
   - Results include reasoning chains explaining confidence scores
   - Cross-pipeline signals connect tool sentiment with problem clusters
   - Self-critique includes caveats and uncertainty flags

3. Add these task handlers to the Processor (in execute_task()):

   'get_latest_analysis':
   - Query analysis_runs where status='completed', ordered by completed_at DESC, limit 1
   - Return the full row (includes executive_summary, key_findings, confidence_level, caveats)

   'get_cross_signals':
   - Query cross_signals where status='active', ordered by strength DESC, limit from params (default 10)
   - Return the rows

Don't modify any other files.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose restart gato

# Test on Telegram:
# /scan — should delegate to Analyst, come back with richer output
# /analysis — should show latest reasoning
# /signals — should show cross-pipeline signals
# /deep-dive security — should delegate focused analysis
```

---

## End-to-End Test

After all prompts are deployed, run the full chain:

```bash
# 1. All 4 services running
docker compose ps

# 2. Trigger a full pipeline (this now delegates analysis to the Analyst)
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline

# 3. Watch the analyst pick up the task
docker compose logs -f analyst

# 4. After completion, check Supabase:
docker compose exec processor python3 -c "
from supabase import create_client
import os, json
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

# Check analysis run
run = c.table('analysis_runs').select('*').order('completed_at', desc=True).limit(1).execute()
if run.data:
    r = run.data[0]
    print(f'Analysis run: {r[\"run_type\"]} | confidence: {r[\"confidence_level\"]}')
    print(f'Notes: {r[\"analyst_notes\"][:200]}...')
    print(f'Caveats: {r.get(\"caveats\", [])}')
else:
    print('No analysis runs yet')

# Check cross-signals
signals = c.table('cross_signals').select('*').order('strength', desc=True).limit(5).execute()
print(f'\nCross-signals: {len(signals.data or [])}')
for s in (signals.data or []):
    print(f'  {s[\"signal_type\"]}: {s[\"description\"][:80]}... (strength: {s[\"strength\"]})')

# Check if opportunities have reasoning
opps = c.table('opportunities').select('title,confidence_score,analyst_reasoning').order('confidence_score', desc=True).limit(3).execute()
print(f'\nTop opportunities:')
for o in (opps.data or []):
    has_reasoning = 'YES' if o.get('analyst_reasoning') else 'no'
    print(f'  {o[\"title\"]} ({o[\"confidence_score\"]}) — reasoning: {has_reasoning}')
"

# 5. Test via Telegram
# /scan
# /analysis
# /signals
```

---

## Troubleshooting

**Analyst poller not running:**
→ `docker compose exec analyst ps aux | grep poller`
→ Check logs: `docker compose exec analyst cat /home/openclaw/.openclaw/logs/analyst-poller.log`

**Analysis tasks stay in_progress forever:**
→ The OpenClaw agent might not be processing the file queue. Check: `docker compose exec analyst ls /home/openclaw/.openclaw/workspace/agentpulse/queue/`
→ If analyst_*.json files are accumulating, OpenClaw isn't picking them up. Check OpenClaw logs.

**analysis_runs table stays empty:**
→ The poller writes to it when it processes responses. Check if response files exist: `docker compose exec analyst ls /home/openclaw/.openclaw/workspace/agentpulse/queue/responses/`

**Cross-signals table empty:**
→ The Analyst only detects cross-signals when both Pipeline 1 and Pipeline 2 have data. Make sure you've run both an analysis AND a tool scan before expecting cross-signals.

**Reasoning is shallow/generic:**
→ This is an IDENTITY.md quality issue. The 6-step reasoning process is designed to force depth. If the Analyst is skipping steps, add more explicit instructions in the identity file.
→ Try `/deep-dive [specific topic]` which focuses the reasoning on one area.
