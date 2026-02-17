# AgentPulse: Agency Upgrade — From Pipelines to Autonomous Agents

**Date:** February 15, 2026  
**Prerequisite:** Phase 3 complete  
**Goal:** Transform the system from task-queue-with-workers into agents with real autonomy, self-correction, proactive behavior, and inter-agent collaboration — with hard guardrails to prevent runaway loops

---

## The Guardrail System

Before anything else: the safety net. Every autonomous behavior in this system is bounded by a **budget system** that limits actions across three dimensions.

### Budget Model

Every agent action costs "credits" from a budget. When the budget runs out, the agent must stop and report what it has so far.

```
BUDGET DIMENSIONS:

1. LLM Calls     — max number of LLM API calls per task
2. Time          — max wall-clock seconds per task
3. Task Depth    — max number of sub-tasks an agent can create

These are PER TASK, not global. A new /scan command gets a fresh budget.
```

### Default Budgets

```json
{
  "budgets": {
    "analyst": {
      "full_analysis": {
        "max_llm_calls": 8,
        "max_seconds": 300,
        "max_subtasks": 3,
        "max_retries": 2
      },
      "deep_dive": {
        "max_llm_calls": 5,
        "max_seconds": 180,
        "max_subtasks": 2,
        "max_retries": 1
      },
      "review_opportunity": {
        "max_llm_calls": 3,
        "max_seconds": 120,
        "max_subtasks": 1,
        "max_retries": 1
      },
      "proactive_scan": {
        "max_llm_calls": 4,
        "max_seconds": 120,
        "max_subtasks": 1,
        "max_retries": 1
      }
    },
    "newsletter": {
      "write_newsletter": {
        "max_llm_calls": 6,
        "max_seconds": 300,
        "max_subtasks": 2,
        "max_retries": 2
      },
      "revise_newsletter": {
        "max_llm_calls": 3,
        "max_seconds": 120,
        "max_subtasks": 1,
        "max_retries": 1
      }
    },
    "global": {
      "max_subtask_depth": 2,
      "max_daily_llm_calls": 100,
      "max_daily_proactive_alerts": 5,
      "cooldown_between_proactive_scans_minutes": 60
    }
  }
}
```

### Budget Enforcement

```python
class AgentBudget:
    """Tracks and enforces budget limits for an agent task."""
    
    def __init__(self, task_type: str, agent_name: str, config: dict):
        budget_config = config.get('budgets', {}).get(agent_name, {}).get(task_type, {})
        self.max_llm_calls = budget_config.get('max_llm_calls', 5)
        self.max_seconds = budget_config.get('max_seconds', 180)
        self.max_subtasks = budget_config.get('max_subtasks', 2)
        self.max_retries = budget_config.get('max_retries', 1)
        
        self.llm_calls_used = 0
        self.subtasks_created = 0
        self.retries_used = 0
        self.start_time = time.time()
    
    def can_call_llm(self) -> bool:
        return (self.llm_calls_used < self.max_llm_calls and 
                self.elapsed_seconds() < self.max_seconds)
    
    def can_create_subtask(self) -> bool:
        return self.subtasks_created < self.max_subtasks
    
    def can_retry(self) -> bool:
        return self.retries_used < self.max_retries
    
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time
    
    def use_llm_call(self):
        self.llm_calls_used += 1
    
    def use_subtask(self):
        self.subtasks_created += 1
    
    def use_retry(self):
        self.retries_used += 1
    
    def remaining(self) -> dict:
        return {
            'llm_calls': self.max_llm_calls - self.llm_calls_used,
            'seconds': max(0, self.max_seconds - self.elapsed_seconds()),
            'subtasks': self.max_subtasks - self.subtasks_created,
            'retries': self.max_retries - self.retries_used
        }
    
    def exhausted_reason(self) -> str:
        if self.elapsed_seconds() >= self.max_seconds:
            return 'time_limit'
        if self.llm_calls_used >= self.max_llm_calls:
            return 'llm_call_limit'
        return None
```

### Global Daily Limits

In addition to per-task budgets, there's a global daily limiter stored in Supabase:

```sql
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
```

Before any LLM call, the agent checks:
```python
def check_daily_budget(agent_name: str) -> bool:
    """Check if the agent has budget left for today."""
    today = datetime.utcnow().date().isoformat()
    usage = supabase.table('agent_daily_usage')\
        .select('*')\
        .eq('agent_name', agent_name)\
        .eq('date', today)\
        .execute()
    
    if not usage.data:
        return True  # No usage today yet
    
    daily = usage.data[0]
    global_config = get_config().get('budgets', {}).get('global', {})
    max_daily = global_config.get('max_daily_llm_calls', 100)
    
    return daily['llm_calls_used'] < max_daily
```

---

## Level 1: Self-Correcting Loops

### What Changes

The Analyst's reasoning becomes a **multi-step conversation** instead of a single-shot prompt. Each step is a separate LLM call that can observe the previous step's output and decide what to do next.

### The Analyst Reasoning Loop

```
START (budget initialized)
│
├─ Step 1: ASSESS (1 LLM call)
│  Input: raw data package
│  Output: assessment + plan
│  "Data quality is thin in payments but rich in tools.
│   I'll focus my deep analysis on tools this round."
│
├─ Step 2: ANALYZE (1 LLM call)  
│  Input: assessment + relevant data subset
│  Output: initial findings + clusters + opportunities
│  "Found 3 strong clusters and 2 weak ones."
│
├─ Step 3: CROSS-SYNTHESIZE (1 LLM call)
│  Input: findings from step 2 + tool data
│  Output: cross-pipeline signals
│  "Tool X sentiment is -0.6 and cluster Y matches — compound signal."
│
├─ Step 4: SELF-CRITIQUE (1 LLM call)
│  Input: all previous outputs
│  Output: critique + quality score (1-10)
│  Decision point:
│  ├─ Score >= 7: proceed to final output
│  ├─ Score < 7 AND budget.can_retry(): 
│  │  "Opportunities are generic. Re-analyzing with tighter criteria."
│  │  → Go back to Step 2 with adjusted parameters
│  └─ Score < 7 AND NOT budget.can_retry():
│     "Quality is below target but budget exhausted. Proceeding with caveats."
│     → Proceed with extra caveats flagged
│
├─ Step 5: FINAL OUTPUT (1 LLM call)
│  Input: all accumulated findings
│  Output: structured intelligence brief
│
└─ END (budget report included in output)
```

### Implementation

The Analyst's OpenClaw session manages this as a multi-turn conversation. But since the Analyst communicates via the file queue, the reasoning loop happens inside the agent's session:

**What the Analyst receives** (from the file queue):
```json
{
  "task": "full_analysis",
  "task_id": "uuid",
  "params": {
    "data_package": { ... },
    "budget": {
      "max_llm_calls": 8,
      "max_seconds": 300,
      "max_subtasks": 3,
      "max_retries": 2
    }
  }
}
```

**What the Analyst's identity tells it to do:**

The IDENTITY.md already has the 6-step reasoning process. The upgrade is adding budget awareness and self-correction:

```markdown
## Budget Awareness

Every task comes with a budget in the params. You MUST track your usage:

- Before each reasoning step, check: "Do I have budget for this?"
- If budget is exhausted mid-analysis: stop, compile what you have, flag as "budget_limited"
- Include budget usage in your output: {llm_calls_used, time_elapsed, retries_used}

## Self-Correction Protocol

After Step 4 (Self-Critique), rate your output quality 1-10:

- 8-10: Output is strong. Proceed to final output.
- 5-7: Output is acceptable but has weaknesses. If budget allows a retry,
  re-run Steps 2-3 with adjusted focus. If no budget, proceed with caveats.
- 1-4: Output is poor. If budget allows, retry with completely different
  approach. If no budget, flag as "low_confidence" and explain what went wrong.

When retrying:
- Don't repeat the same approach. Change something: focus on different clusters,
  use different cross-signal criteria, or narrow scope to do fewer things better.
- Each retry includes a note: "Retry reason: [what was wrong], Adjustment: [what I changed]"
```

### Poller Updates for Multi-Step

The analyst_poller doesn't need to change much. The multi-step reasoning happens inside OpenClaw's session. But the poller needs to:

1. Include the budget config in the task file it writes
2. Track time elapsed and force-complete if the task exceeds max_seconds
3. Read the budget usage from the response and log it

```python
# In analyst_poller.py, when writing the task file:
budget_config = get_budget_config('analyst', task['task_type'])
queue_file.write_text(json.dumps({
    'task': task['task_type'],
    'task_id': task_id,
    'params': {
        **task.get('input_data', {}),
        'budget': budget_config
    },
    'created_by': task.get('created_by', 'system')
}, indent=2, default=str))

# When checking responses, log budget usage:
if result.get('budget_usage'):
    logger.info(f"Budget usage for {task_id}: {result['budget_usage']}")
    # Update daily usage
    increment_daily_usage(
        'analyst',
        llm_calls=result['budget_usage'].get('llm_calls_used', 0),
        subtasks=result['budget_usage'].get('subtasks_created', 0)
    )
```

---

## Level 2: Autonomous Data Requests

### What Changes

Mid-analysis, the Analyst can decide it needs more data and request it from the Processor. The Analyst doesn't wait synchronously — it creates a subtask, pauses that branch of reasoning, and continues with what it has. On the next analysis run, the data will be available.

For time-sensitive requests (within the same task), the Analyst can create a "priority subtask" that the Processor picks up immediately.

### How It Works

```
Analyst is analyzing...
│
├─ "Payments cluster has only 2 mentions. I need more data."
│
├─ Check budget: can_create_subtask()? YES
│
├─ Write subtask to file queue:
│  {
│    "task": "create_agent_task",
│    "params": {
│      "task_type": "targeted_scrape",
│      "assigned_to": "processor",
│      "created_by": "analyst",
│      "priority": 1,
│      "input_data": {
│        "submolts": ["payments", "billing", "invoicing"],
│        "posts_per_submolt": 50,
│        "reason": "Thin data in payments cluster during full_analysis"
│      }
│    }
│  }
│
├─ Budget: subtasks_created += 1
│
├─ Continue analysis with available data
│  (Flag payments cluster as "data_requested — will be richer next run")
│
└─ Include in output:
   "data_requests": [
     {"type": "targeted_scrape", "reason": "...", "status": "requested"}
   ]
```

### Processor: Targeted Scrape Task

New task type in the Processor:

```python
elif task_type == 'targeted_scrape':
    submolts = params.get('submolts', [])
    posts_per = params.get('posts_per_submolt', 50)
    reason = params.get('reason', 'analyst_request')
    
    results = {}
    for submolt in submolts:
        result = scrape_moltbook(submolt_filter=submolt, limit=posts_per)
        results[submolt] = result
    
    # Run extraction on new posts
    extract_result = extract_problems(hours_back=1)  # Just the fresh posts
    
    return {
        'scrape': results,
        'extract': extract_result,
        'triggered_by': reason
    }
```

### Guardrails for Data Requests

- Max subtasks per task (default: 3)
- Max subtask depth: 2 (a subtask can create 1 level of sub-subtasks, no deeper)
- Targeted scrapes are limited to 50 posts per submolt, 3 submolts max
- If the Processor is overloaded (> 10 pending tasks), subtask creation is blocked

```python
def can_create_subtask(budget: AgentBudget, global_check: bool = True) -> bool:
    if not budget.can_create_subtask():
        return False
    if global_check:
        # Check processor isn't overwhelmed
        pending = supabase.table('agent_tasks')\
            .select('id', count='exact')\
            .eq('status', 'pending')\
            .execute()
        if pending.count > 10:
            logger.warning("Processor overloaded, blocking subtask creation")
            return False
    return True
```

---

## Level 3: Proactive Monitoring

### What Changes

Instead of only analyzing when triggered, the Analyst continuously monitors the data stream for anomalies and alerts the operator without being asked.

### How It Works

A new lightweight process runs every hour (within the Processor's scheduler):

```
Every 60 minutes (configurable):
│
├─ proactive_scan():
│  ├─ Check daily budget: proactive_alerts_sent < max_daily_proactive_alerts?
│  ├─ Fetch last hour of data (low cost — just counts and comparisons, no LLM)
│  ├─ Compare against baselines:
│  │  - Problem frequency spike: >3x average for any category
│  │  - Tool sentiment crash: avg sentiment dropped >0.5 in 24h
│  │  - New submolt activity: posts from a submolt we haven't seen before
│  │  - Volume anomaly: >2x or <0.5x normal post volume
│  │
│  ├─ If anomaly detected:
│  │  ├─ Create analysis task for Analyst (budget: proactive_scan)
│  │  ├─ Analyst does a focused mini-analysis (3-4 LLM calls max)
│  │  ├─ If Analyst confirms it's significant:
│  │  │  └─ Send alert to Gato → Telegram notification
│  │  └─ If Analyst says it's noise:
│  │     └─ Log and ignore
│  │
│  └─ If no anomalies: do nothing, log "no anomalies detected"
```

### Anomaly Detection (No LLM — Pure Python)

```python
def detect_anomalies() -> list:
    """Check for data anomalies. No LLM calls — just SQL and math."""
    anomalies = []
    now = datetime.utcnow()
    hour_ago = (now - timedelta(hours=1)).isoformat()
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()
    
    # 1. Problem frequency spike by category
    recent_problems = supabase.table('problems')\
        .select('category')\
        .gte('first_seen', hour_ago)\
        .execute()
    
    baseline_problems = supabase.table('problems')\
        .select('category')\
        .gte('first_seen', week_ago)\
        .lt('first_seen', day_ago)\
        .execute()
    
    if recent_problems.data and baseline_problems.data:
        from collections import Counter
        recent_counts = Counter(p['category'] for p in recent_problems.data)
        baseline_counts = Counter(p['category'] for p in baseline_problems.data)
        # Normalize baseline to hourly rate
        baseline_hours = 24 * 6  # 6 days of baseline
        
        for category, count in recent_counts.items():
            baseline_hourly = baseline_counts.get(category, 0) / max(baseline_hours, 1)
            if baseline_hourly > 0 and count > baseline_hourly * 3:
                anomalies.append({
                    'type': 'frequency_spike',
                    'category': category,
                    'current': count,
                    'baseline_hourly': round(baseline_hourly, 2),
                    'multiplier': round(count / baseline_hourly, 1),
                    'description': f"{category} problems spiked {round(count/baseline_hourly, 1)}x above baseline"
                })
    
    # 2. Tool sentiment crash
    recent_sentiment = supabase.table('tool_mentions')\
        .select('tool_name, sentiment_score')\
        .gte('mentioned_at', day_ago)\
        .execute()
    
    if recent_sentiment.data:
        from collections import defaultdict
        tool_sentiments = defaultdict(list)
        for m in recent_sentiment.data:
            tool_sentiments[m['tool_name']].append(m['sentiment_score'])
        
        for tool_name, scores in tool_sentiments.items():
            avg_recent = sum(scores) / len(scores)
            # Compare to stored average
            stats = supabase.table('tool_stats')\
                .select('avg_sentiment')\
                .eq('tool_name', tool_name)\
                .execute()
            if stats.data:
                historical_avg = stats.data[0].get('avg_sentiment', 0)
                if historical_avg - avg_recent > 0.5:
                    anomalies.append({
                        'type': 'sentiment_crash',
                        'tool_name': tool_name,
                        'current_avg': round(avg_recent, 2),
                        'historical_avg': round(historical_avg, 2),
                        'drop': round(historical_avg - avg_recent, 2),
                        'description': f"{tool_name} sentiment dropped {round(historical_avg - avg_recent, 2)} points"
                    })
    
    # 3. Volume anomaly
    recent_post_count = supabase.table('moltbook_posts')\
        .select('id', count='exact')\
        .gte('scraped_at', hour_ago)\
        .execute()
    
    baseline_post_count = supabase.table('moltbook_posts')\
        .select('id', count='exact')\
        .gte('scraped_at', week_ago)\
        .lt('scraped_at', day_ago)\
        .execute()
    
    if recent_post_count.count and baseline_post_count.count:
        baseline_hourly_posts = baseline_post_count.count / (24 * 6)
        if baseline_hourly_posts > 0:
            ratio = recent_post_count.count / baseline_hourly_posts
            if ratio > 2.5 or ratio < 0.3:
                anomalies.append({
                    'type': 'volume_anomaly',
                    'current': recent_post_count.count,
                    'baseline_hourly': round(baseline_hourly_posts, 1),
                    'ratio': round(ratio, 1),
                    'direction': 'spike' if ratio > 2 else 'drop',
                    'description': f"Post volume {'spiked' if ratio > 2 else 'dropped'} to {round(ratio, 1)}x baseline"
                })
    
    return anomalies


def proactive_scan():
    """Periodic scan for anomalies. No LLM unless anomaly found."""
    # Check daily budget
    if not check_proactive_budget():
        logger.info("Proactive scan budget exhausted for today")
        return {'skipped': 'daily_budget_exhausted'}
    
    # Check cooldown
    if not check_proactive_cooldown():
        return {'skipped': 'cooldown_active'}
    
    anomalies = detect_anomalies()
    
    if not anomalies:
        logger.info("Proactive scan: no anomalies detected")
        return {'anomalies': 0}
    
    logger.info(f"Proactive scan: {len(anomalies)} anomalies detected")
    
    # Create a focused analysis task for the Analyst
    supabase.table('agent_tasks').insert({
        'task_type': 'proactive_analysis',
        'assigned_to': 'analyst',
        'created_by': 'processor',
        'priority': 2,
        'input_data': {
            'anomalies': anomalies,
            'budget': get_budget_config('analyst', 'proactive_scan')
        }
    }).execute()
    
    return {'anomalies': len(anomalies), 'analysis_requested': True}


def check_proactive_budget() -> bool:
    today = datetime.utcnow().date().isoformat()
    usage = supabase.table('agent_daily_usage')\
        .select('proactive_alerts_sent')\
        .eq('agent_name', 'system')\
        .eq('date', today)\
        .execute()
    
    max_daily = get_config().get('budgets', {}).get('global', {}).get('max_daily_proactive_alerts', 5)
    
    if not usage.data:
        return True
    return usage.data[0]['proactive_alerts_sent'] < max_daily


def check_proactive_cooldown() -> bool:
    """Ensure minimum time between proactive scans."""
    cooldown_minutes = get_config().get('budgets', {}).get('global', {}).get('cooldown_between_proactive_scans_minutes', 60)
    
    last_scan = supabase.table('pipeline_runs')\
        .select('completed_at')\
        .eq('pipeline', 'proactive_scan')\
        .order('completed_at', desc=True)\
        .limit(1)\
        .execute()
    
    if not last_scan.data:
        return True
    
    last_time = datetime.fromisoformat(last_scan.data[0]['completed_at'].replace('Z', '+00:00'))
    elapsed = (datetime.utcnow().replace(tzinfo=last_time.tzinfo) - last_time).total_seconds() / 60
    return elapsed >= cooldown_minutes
```

### Proactive Alert Flow

When the Analyst confirms an anomaly is significant:

```
Analyst output includes: "alert": true, "alert_message": "..."
│
├─ Poller reads the response
├─ Detects alert flag
├─ Creates notification task for Gato:
│  {
│    "task_type": "proactive_alert",
│    "assigned_to": "gato",
│    "created_by": "analyst",
│    "input_data": {
│      "alert_message": "⚠️ Anomaly detected: payments problems spiked 4x...",
│      "anomaly_type": "frequency_spike",
│      "details": { ... }
│    }
│  }
│
├─ Processor picks up gato task → sends Telegram alert
├─ Increment proactive_alerts_sent in daily usage
└─ Log alert
```

### Analyst Identity Addition for Proactive

Add to IDENTITY.md:

```markdown
## Proactive Analysis

Sometimes you'll receive anomaly data instead of a full data package. This means
the system detected something unusual and wants your assessment.

Your job: Is this anomaly real and significant, or is it noise?

Approach:
1. Look at the raw anomaly data (category, multiplier, current vs baseline)
2. If you have enough context in the data: assess immediately
3. Rate: "significant" (worth alerting the operator) or "noise" (log and ignore)
4. If significant: write a 2-3 sentence alert message. Be specific.
   Bad: "Something unusual is happening."
   Good: "Payment tool complaints spiked 4x in the last hour. 8 posts from
   5 different agents mentioning settlement delays. This matches the 'Payment
   Settlement' cluster from last week — the problem may be getting worse."

If you flag an alert, it goes directly to the operator's Telegram. Be sure
before you alert — false alarms erode trust.

Budget for proactive analysis is small (4 LLM calls max). Be efficient.
```

---

## Level 4: Agent-to-Agent Negotiation

### What Changes

Agents can request things from each other — not just create tasks, but have expectations about the response and follow up if unsatisfied.

### The Negotiation Protocol

```
NEWSLETTER AGENT:
  "I'm writing this week's brief but Section A is thin.
   Only 2 opportunities scored above 0.6."
  
  → Creates task for Analyst:
    {
      task_type: "enrich_for_newsletter",
      assigned_to: "analyst",
      created_by: "newsletter",
      priority: 2,
      input_data: {
        request: "Need stronger opportunities for the newsletter. Current top 2 
                  are RegTech and ChainTrust. Can you do a quick review of the 
                  next 5 candidates and see if any deserve a higher score?",
        needed_by: "2026-02-17T08:00:00Z",
        min_quality: "at least 3 opportunities above 0.6 confidence"
      }
    }

ANALYST:
  Picks up the task, reviews 5 more opportunities, re-scores them.
  
  → Writes response:
    {
      success: true,
      result: {
        upgraded_opportunities: [ ... ],
        message: "Upgraded 'Agent Memory' from 0.55 to 0.72 — found 3 new 
                  supporting signals. 'Protocol Bridge' stays at 0.48 — data 
                  is too thin. You now have 3 above 0.6."
      }
    }

NEWSLETTER AGENT:
  Reads the response, uses the enriched data, writes a better Section A.
```

### Implementation: Request-Response with Expectations

The requesting agent includes:
- **What it needs** (plain language request)
- **When it needs it** (deadline — optional)
- **Quality criteria** (what "good enough" means)

The responding agent includes:
- **What it did**
- **Whether it met the criteria**
- **If not, why not** (budget exhausted, data insufficient, etc.)

### Negotiation Guardrails

```json
{
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
  }
}
```

- Max 2 back-and-forth rounds per negotiation (request → response → one follow-up → final)
- Max 3 active negotiations per agent at any time
- 30-minute timeout — if no response, the requesting agent proceeds with what it has
- Defined hierarchy: Newsletter can ask Analyst and Processor. Analyst can ask Processor. Processor doesn't ask anyone (it's the worker). Gato can ask anyone.

### Database for Negotiations

```sql
CREATE TABLE agent_negotiations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requesting_agent TEXT NOT NULL,
    responding_agent TEXT NOT NULL,
    status TEXT DEFAULT 'open',           -- open, responded, follow_up, closed, timed_out
    round INT DEFAULT 1,
    
    -- Request
    request_task_id UUID REFERENCES agent_tasks(id),
    request_summary TEXT,
    quality_criteria TEXT,
    needed_by TIMESTAMPTZ,
    
    -- Response
    response_task_id UUID REFERENCES agent_tasks(id),
    criteria_met BOOLEAN,
    response_summary TEXT,
    
    -- Follow-up (if criteria not met)
    follow_up_task_id UUID REFERENCES agent_tasks(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_negotiations_status ON agent_negotiations(status);
CREATE INDEX idx_negotiations_agents ON agent_negotiations(requesting_agent, responding_agent);

-- RLS
ALTER TABLE agent_negotiations ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_daily_usage ENABLE ROW LEVEL SECURITY;
```

### Newsletter Agent: Requesting Enrichment

Add to the Newsletter agent's SKILL.md:

```markdown
## Requesting Help from Other Agents

If your data package is insufficient for a good newsletter:

1. Assess what's missing. Be specific.
2. Create a request task. Include:
   - What you need (specific, actionable)
   - Quality criteria (what "good enough" means)
   - Why you need it (so the other agent can prioritize)
3. Continue writing with what you have.
4. When the response arrives, incorporate it.
5. If still insufficient after one round, proceed with what you have
   and note the gap: "This week's data was thinner than usual in [area]."

You have a budget of max 2 subtasks per newsletter. Use them wisely.
Don't request enrichment for the Curious Corner — that section is fine with thin data.
Focus requests on Section A (opportunities) where weak data means a weak lead.
```

---

## Database Summary: All New Tables

```sql
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

-- Negotiations
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

-- RLS on new tables
ALTER TABLE agent_daily_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_negotiations ENABLE ROW LEVEL SECURITY;
```

---

## Budget Config Location

Add to `config/agentpulse-config.json`:

```json
{
  "models": { ... },
  "budgets": {
    "analyst": {
      "full_analysis": {
        "max_llm_calls": 8,
        "max_seconds": 300,
        "max_subtasks": 3,
        "max_retries": 2
      },
      "deep_dive": {
        "max_llm_calls": 5,
        "max_seconds": 180,
        "max_subtasks": 2,
        "max_retries": 1
      },
      "review_opportunity": {
        "max_llm_calls": 3,
        "max_seconds": 120,
        "max_subtasks": 1,
        "max_retries": 1
      },
      "proactive_scan": {
        "max_llm_calls": 4,
        "max_seconds": 120,
        "max_subtasks": 1,
        "max_retries": 1
      }
    },
    "newsletter": {
      "write_newsletter": {
        "max_llm_calls": 6,
        "max_seconds": 300,
        "max_subtasks": 2,
        "max_retries": 2
      },
      "revise_newsletter": {
        "max_llm_calls": 3,
        "max_seconds": 120,
        "max_subtasks": 1,
        "max_retries": 1
      }
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
  }
}
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/budget` (NEW) | Show today's budget usage per agent |
| `/alerts` (NEW) | Show recent proactive alerts |
| `/alerts-config` (NEW) | View/toggle proactive monitoring |
| `/negotiations` (NEW) | Show active agent negotiations |

---

## Implementation Order

```
Prompt 1:  Database schema (daily_usage, negotiations tables)
Prompt 2:  Budget system (AgentBudget class, config loading, daily tracking)
Prompt 3:  Level 1 — Analyst self-correcting loops (multi-step reasoning, retry logic)
Prompt 4:  Level 2 — Autonomous data requests (targeted_scrape, subtask creation)
Prompt 5:  Level 3 — Proactive monitoring (anomaly detection, scan scheduling, alerts)
Prompt 6:  Level 4 — Agent negotiation (newsletter↔analyst enrichment protocol)
Prompt 7:  Update Analyst identity with budget awareness + all new capabilities
Prompt 8:  Update Newsletter identity with negotiation capability
Prompt 9:  Wire new Telegram commands (/budget, /alerts, /negotiations)
Prompt 10: Update agentpulse-config.json with full budget + negotiation config
```
