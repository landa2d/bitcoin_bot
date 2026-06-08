---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Agent Economy Content
status: executing
stopped_at: Phase 16 complete (verified PASSED)
last_updated: "2026-06-08T17:54:31.047Z"
last_activity: 2026-06-08 -- Phase 16 executed + verified
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 5
  completed_plans: 5
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-08 after v2.0 milestone)

**Core value:** Synthesis with editorial integrity — autonomous ingestion accelerates output, but every consequential publication is gated by human approval. Silence and homogenization are the failure modes to design against.
**Current focus:** Phase 16 complete (content load — LOAD-01/02/03 verified PASSED, 8 bodies loaded unpublished, zero visitor change); Phase 17 Cross-link Wiring & Preview next.

## Current Position

Phase: 17 — Cross-link Wiring & Preview (next to plan)
Plan: Not started
Status: Phase 16 complete (verified) — ready to plan Phase 17
Last activity: 2026-06-08 -- Phase 16 executed + verified (8 canonical bodies loaded as unpublished drafts)
Next: `/gsd-discuss-phase 17`

## Roadmap (v2.1 — Phases 15–18)

| Phase | Goal | Requirements |
|-------|------|--------------|
| 15. Inventory & Roster Reconciliation | Document the live storage/serve contract + verify the maturity enum + resolve the per-slug roster diff before any write (operator-approved plan) | INV-01, INV-02, ROST-01 |
| 16. Content Load (unpublished) | Load all 8 canonical bodies into `economy_map` as unsorted/unpublished, fail-loud on missing fields, correct existing rows via the rewrite path — zero visitor-facing change | LOAD-01, LOAD-02, LOAD-03 |
| 17. Cross-link Wiring & Preview | Make every `#/map/<slug>` cross-block + hub→block link resolve; verify the loaded-but-unpublished content end-to-end on a non-published preview route; hub renders as `#/map` landing (single block list) | LINK-01, PREV-01, HUB-01 |
| 18. Gated Batch Publish | Publish live via the existing atomic publish RPC in ONE operator-approved batch (web-only scoped deploy) | PUB-01 |

**Coverage:** 10/10 v2.1 requirements mapped — no orphans, no duplicates.

These are backend/content/data phases (NOT `ui_phase`) — the v2.0 renderer already displays hub + blocks; this milestone fills it with content. Standing constraints apply: direct PostgREST + `Accept-Profile` (no `.in_()`); append-only trigger → canonical-body-rewrite (never raw UPDATE); fail-loud on missing fields; web-only scoped deploy; no pipeline / proxy / agent-service changes.

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. v2.1 open items to resolve in discuss/plan (per EXECUTION_BRIEF.md §5 — do NOT decide unilaterally):

- **Roster diff vs the live map** (ROST-01, Phase 15): docs ADD `negotiation-coordination` (v2.0-deferred NEGB-01/02), OMIT the live `regulation-legal` (FRAME tier), and use 2 tiers (substrate/behavior) vs the live 3 (substrate/behavior/frame). Decide first-publish vs body-rewrite vs retire-block per slug BEFORE any load.
- **Maturity enum** (INV-02, Phase 15): verify the live enum against the three doc values (`building` / `contested` / `nascent`); surface any mismatch explicitly — never silently remap.
- **Hub block list as cards (preferred) vs prose links** (HUB-01, Phase 17): confirm in the plan; block list appears once, not duplicated as both prose + cards.
- **Distinct visual treatment for `nascent` blocks** beyond the pill — open item; default is pill-only unless discuss decides otherwise.

Standing v1.0/v2.0 decisions still in force (PROJECT.md Key Decisions table): append-only `block_body_versions` + `timeline_entries`; schema isolation via `economy_map` + direct PostgREST; sentinels flag-never-block; synthesis via `llm-proxy:8200`; scoped `agentpulse-web` rebuild (no new infra).

### Pending Todos

7 carried-forward backend todos in `.planning/todos/pending/` (all v1.0 follow-ups — analyst/governance/intake/research/phase-review). Out of v2.1 (content) scope; parked in the ROADMAP Backlog.

### Blockers/Concerns

None for v2.1 start. Source content (`.planning/docs/00-hub.md … 07-*.md` + `EXECUTION_BRIEF.md`) is staged and present.

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v-next — Per-block tuning | Threshold overrides per block (TUNE-01..03) | Deferred — kept separate from content milestone | 2026-05-26 |
| v-next — EU AI Act integration | Wire `eu_ai_act` tracker into regulation-legal block (EUAI-01, EUAI-02) | Deferred — out of v2.1 content scope | 2026-05-26 |
| v-next — Dark mode | Dark-mode variant of the light palette (DARK-01) | Deferred — light mode shipped v2.0 | 2026-06-04 |
| v-next — Richer About | Pipeline/architecture diagram on About (ABOUT-02) | Deferred — About shipped as a stub in v2.0 | 2026-06-04 |
| v2.1 — Timeline content | Manual timeline authoring — bodies publish now with possibly-empty timelines; intake fills weekly | Deferred — future requirement, not this milestone | 2026-06-08 |

Note: `negotiation-coordination` graduation (NEGB-01/02), previously deferred from v2.0, re-enters scope under ROST-01 (Phase 15) — its first-publish vs body-rewrite vs retire disposition is decided there.

### Acknowledged at v2.0 close (2026-06-08)

10 open items acknowledged and deferred at v2.0 milestone close (none are code gaps — v2.0 is deployed live + verified in code). The browser/perceptual/editorial items are testable on the LIVE site; the backend todos are out of content-milestone scope:

| Category | Item | Status |
|----------|------|--------|
| UAT (browser) | Phase 13 HUMAN-UAT — 6 pending map scenarios | Deferred — operator browser walk on live site |
| UAT (browser) | Phase 14 HUMAN-UAT — 4 pending (About render / nav active / POLISH perceptual / copy sign-off) | Deferred — operator browser walk on live site |
| Verification | Phase 13 + Phase 14 VERIFICATION `human_needed` (visual only; 10/10 + 7/7 verified in code) | Deferred — clears when browser UAT passes |
| Todo (backend) | analyst predictions title-expire bug (P2) | Deferred — v1.0 backend, out of content scope |
| Todo (backend) | soft-cap allow-negative hardening (P5) | Deferred — v1.0 governance, out of content scope |
| Todo (backend) | pay-endpoint 500 activation E2E (P2; RPC root-cause fixed m037) | Deferred — v1.0 backend, out of content scope |
| Todo (backend) | phase-05 review follow-ups WR02/04/05 (P4) | Deferred — v1.0 intake, out of content scope |
| Todo (backend) | research trigger file permissions (P4) | Deferred — v1.0 research, out of content scope |

### Acknowledged at v1.0 close (2026-06-04)

14 open items carried forward at v1.0 close (not blockers — manual live-smoke verification + known follow-up todos): UAT/verification for phases 02/04/09/10 are partial/human_needed; 7 follow-up todos in `.planning/todos/pending/`. Full record in MILESTONES.md + RETROSPECTIVE.md.

## Session Continuity

Last session: 2026-06-08T15:10:10.826Z
Stopped at: Phase 16 context gathered
Resume file: .planning/phases/16-content-load-unpublished/16-CONTEXT.md
Next: `/gsd-plan-phase 16`
Note: root `.planning/.continue-here.md` is a STALE v1.0 leftover (Phase 6→7, 2026-05-30) — not the current checkpoint; safe to delete.

## Operator Next Steps

- Plan the next v2.1 phase: `/gsd-plan-phase 16` (Content Load — unpublished). Phase 15's `15-APPROVAL.md` is the read-before-write gate clearing Phase 16's `economy_map` writes.
- Phase 16 executes from the locked docs: load 8 canonical bodies unpublished (`building→emerging` on the substrate trio per D-01), insert `negotiation-coordination` as a new block, apply the D-03 collision-free sort_order reshuffle, and apply the D-04 Option-A hub-tier migration (relax tier CHECK + `'hub'` sentinel).

### Advisory follow-ups (non-blocking, from v2.0 14-REVIEW.md)

- WR-01: dead `.about-lede` rule in `style-base.css` (its only consumer was deleted in v2.0) — trivial cleanup, fold into a future commit.
- IN-03: the `.ad` class name can be hit by ad-blocker cosmetic filters (could hide agent role text) — consider a rename if observed.
- Security: no `14-SECURITY.md` (threats all dispositioned "accept" — static HTML/CSS); `/gsd-secure-phase 14` available if you want the formal record.

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 11 P01 | 8min | 3 tasks | 3 files |
| Phase 11 P02 | 2min | 3 tasks | 3 files |
| Phase 12 P01 | 6min | 3 tasks | 1 files |
| Phase 12 P02 | 4 min | 3 tasks | 2 files |
| Phase 13 P01 | 4min | 3 tasks | 3 files |
| Phase 13 P02 | 6min | 3 tasks | 4 files |
| Phase 14 P01 | 4min | 2 tasks | 2 files |
| Phase 14 P02 | 6min | 2 tasks | 1 file |
