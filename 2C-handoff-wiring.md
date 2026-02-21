# 2C — Analyst → Research Agent Handoff Wiring

## Phase
Phase 2 — Research Agent Core

## Parallel/Sequential
**SEQUENTIAL** — Requires 2A (Research Agent built) and 2B (selection logic built)

## Dependencies
- 2A: Research Agent processor must be operational
- 2B: Selection heuristic must be writing to `research_queue`

## Prompt

Wire the Analyst → Research Agent handoff in AgentPulse. After the Analyst completes its cycle and writes a topic to `research_queue`, the Research Agent should be triggered to process it.

### Trigger Mechanism

Use the existing file-based queue pattern for triggering:

```
1. Analyst writes topic to `research_queue` table
2. Analyst writes trigger file to shared queue directory (e.g., /queue/research-trigger-{timestamp}.json)
3. Research Agent processor watches for trigger files
4. On trigger: Research Agent reads from `research_queue`, processes, writes to `spotlight_history`
5. Research Agent removes trigger file on completion
```

### Trigger File Contents

```json
{
  "trigger_type": "research_request",
  "research_queue_id": "uuid-from-database",
  "topic_name": "MCP Protocol Governance",
  "mode": "spotlight",
  "triggered_at": "2025-02-21T10:00:00Z",
  "triggered_by": "analyst"
}
```

### Timing Considerations

The pipeline timing for a newsletter cycle should be:

```
T+0h:    Scrapers run (existing)
T+1h:    Analyst scan + lifecycle update + Spotlight selection (existing + new)
T+1.5h:  Research Agent deep dive (NEW — triggered by Analyst)
T+2.5h:  Newsletter Agent generates full newsletter (existing, now with Spotlight)
T+3h:    Newsletter ready for review/send
```

Adjust cron schedules to accommodate the Research Agent's processing time (budget ~60 minutes for source gathering + thesis generation).

### Pipeline Resilience

1. **Research Agent timeout**: If the Research Agent hasn't completed within 90 minutes of trigger, the Newsletter Agent should proceed without a Spotlight. The newsletter should still work — just without the deep dive for that issue.
2. **Missing trigger**: If the Analyst finds no suitable topic (and synthesis mode also doesn't trigger), no trigger file is written. The Newsletter Agent should check `spotlight_history` for the current issue number — if no entry exists, skip the Spotlight section gracefully.
3. **Duplicate triggers**: If a trigger file already exists when the Analyst tries to write one (edge case), skip — don't queue duplicate research.

### Monitoring

Add logging at each handoff point:
- Analyst: "Spotlight topic selected: {topic_name}, score: {score}, mode: {mode}"
- Analyst: "Research trigger written: {queue_id}"
- Research Agent: "Trigger received, starting research: {topic_name}"
- Research Agent: "Research complete, stored in spotlight_history: {spotlight_id}"
- Research Agent: "Research failed: {error}" (if applicable)

### Implementation Notes
- Follow the same Docker networking patterns as existing agent communication
- The Research Agent container should be able to access both Supabase and the thought leader source data
- Consider adding a simple health check endpoint or log for the Research Agent so you can verify it's running

### Acceptance Criteria
- [ ] Analyst trigger correctly starts Research Agent processing
- [ ] Trigger file written and cleaned up properly
- [ ] Research Agent reads queue and processes the correct topic
- [ ] Pipeline timing allows sufficient time for research before newsletter generation
- [ ] Newsletter Agent gracefully handles missing Spotlight (timeout/failure case)
- [ ] No duplicate triggers in edge cases
- [ ] Logging provides visibility into the full handoff chain
- [ ] End-to-end: Analyst selects → Research Agent processes → result available for Newsletter Agent
