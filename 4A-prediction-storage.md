# 4A — Prediction Extraction and Storage

## Phase
Phase 4 — Scorecard System

## Parallel/Sequential
**PARALLEL** — Can start after 2D (Research Agent producing output). Runs parallel to Phase 3 work.

## Dependencies
- 2D: Research Agent must be producing Spotlight content with predictions
- 1B: `predictions` table must exist

## Prompt

When the Research Agent generates a Spotlight, automatically extract the core falsifiable prediction and store it in the `predictions` table. This is the foundation for the Scorecard — without stored predictions, there's nothing to look back on.

### Extraction Logic

After a Spotlight is stored in `spotlight_history`, run a prediction extraction step:

1. Read the `prediction` field from the Spotlight
2. Extract the **specific falsifiable claim** — this is NOT the full prediction paragraph, it's the core testable statement
3. Store in the `predictions` table linked to the Spotlight

### What Makes a Good Extracted Prediction

**Good** (specific, falsifiable, has a timeframe):
- "At least two major enterprise frameworks will fork MCP's core protocol by mid-2025"
- "OpenAI will ship native agent-to-agent communication within 90 days"
- "The local model fine-tuning trend will pull at least 30% of simple agent tasks off API providers by Q3"

**Bad** (vague, unfalsifiable, no timeframe):
- "MCP adoption will continue to grow"
- "This trend will have significant implications"
- "Enterprises will need to adapt"

### Extraction Method

Use the LLM to extract the prediction (not regex — predictions are too varied in structure):

```
System: You are a prediction extractor. Given a Spotlight analysis, extract the single most 
specific, falsifiable prediction. Output ONLY the prediction as a single sentence. It must 
include a timeframe and a specific, measurable outcome. If the original prediction is too 
vague, sharpen it while staying true to the original intent.

Input: [spotlight.prediction field]
Output: [one sentence — the falsifiable claim]
```

### Storage

```python
prediction = {
    'spotlight_id': spotlight.id,
    'topic_id': spotlight.topic_id,
    'prediction_text': extracted_prediction,  # the sharpened one-sentence claim
    'issue_number': spotlight.issue_number,
    'status': 'open',
    'created_at': now()
}
supabase.table('predictions').insert(prediction)
```

### Timing

This runs as a post-generation task, after the newsletter has been assembled but before (or shortly after) delivery. It's not time-critical — it just needs to happen before the next Analyst cycle so predictions are available for monitoring.

### Edge Cases
- **Synthesis mode Spotlights**: May contain multiple predictions (one per connected topic). Extract the PRIMARY prediction — the one that ties the synthesis together. Store only one per Spotlight.
- **Vague prediction from Research Agent**: The extraction prompt should sharpen it, but if it's truly unfalsifiable, store it anyway with a flag: `needs_sharpening: true`. Fix the Research Agent prompt to prevent this in future.
- **No prediction in Spotlight**: This shouldn't happen (the system prompt requires it), but if it does, skip extraction and log a warning. Fix the Research Agent prompt.

### Acceptance Criteria
- [ ] Prediction automatically extracted after each Spotlight generation
- [ ] Extracted prediction is specific and falsifiable (not a vague restatement)
- [ ] Stored in `predictions` table with correct `spotlight_id` link
- [ ] Synthesis mode Spotlights produce exactly one prediction
- [ ] Edge cases handled (vague predictions, missing predictions)
- [ ] Post-generation timing doesn't block newsletter delivery
