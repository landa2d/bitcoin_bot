# 3B — End-to-End Pipeline Wiring

## Phase
Phase 3 — Newsletter Integration

## Parallel/Sequential
**SEQUENTIAL** — Requires 3A (Spotlight template ready)

## Dependencies
- 3A: Spotlight template implemented in Newsletter Agent
- 1D: Radar section implemented
- All Phase 2 components operational

## Prompt

Wire the full AgentPulse pipeline end-to-end so that a single cron trigger produces a complete newsletter with Spotlight + Signals + Radar. This is the integration task that connects all the new components.

### Full Pipeline Execution Flow

```
PHASE 1: DATA COLLECTION (existing + enhanced)
├── T+0h:   Scrapers run (existing sources)
├── T+0h:   Thought leader scrapers run (new, from 1A)
└── T+0.5h: All sources ingested and stored

PHASE 2: ANALYSIS (existing + enhanced)
├── T+1h:   Analyst scan cycle
│   ├── Process all new items (existing)
│   ├── Update topic lifecycle phases (existing)
│   ├── Apply anti-repetition mechanisms (existing)
│   └── NEW: Run Spotlight selection heuristic (2B)
│       ├── Score eligible topics
│       ├── Apply cooldown filters
│       └── Write to research_queue OR trigger synthesis mode
└── T+1h:   Analyst writes research trigger file (2C)

PHASE 3: DEEP RESEARCH (new)
├── T+1.5h: Research Agent triggered
│   ├── Read from research_queue
│   ├── Gather sources (general + thought leader)
│   ├── Run thesis-building chain
│   ├── Store result in spotlight_history
│   └── Mark queue item as completed
└── T+2.5h: Research complete (or timeout at T+3h)

PHASE 4: NEWSLETTER GENERATION (existing + enhanced)
├── T+3h:   Newsletter Agent generates full newsletter
│   ├── Check spotlight_history for current issue → Spotlight section (or skip)
│   ├── Generate Signals section (existing)
│   ├── Generate Radar section from emerging topics (1D)
│   ├── Check for resolved predictions → Scorecard section if available (4C)
│   └── Assemble final newsletter
├── T+3.5h: Newsletter posted to web archive
└── T+3.5h: Newsletter sent via Telegram

PHASE 5: POST-GENERATION (new)
├── T+3.5h: Extract prediction from Spotlight → store in predictions table (4A)
└── T+3.5h: Log issue completion metrics
```

### Cron Schedule Updates

```cron
# Existing (adjust times as needed)
0 6 * * 1    scrapers_general          # Monday 6:00 AM
0 6 * * 1    scrapers_thought_leader   # NEW: Monday 6:00 AM (parallel)
30 6 * * 1   analyst_cycle             # Monday 6:30 AM (includes selection heuristic)

# New
0 7 * * 1    research_agent            # Monday 7:00 AM (triggered by analyst, cron as backup)
0 9 * * 1    newsletter_agent          # Monday 9:00 AM (allows 2h for research)
30 9 * * 1   post_generation_tasks     # Monday 9:30 AM (prediction extraction, metrics)
```

### Orchestration Logic

The pipeline should be resilient to partial failures:

| Component Fails | Impact | Newsletter Still Ships? |
|-----------------|--------|------------------------|
| Thought leader scrapers | Research Agent has less input | Yes — uses general sources |
| Analyst selection heuristic | No Spotlight selected | Yes — without Spotlight |
| Research Agent | No Spotlight generated | Yes — without Spotlight |
| Research Agent timeout | Spotlight incomplete | Yes — without Spotlight |
| Radar query | No emerging topics found | Yes — without Radar section |
| Prediction extraction | No Scorecard data stored | Yes — Scorecard just won't appear in future |

**The newsletter ALWAYS ships.** New features are additive — their failure should never block the core product.

### Docker Compose Updates

Add the Research Agent container to the existing Docker Compose:

```yaml
research-agent:
  build: ./agents/research
  environment:
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_KEY=${SUPABASE_KEY}
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  volumes:
    - ./queue:/queue          # shared queue directory
    - ./data:/data            # shared data directory
  depends_on:
    - analyst                 # only runs after analyst
  restart: unless-stopped
```

### Issue Number Management

Add a simple issue counter:
- Before newsletter generation, increment the issue number
- Pass this number to all components that need it (research_queue, spotlight_history, predictions)
- Store in Supabase or a simple file — just needs to be consistent within a cycle

### Monitoring and Alerting

Add logging checkpoints that make it easy to debug pipeline issues:

```
[PIPELINE] Issue #42 started
[SCRAPER] General: 47 items ingested
[SCRAPER] Thought leader: 12 items ingested
[ANALYST] Scan complete: 15 topics tracked, 3 lifecycle transitions
[ANALYST] Spotlight selected: "MCP Governance" (score: 0.82, mode: spotlight)
[RESEARCH] Started: "MCP Governance"
[RESEARCH] Sources gathered: 18 general, 6 thought_leader, 4 github
[RESEARCH] Thesis generated, stored as spotlight_id: xxx
[NEWSLETTER] Generating issue #42
[NEWSLETTER] Sections: Spotlight ✓, Signals ✓, Radar ✓, Scorecard ✗ (no resolved predictions)
[NEWSLETTER] Issue #42 complete, 1,847 words
[PIPELINE] Issue #42 completed in 3h 22m
```

### Acceptance Criteria
- [ ] Full pipeline runs from scraping to newsletter delivery without manual intervention
- [ ] All new components (thought leader scraping, selection heuristic, Research Agent, Spotlight/Radar formatting) execute in correct order
- [ ] Pipeline completes within the expected time window
- [ ] Partial failures are handled gracefully — newsletter always ships
- [ ] Issue numbering is consistent across all components
- [ ] Docker Compose includes Research Agent container
- [ ] Cron schedule accounts for Research Agent processing time
- [ ] Monitoring logs provide clear visibility into each pipeline stage
- [ ] Telegram delivery works with the new newsletter format
- [ ] Web archive displays the new newsletter format correctly
