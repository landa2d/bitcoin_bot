# Roadmap: AgentPulse — The Agent Economy (Living Reference Articles)

## Milestones

- ✅ **v1.0 Agent Economy Map** — Phases 1–10 + 4.1 (shipped 2026-06-04) — full details: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Frontend Redesign** — Phases 11–14 (shipped 2026-06-08) — full details: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Agent Economy Content** — Phases 15–18 (shipped 2026-06-09) — full details: [`milestones/v2.1-ROADMAP.md`](milestones/v2.1-ROADMAP.md)
- ✅ **v2.2 Landing Redesign + Signals Feed** — Phases 19–25 (shipped 2026-06-19) — full details: [`milestones/v2.2-ROADMAP.md`](milestones/v2.2-ROADMAP.md)

_No active milestone — run `/gsd-new-milestone` to start the next. Phase numbering continues from 25._

## Phases

<details>
<summary>✅ v1.0 Agent Economy Map (Phases 1–10 + 4.1) — SHIPPED 2026-06-04 — 11 phases, 29 plans</summary>

- [x] Phase 1: Render-Stack Diagnostic (1/1) — completed 2026-05-26
- [x] Phase 2: `economy_map` Schema + Seven-Block Seed (2/2) — completed 2026-05-27
- [x] Phase 3: Design Tokens (3/3) — completed 2026-05-27
- [x] Phase 4: Hub, Block, and Status Renderer (6/6) — completed 2026-05-28
- [x] Phase 4.1: Prod↔Main Reconciliation + LLM-Proxy Governance Migration (3/3) — completed 2026-05-28
- [x] Phase 5: Intake Classifier + `unsorted` Handling (3/3) — completed 2026-05-28
- [x] Phase 6: Telegram Read-Only Scaffolding (2/2) — completed 2026-05-30
- [x] Phase 7: Synthesis Loop Core (2/2) — completed 2026-06-01
- [x] Phase 8: Validation Sentinels (2/2) — completed 2026-06-02
- [x] Phase 9: Gated Publishing + Approval Commands (2/2) — completed 2026-06-03
- [x] Phase 10: Operator Write Commands (3/3) — completed 2026-06-04

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).

</details>

<details>
<summary>✅ v2.0 Frontend Redesign (Phases 11–14) — SHIPPED 2026-06-08 — 4 phases, 8 plans</summary>

UI-only redesign of the public `aiagentspulse.com` SPA: persistent stateful 3-tab nav shell, editorial Source Serif 4 / IBM Plex Mono typography, single light-mode violet accent (replacing the dark map theme), the Agent Economy as a responsive grouped card grid, a Newsletter-only mode toggle, and a "What is AgentPulse" About page. Frontend-only — no backend/pipeline/Supabase/content changes. Deployed live via the scoped `agentpulse-web` rebuild.

- [x] Phase 11: Design System + Nav Shell (2/2) — completed 2026-06-04 (NAV-01..04, TYPE-01..03, COLOR-01..02)
- [x] Phase 12: Newsletter Section Restyle (2/2) — completed 2026-06-04 (TGL-01, TGL-02)
- [x] Phase 13: Agent Economy Grid (2/2) — completed 2026-06-05 (MAP-01..04)
- [x] Phase 14: About Stub + Polish Pass (2/2) — completed 2026-06-08 (ABOUT-01, POLISH-01)

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md).

</details>

<details>
<summary>✅ v2.1 Agent Economy Content (Phases 15–18) — SHIPPED 2026-06-09 — 4 phases, 10 plans</summary>

Filled the v2.0 grid with real editorial content: loaded the hub `agent-economy` + 7 block bodies into `economy_map` as unpublished (migration 043 + a standalone PostgREST loader), wired every `#/map/<slug>` cross-link, verified on a flag-gated preview route, then published all 8 in-scope bodies live in ONE operator-approved batch via the atomic `publish_block_version` RPC. Content-only — no UI redesign, no pipeline/proxy/agent-service changes. `regulation-legal` kept deferred.

- [x] Phase 15: Inventory & Roster Reconciliation (2/2) — completed 2026-06-08 (INV-01, INV-02, ROST-01)
- [x] Phase 16: Content Load (unpublished) (3/3) — completed 2026-06-08 (LOAD-01, LOAD-02, LOAD-03)
- [x] Phase 17: Cross-link Wiring & Preview (2/2) — completed 2026-06-09 (LINK-01, PREV-01, HUB-01)
- [x] Phase 18: Gated Batch Publish (3/3) — completed 2026-06-09 (PUB-01)

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v2.1-ROADMAP.md`](milestones/v2.1-ROADMAP.md).

</details>

<details>
<summary>✅ v2.2 Landing Redesign + Signals Feed (Phases 19–25) — SHIPPED 2026-06-19 — 7 phases, 17 plans</summary>

Re-skinned the public `aiagentspulse.com` SPA to the new editorial mockup — the four top-level sections (newsletter / signals / agent-economy / about) merged into ONE single-scroll landing with an `IntersectionObserver` scroll-spy nav, while individual editions (`#/edition/<n>`) and block pages (`#/map/<slug>`) stayed deep-linkable detail routes — fixed the four live-site defects the redesign brief called out, and added a new tier-1 Signals feed. NOT frontend-only: Phase 19 touched the newsletter write-path (+ a confirm-and-close storage scan, no backfill needed) and Phase 24 added the milestone's one Supabase migration (a security-definer anon `signals_feed` view over tier-1 `source_posts`). Deployed live via gated, drift-checked, operator-approved scoped `web` rebuilds throughout.

- [x] Phase 19: Smart-Quote / Apostrophe Corruption Fix (2/2) — completed 2026-06-10 (QUOTE-01, QUOTE-02)
- [x] Phase 20: Width Tokens & Centering Foundation (2/2) — completed 2026-06-11 (WIDTH-01, RHYTHM-01)
- [x] Phase 21: Single-Scroll Landing + Scroll-Spy Nav (2/2) — completed 2026-06-11 (SCROLL-01, SCROLL-02)
- [x] Phase 22: Per-Section Visual Fixes (4/4) — completed 2026-06-12 (HEAD-01, GRID-01, GRID-02, AGENTS-01)
- [x] Phase 23: Distinct Newsletter Excerpts (2/2) — completed 2026-06-16 (EXCERPT-01)
- [x] Phase 24: Signals Section (3/3) — completed 2026-06-17 (SIGNAL-01..04)
- [x] Phase 25: Responsive & Accessibility Pass (2/2) — completed 2026-06-19 (RESP-01, A11Y-01)

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v2.2-ROADMAP.md`](milestones/v2.2-ROADMAP.md).

</details>

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Render-Stack Diagnostic | v1.0 | 1/1 | Complete | 2026-05-26 |
| 2. economy_map Schema + Seed | v1.0 | 2/2 | Complete | 2026-05-27 |
| 3. Design Tokens | v1.0 | 3/3 | Complete | 2026-05-27 |
| 4. Hub/Block/Status Renderer | v1.0 | 6/6 | Complete | 2026-05-28 |
| 4.1. Prod Reconciliation + Governance | v1.0 | 3/3 | Complete | 2026-05-28 |
| 5. Intake Classifier | v1.0 | 3/3 | Complete | 2026-05-28 |
| 6. Telegram Read-Only Scaffolding | v1.0 | 2/2 | Complete | 2026-05-30 |
| 7. Synthesis Loop Core | v1.0 | 2/2 | Complete | 2026-06-01 |
| 8. Validation Sentinels | v1.0 | 2/2 | Complete | 2026-06-02 |
| 9. Gated Publishing + Approval | v1.0 | 2/2 | Complete | 2026-06-03 |
| 10. Operator Write Commands | v1.0 | 3/3 | Complete | 2026-06-04 |
| 11. Design System + Nav Shell | v2.0 | 2/2 | Complete | 2026-06-04 |
| 12. Newsletter Section Restyle | v2.0 | 2/2 | Complete | 2026-06-04 |
| 13. Agent Economy Grid | v2.0 | 2/2 | Complete | 2026-06-05 |
| 14. About Stub + Polish Pass | v2.0 | 2/2 | Complete | 2026-06-08 |
| 15. Inventory & Roster Reconciliation | v2.1 | 2/2 | Complete | 2026-06-08 |
| 16. Content Load (unpublished) | v2.1 | 3/3 | Complete | 2026-06-08 |
| 17. Cross-link Wiring & Preview | v2.1 | 2/2 | Complete | 2026-06-09 |
| 18. Gated Batch Publish | v2.1 | 3/3 | Complete | 2026-06-09 |
| 19. Smart-Quote / Apostrophe Corruption Fix | v2.2 | 2/2 | Complete | 2026-06-10 |
| 20. Width Tokens & Centering Foundation | v2.2 | 2/2 | Complete | 2026-06-11 |
| 21. Single-Scroll Landing + Scroll-Spy Nav | v2.2 | 2/2 | Complete | 2026-06-11 |
| 22. Per-Section Visual Fixes | v2.2 | 4/4 | Complete | 2026-06-12 |
| 23. Distinct Newsletter Excerpts | v2.2 | 2/2 | Complete | 2026-06-16 |
| 24. Signals Section | v2.2 | 3/3 | Complete | 2026-06-17 |
| 25. Responsive & Accessibility Pass | v2.2 | 2/2 | Complete | 2026-06-19 |

## Backlog

Parked for a future milestone — **not scheduled, not for now**. Surfaces at next `/gsd-new-milestone` planning. Source-of-truth detail lives in `.planning/todos/pending/`.

### v2.2 future requirements (deferred this milestone)

Tracked in `.planning/milestones/v2.2-REQUIREMENTS.md` → Future Requirements.

- **EXCERPT-F1** — stored `summary` field on `newsletters`, emitted by the Newsletter agent at generation time (the cleaner long-term excerpt path; deferred in favor of strip-at-render — touches schema + pipeline + backfill).
- **SIGNAL-F1** — a full Signals archive page behind the "view all signals" affordance (if the capped feed proves insufficient).
- **THEME-F1** — dark-mode variant of the light palette (DARK-01, carried from v2.0).
- **THEME-F2** — richer About page with a pipeline/architecture diagram (ABOUT-02, carried from v2.0).

### Backend follow-ups (candidate: a backend-hardening milestone)

Carried forward from v1.0; out of v2.0/v2.1/v2.2 (frontend + scoped-touch) scope.

- analyst predictions `title` expire bug (P2)
- soft-cap allow-negative hardening (P5)
- pay-endpoint 500 activation E2E — RPC root-cause fixed in migration 037 (P2)
- phase-05 intake-classifier review follow-ups WR02/04/05 (P4)
- research trigger file permissions (P4)
