# 4C — Scorecard Generation in Newsletter Agent

## Phase
Phase 4 — Scorecard System

## Parallel/Sequential
**SEQUENTIAL** — Requires 4B (predictions being monitored and flagged/resolved)

## Dependencies
- 4B: Prediction monitoring must be flagging predictions
- Resolved predictions must exist in the `predictions` table (status = confirmed/refuted/partially_correct)

## Prompt

Add Scorecard generation to the AgentPulse Newsletter Agent. When resolved predictions exist, generate a "Looking Back" blurb that revisits the original thesis and honestly assesses what happened.

### When to Include Scorecard

- Check `predictions` table for any entries with status in (`confirmed`, `refuted`, `partially_correct`) that haven't been included in a previous Scorecard
- If found: generate Scorecard blurb and include in newsletter
- If not found: skip the section entirely — don't include an empty placeholder
- Max 2 lookbacks per issue (if multiple predictions resolved, pick the most interesting ones)

### Scorecard Format

Keep it short and honest. Three to four sentences, no more.

**Template:**

> **Looking Back: [Original thesis headline, shortened]**
>
> [One sentence: what we predicted and when.] [One sentence: what actually happened.] [One sentence: honest assessment — right, wrong, or partially right, and what we missed or got right.]

**Examples:**

> **Looking Back: Our Take on MCP Enterprise Forks**
>
> In Issue #38, we predicted that at least two major frameworks would fork MCP's core protocol by mid-2025. LangChain shipped their own MCP variant in April, and AWS announced a "compatible but independent" implementation in May. Directionally right, though we underestimated how quickly cloud providers would move — the timeline was about two months faster than we expected.

> **Looking Back: The Agent Middleware Bet**
>
> Back in Issue #35, we argued that agent middleware would become the most contested layer in the stack. Six weeks later, the middleware space looks competitive but hasn't consolidated the way we predicted. We were right about the investment activity but wrong about the timeline — the consolidation is happening at the model layer first, with middleware likely following in Q4.

> **Looking Back: Local Models for Agent Tasks**
>
> We predicted in Issue #40 that local model fine-tuning would pull 30% of simple agent tasks off API providers by Q3. The actual shift has been closer to 10-15%. We overestimated the pace — the tooling is improving but enterprise adoption is slower than the open-source enthusiasm suggested. Marking this one as partially correct.

### Tone Guidelines
- Intellectually honest, not defensive
- If wrong, say so directly — "we got this wrong" is more credible than "the situation evolved differently than anticipated"
- If right, don't gloat — state it plainly
- If partially right, be specific about what hit and what missed
- No excuses, no hedging, no face-saving language
- This builds trust. Readers who see you own your misses will trust your hits

### Generation Logic

```python
def generate_scorecard(current_issue_number):
    resolved = supabase.table('predictions') \
        .select('*, spotlight_history(*)') \
        .in_('status', ['confirmed', 'refuted', 'partially_correct']) \
        .is_('scorecard_issue', None) \  # not yet included in a Scorecard
        .order('resolved_at', desc=True) \
        .limit(2) \
        .execute()
    
    if not resolved.data:
        return None  # no Scorecard this issue
    
    scorecard_blurbs = []
    for prediction in resolved.data:
        blurb = generate_lookback_blurb(
            original_thesis=prediction.spotlight_history.thesis,
            prediction_text=prediction.prediction_text,
            original_issue=prediction.issue_number,
            resolution_notes=prediction.resolution_notes,
            status=prediction.status
        )
        scorecard_blurbs.append(blurb)
        
        # Mark as included in Scorecard
        supabase.table('predictions').update({
            'scorecard_issue': current_issue_number
        }).eq('id', prediction.id).execute()
    
    return scorecard_blurbs
```

### LLM Prompt for Blurb Generation

```
System: You are writing a brief lookback for the AgentPulse newsletter. Be honest and direct.
No defensive language. If the prediction was wrong, say so plainly. If right, state it without
gloating. Keep it to 3-4 sentences maximum.

Original thesis: "{thesis}"
Our prediction (Issue #{issue_number}): "{prediction_text}"
What actually happened: "{resolution_notes}"
Assessment: {status}

Write the lookback blurb. Start with "In Issue #{issue_number}, we predicted..." or similar.
End with an honest one-sentence assessment of what we got right and wrong.
```

### Newsletter Placement

```
1. Spotlight (if available)
2. Signals
3. Radar
4. Looking Back (if resolved predictions exist) ← Scorecard goes here
```

### Schema Addition

Add a column to `predictions` to track which Scorecard included it:

```sql
ALTER TABLE predictions ADD COLUMN scorecard_issue INTEGER;
```

### Acceptance Criteria
- [ ] Scorecard blurbs generated for resolved predictions
- [ ] Blurbs are 3-4 sentences, no more
- [ ] Tone is honest — admits when wrong, doesn't gloat when right
- [ ] Max 2 lookbacks per issue
- [ ] Predictions marked as included so they don't repeat
- [ ] Section skipped gracefully when no resolved predictions exist
- [ ] Placement is correct: last section of newsletter
- [ ] Generated blurbs match the quality/tone of examples above
