# Agency Upgrade: Cursor Prompts

> **Upload `AGENTPULSE_AGENCY_UPGRADE.md` as context for every prompt.**
> **This is the most complex upgrade yet. Test carefully between prompts.**

---

## Prompt 1: Database Schema

Run in Supabase SQL Editor:

```sql
-- ================================================
-- AGENCY UPGRADE SCHEMA
-- ================================================

-- Budget tracking
CREATE TABLE agent_daily_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name TEXT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    llm_calls_used INT DEFAULT 0,
    subtasks_created INT DEFAULT 0,
    proactive_alerts_sent INT DEFAULT 0,
    total_cost_estimate FLOAT DEFAULT 0,
    UNIQUE(agent_name, date)
);
CREATE INDEX idx_daily_usage_agent_date ON agent_daily_usage(agent_name, date);

-- Agent negotiations
CREATE TABLE agent_negotiations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requesting_agent TEXT NOT NULL,
    responding_agent TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    round INT DEFAULT 1,
    request_task_id UUID REFERENCES agent_tasks(id),
    request_summary TEXT,
    quality_criteria TEXT,
    needed_by TIMESTAMPTZ,
    response_task_id UUID REFERENCES agent_tasks(id),
    criteria_met BOOLEAN,
    response_summary TEXT,
    follow_up_task_id UUID REFERENCES agent_tasks(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    metadata JSONB
);
CREATE INDEX idx_negotiations_status ON agent_negotiations(status);
CREATE INDEX idx_negotiations_agents ON agent_negotiations(requesting_agent, responding_agent);

-- RLS
ALTER TABLE agent_daily_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_negotiations ENABLE ROW LEVEL SECURITY;
```

---

## Prompt 2: Budget System

```
Add a budget enforcement system to docker/processor/agentpulse_processor.py. This system limits how many LLM calls, how much time, and how many subtasks an agent can use per task.

Reference: AGENTPULSE_AGENCY_UPGRADE.md, "The Guardrail System" section.

1. Add an AgentBudget class that tracks per-task budget:
   - __init__(task_type, agent_name): reads budget config from agentpulse-config.json
   - Attributes: max_llm_calls, max_seconds, max_subtasks, max_retries, plus counters for each
   - Methods:
     * can_call_llm() → bool (checks both call count AND elapsed time)
     * can_create_subtask() → bool
     * can_retry() → bool
     * use_llm_call() / use_subtask() / use_retry() — increment counters
     * elapsed_seconds() → float
     * remaining() → dict with remaining counts for each dimension
     * exhausted_reason() → str or None (returns 'time_limit', 'llm_call_limit', etc.)
     * to_dict() → serializable summary of usage for including in task output

2. Add helper functions:
   - get_budget_config(agent_name, task_type) → dict: reads from agentpulse-config.json budgets section, with defaults if not found
   - check_daily_budget(agent_name) → bool: queries agent_daily_usage table for today, checks against global.max_daily_llm_calls
   - increment_daily_usage(agent_name, llm_calls=0, subtasks=0, alerts=0): upserts into agent_daily_usage table for today's date
   - get_daily_usage(agent_name=None) → dict: returns today's usage, optionally filtered by agent

3. Update agentpulse-config.json to include the full budgets section from the architecture doc. Keep existing model routing config. Add budgets for analyst (full_analysis, deep_dive, review_opportunity, proactive_scan) and newsletter (write_newsletter, revise_newsletter) plus global limits.

4. Add these task types to execute_task():
   - 'get_budget_status' → get_daily_usage() for all agents
   - 'get_budget_config' → return the budgets section of config

5. Add 'get_budget_status' to argparse choices.

Don't modify any existing functions yet — just add the budget infrastructure. We'll integrate it into the analysis flow in the next prompt.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
# Test budget infrastructure
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task get_budget_status
# Should return daily usage (zeroes initially)
```

---

## Prompt 3: Level 1 — Analyst Self-Correcting Loops

```
Upgrade the Analyst's task processing to support multi-step reasoning with self-correction.

Reference: AGENTPULSE_AGENCY_UPGRADE.md, "Level 1: Self-Correcting Loops" section.

This changes the analyst_poller.py to include budget information in tasks and track budget usage in responses.

1. Update docker/analyst/analyst_poller.py:

   a. Import the budget config reader. Add a function get_budget_config(agent_name, task_type) that reads agentpulse-config.json from /home/openclaw/.openclaw/config/ and returns the budget for that agent+task. Include sensible defaults if file doesn't exist.

   b. When writing task files to the queue (in the poll() function):
      - Read the budget config for this task type
      - Include it in the task params:
        {
          'task': task_type,
          'task_id': task_id,
          'params': {
            **input_data,
            'budget': {
              'max_llm_calls': N,
              'max_seconds': N,
              'max_subtasks': N,
              'max_retries': N
            }
          }
        }

   c. When processing responses (in check_responses()):
      - Read budget_usage from the result if present
      - Log it: "Budget usage for task X: {llm_calls: N, time: Ns, retries: N}"
      - Update daily usage in agent_daily_usage table:
        * Upsert for agent_name='analyst', date=today
        * Increment llm_calls_used by the amount in budget_usage
        * Increment subtasks_created by the amount in budget_usage
      - Use upsert with on_conflict='agent_name,date'

   d. Add a safety timeout: when a task has been in_progress for longer than max_seconds * 2 (double the budget to allow for network delays), force-complete it:
      - Check in_progress tasks where started_at is older than the timeout
      - Update status to 'failed', error_message = 'budget_timeout'
      - Log warning

2. The actual multi-step reasoning happens inside the OpenClaw agent session — that's controlled by the IDENTITY.md file, not the poller code. The poller's job is:
   - Deliver the budget constraints to the agent
   - Enforce the timeout as a hard backstop
   - Track usage for the daily budget

Don't modify any other files in this prompt. The Analyst identity update comes in Prompt 7.
```

**After this:**
```bash
docker compose build analyst --no-cache
docker compose up analyst -d
# Test by creating a task
docker compose exec processor python3 -c "
from supabase import create_client
import os, json
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
c.table('agent_tasks').insert({
    'task_type': 'full_analysis',
    'assigned_to': 'analyst',
    'created_by': 'system',
    'priority': 3,
    'input_data': {'test': True}
}).execute()
print('Test task created')
"
# Watch analyst logs
docker compose logs -f analyst
```

---

## Prompt 4: Level 2 — Autonomous Data Requests

```
Add the ability for agents to request additional data from the Processor mid-analysis.

Reference: AGENTPULSE_AGENCY_UPGRADE.md, "Level 2: Autonomous Data Requests" section.

1. Add a targeted_scrape task to docker/processor/agentpulse_processor.py:
   
   elif task_type == 'targeted_scrape':
       submolts = params.get('submolts', [])[:3]  # Max 3 submolts
       posts_per = min(params.get('posts_per_submolt', 50), 50)  # Max 50 per submolt
       reason = params.get('reason', 'agent_request')
       
       results = {}
       for submolt in submolts:
           result = scrape_moltbook(submolt_filter=submolt, limit=posts_per)
           results[submolt] = result
       
       extract_result = extract_problems(hours_back=1)
       
       return {
           'scrape': results,
           'extract': extract_result,
           'triggered_by': reason
       }

   Note: scrape_moltbook() may need a submolt_filter parameter. If it doesn't already support filtering by submolt, add a simple filter: when submolt_filter is provided, add it to the API query. If the Moltbook API doesn't support submolt filtering, just run a normal scrape and log that filtering wasn't possible.

2. Add a can_create_subtask_check task to the processor:
   
   elif task_type == 'can_create_subtask':
       # Check if the processor is overloaded
       pending = supabase.table('agent_tasks')\
           .select('id', count='exact')\
           .eq('status', 'pending')\
           .execute()
       return {
           'can_create': pending.count < 10,
           'pending_tasks': pending.count,
           'reason': 'processor_overloaded' if pending.count >= 10 else 'ok'
       }

3. Add 'targeted_scrape' and 'can_create_subtask' to argparse choices.

4. Update the analyst_poller.py to handle subtask responses:
   When the Analyst's response includes a 'data_requests' array, the poller creates the corresponding agent_tasks:
   
   for request in result.get('data_requests', []):
       if request.get('type') == 'targeted_scrape':
           supabase.table('agent_tasks').insert({
               'task_type': 'targeted_scrape',
               'assigned_to': 'processor',
               'created_by': 'analyst',
               'priority': 1,
               'input_data': {
                   'submolts': request.get('submolts', []),
                   'posts_per_submolt': request.get('posts_per', 50),
                   'reason': request.get('reason', 'analyst_data_request')
               }
           }).execute()
           logger.info(f"Created targeted_scrape subtask for analyst")

Don't modify existing functions except to add the new task types.
```

**After this:**
```bash
docker compose build processor analyst --no-cache
docker compose up processor analyst -d
# Test targeted scrape
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task targeted_scrape
```

---

## Prompt 5: Level 3 — Proactive Monitoring

```
Add proactive anomaly detection to docker/processor/agentpulse_processor.py. The system periodically scans for unusual patterns and alerts the operator via Telegram when something significant is detected.

Reference: AGENTPULSE_AGENCY_UPGRADE.md, "Level 3: Proactive Monitoring" section.

1. Add detect_anomalies() function:
   No LLM calls — pure Python/SQL comparisons. Checks:
   
   a. Problem frequency spike: compare last 1 hour's problem count per category against baseline (average hourly rate over past 6 days). Flag if current > 3x baseline.
   
   b. Tool sentiment crash: compare average sentiment of tool mentions in last 24h against historical avg in tool_stats. Flag if drop > 0.5 points.
   
   c. Volume anomaly: compare last 1 hour's post count against baseline hourly rate. Flag if ratio > 2.5x or < 0.3x.
   
   Returns a list of anomaly dicts, each with: type, description, and relevant metrics.
   
   Use collections.Counter for category counting. Handle empty data gracefully (no anomalies if no baseline data exists yet).

2. Add check_proactive_budget() function:
   - Queries agent_daily_usage for agent_name='system', today's date
   - Returns True if proactive_alerts_sent < global.max_daily_proactive_alerts (from config, default 5)

3. Add check_proactive_cooldown() function:
   - Queries pipeline_runs for the most recent 'proactive_scan' run
   - Returns True if enough time has passed (cooldown_between_proactive_scans_minutes from config, default 60)

4. Add proactive_scan() function:
   - Checks daily budget (skip if exhausted)
   - Checks cooldown (skip if too recent)
   - Calls detect_anomalies()
   - If no anomalies: log and return
   - If anomalies found: create an agent_task for the Analyst:
     task_type='proactive_analysis', assigned_to='analyst', priority=2
     input_data includes the anomalies list and a proactive_scan budget
   - Log pipeline run
   - Return {anomalies: N, analysis_requested: bool}

5. Add to setup_scheduler():
   schedule.every(60).minutes.do(proactive_scan)

6. Update the analyst_poller.py response handler:
   If the Analyst's response to a proactive_analysis task includes "alert": true:
   - Create a notification task for the processor (which sends to Telegram):
     task_type='send_alert', assigned_to='processor', input_data includes alert_message
   - Increment proactive_alerts_sent in daily usage

7. Add send_alert task to the processor:
   elif task_type == 'send_alert':
       message = params.get('alert_message', 'Unknown alert')
       send_telegram(f"⚠️ Proactive Alert\n\n{message}")
       increment_daily_usage('system', alerts=1)
       return {'sent': True}

8. Add 'proactive_scan', 'send_alert' to execute_task() and argparse choices.

Don't modify existing functions.
```

**After this:**
```bash
docker compose build processor analyst --no-cache
docker compose up processor analyst -d
# Test anomaly detection (may find nothing if data is stable)
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task proactive_scan
# Check processor logs
docker compose logs processor | tail -20
```

---

## Prompt 6: Level 4 — Agent-to-Agent Negotiation

```
Add negotiation capability so agents can request enrichment from each other.

Reference: AGENTPULSE_AGENCY_UPGRADE.md, "Level 4: Agent-to-Agent Negotiation" section.

1. Add to docker/processor/agentpulse_processor.py:

   a. A create_negotiation(requesting_agent, responding_agent, request_task_id, request_summary, quality_criteria, needed_by=None) function:
      - Checks negotiation config: is this pair allowed? (from config negotiation.allowed_pairs)
      - Checks: does requesting_agent have < max_active_negotiations_per_agent active negotiations?
      - If checks pass: insert into agent_negotiations table
      - Return the negotiation ID
      - If checks fail: return error with reason

   b. A check_negotiation_timeouts() function:
      - Queries open negotiations where created_at + negotiation_timeout_minutes has passed
      - For each: update status to 'timed_out', set closed_at
      - Log timeouts
   
   c. A respond_to_negotiation(negotiation_id, response_task_id, criteria_met, response_summary) function:
      - Updates the negotiation with response data
      - If criteria_met: set status to 'closed', closed_at = now
      - If not criteria_met and round < max_rounds: set status to 'follow_up', increment round
      - If not criteria_met and round >= max_rounds: set status to 'closed' (max rounds reached)

   d. Task types in execute_task():
      - 'create_negotiation' → create_negotiation() with params
      - 'respond_to_negotiation' → respond_to_negotiation() with params
      - 'get_active_negotiations' → query agent_negotiations where status IN ('open', 'follow_up')
      - 'check_negotiation_timeouts' → check_negotiation_timeouts()

2. Add check_negotiation_timeouts to the scheduler:
   schedule.every(10).minutes.do(check_negotiation_timeouts_scheduled)
   
   def check_negotiation_timeouts_scheduled():
       check_negotiation_timeouts()

3. Update the newsletter_poller.py:
   When the Newsletter agent's response includes a 'negotiation_request':
   - Create the negotiation via agent_tasks
   - Create the enrichment task for the target agent
   - Log the negotiation

4. Update the analyst_poller.py:
   When the Analyst receives a task that's part of a negotiation (input_data contains 'negotiation_id'):
   - After completing, include negotiation_id in the response
   - The poller updates the negotiation via respond_to_negotiation

5. Add 'create_negotiation', 'respond_to_negotiation', 'get_active_negotiations' to argparse choices.

Don't modify existing functions.
```

**After this:**
```bash
docker compose build processor analyst newsletter --no-cache
docker compose up -d
# Test negotiation creation
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
c.table('agent_negotiations').insert({
    'requesting_agent': 'newsletter',
    'responding_agent': 'analyst',
    'request_summary': 'Need stronger opportunities for Section A',
    'quality_criteria': 'At least 3 opportunities above 0.6 confidence'
}).execute()
print('Test negotiation created')
"
```

---

## Prompt 7: Update Analyst Identity for Agency

```
Update the Analyst's identity and skill files for the full agency upgrade: budget awareness, self-correction, autonomous data requests, proactive analysis, and negotiation responses.

Reference: AGENTPULSE_AGENCY_UPGRADE.md for all the details.

1. Edit data/openclaw/agents/analyst/agent/IDENTITY.md — ADD these sections (keep everything already there):

   ## Budget Awareness
   
   Every task comes with a budget in the params. You MUST track your usage:
   - Before each reasoning step, check: "Do I have budget for this?"
   - If budget is exhausted mid-analysis: stop, compile what you have, flag as "budget_limited"
   - Include budget usage in your output: {llm_calls_used, time_elapsed, retries_used}
   - Never ignore budget limits. They exist to prevent runaway costs.

   ## Self-Correction Protocol
   
   After your self-critique step, rate your output quality 1-10:
   - 8-10: Strong output. Proceed to final.
   - 5-7: Acceptable but weak. If budget.can_retry: re-run Steps 2-3 with adjusted focus. If no budget: proceed with caveats.
   - 1-4: Poor output. If budget allows: retry with completely different approach. If no budget: flag "low_confidence" and explain what went wrong.
   
   When retrying, CHANGE something. Don't repeat the same approach:
   - Focus on different clusters
   - Use different cross-signal criteria
   - Narrow scope to do fewer things better
   - Each retry includes: "Retry reason: [what was wrong], Adjustment: [what I changed]"

   ## Autonomous Data Requests
   
   If you're analyzing and the data is thin for a specific area, you can request more:
   - Include a "data_requests" array in your output
   - Each request: {"type": "targeted_scrape", "submolts": [...], "posts_per": 50, "reason": "..."}
   - Max 3 subtasks per task (check your budget)
   - The data won't arrive during this task — it'll be available next run
   - Flag the thin area: "Data requested for [area] — will be richer next analysis"

   ## Proactive Analysis
   
   Sometimes you receive anomaly data instead of a full package. The system detected something unusual.
   - Assess: Is this anomaly real and significant, or noise?
   - If significant: set "alert": true in your output with a specific 2-3 sentence alert_message
   - If noise: set "alert": false, explain why it's noise
   - Budget is small for proactive tasks (4 LLM calls max). Be efficient.
   - False alarms erode trust. Be sure before alerting.

   ## Negotiation Responses
   
   When a task includes negotiation_id, another agent is requesting your help.
   - Read what they need (request_summary, quality_criteria)
   - Do your best to meet the criteria within your budget
   - In your output, include: negotiation_id, criteria_met (bool), response_summary
   - If you can't meet the criteria, explain why honestly

2. Update skills/analyst/SKILL.md — ADD:
   - proactive_analysis task type: input is anomaly list + budget, output includes alert flag
   - enrich_for_newsletter task type: input is negotiation request + budget, output includes enriched data + criteria_met
   - Document the budget object that comes with every task
   - Document the data_requests output format

Don't modify SOUL.md or any other files.
```

**After this:**
```bash
docker compose restart analyst
docker compose logs analyst | tail -20
```

---

## Prompt 8: Update Newsletter Identity for Negotiation

```
Update the Newsletter agent's identity and skill files to support requesting enrichment from other agents.

1. Edit data/openclaw/agents/newsletter/agent/IDENTITY.md — ADD this section:

   ## Requesting Help from Other Agents
   
   If your data package is insufficient for a good newsletter:
   
   1. Assess what's specifically missing. "Section A is thin" isn't enough — 
      "Only 2 opportunities above 0.6, need at least 3 for a strong lead" is specific.
   2. Include a "negotiation_request" in your output:
      {
        "negotiation_request": {
          "target_agent": "analyst",
          "request_summary": "Need stronger opportunities for Section A...",
          "quality_criteria": "At least 3 opportunities above 0.6 confidence",
          "task_to_create": {
            "task_type": "enrich_for_newsletter",
            "input_data": { "focus": "opportunities", "min_confidence": 0.6 }
          }
        }
      }
   3. Continue writing with what you have — don't wait for the response.
   4. If the enrichment arrives before you finish, incorporate it.
   5. If it doesn't arrive, proceed and note: "This week's data was thinner than usual in [area]."
   
   Budget: max 2 negotiation requests per newsletter. Use wisely.
   Don't request enrichment for the Curious Corner — thin data is fine there.
   Focus on Section A where weak data means a weak lead.

   ## Budget Awareness
   
   Same as the Analyst: every task has a budget. Track your LLM calls.
   If you run out of budget mid-write, compile what you have. A slightly
   shorter newsletter is better than no newsletter.

2. Update skills/newsletter/SKILL.md — ADD:
   - Document the negotiation_request output format
   - Document budget tracking expectations
   - Add enrich_for_newsletter as a task the Newsletter agent can trigger

Don't modify SOUL.md or any other files.
```

**After this:**
```bash
docker compose restart newsletter
```

---

## Prompt 9: Wire New Telegram Commands

```
Add agency-related Telegram commands.

1. Add to docker/processor/agentpulse_processor.py execute_task():

   'get_budget_status':
   - Query agent_daily_usage for today's date, all agents
   - Also include global limits from config for comparison
   - Return structured stats

   'get_recent_alerts':
   - Query agent_tasks where task_type='send_alert' and created_at in last 7 days
   - Order by created_at DESC, limit 10
   - Return the alert messages and timestamps

   'get_active_negotiations':
   - Query agent_negotiations where status IN ('open', 'follow_up')
   - Return with agent names and summaries

2. Update data/openclaw/workspace/AGENTS.md:
   - /budget → write {"task":"get_budget_status","params":{}} to the queue.
     Display: per-agent usage today (LLM calls, subtasks) vs limits.
   - /alerts → write {"task":"get_recent_alerts","params":{}} to the queue.
     Display recent proactive alerts with timestamps.
   - /negotiations → write {"task":"get_active_negotiations","params":{}} to the queue.
     Display active negotiations between agents.

3. Update skills/agentpulse/SKILL.md — add to commands table:
   | /budget | Show today's agent budget usage |
   | /alerts | Show recent proactive alerts |
   | /negotiations | Show active agent negotiations |

Don't modify any other files.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose restart gato
# Test: /budget on Telegram
```

---

## Prompt 10: Budget + Negotiation Config

```
Ensure the full agency configuration is in config/agentpulse-config.json.

Update config/agentpulse-config.json to include BOTH the existing models section AND the full budgets and negotiation config.

The final file should look like this (merge with what's already there):

{
  "models": {
    "extraction": "gpt-4o-mini",
    "clustering": "gpt-4o-mini",
    "trending_topics": "gpt-4o-mini",
    "opportunity_generation": "gpt-4o",
    "digest": "gpt-4o-mini",
    "default": "gpt-4o"
  },
  "budgets": {
    "analyst": {
      "full_analysis": {"max_llm_calls": 8, "max_seconds": 300, "max_subtasks": 3, "max_retries": 2},
      "deep_dive": {"max_llm_calls": 5, "max_seconds": 180, "max_subtasks": 2, "max_retries": 1},
      "review_opportunity": {"max_llm_calls": 3, "max_seconds": 120, "max_subtasks": 1, "max_retries": 1},
      "proactive_scan": {"max_llm_calls": 4, "max_seconds": 120, "max_subtasks": 1, "max_retries": 1}
    },
    "newsletter": {
      "write_newsletter": {"max_llm_calls": 6, "max_seconds": 300, "max_subtasks": 2, "max_retries": 2},
      "revise_newsletter": {"max_llm_calls": 3, "max_seconds": 120, "max_subtasks": 1, "max_retries": 1}
    },
    "global": {
      "max_subtask_depth": 2,
      "max_daily_llm_calls": 100,
      "max_daily_proactive_alerts": 5,
      "cooldown_between_proactive_scans_minutes": 60
    }
  },
  "negotiation": {
    "max_rounds_per_negotiation": 2,
    "max_active_negotiations_per_agent": 3,
    "negotiation_timeout_minutes": 30,
    "allowed_pairs": {
      "newsletter_can_ask": ["analyst", "processor"],
      "analyst_can_ask": ["processor"],
      "gato_can_ask": ["analyst", "processor", "newsletter"],
      "processor_can_ask": []
    }
  },
  "pipeline": {
    "scrape_interval_hours": 6,
    "analysis_interval_hours": 12
  }
}

Keep any existing config entries that aren't shown here. Merge, don't replace.
```

**After this:**
```bash
# No rebuild needed — config is volume-mounted
docker compose restart processor analyst newsletter
# Verify config is readable
docker compose exec processor python3 -c "
import json
config = json.load(open('/home/openclaw/.openclaw/config/agentpulse-config.json'))
print('Models:', list(config.get('models', {}).keys()))
print('Budgets:', list(config.get('budgets', {}).keys()))
print('Negotiation:', config.get('negotiation', {}).get('allowed_pairs', {}))
"
```

---

## End-to-End Agency Test

```bash
# 1. All services running
docker compose ps

# 2. Test self-correction: trigger a full analysis
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_analysis
# Watch analyst — it should show multi-step reasoning with budget tracking
docker compose logs -f analyst

# 3. Check budget usage
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
usage = c.table('agent_daily_usage').select('*').execute()
for u in (usage.data or []):
    print(f\"{u['agent_name']}: {u['llm_calls_used']} LLM calls, {u['subtasks_created']} subtasks\")
"

# 4. Test proactive monitoring
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task proactive_scan

# 5. Test via Telegram
# /budget — should show usage
# /alerts — should show recent alerts (may be empty)
# /scan — full pipeline with agency

# 6. Generate newsletter and watch for negotiation
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
# If Section A data is thin, newsletter agent should request enrichment
docker compose logs newsletter | tail -50
# Check negotiations table
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
negs = c.table('agent_negotiations').select('*').order('created_at', desc=True).limit(5).execute()
for n in (negs.data or []):
    print(f\"{n['requesting_agent']} → {n['responding_agent']}: {n['status']} | {n['request_summary'][:60]}\")
"
```

---

## Troubleshooting

**Budget always shows 0 usage:**
→ The pollers increment daily usage when processing responses. If no tasks complete, usage stays at 0.
→ Check: `docker compose exec analyst cat /home/openclaw/.openclaw/logs/analyst-poller.log | tail -20`

**Analyst ignores budget:**
→ The budget is advisory in the IDENTITY.md — the LLM follows it based on instructions, not hard enforcement. The hard limit is the poller's timeout (max_seconds * 2).
→ If the Analyst consistently ignores budget, strengthen the language in IDENTITY.md.

**Proactive scan never fires:**
→ Check scheduler: `docker compose logs processor | grep "proactive"`
→ Check cooldown: default 60 minutes between scans
→ Check daily budget: max 5 alerts per day

**Negotiations time out:**
→ Default timeout is 30 minutes. If the responding agent takes longer, negotiations auto-close.
→ Check if the responding agent's poller is running.

**Runaway costs:**
→ Check daily usage: /budget on Telegram
→ Global limit is 100 LLM calls/day across all agents
→ Reduce budgets in agentpulse-config.json and restart services
→ In emergencies: `docker compose stop analyst newsletter` — processor keeps scraping but no LLM calls
