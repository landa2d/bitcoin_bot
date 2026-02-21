# AgentPulse Enhancement — Execution Plan

## Objective
Transform AgentPulse from a summary-focused newsletter into a conviction-driven analysis publication with deep Spotlight sections, trend-based rotation, and prediction accountability.

## Target Newsletter Structure
1. **Spotlight** — One conviction-driven thesis (~400 words), with prediction, evidence, counter-argument
2. **Signals** — 5-7 curated developments with brief analysis
3. **Radar** — 3-4 emerging topics to watch
4. **Scorecard** (periodic) — Revisiting past Spotlight predictions

## Architecture Changes
- New standalone **Research Agent** focused on thesis-building and deep sourcing
- New **thought leader source tier** feeding the Research Agent
- **Prediction tracking** in Supabase for Scorecard generation
- Enhanced **Analyst Agent** with Spotlight selection heuristic
- Enhanced **Newsletter Agent** with Spotlight + Radar + Scorecard templates

---

## Execution Timeline

```
Week 1:  Phase 1 — Foundation (all parallel)
         ├── 1A: Thought leader source ingestion
         ├── 1B: Supabase schema additions
         ├── 1C: Research Agent system prompt design
         └── 1D: Radar section for Newsletter Agent

Week 2:  Phase 2 — Research Agent Core (sequential)
         ├── 2A: Build Research Agent processor
         ├── 2B: Analyst selection heuristic
         ├── 2C: Analyst → Research Agent handoff
         └── 2D: Test with 3-5 topics (iterate on prompt)

Week 3:  Phase 3 + Phase 4 start (mixed)
         ├── 3A: Spotlight template in Newsletter Agent
         ├── 3B: End-to-end pipeline wiring
         ├── 4A: Prediction storage (parallel with 3A/3B)
         └── 4B: Prediction monitoring (parallel with 3A/3B)

Week 4:  Final integration
         ├── 3C: Generate test newsletters, review quality
         ├── 4C: Scorecard generation
         └── Ship first enhanced newsletter
```

## Dependency Graph

```
1A ─┐
1B ─┼──→ 2A ──→ 2C ──→ 2D ──→ 3A ──→ 3B ──→ 3C
1C ─┘          ↗              ↘
1D (independent)    2B ────────┘   4A ──→ 4B ──→ 4C
```

## Prompt Files
- `phase-1/1A-source-ingestion.md`
- `phase-1/1B-supabase-schema.md`
- `phase-1/1C-research-agent-prompt.md`
- `phase-1/1D-radar-section.md`
- `phase-2/2A-research-agent-core.md`
- `phase-2/2B-selection-heuristic.md`
- `phase-2/2C-handoff-wiring.md`
- `phase-2/2D-testing-iteration.md`
- `phase-3/3A-spotlight-template.md`
- `phase-3/3B-end-to-end-pipeline.md`
- `phase-3/3C-test-newsletters.md`
- `phase-4/4A-prediction-storage.md`
- `phase-4/4B-prediction-monitoring.md`
- `phase-4/4C-scorecard-generation.md`
