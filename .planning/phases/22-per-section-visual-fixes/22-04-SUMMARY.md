---
phase: 22-per-section-visual-fixes
plan: 04
subsystem: infra
tags: [deploy, docker-compose, caddy, web, live-verify, supabase-rest]

# Dependency graph
requires:
  - phase: 22-per-section-visual-fixes (plans 01/02/03)
    provides: HEAD-01 edition-header de-dup (app.js), GRID-01/02 map 3-col + maturity legend (app.js + css), AGENTS-01 About made-cols (index.html + css)
provides:
  - Live-deployed Phase 22 render on aiagentspulse.com via scoped web rebuild
  - Operator-approved deploy + D-12 About-copy sign-off + human-verify live sign-off
  - Live-data verification of HEAD-01 (suffix strip) and GRID-02 (per-card maturity fill)
affects: [phase-23-excerpts, phase-24-signals, phase-25-responsive-a11y]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Orchestrator-owned worktree-unsafe deploy: scoped `docker compose up -d --build web` from the main tree, drift-checked + operator-approved, NO --delete"
    - "Render verification reproduces the rendered output (live anon REST + the deployed regex) rather than inferring clean from source bytes (Phase-19 discipline)"

key-files:
  created:
    - .planning/phases/22-per-section-visual-fixes/22-04-SUMMARY.md
  modified: []

key-decisions:
  - "Deploy ran on the MAIN tree (no worktree) — config/.env is gitignored/absent in worktrees and the scoped rebuild cds to the absolute main-tree path (worktree executors would build stale code)"
  - "newsletter + migration-043 drift surfaced to operator as PRE-EXISTING (Phase 19 / Phase-24-owned) — not introduced by Phase 22 and not touched by a scoped web rebuild; operator approved proceeding"
  - "Operator approval = D-12 About-copy sign-off (Gato + Gato Brain distinct; 4 pipeline + 4 supporting = eight cooperating services)"

patterns-established:
  - "Data-driven render checks done headlessly: HEAD-01 suffix strip reproduced against live newsletters.title/title_impact; GRID-02 per-card fill validated against stored economy_map maturity (no MATURITY_STAGE fallback masking)"

requirements-completed: [HEAD-01, GRID-01, GRID-02, AGENTS-01]

# Metrics
duration: ~15min
completed: 2026-06-12
---

# Phase 22 Plan 04: Deploy + Live-Verify Summary

**Phase 22 (HEAD-01 edition-header de-dup, GRID-01/02 map 3-col + maturity legend, AGENTS-01 About made-cols) deployed live via a drift-checked, operator-approved scoped `web` rebuild and verified on aiagentspulse.com.**

## Performance

- **Duration:** ~15 min (Task 1 preflight + operator checkpoint + deploy + verification)
- **Completed:** 2026-06-12T13:27:42Z
- **Tasks:** 2 (1 auto preflight + 1 blocking-human checkpoint)
- **Files modified:** 0 source files (deploy/verify plan — the three source plans 22-01/02/03 carried the code)

## Accomplishments
- **Pre-deploy gate (Task 1):** `scripts/drift-check.sh` run; source-marker preflight printed **PASS** (all HEAD-01/GRID-01/GRID-02/AGENTS-01 markers present, `node --check` clean, `style-shared.css` + `index.html` hex-free — RHYTHM-01 holds).
- **Deploy (Task 2):** scoped `cd /root/bitcoin_bot/docker && docker compose up -d --build web` (SERVICE key `web`, **no `--delete`**) from the main tree, after explicit operator approval. Container `agentpulse-web` recreated and `Up`; Caddy returns HTTP **200** over HTTPS (HTTP :80 → 308 redirect). `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` substitution confirmed in the served `/srv/app.js` (0 remaining placeholders, real `supabase.co` URL present) — the live SPA loads, not a placeholder shell.
- **Live verification:**
  - **HEAD-01** — served `EDITION_SUFFIX_RE` present (×2) + eyebrow line gone; the strip reproduced against **live** `newsletters` data: ed#29/#30 `title` AND `title_impact` → headline-only in both Technical and Strategic modes; single byline retained.
  - **GRID-01** — served CSS `grid-template-columns: repeat(3, 1fr)` + `@max-width:880px → 2col` + `@max-width:600px → 1col`; old `640px` rule gone; `.card-deferred { grid-column: 1 / -1; }` preserved.
  - **GRID-02** — served legend reuses the real 5-seg `.maturity-pill data-stage="1"`; per-card fill **data-verified** against stored `economy_map` maturity (every block maturity is a valid `MATURITY_STAGE` key — no silent fallback): substrate 2/5, behavior 3/5 & 1/5, frame deferred (full-width), hub excluded.
  - **AGENTS-01** — served `made-cols` numbered pipeline + bulleted supporting + violet `.approval` callout; `agent-row` gone; `Gato Brain` retained distinct.
  - **Operator human-verify sign-off:** "Approved — all correct" on the live render (3-col layout + breakpoint collapses, no orphaned About card, legend scale matches cards, no Phase 20/21 regression).

## Task Commits

Task 1 (preflight) and Task 2 (deploy + verify) modified no source files; this plan's only artifact is this SUMMARY plus the live deployment. Phase-22 source commits live in plans 22-01/02/03.

## Files Created/Modified
- `.planning/phases/22-per-section-visual-fixes/22-04-SUMMARY.md` — this record (deploy + verification + sign-offs).
- (live) `agentpulse-web` container — rebuilt from the current main tree.

## Decisions Made
- Ran the deploy on the **main tree, no worktree** (config/.env gitignored → absent in worktrees; scoped rebuild cds to the absolute main-tree path).
- Surfaced **pre-existing** drift to the operator (`newsletter` from Phase-19 commit `437cdb1`; migration `043` Phase-24-owned) — neither introduced by Phase 22, neither touched by a scoped `web` rebuild. Operator approved proceeding.
- Took operator "Approve & deploy" as the **D-12 copy sign-off** (Gato + Gato Brain distinct; 4 pipeline + 4 supporting = "eight cooperating services").

## Deviations from Plan
None — plan executed as written. The plan's "create/confirm a working branch" step resolved to the project's `branching_strategy: none` (all v2.2 phase work commits to `main`, consistent with history); the real deploy safety gates (drift check + operator approval + scoped service + no `--delete`) were all honored.

## D-04 / D-12 findings (surfaced at checkpoint)
- **D-04 (from 22-01):** the ` — Edition #N | <Month D, YYYY>` suffix (separator = SPACE + EM-DASH U+2014 + SPACE) IS baked into both `newsletters.title` and `newsletters.title_impact`. Confirmed live; the render-only strip handles both, defensively no-op when absent.
- **D-12 (from 22-02):** supporting-layer copy keeps Gato + Gato Brain distinct; 4 pipeline + 4 supporting = the "eight cooperating services" intro P1 commits to. Operator signed off.

## Issues Encountered
- Local `curl https://localhost` failed TLS (Caddy serves the `aiagentspulse.com` domain cert) — resolved by curling with correct SNI (`--resolve aiagentspulse.com:443:127.0.0.1`), which returned 200. Not a deploy fault.

## Next Phase Readiness
- Phase 22 fully shipped and verified live. Ready for Phase 23 (distinct newsletter excerpts).
- Carry-over (unchanged, not Phase 22): `newsletter` image drift (Phase 19), migration `043` unapplied (Phase-24-owned), `lab-data-provider` known carry-over.

## Self-Check: PASSED
- All Phase-22 source markers present in the served files; substitution confirmed; Caddy 200.
- HEAD-01 reproduced against live data (both modes); GRID-02 fill data-verified; operator approved the live render + D-12 copy.

---
*Phase: 22-per-section-visual-fixes*
*Completed: 2026-06-12*
