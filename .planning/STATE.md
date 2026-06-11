---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Landing Redesign + Signals Feed
status: executing
stopped_at: "Phase 21 COMPLETE (single-scroll landing + scroll-spy, SCROLL-01/02) — verifier PASSED 4/4, operator holistic live-render sign-off 2026-06-11. Plan 01 (router two-mode + #landing/4-section restructure) + Plan 02 (scroll-spy IO + scroll-restore + 4 net-new CSS rules) shipped + DEPLOYED live via scoped `web` rebuild (orchestrator-owned, main tree). Post-verify iterations all redeployed + re-approved: width-consistency (77da515 uniform --wide band, 33cef15 full-band landing copy), 4 code-review warnings (e4a54eb WR-01 deep-link scroll timing / WR-02 legacy #/map+#/about redirect / WR-03 instant scroll-restore / WR-04 clamp+reset), scroll-spy height-robust detection (7e4a341 — replaced viewport-centre rootMargin with a ~96px-below-top band so the short #signals placeholder highlights correctly). 21-REVIEW.md status=resolved (4 INFO deferred). Next: Phase 22 (per-section visual fixes — HEAD-01/GRID-01/GRID-02/AGENTS-01)."
last_updated: "2026-06-11T14:18:42.091Z"
last_activity: 2026-06-11
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 6
  completed_plans: 6
  percent: 43
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-10 — Current Milestone v2.2)

**Core value:** Synthesis with editorial integrity — autonomous ingestion accelerates output, but every consequential publication is gated by human approval. Silence and homogenization are the failure modes to design against.
**Current focus:** Phase 22 — per-section-visual-fixes (Phase 21 single-scroll landing + scroll-spy COMPLETE)

## Current Position

Phase: 22 (per-section-visual-fixes) — NOT STARTED
Plan: Not started
Status: Phase 21 complete + verified + deployed live (operator-approved). Phase 22 next — three non-conflicting per-section fixes: edition-header de-dup (detail route), map 3-col grid + maturity legend, About pipeline-vs-supporting agent grid + approval callout (HEAD-01, GRID-01, GRID-02, AGENTS-01).
Last activity: 2026-06-11 -- Phase 21 complete (single-scroll landing + scroll-spy, deployed + verified)

## Roadmap (v2.2 — Phases 19–25, REVISED 2026-06-11)

| Phase | Goal | Requirements |
|-------|------|--------------|
| 19. Smart-Quote / Apostrophe Corruption Fix ✅ | Root-cause + fix-forward the apostrophe→straight-quote corruption (write path / stored markdown), scoped reviewed backfill, regression-tested | QUOTE-01, QUOTE-02 |
| 20. Width Tokens & Centering Foundation ✅ | Two coexisting both-centered max-widths (`--measure` prose / `--wide` grids) kill the dead left gutter; token-only color + section-rhythm baseline everything else sits on (deployed live 2026-06-11) | WIDTH-01, RHYTHM-01 |
| 21. Single-Scroll Landing + Scroll-Spy Nav ⬅ NEXT | Merge the four top-level sections (newsletter/about/map/signals) into one scroll page + scroll-spy nav; editions/blocks stay deep-linkable routes; back-to-landing scroll restore. Re-verifies WIDTH-01/RHYTHM-01 holistically on the assembled page | SCROLL-01, SCROLL-02 |
| 22. Per-Section Visual Fixes | Three non-conflicting fixes: edition-header de-dup (detail route), map 3-col grid + maturity legend, About pipeline-vs-supporting agent grid + approval callout | HEAD-01, GRID-01, GRID-02, AGENTS-01 |
| 23. Distinct Newsletter Excerpts | Strip the boilerplate intro at render + show the first distinct sentence in the indexed-row archive format — no schema change | EXCERPT-01 |
| 24. Signals Section | `#signals` section in the landing, tier-1 `source_posts` newest-first (capped, safe external links), gated on the one Supabase migration (anon tier-1 RLS on `source_posts`, fail-loud) | SIGNAL-01, SIGNAL-02, SIGNAL-03, SIGNAL-04 |
| 25. Responsive & Accessibility Pass | Holistic cross-cutting verify: grids/rows reflow (3→2→1, nav condenses, rows stack), scroll-spy keyboard/motion-safe, visible `:focus-visible`, `prefers-reduced-motion`, real `<a>` links | RESP-01, A11Y-01 |

**Coverage:** 17/17 v2.2 requirements mapped (15 original + SCROLL-01/02) — no orphans, no duplicates.

**Phase nature:** Mostly `ui_phase` (Phases 20–25 touch `docker/web/site/` — `app.js`, `style-base.css`, `style-shared.css`; the other CSS files are legacy/unloaded; `marked.js` renders markdown, no typographer). Phase 21 (single-scroll landing + scroll-spy) is the navigation-architecture change — an `app.js` router refactor. Two phases reach the backend and are deliberately isolated from the CSS work: Phase 19 (content write-path + scoped data backfill) and Phase 24 (the milestone's only Supabase migration — anon tier-1 RLS on `source_posts`). Ordering is low-to-high risk, each phase independently shippable.

**Standing constraints apply throughout:** hybrid single-scroll landing (top-level sections scroll + scroll-spy; editions/blocks stay deep-linkable routes — REVISED 2026-06-11); all LLM via `llm-proxy:8200`; isolated-schema / `economy_map` access via direct PostgREST + `Accept-Profile` (never supabase-py `.in_()`); append-only — corrections via the canonical-body-rewrite path, never a raw UPDATE; fail-loud on missing fields; the apostrophe backfill is a scoped reviewed UPDATE shown before/after on ONE edition first, never a blind find-replace; deploy via prod↔main drift check → branch → `/diff` per work group → scoped `docker compose up -d --build web` (NO `--delete`) → operator approval. Worktree-unsafe steps (scoped web rebuild, the Phase 24 migration apply) are orchestrator-owned from the main tree, never a worktree executor.

## Accumulated Context

### Decisions

Operator decisions locked at v2.2 start (2026-06-10, in PROJECT.md Current Milestone):

- **~~Keep separate routes~~ → REVISED 2026-06-11: Hybrid single-scroll landing.** The four top-level sections (newsletter/about/map/signals) merge into ONE scroll page with scroll-spy nav per the mockup; editions (`#/<edition>`) and block pages (`#/map/<slug>`) STAY deep-linkable routes (keeps SEO/deep-linking). Re-scopes Phases 21–24 (see ROADMAP); Phase 20's width/rhythm foundation is layout-agnostic and carries over. Supersedes the 2026-06-10 separate-routes call.
- **Signals = a section in the single-scroll landing** (`#signals` anchor) — REVISED 2026-06-11 (was its own route+tab); the anon tier-1 RLS migration on `source_posts` is unchanged.
- **Excerpts = strip-at-render** (no schema / pipeline change; the stored-`summary` path is the deferred EXCERPT-F1).
- **No domain research** — the 7-task brief + mockup specify the work on an existing, well-understood codebase.

Open items to resolve in discuss/plan (do NOT decide unilaterally):

- **Phase 19 root cause** (QUOTE-01): is the corruption at storage (write path) or render? Query raw `body_md` bytes around an apostrophe FIRST; the fix follows from the finding (render-layer if data is clean; write-path-first-then-backfill if corrupt). `marked.js` has no typographer, so a render-layer smartquote transform is unlikely — diagnose stored bytes before choosing.
- **Phase 19 backfill scope** (QUOTE-01): which editions are affected, and the exact before/after on ONE edition shown for operator approval before any batch UPDATE.
- **Phase 24 RLS shape** (SIGNAL-04): the precise tier-1 predicate for the read-only anon SELECT policy on `source_posts` (which tier column/value defines tier-1), and the migration number (next after 043).
- **Phase 22 distinct-sentence rule** (EXCERPT-01): the exact boilerplate-intro pattern to strip and the first-distinct-sentence heuristic (verified on editions 29 vs 30).

Standing v1.0/v2.0/v2.1 decisions still in force (PROJECT.md Key Decisions table): append-only `block_body_versions` + `timeline_entries`; schema isolation via direct PostgREST + `Accept-Profile`; sentinels flag-never-block; synthesis via `llm-proxy:8200`; scoped `agentpulse-web` rebuild (no new infra); single light-mode violet accent (dark mode deferred); Source Serif 4 body + IBM Plex Mono chrome.

- [Phase 19 — CORRECTED]: the apostrophe corruption is a DOUBLED apostrophe (`''`, two U+0027), which renders as a *visual* double-quote in the Source Serif 4 body face — NOT a literal `"` character and NOT a clean corpus. The original diagnosis (searched for U+0022, spot-checked one clean `Cash App's`) was WRONG; the operator caught it at live-site verification. Real signature = word-flanked `'{2,}`. 103 occurrences across published editions 26/29/30. Render path is genuinely clean (verified end-to-end: anon REST → marked v15.0.12 → `App&#39;s`). Lesson saved: [[feedback_verify_render_bugs_end_to_end]].
- [Phase 19 / fix + backfill]: write-path guard `nl.normalize_apostrophe_corruption` corrected to collapse word-flanked `''`→`'` (+ defensive mid-word double-quote repair), fail-loud, genuine quotes preserved; 36 regression tests. Operator-approved scoped backfill (by row id) of editions 26/29/30 — 103 repaired, 0 remaining, genuine `"` counts unchanged. `newsletter` rebuilt to ship the corrected guard; `web` NOT rebuilt (renderer unchanged — stored bytes render directly). Operator confirmed the live site. QUOTE-01 + QUOTE-02 satisfied; Phase 19 closed.
- [Phase 20 / Plan 01 — WIDTH-01 foundation]: two coexisting centered axes shipped in source — `.prose` (`--measure:64ch`) for reading copy, `.wide` (`--wide:1080px`) for tiled content, `--gutter:clamp(1.25rem,5vw,3.5rem)` side padding (D-01, operator-locked mockup values verbatim). The single 720px `.container` (the D-06 dead-gutter root cause — centered but too narrow, so wide content read as a left gutter) is fully retired (0 refs in index.html + style-shared.css); each route re-homed onto its correct axis per the D-03 apply-map (list/map/status/about-grid/subscribe → wide; reader/block/about-intro → prose; About explicitly split). Nav widened 880px→`var(--wide)` so chrome and content share ONE centered axis (D-02), via the `.nav` rule only — no `.wide` on nav markup (Pitfall 3). `body > header` sticky scoping preserved (Pitfall 1); map grid still 2-col (3-col is Phase 22 post-renumber). Source-only — live-render verification is Plan 02 (orchestrator-owned). 3 atomic commits: 5ce580e / 76888c9 / c974018.
- [Phase 21 / Plan 01 — SCROLL-01 structural foundation]: the four top-level sections now render on ONE single-scroll `<main id="landing">` (4 stacked `<section>` — `#newsletter`/`#signals`/`#map`/`#about`, LOCKED mockup order, Signals 2nd) REUSING the existing `#list-view`/`#map-view`/`#about-view` DOM verbatim; editions (`#/edition/<n>`) + block pages (`#/map/<slug>`) stay deep-linkable detail routes (siblings outside `#landing`). `getRoute()` is now two-mode (`{mode:'landing'|'detail'}`) — detail prefixes tested FIRST, bare-anchor landing fallthrough via an ANCHORED allowlist `/^#(newsletter|signals|map|about)$/` (Pitfall 1 / Security V5); the old plain-`#/map` (`view:'map'`) + `#/about` (`view:'about'`) routes are REMOVED (now landing sections). `route()` branches on mode (detail → stash `landingScrollY` + `setActiveTab` + dispatch; landing → `showLanding`, NO `setActiveTab` so the Plan-02 scroll-spy IO owns landing active state). `showView()` split into `showLanding()`/`showDetail()`; `loadList()`/`loadHub()` decoupled from view-switching behind an idempotent `ensureLandingDataLoaded()` guard; the mode-toggle/`.hero` re-homed into `#newsletter` (TGL-01). `#signals` is a PURE static shell (zero `source_posts`, no fetch, no new `<script>` — Phase 24 owns data + RLS). All Supabase queries byte-identical (no new `.eq('status','published')`, `.eq('status'` count frozen at 11, D-17); `__SUPABASE_*__` placeholders intact. Source-only — NO `docker compose` build/deploy run (Plan 02 / orchestrator-owned). Deviation: the two detail "Back to the map" backlinks re-pointed `#/map`→bare `#map` (the removed route would land on the wrong section). 3 task gates PASS. 4 commits: a000039 / 4941e57 / 040bdc7 / 80c1e05.

### Pending Todos

7 carried-forward backend todos in `.planning/todos/pending/` (all v1.0 follow-ups — analyst/governance/intake/research/phase-review). Out of v2.2 scope; parked in the ROADMAP Backlog (candidate backend-hardening milestone).

### Blockers/Concerns

None for v2.2 start. Source brief (`.planning/docs/REDESIGN_CC_BRIEF.md`, 7 work groups) + the visual mockup (`agentpulse-redesign (1).html`) are present and staged. Frontend files known: `docker/web/site/app.js`, `style-base.css`, `style-shared.css`; migrations live in `supabase/migrations/` (highest is 043).

Carry-over advisories (non-blocking): a PRE-EXISTING service_role leak in tracked `.claude/settings.local.json` (logged DEF-17-01 in v2.1 — recommend key rotation + scrub + gitignore); dead `.about-lede` rule in `style-base.css` (trivial cleanup, fold into a future commit — likely touched in Phase 22 About work / Phase 25 pass).

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
| ~~v2.2 future — Layout~~ | Single-page scroll + scroll-spy nav (WIDTH-F1) | **PULLED INTO v2.2 (2026-06-11)** as a hybrid single-scroll landing (top-level sections scroll; editions/blocks stay routes) — operator reversed the deferral | 2026-06-10 → 2026-06-11 |
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

Last session: 2026-06-11T11:26:49.426Z
Stopped at: Phase 20 COMPLETE — Plan 02 code committed (c813005 on-accent alias, 33002fa D-05 rhythm; both gates pass) + scoped `web` rebuild DEPLOYED live 2026-06-11 (drift clean: newsletter drift was a false build-then-commit artifact, guard 437cdb1 confirmed live; lab-data-provider = D-07; migration 043 unapplied = pre-existing advisory → now owned by Phase 24). Served CSS confirmed over-the-wire (HTTP 200). 20-02-SUMMARY written. Then: v2.2 RE-SCOPED to hybrid single-scroll landing — ROADMAP/REQUIREMENTS/PROJECT/STATE updated, Phase 21 (Single-Scroll Landing + Scroll-Spy Nav, SCROLL-01/02) inserted, old 21–24 renumbered to 22–25. Phase 20's per-route visual sign-off folded into Phase 21.
Resume file: None
Next: `/gsd-plan-phase 21` (operator chose "approve + plan directly" — design unknowns surfaced inside planning research: scroll-spy ↔ detail-route coexistence, app.js router two-mode refactor, back-to-landing scroll restore, Signals section shell vs Phase 24 data). Do NOT re-run the web rebuild (Phase 20 already deployed).
Note: root `.planning/.continue-here.md` is a STALE v1.0 leftover (Phase 6→7, 2026-05-30) — not the current checkpoint; safe to delete.

## Operator Next Steps

- **Phases 19 + 20 are COMPLETE.** Phase 19 (smart-quote fix): storage proven clean, fail-loud guard live, regression-locked. Phase 20 (width/centering/rhythm foundation): code committed + scoped `web` rebuild deployed live 2026-06-11; WIDTH-01/RHYTHM-01 satisfied (holistic visual re-verify folded into Phase 21).
- **Plan the new Phase 21:** `/gsd-plan-phase 21` (Single-Scroll Landing + Scroll-Spy Nav — SCROLL-01, SCROLL-02). The nav-architecture conversion from the 2026-06-11 hybrid pivot; everything downstream re-homes onto the landing, so it lands before the per-section fixes. Design unknowns surface inside planning research (scroll-spy ↔ detail-route coexistence, app.js two-mode router, back-to-landing scroll restore, Signals section shell vs Phase 24 data).
- Phase 22 = per-section visual fixes; Phase 23 = excerpts; Phase 24 = Signals section + migration; Phase 25 = the final holistic responsive/a11y (now incl. scroll-spy) pass.
- Phase 24 carries the milestone's ONLY Supabase migration (anon tier-1 RLS on `source_posts`, next after 043) — orchestrator-owned apply, fail-loud on absence. Pre-existing migration 043 (unapplied) also owned here.

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
| Phase 20 P01 | ~4min | 3 tasks | 4 files (width tokens + .prose/.wide axes; 720px .container retired; source-only) |
| Phase 21 P01 | ~6min | 3 tasks | 2 files |
