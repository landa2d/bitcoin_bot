---
phase: 24-signals-section
plan: 02
subsystem: ui
tags: [supabase, postgrest, anon-view, xss, escapehtml, safehttpurl, vanilla-js, scroll-spy]

# Dependency graph
requires:
  - phase: 24-signals-section (Plan 01)
    provides: "public.signals_feed security-definer view (id,title,source_url,source,scraped_at; source_tier=1 AND source_url IS NOT NULL) + anon GRANT SELECT — the read contract this frontend consumes"
  - phase: 21-single-scroll-landing-scroll-spy-nav
    provides: "the static #signals shell (#signals-list render target, scroll-spy reachability) + the gated ensureLandingDataLoaded() load seam + the two-mode router"
  - phase: 23-distinct-newsletter-excerpts
    provides: "the .row indexed-row family (markup + token-only CSS) + escapeHtml()/safeHttpUrl()/formatDate() sinks + the WR-01 no-lookbehind browser-compat constraint"
provides:
  - "fetchSignals(): queries public.signals_feed (5 cols, newest-first, limit 50) with a D-07 three-way fail-loud split (error->loud+console.error / 200[]->benign empty / rows->render)"
  - "renderSignals(data, expanded): escaped, safeHttpUrl-gated external <a class='row signal-row'> rows (date . headline . www-stripped source domain, ↗ hover) capped at 15 with an inline view-all expand-in-place"
  - "signalHost(url, fallback): lookbehind-free anchored ^www. hostname strip with source fallback"
  - "fetchSignals() wired into ensureLandingDataLoaded()'s Promise.all (gated, non-premature fetch)"
  - "token-only .row .host + .view-all CSS; #signals 'Coming soon.' placeholder removed"
affects: [24-03-live-apply, 25-responsive-accessibility-pass]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-way fail-loud fetch split (error vs 200[] vs rows) keyed off the HTTP response, not emptiness — the deliberate deviation from loadList()'s conflated error+empty branch"
    - "External-link row variant of the Phase 23 .row family: whole-<a> click target with safeHttpUrl-gated + escapeHtml'd href, target=_blank rel=noopener noreferrer"
    - "Expand-in-place control (view-all) re-rendering an already-fetched cached batch (window.currentSignals) — no route, no re-query"

key-files:
  created: []
  modified:
    - "docker/web/site/app.js — fetchSignals/renderSignals/signalHost + view-all handler + ensureLandingDataLoaded wiring"
    - "docker/web/site/style-shared.css — token-only .row .host + .view-all (+ :hover/:focus-visible)"
    - "docker/web/site/index.html — removed 'Coming soon.' placeholder from the #signals intro"

key-decisions:
  - "Slice an already-fetched limit(50) batch for view-all (D-03 planner discretion) — one query, expand-in-place by re-rendering window.currentSignals"
  - "escapeHtml() the safeHttpUrl-gated href in its attribute context (defense-in-depth beyond the scheme gate — a scraped URL with an embedded quote could otherwise break out of the href attribute)"
  - "DEFAULT_VISIBLE=15 (top of the D-03 ~12-15 band); 50 = the D-03 hard expand ceiling, enforced in the query .limit(50)"

patterns-established:
  - "Fail-loud-vs-benign-empty: distinguish a broken read path (HTTP error -> loud diagnostic + console.error) from a genuinely empty result (200 [] -> quiet empty state)"
  - "Reuse the shared .row family for a new row type by adding only a scoped sub-selector (.row .host), never mutating the shared grid"

requirements-completed: []  # SIGNAL-01..04 span Plan 24-02 (frontend) + 24-03 (live apply); NOT satisfied by source authoring alone — left Pending until the orchestrator-owned live apply + render proof (Plan 24-03)

# Metrics
duration: 5min
completed: 2026-06-17
---

# Phase 24 Plan 02: Signals Section Frontend Summary

**Fills the static `#signals` shell with the live tier-1 feed: `fetchSignals()` (3-way fail-loud split querying `public.signals_feed`), `renderSignals()` (escaped, `safeHttpUrl`-gated external rows, capped at 15 with inline view-all), `signalHost()` (lookbehind-free `www.` strip), wired into the gated `ensureLandingDataLoaded()` — source-only, live proof pending Plan 24-03.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-17T08:47:24Z
- **Completed:** 2026-06-17T08:52:35Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `fetchSignals()` queries the Plan-24-01 contract view `public.signals_feed` (exactly the 5 whitelisted columns, `.order('scraped_at', desc).order('id', desc).limit(50)`) and applies the **D-07 three-way fail-loud split** — the deliberate deviation from `loadList()`'s conflated `if (error || !data || length===0)` branch: a missing/broken view or anon grant returns an HTTP `error` (not `200 []`), so the LOUD `signals-error` diagnostic + `console.error('fetchSignals error:', error)` fires exactly when the migration is absent, while a genuinely thin tier-1 week reads as the benign `signals-empty` state.
- `renderSignals(data, expanded)` builds whole-`<a class="row signal-row">` external links — `href = escapeHtml(safeHttpUrl(source_url))` (scheme-gated, unsafe/null rows skipped — T-24-06), `target="_blank" rel="noopener noreferrer"` (reverse-tabnabbing), `↗` `.num` affordance, `.title` headline + `.host` www-stripped domain, `.date = formatDate(scraped_at)` (D-04). Every DB-derived value passes `escapeHtml()` at the innerHTML sink (T-24-05). Capped at 15; an inline `#signals-view-all` button re-renders `window.currentSignals` expanded (D-03 — no route, no re-query).
- `signalHost()` derives the reader-facing source domain via `new URL(url).hostname.replace(/^www\./, '')` inside try/catch with a `source` fallback — an anchored prefix strip, **never** a regex lookbehind (WR-01: a lookbehind is a parse-time SyntaxError on WebKit<16.4 that blanks the whole SPA).
- Wired `fetchSignals()` into `ensureLandingDataLoaded()`'s `Promise.all([loadList(), loadHub(), fetchSignals()])` — the gated, non-premature one-shot Phase 21 mandated; it returns a Promise so it joins the WR-01 settle gate.
- Token-only CSS (`.row .host`, `.view-all` + `:hover`/`:focus-visible`), zero new hex; rows reuse the Phase 23 `.row` family. The `#signals` "Coming soon." placeholder is gone; the `#signals-list` render target and Phase-21-locked section copy/anchor/order are untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: app.js — fetchSignals + renderSignals + signalHost + view-all + wiring** - `b791e3e` (feat)
2. **Task 2: style-shared.css source-domain + view-all styling; index.html placeholder removal** - `4651134` (style)

_No package installs, no new dependencies (T-24-SC accept) — reuses the existing CDN supabase client + helpers._

## Files Created/Modified
- `docker/web/site/app.js` - Added `SIGNALS_DEFAULT_VISIBLE`, `signalHost()`, `fetchSignals()` (3-way fail-loud), `renderSignals()` (escaped safe-external rows + view-all handler); wired `fetchSignals()` into the gated `Promise.all`.
- `docker/web/site/style-shared.css` - Added token-only `.row .host` (source-domain sub-line) and `.view-all` (expand control + `:hover`/`:focus-visible`); zero new hex.
- `docker/web/site/index.html` - Removed the trailing " Coming soon." from the `#signals` `.about` intro; render target + locked copy intact.

## Decisions Made
- **Slice an already-fetched `limit(50)` batch for view-all** (D-03 planner discretion): the single-query path. `fetchSignals()` stashes the full (≤50) batch in `window.currentSignals`; the button re-renders it expanded — no second round-trip.
- **`escapeHtml()` the href in attribute context** (defense-in-depth): the plan specified `href = safeHttpUrl(source_url)`; I additionally wrapped it in `escapeHtml()` because `source_url` is third-party scraped content and a URL with an embedded `"` would pass the `https?://` scheme gate yet break out of the `href` attribute. This strengthens T-24-06 without weakening the scheme allowlist. (Tracked below as a Rule 2 hardening.)
- **`DEFAULT_VISIBLE = 15`** (top of the D-03 ~12-15 band) with **50** as the hard expand ceiling enforced in the query `.limit(50)`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical / XSS hardening] escapeHtml() applied to the href attribute value**
- **Found during:** Task 1 (renderSignals external-link rows)
- **Issue:** The plan's row spec gates the href through `safeHttpUrl()` (scheme allowlist) but renders it raw into the `href="..."` attribute. `source_url` is untrusted scraped third-party content; a value like `https://x/"onmouseover="alert(1)` passes the `https?://` scheme check yet breaks out of the double-quoted attribute (attribute-injection XSS). `safeHttpUrl()` alone does not neutralize attribute-context metacharacters.
- **Fix:** Wrapped the gated URL in the existing `escapeHtml()` sink: `href="' + escapeHtml(href) + '"`. Keeps the scheme allowlist as the primary gate (T-24-06) and adds attribute-context escaping as defense-in-depth.
- **Files modified:** docker/web/site/app.js
- **Verification:** `safeHttpUrl(` and `escapeHtml(` both present in the signals path; `node --check` clean; the `rel="noopener noreferrer"` / `target="_blank"` gates pass.
- **Committed in:** `b791e3e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing-critical / XSS hardening)
**Impact on plan:** The single auto-fix strengthens an existing HIGH-severity threat disposition (T-24-06) at zero scope cost — no behavior change for legitimate URLs, no new dependency. All other work followed the plan exactly.

## Issues Encountered
- `gsd-tools state record-metric` rejected its positional args ("phase, plan, and duration required") despite the documented `<phase> <plan> <duration> <tasks> <files>` form; the Performance Metrics row was hand-added to STATE.md instead (consistent with the known executor-edits-STATE pattern). `state advance-plan` / `update-progress` / `record-session` and the SUMMARY/ROADMAP updates succeeded via the SDK; the remaining stale free-form STATE lines (`Next:`/`Previously:`, `stopped_at`) were reconciled by hand.

## User Setup Required
None - no external service configuration required. (The live read path depends on migration 044, which is applied by the orchestrator in Plan 24-03 — not a user setup step.)

## Next Phase Readiness
- **Source is complete and parse-valid** — `node --check docker/web/site/app.js` passes, zero regex lookbehind, `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders intact, no new `<script>`, no second Supabase client, no `#/signals` route.
- **SIGNAL-01..04 stay UNCHECKED in REQUIREMENTS.md** — source authored ≠ requirement satisfied. The live render proof is **Plan 24-03 (ORCHESTRATOR-OWNED, worktree-unsafe):** live-apply migration 044 via Supabase MCP `apply_migration` from the main tree → scoped `docker compose up -d --build web` (SERVICE key `web`, NO `--delete`) from `/root/bitcoin_bot/docker` → operator live-render verify of the `#signals` tier-1 feed (newest-first, capped, safe external links, view-all, and the fail-loud-vs-benign-empty distinction). Reproduce on the substituted `/srv/app.js` (Phase 22 lesson).
- **No blockers.** Pre-live, the new code is a provable no-op for the existing app: until the view+grant land, `fetchSignals()` simply renders the `signals-error` diagnostic into the (previously empty) `#signals-list` — by design (D-07 fail-loud), not a regression of any prior section.

## Known Stubs
None — `#signals-list` is wired to the live `signals_feed` view (the data source ships in Plan 24-01's migration, applied in Plan 24-03). The "Coming soon." placeholder copy was removed, not replaced with a stub.

## Self-Check: PASSED
- Files exist: `docker/web/site/app.js`, `docker/web/site/style-shared.css`, `docker/web/site/index.html` — all FOUND.
- Commits exist: `b791e3e` (Task 1), `4651134` (Task 2) — both FOUND in `git log`.
- `node --check docker/web/site/app.js` exits 0; `grep -ac '(?<'` = 0 (no lookbehind).
- All plan `<automated>` gates (Task 1 + Task 2) return PASS.

---
*Phase: 24-signals-section*
*Completed: 2026-06-17*
