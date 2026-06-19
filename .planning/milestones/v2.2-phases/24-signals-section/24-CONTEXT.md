# Phase 24: Signals Section - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Fill the existing `#signals` landing-section shell with live data. Two surfaces:

1. **Backend (the milestone's ONLY migration, next number = `044`, orchestrator-applied / worktree-unsafe):** a new anon read path so the public site can read **tier-1** `source_posts` — the table currently has RLS enabled but no anon policy, so anon is fully blocked.
2. **Frontend (`docker/web/site/app.js` + `index.html`/CSS):** fetch the tier-1 source links and render them into the empty `#signals-list` container — newest-first, capped, each a safe external link showing date · headline · source domain, with a "view all" affordance and fail-loud behavior on a broken feed path.

**In scope:** the anon read path (migration 044), the signals fetch + render in `app.js`, the row markup/style (reusing the Phase 23 indexed-row precedent), the expand-in-place "view all", and the fail-loud surfacing.

**Out of scope (locked by Phase 21, do NOT re-open):** the section's placement/order/anchor (`#signals`, 2nd after Newsletter), the shell copy (eyebrow "Tier-1 Source Links" / "Signals" / "The week's tier-1 sources, newest first"), scroll-spy reachability, and the `.prose`/`.wide` axis. Also out of scope: the holistic responsive/a11y pass (Phase 25), any write path, and any change to the scraper/ingest pipeline.
</domain>

<decisions>
## Implementation Decisions

### Anon Data Exposure (SIGNAL-04) — the security crux
- **D-01: Minimal public VIEW, not a blanket table policy.** RLS is row-level and cannot hide columns, so anon reads tier-1 through a dedicated **view** exposing ONLY `id, title, source_url, source, scraped_at` for `source_tier = 1`. `GRANT SELECT` on the view to `anon`. The base `source_posts` table stays anon-blocked (RLS enabled, no anon policy). `body` (full scraped article/post text — copyright/leak risk), `score`, `author`, `comment_count`, `tags`, and `metadata` (internal extraction JSONB) are therefore **never** reachable by the anon key. The frontend selecting only 4 columns does NOT substitute for this — the column ceiling lives in the view. The exact view mechanism (`security_invoker`, schema placement, naming) is research/planner's call, but it MUST NOT widen exposure beyond these columns/rows.
- **D-02: The view filters `source_url IS NOT NULL`** (in addition to `source_tier = 1`) so the cap counts only genuinely linkable rows — every Signals row must BE a safe external link (SIGNAL-02). Ordering is `scraped_at DESC` (see D-04), with a stable tie-break (e.g. `id`) at planner discretion. Index `idx_source_posts_tier_scraped (source_tier, scraped_at DESC)` already supports this.

### "View All" Affordance (SIGNAL-01)
- **D-03: Expand-in-place — NO route.** Render the default cap (~12–15) plus a "View all" / "Show more" control that reveals the rest **inline** up to a bounded higher cap (~50). The standalone `#/signals` route was deliberately folded into the single-scroll landing in Phase 21 (SIGNAL-03 revision) and is NOT resurrected. Exact cap numbers (default within ~12–15, hard ceiling ~50) are planner discretion.

### Row Display (SIGNAL-02)
- **D-04: Date = `scraped_at`.** It is the only reliable temporal column (`source_posts` has no `published_at`; any source-published date lives in `metadata` JSONB, which the view does not expose). Reuse the existing `formatDate()` helper for consistency with the newsletter list.
- **D-05: Source label = www-stripped hostname derived from `source_url`** at render in `app.js` (e.g. `deepmind.google`, `news.ycombinator.com`). Matches the literal "source domain" wording in SIGNAL-02 and is reader-facing. Fall back to the internal `source` value ONLY if a URL lacks a parseable host.
- **D-06: Each row is a safe external link** — `href = source_url` (validate scheme is `http`/`https` before using as href), `target="_blank"`, `rel="noopener noreferrer"`, `↗` hover affordance (SIGNAL-02). Null/unparseable URLs are already excluded upstream by D-02.

### Fail-Loud Surfacing (SIGNAL-04)
- **D-07: Distinguish by HTTP response, not by emptiness.** Because the read path is a view+grant: a **missing view or missing anon grant returns an HTTP error** (4xx / PostgREST error body), NOT `200 []`. Mapping:
  - Non-2xx / PostgREST error → **LOUD** inline diagnostic ("Signals feed is temporarily unavailable") **+ `console.error`** (operator-visible signal that the migration/view/grant is absent or broken).
  - `200` with rows → render the feed.
  - `200` with `[]` → **benign** quiet empty state ("No tier-1 signals this week").

  This catches a missing/broken migration loudly (satisfying "fail-loud, not silent empty feed") while NOT crying wolf on a genuinely thin tier-1 week.

### Claude's Discretion
- Exact cap numbers (default ~12–15, expand hard cap ~50); the `scraped_at` tie-break column; view `security_invoker`/schema/naming (within D-01's exposure ceiling); the precise diagnostic and empty-state copy; whether the expand control re-queries or slices an already-fetched batch.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — SIGNAL-01..04 (lines ~55–58): the locked acceptance criteria (cap ~12–15 + view-all, safe external link with `rel`/`target`, `#signals` section reachability, anon tier-1 RLS with fail-loud).
- `.planning/ROADMAP.md` — Phase 24 row (line ~266) + notes (line ~218): backend phase, the milestone's ONLY migration (next after 043), fail-loud is a HARD requirement, deploy-gated, orchestrator-applied migration (worktree-unsafe).

### Prior phase contracts (locked — do not re-open)
- `.planning/phases/21-single-scroll-landing-scroll-spy-nav/21-CONTEXT.md` — the `#signals` shell seam: section order/anchor/copy locked, "STATIC placeholder only; Phase 24 owns the data + anon RLS migration; a premature anon fetch on the RLS-blocked table would render silently empty (fail-loud violation)".
- `.planning/phases/23-distinct-newsletter-excerpts/23-CONTEXT.md` — indexed-row / safe-link render precedent + `escapeHtml()`-at-sink discipline; the browser-compat constraint (no regex lookbehind — WR-01) applies to any new `app.js` code.

### Schema & migration precedent
- `supabase/migrations/004_core_tables.sql` (lines 9–24) — `source_posts` columns; `source_tier INTEGER` (1=authority, 2=curated, 3=community) → **tier-1 = `source_tier = 1`**.
- `supabase/migrations/006_rls_policies.sql` (line 21) — `source_posts` RLS is ENABLED; no anon policy exists (the current anon block SIGNAL-04 lifts narrowly).
- `supabase/migrations/005_missing_indexes.sql` (lines 24–25) — `idx_source_posts_tier_scraped (source_tier, scraped_at DESC)` backs the newest-first tier-1 query.
- Migration numbering: latest applied in-repo is `043`; **the new migration is `044`**.

### Standing constraints
- `CLAUDE.md` / `.planning/PROJECT.md` — fail-loud governance; structural-over-application enforcement (a view+grant is structural); deploy discipline (branch → `/diff` → scoped `docker compose up -d --build web`, NO `--delete` → operator approval); migration applied by the orchestrator from the main tree (worktree-unsafe), never a worktree executor.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker/web/site/index.html` §`#signals` (lines 82–96) — the static shell to fill: `.prose` wrapper with eyebrow/title/sub and an empty `<div class="wide" id="signals-list"></div>`. The "Coming soon" `<p>` is replaced by the rendered feed. No new `<script>` tag is needed — render from `app.js`.
- `docker/web/site/app.js` — the existing Supabase anon client + `loadList()`/`renderList()` (newsletter list fetch→render) is the direct analog for `fetchSignals()`/`renderSignals()`; `escapeHtml()` is already the innerHTML-sink guard; `formatDate()` formats the date column. The Phase 23 `.row` indexed-row markup is the row-style precedent.
- `docker/web/site/style-shared.css` — the Phase 23 `.row` / token-only block is the styling analog for signal rows (hand-authored, token-only, no hex).
- `docker/web/site/style-base.css` §`#signals-list` (lines ~317–327) — width wrappers already handle `#signals-list` (`.wide`); a de-dupe note exists there.

### Established Patterns
- Anon REST reads use the substituted `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` (entrypoint `sed` at container start) — the signals fetch uses the same client, querying the new **view** (public schema → standard anon REST; no `Accept-Profile` needed, unlike `economy_map`).
- Pure read path — no writes, no append-only structures involved.
- `escapeHtml()` at every DB-derived sink (title, derived hostname); `source_url` only used as an `href` after an `http(s)` scheme check.
- `app.js` must stay within widely-supported JS (served raw, no transpile; a parse-time error blanks the whole SPA — see Phase 23 WR-01). No regex lookbehind.

### Integration Points
- New Postgres view (migration 044) ← anon `GRANT SELECT`; base table untouched.
- `app.js`: new `fetchSignals()`/`renderSignals()` populating `#signals-list`, wired into the landing render (gated by the section being present — not a premature fetch).
- Deploy: migration applied by the orchestrator (worktree-unsafe), then a scoped `web` rebuild + operator approval.
</code_context>

<specifics>
## Specific Ideas

- The operator explicitly wants the exposure narrowed at the data layer (a view), on the reasoning that "RLS can't hide columns" — the frontend selecting fewer columns is not a security boundary.
- The fail-loud behavior should key off the HTTP response (error vs `200 []`), specifically so a genuinely quiet tier-1 week reads as a benign empty state rather than an error.
</specifics>

<deferred>
## Deferred Ideas

- **Curated source display-name map** (hostname → pretty name, e.g. `news.ycombinator.com` → "Hacker News", `arxiv.org` → "arXiv") — nicer reading, but adds a map to maintain and is below this phase's value bar. Possible later polish.
- **Surfacing the source-published date** (digging `published_at` out of `metadata` JSONB) — deferred; `scraped_at` is sufficient for v1, and `metadata` is intentionally not exposed by the view.

None of the discussion strayed into new capabilities — scope stayed within the Signals data + anon read path.
</deferred>

---

*Phase: 24-signals-section*
*Context gathered: 2026-06-16*
