---
phase: 24-signals-section
plan: 01
subsystem: database
tags: [supabase, postgres, view, security-definer, rls, anon, source_posts, signals]

# Dependency graph
requires:
  - phase: 21-single-scroll-landing-scroll-spy-nav
    provides: the static #signals landing-section shell this feed will populate
provides:
  - "supabase/migrations/044_signals_anon_view.sql — security-definer view public.signals_feed over tier-1 source_posts + GRANT SELECT TO anon (the structural anon read path SIGNAL-04 requires)"
  - "A 5-column anon-readable contract (id, title, source_url, source, scraped_at) for tier-1 linkable rows, newest-first — consumable by the public-schema anon REST client"
affects: [24-02-frontend-fetch-render, 24-03-orchestrator-live-apply, signals-feed]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Security-DEFINER view as a column+row exposure ceiling (the inversion of the in-repo security_invoker view idiom) — the boundary lives in the view body, not the frontend select"
    - "Explicit GRANT SELECT ... TO anon on a freshly-created public-schema object (do not rely on default privileges)"

key-files:
  created:
    - supabase/migrations/044_signals_anon_view.sql
  modified: []

key-decisions:
  - "Security-DEFINER view (Postgres default, NO security_invoker clause) — an invoker view would run as anon, hit source_posts' RLS-with-no-anon-policy, and return zero rows forever (silent empty feed = fail-loud violation)"
  - "Column ceiling lives in the view body (exactly 5 whitelisted columns), not the frontend — RLS cannot hide columns (operator's explicit reasoning)"
  - "Base source_posts table left untouched: RLS stays enabled with no anon policy, so body/metadata/score/author/comment_count/tags stay anon-unreachable"
  - "Row ceiling source_tier = 1 AND source_url IS NOT NULL, newest-first scraped_at DESC, id DESC — backed by existing mig-005 idx_source_posts_tier_scraped, no new index"
  - "SIGNAL-04 left UNCHECKED: source authored != requirement satisfied; it is satisfied only after the orchestrator-owned live apply (Plan 24-03) + frontend fail-loud wiring (Plan 24-02)"

patterns-established:
  - "Pattern 1: a narrow anon read path = security-definer view (column+row whitelist) + explicit anon grant, base table never touched"
  - "Pattern 2: comment-filtered acceptance gates (grep -v '^[[:space:]]*--') so prose rationale cannot self-trip a security grep"

requirements-completed: []  # SIGNAL-04 spans Plans 24-01 (author) + 24-02 (frontend) + 24-03 (live apply); NOT satisfied by source authoring alone — left Pending until the live apply.

# Metrics
duration: ~3min
completed: 2026-06-17
---

# Phase 24 Plan 01: Signals Anon View Summary

**Security-definer Postgres view `public.signals_feed` exposing exactly 5 whitelisted columns of tier-1 linkable `source_posts` (newest-first) plus `GRANT SELECT TO anon` — the structural, column-ceilinged anon read path SIGNAL-04 needs, with the base table left fully RLS-blocked.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-17T08:41:13Z
- **Completed:** 2026-06-17
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- Authored `supabase/migrations/044_signals_anon_view.sql` — the milestone's ONLY migration — as a source-only, worktree-safe file (no docker, no network, no MCP, no apply).
- Encoded the column ceiling structurally: the view SELECTs exactly `id, title, source_url, source, scraped_at`, so `body` (copyright/leak), `metadata` (internal extraction JSONB), `score`, `author`, `comment_count`, and `tags` are unreachable by the anon key.
- Encoded the row ceiling: `WHERE source_tier = 1 AND source_url IS NOT NULL`, ordered `scraped_at DESC, id DESC` (newest-first, stable tie-break), backed by the existing mig-005 index — no new index.
- Navigated the load-bearing inversion landmine: the view is **security-DEFINER** (Postgres default, no `security_invoker` clause) so it bypasses the base-table RLS and returns the whitelisted set, rather than an invoker-rights view that would silently return zero rows for anon.
- Left the base `source_posts` table untouched (RLS enabled, no anon policy) — zero `ALTER TABLE` / `CREATE POLICY` against it.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author migration 044 — security-definer signals_feed view + anon grant** - `3217464` (feat)

**Plan metadata:** see final `docs(24-01)` commit (this SUMMARY + STATE.md + ROADMAP.md)

## Files Created/Modified
- `supabase/migrations/044_signals_anon_view.sql` - Creates `public.signals_feed` (security-definer view over tier-1 linkable `source_posts`, 5 whitelisted columns, newest-first) and `GRANT SELECT ... TO anon`. Idempotent (`CREATE OR REPLACE VIEW` + `GRANT`).

## Decisions Made
- **Security-DEFINER, not invoker-rights** — the Postgres default with no `WITH (security_invoker = on)` clause. This is the deliberate inversion of the only in-repo `CREATE VIEW` idiom (001's `top_problems_recent`, which uses `security_invoker = on`). An invoker view runs as the calling anon role, hits `source_posts`' RLS (enabled, no anon policy), and returns zero rows forever — a silent permanently-empty feed, the exact fail-loud violation this phase guards against.
- **Column ceiling in the view body, not the frontend** — RLS is row-level and cannot hide columns, so the 5-column whitelist is the security boundary (operator's "RLS can't hide columns"). The frontend selecting fewer columns is not a substitute.
- **Base table untouched** — D-01 keeps `source_posts` RLS-blocked from anon; the view is the only new surface. No policy/grant/ALTER against the base table.
- **SIGNAL-04 left Pending (UNCHECKED)** — authoring the source `.sql` does not satisfy the requirement. SIGNAL-04 ("tier-1 readable by anon via the policy, fail-loud if absent") is satisfied only after the orchestrator-owned LIVE apply (Plan 24-03) lands the view in the DB and the frontend fail-loud surfacing (Plan 24-02) is wired. This mirrors the project's established "stays unchecked until live proof" discipline (EXCERPT-01).

## Deviations from Plan

None - plan executed exactly as written.

The one micro-fix-by-design (already mandated by the plan) was phrasing the "do not use invoker rights" rationale WITHOUT the literal `security_invoker` token in the comment, so the comment cannot self-trip the no-invoker grep gate. This was an explicit plan instruction, not a deviation.

## Issues Encountered
None. All 8 acceptance-criteria gates plus the plan's `<automated>` verification gate passed on the first authoring:
- view present; exactly the 5 columns; `source_tier = 1`; `source_url IS NOT NULL`; `ORDER BY scraped_at DESC`; anon grant present;
- 0 sensitive-column tokens (`body|metadata|score|author|comment_count|tags`) in the comment-filtered SQL body;
- 0 `security_invoker` in the comment-filtered SQL body;
- 0 base-table mutations (`ALTER TABLE source_posts` / `CREATE POLICY` / `ON source_posts`) in the comment-filtered SQL body.

## Threat Model Compliance
The plan's HIGH-severity over-exposure threats are all structurally mitigated in the view body:
- **T-24-01 (column over-exposure):** view SELECTs only the 5 whitelisted columns — verified by the no-sensitive-column gate.
- **T-24-02 (row over-exposure):** `WHERE source_tier = 1` restricts to tier-1 authority rows.
- **T-24-03 (the inversion landmine):** security-DEFINER (no `security_invoker`), so the feed is non-empty AND bounded by the column list + WHERE, not by RLS.
- **T-24-04 (base table):** `source_posts` not touched — verified by the zero-base-mutation gate.

No new security surface introduced beyond the single intended view.

## User Setup Required
None - no external service configuration required by this plan. (The live migration apply is the orchestrator-owned Plan 24-03.)

## Next Phase Readiness
- `044_signals_anon_view.sql` is committed and ready for the orchestrator-owned live apply (Plan 24-03, worktree-unsafe — via the Supabase MCP `apply_migration` tool from the main tree).
- Plan 24-02 (frontend `fetchSignals()`/`renderSignals()` + D-07 fail-loud in `docker/web/site/app.js`) can proceed in parallel against this view's 5-column contract; it stays source-only/worktree-safe.
- Carry-over reminder (not Phase 24): a separate orchestrator-owned Phase 23 Plan 02 web deploy + live ed29≠ed30 verify is still outstanding from the prior session; pre-existing migration 043 is also unapplied and Phase-24-owned.

## Self-Check: PASSED

- FOUND: `supabase/migrations/044_signals_anon_view.sql`
- FOUND: `.planning/phases/24-signals-section/24-01-SUMMARY.md`
- FOUND commit: `3217464` (feat(24-01): security-definer signals_feed anon view)

---
*Phase: 24-signals-section*
*Completed: 2026-06-17*
