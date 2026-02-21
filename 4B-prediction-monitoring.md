# 4B — Prediction Monitoring in Analyst Cycle

## Phase
Phase 4 — Scorecard System

## Parallel/Sequential
**SEQUENTIAL** — Requires 4A (predictions being stored)

## Dependencies
- 4A: `predictions` table must have entries with status = 'open'

## Prompt

Add prediction monitoring to the Analyst's scan cycle. For each open prediction, the Analyst should check whether new evidence strongly confirms or contradicts it, and flag predictions that appear to be resolving.

### Integration with Analyst Cycle

Add a new step at the end of the Analyst's existing cycle:

```
1. Analyst completes normal scan (existing)
2. Analyst runs topic lifecycle updates (existing)
3. Analyst runs Spotlight selection heuristic (added in 2B)
4. NEW: Analyst runs prediction monitoring
```

### Monitoring Logic

```python
def monitor_predictions(recent_items):
    open_predictions = supabase.table('predictions') \
        .select('*') \
        .eq('status', 'open') \
        .execute()
    
    for prediction in open_predictions:
        # Find recent items related to this prediction's topic
        related_items = [item for item in recent_items 
                        if prediction.topic_id in item.topics]
        
        if not related_items:
            continue  # no new signal, skip
        
        # Use LLM to assess whether new evidence confirms or contradicts
        assessment = assess_prediction(prediction, related_items)
        
        if assessment.significance >= THRESHOLD:
            # Flag for review — don't auto-resolve
            supabase.table('predictions').update({
                'status': 'flagged',
                'evidence_notes': assessment.evidence_summary,
                'flagged_at': now()
            }).eq('id', prediction.id).execute()
```

### Assessment Prompt

```
System: You are evaluating whether new evidence affects an existing prediction.

Prediction: "{prediction_text}"
Made in issue #{issue_number} on {created_at}

New evidence from the last 7 days:
{related_items_summary}

Assess:
1. Does this evidence CONFIRM the prediction, CONTRADICT it, or is it NEUTRAL?
2. How significant is this evidence? (low / medium / high)
3. If significant, summarize in 2-3 sentences what happened and how it relates to the prediction.

Output as JSON:
{
  "direction": "confirms" | "contradicts" | "neutral",
  "significance": "low" | "medium" | "high",
  "evidence_summary": "..."
}
```

### Flagging vs Auto-Resolution

**Important: The Analyst flags predictions but does NOT auto-resolve them.**

Reasons:
- Predictions are nuanced — "partially correct" is common and needs human judgment
- Auto-resolution could embarrass the newsletter with wrong calls
- The Scorecard blurb requires editorial quality that the Analyst shouldn't generate

Workflow:
1. Analyst flags prediction with evidence
2. During newsletter generation, the Newsletter Agent (or Diego manually) reviews flagged predictions
3. If a flagged prediction is clearly resolved, update status to `confirmed`, `refuted`, or `partially_correct` and add `resolution_notes`
4. The Scorecard in 4C picks up resolved predictions

### Significance Threshold

Only flag when evidence is HIGH significance — meaning the prediction is clearly being confirmed or contradicted by concrete events, not just more discussion about the topic.

Examples:
- **HIGH (flag)**: Prediction was "two frameworks will fork MCP" and a major framework just announced an MCP fork → flag as confirming
- **MEDIUM (don't flag)**: More blog posts discussing MCP governance concerns → related but not decisive
- **LOW (don't flag)**: Someone mentions MCP in passing on Hacker News → noise

### Configuration
```yaml
prediction_monitoring:
  significance_threshold: "high"     # only flag high-significance evidence
  check_frequency: "every_cycle"     # run on every Analyst cycle
  max_open_predictions: 20           # don't monitor more than 20 at once (performance)
  stale_after_days: 180              # predictions older than 6 months auto-close as 'expired'
```

### Token Budget Consideration

Each open prediction requires an LLM call to assess new evidence. With 10 open predictions and the Analyst running weekly, this is manageable. But add a circuit breaker: if there are more than 20 open predictions, only assess the 20 most recent. Older predictions should be manually reviewed and resolved or expired.

### Acceptance Criteria
- [ ] Analyst checks open predictions at the end of each cycle
- [ ] Only flags predictions with HIGH significance evidence
- [ ] Does NOT auto-resolve — only flags for review
- [ ] Evidence summary is clear and useful for Scorecard generation
- [ ] Stale predictions (>6 months) auto-expire
- [ ] Performance is reasonable with up to 20 open predictions
- [ ] Token usage for prediction assessment is logged
- [ ] Flagging doesn't block or delay the rest of the Analyst cycle
