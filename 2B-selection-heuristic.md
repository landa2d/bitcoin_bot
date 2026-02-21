# 2B — Analyst Selection Heuristic for Spotlight

## Phase
Phase 2 — Research Agent Core

## Parallel/Sequential
**PARALLEL with 2A** — Both depend on Phase 1 but not on each other

## Dependencies
- 1B: `research_queue`, `spotlight_history` tables and `spotlight_cooldown` view must exist

## Prompt

Add Spotlight topic selection logic to the AgentPulse Analyst. At the end of each analysis cycle, the Analyst should select the best candidate topic for the Research Agent to deep-dive and write it to the `research_queue`.

### Selection Heuristic

Score each topic using:

```
spotlight_score = velocity × source_diversity × lifecycle_bonus
```

Where:
- **velocity**: Rate of new mentions in the last 7 days (normalized 0-1)
- **source_diversity**: Number of distinct source tiers mentioning the topic (0-1 scale, where coverage across institutional + thought_leader + community = 1.0)
- **lifecycle_bonus**: Multiplier based on lifecycle phase:
  - `emerging`: 1.0x (interesting but might not have enough signal yet)
  - `debating`: 1.5x (peak interest — ideal for Spotlight)
  - `building`: 1.3x (strong signal, people acting on it)
  - `mature`: 0.5x (already well-understood, lower novelty)
  - `declining`: 0.2x (rarely worth a deep dive)

### Filters and Cooldowns

Before scoring, exclude:
1. **Cooldown topics**: Any topic where `spotlight_cooldown.on_cooldown = true` (spotlighted in last 4 issues)
2. **Insufficient signal**: Topics with fewer than 3 total mentions across all sources in the last 7 days
3. **Single-source topics**: Topics mentioned by only 1 source tier (not diverse enough for a credible thesis)

### Fallback: Synthesis Mode

If no topic scores above the minimum threshold (define a configurable threshold, suggest starting at 0.5):

1. Don't force a weak Spotlight
2. Instead, select the top 3 emerging/debating topics
3. Write to `research_queue` with `mode = 'synthesis'`
4. Include context for all 3 topics in `context_payload`
5. The Research Agent will connect these into a landscape thesis

### Context Payload

When writing to `research_queue`, include everything the Research Agent needs:

```json
{
  "topic_id": "mcp-governance",
  "topic_name": "MCP Protocol Governance",
  "priority_score": 0.82,
  "velocity": 0.7,
  "source_diversity": 0.9,
  "lifecycle_phase": "debating",
  "recent_mentions": [
    {
      "source": "a16z blog",
      "tier": "institutional",
      "title": "...",
      "summary": "...",
      "url": "..."
    },
    {
      "source": "Simon Willison",
      "tier": "thought_leader",
      "title": "...",
      "summary": "...",
      "url": "..."
    }
  ],
  "contrarian_signals": [
    "Willison raised concerns about X while a16z is bullish"
  ],
  "related_topics": ["agent-interop", "tool-calling-standards"],
  "last_spotlighted": null
}
```

### Integration with Analyst Cycle

This runs at the END of the Analyst's normal scan cycle:

```
1. Analyst completes normal scan (existing behavior)
2. Analyst runs topic lifecycle updates (existing behavior)
3. NEW: Analyst runs Spotlight selection heuristic
4. NEW: If candidate found, write to research_queue
5. NEW: If no candidate, check synthesis fallback
6. NEW: If synthesis, write top 3 topics to research_queue with mode='synthesis'
```

### Configuration
```yaml
spotlight_selection:
  min_score_threshold: 0.5        # below this, trigger synthesis mode
  cooldown_issues: 4              # number of issues before topic can be re-spotlighted
  min_mentions: 3                 # minimum mentions to be eligible
  min_source_tiers: 2             # minimum distinct source tiers
  max_queue_items: 1              # only queue 1 topic per cycle
```

### Acceptance Criteria
- [ ] Scoring formula correctly combines velocity, source diversity, and lifecycle bonus
- [ ] Cooldown filter correctly excludes recently spotlighted topics
- [ ] Minimum signal filters work (mentions count, source tier diversity)
- [ ] Highest scoring topic written to `research_queue` with full context payload
- [ ] Synthesis mode triggers correctly when no topic meets threshold
- [ ] Context payload includes all fields the Research Agent needs
- [ ] Selection runs after normal Analyst cycle without disrupting it
- [ ] Configuration values are tunable without code changes
