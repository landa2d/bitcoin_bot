---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Frontend Redesign
status: planning
stopped_at: Milestone v2.0 — defining requirements
last_updated: "2026-06-04T12:31:37.932Z"
last_activity: 2026-06-04 — Milestone v2.0 (Frontend Redesign) started
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-04)

**Core value:** Synthesis with editorial integrity — autonomous ingestion accelerates output, but every consequential publication is gated by human approval. Silence and homogenization are the failure modes to design against.
**Current focus:** Milestone v2.0 (Frontend Redesign) — a UI-only public-site redesign: persistent 3-tab nav with stateful active state, Source Serif 4 / IBM Plex Mono typography, a single light-mode violet accent (replacing the dark map theme), the Agent Economy as a 2-col grouped grid, and a new "What is AgentPulse" About stub. Defining requirements → roadmap. Backend / pipeline / Supabase / content untouched.

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-06-04 — Milestone v2.0 started

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent decisions affecting current work:

- v2.0 is frontend-only — no backend/pipeline/Supabase/content changes; only the mode toggle's placement + styling move
- Single light-mode violet accent replaces the dark map theme; dark mode deferred this pass
- Source Serif 4 for body/titles, IBM Plex Mono for chrome only; one serif heading style; no monospace body
- Persistent 3-tab nav (Newsletter / Agent Economy / What is AgentPulse) with stateful active state on nested pages; "Map" becomes the Agent Economy tab; back-arrow on every nested page
- Economy map grid uses the canonical 7-block data-source taxonomy, not the mockup's placeholder blocks
- Reuse the v1.0-proven scoped web rebuild (single `agentpulse-web` container) — no new infra
- The mockup (`.planning/docs/agentpulse-redesign-mockup.html`) is a reference for intent, not markup to copy

### Pending Todos

7 carried-forward backend todos in `.planning/todos/pending/` (all v1.0 follow-ups — analyst/governance/intake/research/phase-review). None are in v2.0 (frontend) scope; left unlinked.

### Blockers/Concerns

None for v2.0 start.

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v-next — Negotiation graduation | Promote `negotiation-coordination` to its own block (NEGB-01, NEGB-02) | Deferred — kept separate from v2.0 | 2026-05-26 |
| v-next — Per-block tuning | Threshold overrides per block (TUNE-01..03) | Deferred — kept separate from v2.0 | 2026-05-26 |
| v-next — EU AI Act integration | Wire `eu_ai_act` tracker into regulation-legal block (EUAI-01, EUAI-02) | Deferred — kept separate from v2.0 | 2026-05-26 |
| Design pass | Bespoke typography / page chrome (DSGN-01..03) | Being addressed by v2.0 Frontend Redesign | 2026-05-26 |

### Acknowledged at v1.0 close (2026-06-04)

14 open items carried forward at v1.0 close (not blockers — manual live-smoke verification + known follow-up todos): UAT/verification for phases 02/04/09/10 are partial/human_needed; 7 follow-up todos in `.planning/todos/pending/`. Full record in MILESTONES.md + RETROSPECTIVE.md.

## Operator Next Steps

- Defining v2.0 requirements → roadmap (in progress via /gsd-new-milestone)
