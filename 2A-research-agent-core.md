# 2A — Research Agent Core Processor

## Phase
Phase 2 — Research Agent Core

## Parallel/Sequential
**SEQUENTIAL** — Requires Phase 1A (sources available), 1B (schema ready), 1C (system prompt designed)

## Dependencies
- 1A: Thought leader sources must be ingesting
- 1B: `research_queue`, `spotlight_history` tables must exist
- 1C: System prompt must be drafted

## Prompt

Build the Research Agent as a standalone processor for AgentPulse. This agent picks up topics from the research queue, conducts deep analysis using all available sources (with emphasis on thought leader tier), runs the thesis-building reasoning chain, and outputs a structured Spotlight object.

### Execution Flow

```
1. Poll `research_queue` for highest priority item with status = 'queued'
2. Update status to 'in_progress', set `started_at`
3. Gather source material:
   a. Pull all recent items mentioning this topic from general sources
   b. Pull all recent items from thought_leader sources on this topic
   c. Pull any existing topic lifecycle context
4. Build context window for the LLM:
   - Topic name and lifecycle phase
   - Key data points from institutional/general sources
   - Thought leader perspectives (especially contrarian takes)
   - Community signals and GitHub activity
   - Context payload from Analyst (in research_queue.context_payload)
5. Run thesis-building chain using Research Agent system prompt
6. Parse structured output (thesis, evidence, counter_argument, prediction, builder_implications)
7. Store result in `spotlight_history`
8. Update research_queue status to 'completed', set `completed_at`
```

### Architecture

- **Standalone Python processor** following existing Docker/processor patterns
- **Model**: Use Anthropic Claude for the thesis-building (higher reasoning quality for opinionated analysis)
- **Token budget**: Set a ceiling for the research phase (source gathering) and the generation phase separately. Log token usage for cost monitoring but don't expose to the output.
- **Single execution**: One topic per run. If multiple items are queued, process only the highest priority.

### Source Gathering Logic

```python
# Pseudocode for source gathering
def gather_sources(topic_id, topic_name):
    # 1. General sources — last 7 days
    general = query_sources(
        topic=topic_name,
        source_tier=['institutional', 'community'],
        days=7,
        limit=20
    )
    
    # 2. Thought leader sources — last 14 days (wider window, fewer posts)
    thought_leaders = query_sources(
        topic=topic_name,
        source_tier=['thought_leader'],
        days=14,
        limit=15
    )
    
    # 3. GitHub signals — last 7 days
    github = query_github_activity(topic=topic_name, days=7)
    
    return {
        'general': general,
        'thought_leaders': thought_leaders,
        'github': github,
        'total_sources': len(general) + len(thought_leaders) + len(github)
    }
```

### Error Handling

1. **Source gathering fails**: If thought leader sources are unavailable, proceed with general sources only. Log warning. The thesis quality may be lower but shouldn't block.
2. **LLM generation fails**: Retry once. If still failing, mark queue item as 'failed' with error details. Don't block the newsletter pipeline — the Newsletter Agent should handle missing Spotlights gracefully.
3. **Output parsing fails**: If the LLM output doesn't match expected structure, attempt to extract what's available and store partial result. Flag for manual review.
4. **Token budget exceeded**: If source material exceeds context window, prioritize thought leader sources, then institutional, then community. Truncate community sources first.
5. **Timeout**: Set a maximum execution time (e.g., 5 minutes). If exceeded, store whatever has been generated and mark as 'completed' with a warning flag.

### Synthesis Mode
When `research_queue.mode = 'synthesis'`:
- Instead of deep-diving one topic, pull context for the top 3 emerging topics
- Use the synthesis variant of the system prompt (designed in 1C)
- Output structure is the same but `mode` field = 'synthesis'
- The thesis should connect the topics into a bigger picture

### Configuration
```yaml
research_agent:
  model: claude-sonnet-4-20250514  # or appropriate model
  max_source_tokens: 8000           # token budget for source material
  max_generation_tokens: 2000       # token budget for output
  source_window_general: 7          # days to look back for general sources
  source_window_thought_leader: 14  # days for thought leader sources
  max_execution_time: 300           # seconds
  retry_on_failure: 1               # number of retries
```

### Expected Output
A row in `spotlight_history` with all fields populated:
- `thesis`: One sharp sentence
- `evidence`: 2-3 paragraphs of editorial prose
- `counter_argument`: 1 paragraph
- `prediction`: 1-2 sentences, specific and falsifiable
- `builder_implications`: 1 paragraph
- `full_output`: All of the above concatenated as the complete Spotlight text
- `sources_used`: JSONB array of sources referenced

### Acceptance Criteria
- [ ] Agent picks up queued items and processes them
- [ ] Source gathering pulls from all tiers correctly
- [ ] Thesis-building chain produces structured output matching expected format
- [ ] Result stored in `spotlight_history` with all fields
- [ ] Queue item status updated correctly through lifecycle
- [ ] Error handling works for each failure mode
- [ ] Synthesis mode works when triggered
- [ ] Token usage logged for cost monitoring
- [ ] Execution completes within timeout
