# Analyst Agent Skills — Intelligence Analysis

## Task Types

### full_analysis
The complete reasoning loop. This is your primary task.

**Input:** `{data_package}` containing:
- `problems`: Recent extracted problems with metadata
- `clusters`: Current problem clusters with scores
- `tool_mentions`: Recent tool mentions with sentiment
- `tool_stats`: Aggregated tool statistics
- `opportunities`: Existing opportunities (for comparison/update)
- `previous_run`: Summary of last analysis run (for delta detection)
- `stats`: Post counts, timeframes, coverage metrics

**Process:** Run all 6 reasoning steps from IDENTITY.md in order.

**Output:**
```json
{
  "executive_summary": "2-3 sentence summary of key finding",
  "situational_assessment": {
    "data_quality": "rich|normal|thin",
    "total_signals": N,
    "notable_changes": ["..."]
  },
  "key_findings": [
    {
      "finding": "...",
      "evidence": ["post_id_1", "mention_count: N", "..."],
      "significance": "high|medium|low",
      "actionability": "..."
    }
  ],
  "opportunities": [
    {
      "title": "...",
      "confidence_score": 0.0-1.0,
      "reasoning_chain": "Score is X because: ...",
      "signal_sources": {
        "pipeline_1": ["cluster_id", "..."],
        "pipeline_2": ["tool_name", "..."],
        "cross_signals": ["..."]
      },
      "upgrade_factors": ["..."],
      "downgrade_factors": ["..."]
    }
  ],
  "cross_signals": [
    {
      "type": "tool_problem_match|sentiment_opportunity|trend_convergence",
      "description": "...",
      "strength": 0.0-1.0,
      "reasoning": "..."
    }
  ],
  "watch_list": [
    {
      "signal": "...",
      "why_watching": "...",
      "what_would_confirm": "..."
    }
  ],
  "self_critique": {
    "confidence_level": "high|medium|low",
    "caveats": ["..."],
    "weakest_links": ["..."],
    "additional_data_needed": ["..."]
  }
}
```

### deep_dive
Focused analysis on a specific cluster, tool, or opportunity.

**Input:** `{target_type, target_id, context}`
**Process:** Steps 2-5 focused on the specific target.
**Output:** Detailed analysis with reasoning.

### review_opportunity
Re-evaluate an existing opportunity with fresh data.

**Input:** `{opportunity_id}`
**Process:** Steps 3-5 focused on the opportunity. Compare current signals to when it was created.
**Output:** Updated score, reasoning, and recommendation (keep/upgrade/downgrade/archive).

### compare_runs
Compare two analysis runs and highlight what changed.

**Input:** `{run_id_a, run_id_b}` or `{run_id, compare_to: "previous"}`
**Output:** Delta report — new signals, lost signals, score changes, emerging trends.

## Data Access

You can query Supabase directly for additional data during analysis:
- `moltbook_posts` — raw posts for deeper context
- `problems` — all extracted problems
- `problem_clusters` — current clusters
- `tool_mentions` — individual tool mentions
- `tool_stats` — aggregated stats
- `opportunities` — existing opportunities
- `analysis_runs` — your previous analysis runs
- `cross_signals` — previously detected cross-pipeline signals

### proactive_analysis
Assess a single anomaly detected by the proactive monitoring system.

**Input:** `{anomaly_type, description, metrics, budget}`
- `anomaly_type`: Type of anomaly — e.g. `frequency_spike`, `sentiment_crash`, `volume_anomaly`
- `description`: Plain-language description of what was detected
- `metrics`: Relevant numeric metrics dict — e.g. `{"multiplier": 3.2, "current": 45, "baseline_hourly": 14, "drop": 0.4}`
- `budget`: Budget constraints for this task (see Budget Object below)

**Process:** Assess the anomaly — is it significant or noise? Be efficient (budget is small).

**Output:**
```json
{
  "run_type": "proactive_analysis",
  "alert": true,
  "alert_message": "2-3 sentence specific alert for Telegram",
  "anomaly_type": "frequency_spike|sentiment_crash|volume_anomaly",
  "alert_details": {},
  "assessment": [
    {
      "anomaly_type": "...",
      "verdict": "significant|noise",
      "reasoning": "...",
      "confidence": 0.0
    }
  ],
  "executive_summary": "1-2 sentence overall assessment",
  "budget_usage": { "llm_calls_used": N, "elapsed_seconds": N, "retries_used": N, "subtasks_created": N }
}
```

### enrich_for_newsletter
Review and re-score opportunities at the Newsletter agent's request (via negotiation).

**Input:** `{negotiation_request, budget, ...opportunity data}`
- `negotiation_request.request_summary`: What the Newsletter agent needs
- `negotiation_request.quality_criteria`: What "good enough" means
- `budget`: Budget constraints for this task

**Process:** Review candidate opportunities, look for new supporting signals, re-score where warranted.

**Output:**
```json
{
  "run_type": "enrich_for_newsletter",
  "executive_summary": "1-2 sentence summary",
  "upgraded_opportunities": [
    {
      "id": "<uuid>",
      "title": "...",
      "previous_score": 0.0,
      "new_score": 0.0,
      "reasoning": "Why the score changed",
      "new_signals": ["..."]
    }
  ],
  "negotiation_criteria_met": true,
  "negotiation_response_summary": "Did you meet the criteria? Explain.",
  "message": "Plain-language message for the Newsletter agent",
  "budget_usage": { "llm_calls_used": N, "elapsed_seconds": N, "retries_used": N, "subtasks_created": N }
}
```

## Budget Object

Every task includes a `budget` field in its `input_data`:

```json
{
  "budget": {
    "max_llm_calls": 8,
    "max_seconds": 300,
    "max_subtasks": 3,
    "max_retries": 2
  }
}
```

You MUST track your usage and include `budget_usage` in your output (see IDENTITY.md § Budget Awareness). If you exhaust your budget mid-analysis, stop and compile what you have so far.

## Autonomous Data Requests (output format)

When data is thin for a specific area, include a `data_requests` array in your output:

```json
{
  "data_requests": [
    {
      "type": "targeted_scrape",
      "submolts": ["payments", "billing"],
      "posts_per": 50,
      "reason": "Thin data in payments cluster during full_analysis"
    }
  ]
}
```

- Maximum 3 requests per task (bounded by `budget.max_subtasks`)
- The Processor will scrape and extract on your behalf
- Data arrives asynchronously — it will be available in your next analysis run
- Flag the thin area in your output so the operator knows enrichment is pending

## Requesting More Data (legacy)

If you need data the Processor hasn't gathered yet, create an agent_task:
```json
{
  "task": "create_agent_task",
  "params": {
    "task_type": "scrape",
    "assigned_to": "processor",
    "created_by": "analyst",
    "input_data": {"submolts": ["specific_submolt"], "posts_per_submolt": 100}
  }
}
```
