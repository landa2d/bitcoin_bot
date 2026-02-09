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

## Requesting More Data

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
