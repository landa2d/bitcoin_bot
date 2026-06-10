---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Landing Redesign + Signals Feed
status: executing
stopped_at: "Completed 19-02-PLAN.md (confirm-and-close: empty affected set; operator approved Close+rebuild; write-path guard live). Phase 19 complete (2/2)."
last_updated: "2026-06-10T15:02:52Z"
last_activity: 2026-06-10
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 2
  completed_plans: 2
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-10 — Current Milestone v2.2)

**Core value:** Synthesis with editorial integrity — autonomous ingestion accelerates output, but every consequential publication is gated by human approval. Silence and homogenization are the failure modes to design against.
**Current focus:** Phase 19 complete — next up Phase 20 (Width Tokens & Centering Foundation)

## Current Position

Phase: 19 (smart-quote-apostrophe-corruption-fix) — COMPLETE (2/2 plans)
Plan: 2 of 2 — complete
Status: Phase 19 complete. QUOTE-01 + QUOTE-02 satisfied. Storage proven clean (both Plan 01 and Plan 02's independent live scan); fail-loud write-path guard live in the recreated newsletter container; 17/17 regression tests pass; no backfill UPDATE needed (empty affected set, confirm-and-close). Next: plan Phase 20 (Width Tokens & Centering Foundation).
Last activity: 2026-06-10 -- Plan 19-02 executed: independent scan of 43 newsletter rows reproduced storage-clean (0 corrupt corpus-wide), operator approved "Close + rebuild newsletter", scoped newsletter rebuild shipped the Plan 01 guard live (web untouched, no DB mutation)

## Roadmap (v2.2 — Phases 19–24)

| Phase | Goal | Requirements |
|-------|------|--------------|
| 19. Smart-Quote / Apostrophe Corruption Fix | Root-cause + fix-forward the apostrophe→straight-quote corruption (write path / stored markdown), scoped reviewed backfill of existing editions, regression-tested | QUOTE-01, QUOTE-02 |
| 20. Width Tokens & Centering Foundation | Two coexisting both-centered max-widths (`--measure` prose / `--wide` grids) kill the dead left gutter; token-only color + section-rhythm baseline everything else sits on | WIDTH-01, RHYTHM-01 |
| 21. Per-Route Visual Fixes | Three non-conflicting per-route fixes: edition-header de-dup, map 3-col grid + maturity legend, About pipeline-vs-supporting agent grid + approval callout | HEAD-01, GRID-01, GRID-02, AGENTS-01 |
| 22. Distinct Newsletter Excerpts | Strip the boilerplate intro at render + show the first distinct sentence in the indexed-row archive format — no schema change | EXCERPT-01 |
| 23. Signals Feed | New `#/signals` route + nav tab, tier-1 `source_posts` newest-first (capped, safe external links), gated on the one Supabase migration (anon tier-1 RLS on `source_posts`, fail-loud) | SIGNAL-01, SIGNAL-02, SIGNAL-03, SIGNAL-04 |
| 24. Responsive & Accessibility Pass | Holistic cross-cutting verify: grids/rows reflow (3→2→1, nav condenses, rows stack), visible `:focus-visible`, `prefers-reduced-motion`, real `<a>` links | RESP-01, A11Y-01 |

**Coverage:** 15/15 v2.2 requirements mapped — no orphans, no duplicates.

**Phase nature:** Mostly `ui_phase` (Phases 20–24 touch `docker/web/site/` — `app.js`, `style-base.css`, `style-shared.css`; the other CSS files are legacy/unloaded; `marked.js` renders markdown, no typographer). Two phases reach the backend and are deliberately isolated from the CSS work: Phase 19 (content write-path + scoped data backfill) and Phase 23 (the milestone's only Supabase migration — anon tier-1 RLS on `source_posts`). Ordering is low-to-high risk, each phase independently shippable.

**Standing constraints apply throughout:** keep separate routes (not single-scroll); all LLM via `llm-proxy:8200`; isolated-schema / `economy_map` access via direct PostgREST + `Accept-Profile` (never supabase-py `.in_()`); append-only — corrections via the canonical-body-rewrite path, never a raw UPDATE; fail-loud on missing fields; the apostrophe backfill is a scoped reviewed UPDATE shown before/after on ONE edition first, never a blind find-replace; deploy via prod↔main drift check → branch → `/diff` per work group → scoped `docker compose up -d --build web` (NO `--delete`) → operator approval. Worktree-unsafe steps (scoped web rebuild, the Phase 23 migration apply) are orchestrator-owned from the main tree, never a worktree executor.

## Accumulated Context

### Decisions

Operator decisions locked at v2.2 start (2026-06-10, in PROJECT.md Current Milestone):

- **Keep separate routes** (NOT single-scroll) — apply width tokens / centering / visual fixes per-route; preserve v2.0's persistent 3-tab nav shell (add a Signals tab); deep-linkable editions & block pages + SEO retained. The mockup is intent reference, not markup to copy.
- **Signals = its own route + tab** (`#/signals`).
- **Excerpts = strip-at-render** (no schema / pipeline change; the stored-`summary` path is the deferred EXCERPT-F1).
- **No domain research** — the 7-task brief + mockup specify the work on an existing, well-understood codebase.

Open items to resolve in discuss/plan (do NOT decide unilaterally):

- **Phase 19 root cause** (QUOTE-01): is the corruption at storage (write path) or render? Query raw `body_md` bytes around an apostrophe FIRST; the fix follows from the finding (render-layer if data is clean; write-path-first-then-backfill if corrupt). `marked.js` has no typographer, so a render-layer smartquote transform is unlikely — diagnose stored bytes before choosing.
- **Phase 19 backfill scope** (QUOTE-01): which editions are affected, and the exact before/after on ONE edition shown for operator approval before any batch UPDATE.
- **Phase 23 RLS shape** (SIGNAL-04): the precise tier-1 predicate for the read-only anon SELECT policy on `source_posts` (which tier column/value defines tier-1), and the migration number (next after 043).
- **Phase 22 distinct-sentence rule** (EXCERPT-01): the exact boilerplate-intro pattern to strip and the first-distinct-sentence heuristic (verified on editions 29 vs 30).

Standing v1.0/v2.0/v2.1 decisions still in force (PROJECT.md Key Decisions table): append-only `block_body_versions` + `timeline_entries`; schema isolation via direct PostgREST + `Accept-Profile`; sentinels flag-never-block; synthesis via `llm-proxy:8200`; scoped `agentpulse-web` rebuild (no new infra); single light-mode violet accent (dark mode deferred); Source Serif 4 body + IBM Plex Mono chrome.

- [Phase 19]: stored newsletter corpus is CLEAN (zero mid-word U+0022 corpus-wide); apostrophe corruption is NOT a write-path/storage defect. Fix-forward = fail-loud no-op-on-clean guard nl.normalize_apostrophe_corruption at the shared save_newsletter insert; Plan 02 backfill has no corrupt data to UPDATE (confirm-and-close, reuse the same function).
- [Phase 19 / Plan 02]: CONFIRM-AND-CLOSE executed. Independent live read-only scan of all 43 newsletter rows reproduced the storage-clean finding (0 corrupt corpus-wide; canonical repair a no-op on edition 30); affected-edition set EMPTY → NO scoped UPDATE (an empty WHERE set means a no-op or the spine-forbidden table-wide find-replace — both rejected). Operator chose "Close + rebuild newsletter" at the blocking-human gate. Scoped `docker compose up -d --build newsletter` recreated agentpulse-newsletter (healthy, guard live in container); web NOT rebuilt (renderer unchanged); no DB mutation. QUOTE-01 + QUOTE-02 satisfied; Phase 19 closed.

### Pending Todos

7 carried-forward backend todos in `.planning/todos/pending/` (all v1.0 follow-ups — analyst/governance/intake/research/phase-review). Out of v2.2 scope; parked in the ROADMAP Backlog (candidate backend-hardening milestone).

### Blockers/Concerns

None for v2.2 start. Source brief (`.planning/docs/REDESIGN_CC_BRIEF.md`, 7 work groups) + the visual mockup (`agentpulse-redesign (1).html`) are present and staged. Frontend files known: `docker/web/site/app.js`, `style-base.css`, `style-shared.css`; migrations live in `supabase/migrations/` (highest is 043).

Carry-over advisories (non-blocking): a PRE-EXISTING service_role leak in tracked `.claude/settings.local.json` (logged DEF-17-01 in v2.1 — recommend key rotation + scrub + gitignore); dead `.about-lede` rule in `style-base.css` (trivial cleanup, fold into a future commit — likely touched in Phase 21/24).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260609-fpc | Fix duplicate block title on `#/map/<slug>` — `renderBlock` strips the body's leading `# <Title>` H1 (guarded by trimmed/case-insensitive title match) so the title renders once; deployed live via scoped `agentpulse-web` rebuild | 2026-06-09 | 19115b2 | [260609-fpc-fix-duplicate-block-title-on-map-slug](./quick/260609-fpc-fix-duplicate-block-title-on-map-slug/) |
| 260609-ivq | Map page rendering fixes (3): site-wide prose paragraph rhythm via `--space-lg` incl. `.hub-storyline p`; hub duplicate-title de-dup via `stripLeadingTitleH1` shared helper; maturity-pill/nav overlap fixed by re-scoping the bare `header{position:sticky}` rule to `body > header`. Deployed live via scoped `agentpulse-web` rebuild | 2026-06-09 | 9e350f3 | [260609-ivq-map-page-rendering-fixes-hub-duplicate-t](./quick/260609-ivq-map-page-rendering-fixes-hub-duplicate-t/) |

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v2.2 future — Excerpts | Stored `summary` field on `newsletters`, agent-emitted (EXCERPT-F1) | Deferred — strip-at-render chosen this milestone | 2026-06-10 |
| v2.2 future — Signals | Full Signals archive page behind "view all signals" (SIGNAL-F1) | Deferred — capped feed ships first | 2026-06-10 |
| v2.2 future — Layout | Single-page scroll + scroll-spy nav (WIDTH-F1) | Deferred — separate routes chosen (SEO / deep-linking / lower risk) | 2026-06-10 |
| v-next — Dark mode | Dark-mode variant of the light palette (DARK-01 / THEME-F1) | Deferred — light mode shipped v2.0 | 2026-06-04 |
| v-next — Richer About | Pipeline/architecture diagram on About (ABOUT-02 / THEME-F2) | Deferred — About ships as the v2.0 stub + agent-grid fix only | 2026-06-04 |
| v-next — Per-block tuning | Threshold overrides per block (TUNE-01..03) | Deferred — kept separate from UI milestones | 2026-05-26 |
| v-next — EU AI Act integration | Wire `eu_ai_act` tracker into regulation-legal block (EUAI-01, EUAI-02) | Deferred — out of v2.2 UI scope | 2026-05-26 |

### Backend follow-ups (candidate: a backend-hardening milestone)

Carried forward from v1.0; out of v2.0/v2.1/v2.2 scope (parked in ROADMAP Backlog, detail in `.planning/todos/pending/`):

| Item | Priority |
|------|----------|
| analyst predictions `title` expire bug | P2 |
| soft-cap allow-negative hardening | P5 |
| pay-endpoint 500 activation E2E (RPC root-cause fixed m037) | P2 |
| phase-05 intake-classifier review follow-ups WR02/04/05 | P4 |
| research trigger file permissions | P4 |

## Session Continuity

Last session: 2026-06-10T15:02:52Z
Stopped at: Completed 19-02-PLAN.md (confirm-and-close: empty affected set; operator approved Close+rebuild; write-path guard live). Phase 19 complete (2/2).
Resume file: None
Next: `/gsd-plan-phase 20` (Width Tokens & Centering Foundation — WIDTH-01, RHYTHM-01). The layout substrate every later v2.2 visual phase sits on.
Note: root `.planning/.continue-here.md` is a STALE v1.0 leftover (Phase 6→7, 2026-05-30) — not the current checkpoint; safe to delete.

## Operator Next Steps

- **Phase 19 is COMPLETE** (2/2): storage proven clean (twice — Plan 01 diagnosis + Plan 02 independent live scan), fail-loud write-path guard live in the recreated newsletter container, QUOTE-02 regression locks it, no backfill UPDATE needed (confirm-and-close on an empty affected set). QUOTE-01 + QUOTE-02 satisfied.
- **Plan the next v2.2 phase:** `/gsd-plan-phase 20` (Width Tokens & Centering Foundation — WIDTH-01, RHYTHM-01). It is the layout substrate every later visual phase sits on; lands before the per-route fixes.
- Phases 21/22/23 are the per-route + Signals work; Phase 24 is the final holistic responsive/a11y pass.
- Phase 23 carries the milestone's ONLY Supabase migration (anon tier-1 RLS on `source_posts`, next after 043) — orchestrator-owned apply, fail-loud on absence.

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
| Phase 17 P01 | 7min | 3 tasks | 1 files |
| Phase 19 P01 | ~10min | 3 tasks | 3 files |
| Phase 19 P02 | ~5min | 3 tasks | 1 file (confirm-and-close; no DB mutation, newsletter rebuilt) |
