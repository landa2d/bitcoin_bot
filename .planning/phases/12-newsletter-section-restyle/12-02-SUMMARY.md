---
phase: 12-newsletter-section-restyle
plan: 02
subsystem: ui
tags: [vanilla-js, html, newsletter, toggle-relocation, magazine-header, xss-non-regression]

# Dependency graph
requires:
  - phase: 12-newsletter-section-restyle
    plan: 01
    provides: "Restyled style-shared.css — A1 segmented pill (.mode-toggle/.toggle-btn), B1 .article-entry rows, .section-label/.entry-title/.entry-preview, magazine article rules, #newsletter-content > p:first-of-type lead, .preview-banner class, minimal D3 .hero/.hero-headline/.hero-date text rules"
  - phase: 11-design-system-nav-shell
    provides: "Locked .page-title (serif clamp display) + .eyebrow (mono 11px kicker) display classes; :root tokens (style-base.css)"
provides:
  - "TGL-01 structural relocation: the Technical/Strategic toggle host (.hero) renders only on the list route in showView(); it is hidden on reader/map/block/status/about"
  - "TGL-02 wiring intact: btn-technical/btn-strategic/mode-subtitle IDs + onclick=setMode() preserved verbatim — setMode() has zero logic change; .active drives Plan 01's filled-accent pill"
  - "Date-bearing list kicker: renderList() .section-label reads EDITION #N · {formatDate(published_at)}"
  - "Reader-view magazine header: renderArticle() emits .eyebrow mono kicker + escaped .page-title serif display title + mono byline under the static ← Back to Newsletter control"
  - "Token-based PREVIEW banner: inline-amber #f59e0b swapped for the .preview-banner class (Plan 01 CSS)"
  - "Minimal D3 header markup: WEEKLY INTELLIGENCE BRIEFING tagline dropped; .page-title applied to #hero-headline"
affects: [13-agent-economy-grid, 14-about-stub-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Toggle relocation = scope its host (.hero) to the list route via showView() — no markup move needed; the IDs/onclick stay put so setMode() is untouched (TGL-01 satisfied structurally)"
    - "Magazine header wraps its kicker/byline <p> in a .article-header <div> so they are NOT direct children of #newsletter-content — preserves Plan 01's #newsletter-content > p:first-of-type lead-paragraph rule (matches the first body <p>, not the header)"
    - "escapeHtml() on every DB-derived header string (title); MODES[currentMode].label for the mode token (no hardcoded label); marked.parse() body path unchanged (XSS sink not widened — T-12-03/T-12-04 mitigated)"
    - "U+00B7 separator emitted via String.fromCharCode(0xB7) in the new header strings (toolchain-safe); the literal ' \\u00b7 ' escape elsewhere in app.js left untouched"

key-files:
  created: []
  modified:
    - "docker/web/site/index.html — .hero restructured into the minimal D3 header (tagline dropped, .page-title on #hero-headline); .mode-toggle markup + load-bearing IDs preserved verbatim"
    - "docker/web/site/app.js — showView() scopes the hero/toggle to the list route; renderList() date-appends the kicker; renderArticle() emits the magazine header + .preview-banner; setMode() stale comment corrected (content-re-render-only, D-03)"

key-decisions:
  - "Toggle relocation is structural-via-showView, not a DOM move: the .mode-toggle markup stays inside the .hero block (IDs/onclick untouched) and the hero is scoped to viewName === 'list'. This satisfies TGL-01 without touching setMode()'s getElementById targets — the UI-SPEC §A 'DOM-home discretion resolved' mechanism."
  - "Header kicker/byline <p> wrapped in a .article-header <div> so they are not direct <p> children of #newsletter-content — protects Plan 01's #newsletter-content > p:first-of-type emphasized-lead rule (it must keep matching the first BODY paragraph, not the header)."
  - "Empty-state line re-classed from inline color/size to .entry-preview (serif) — copy 'No newsletters published yet.' unchanged; lets Plan 01's serif rule style it (UI-SPEC permitted dropping the inline style at discretion)."
  - "The new header byline (.byline) was left WITHOUT a dedicated CSS rule — adding one would require editing style-shared.css, which this plan's scope guard explicitly forbids (Plan 01 owns CSS). Documented as a Known Stub; the byline currently inherits article p serif rather than the UI-SPEC §D mono-14px/--ink-faint treatment."

requirements-completed: [TGL-01]

# Metrics
duration: 4 min
completed: 2026-06-04
---

# Phase 12 Plan 02: Newsletter Markup/JS Wiring Summary

**Wired the Newsletter list + article markup/JS onto Plan 01's CSS: relocated the Technical/Strategic toggle to the Newsletter list (TGL-01) by scoping its `.hero` host to the `list` route in `showView()`, restructured the `.hero` into the minimal D3 header, date-appended the `renderList()` kicker, gave the reader view its own escaped magazine header in `renderArticle()`, and swapped the inline-amber PREVIEW banner for the class-based `.preview-banner` — with `setMode()` requiring zero logic change and no new XSS sink introduced.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-04T20:31:21Z
- **Completed:** 2026-06-04T20:35:14Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- **TGL-01 (structural toggle relocation):** `showView()` now renders the `.hero` (the toggle host) **only** on the `list` route (`hero.style.display = viewName === 'list' ? 'block' : 'none'`). The toggle/subtitle display lines were inverted to a `showToggle = (viewName === 'list')` belt-and-suspenders guard, and all three defensive null-checks (`if (hero)`, `if (toggle)`, `if (subtitle)`) are preserved. The toggle no longer appears on reader/map/block/status/about — it lives only inside the Newsletter list.
- **Minimal D3 header (D-07):** the `WEEKLY INTELLIGENCE BRIEFING` `.hero-tagline` line was deleted from `index.html` (grep returns 0); `#hero-headline` carries the locked `.page-title` class (kept `id="hero-headline"` so `updateHero()` still writes into it); `#hero-date` metadata line kept.
- **TGL-02 wiring preserved (zero `setMode()` logic change):** the `.mode-toggle` block — `id="btn-technical" onclick="setMode('technical')"`, `id="btn-strategic" onclick="setMode('strategic')"`, `id="mode-subtitle"`, and the `Technical`/`Strategic` segment labels — is verbatim. `setMode()` still toggles `.active` (drives Plan 01's filled-accent pill), writes `#mode-subtitle` (drives the hint line), persists localStorage, sets `?mode=`, and re-renders.
- **Date-bearing list kicker (criterion 3):** `renderList()` builds `.section-label` as `EDITION #{N} · {formatDate(published_at)}` (U+00B7 separator); the `.substring(0, 150)` excerpt truncation and the locked `updateHero('AI Agents Pulse', 'Latest: …')` strings are unchanged.
- **Magazine article header (D-05, criterion 3):** `renderArticle()` prepends a `.article-header` containing a `.eyebrow` mono kicker (`Edition #{N} · {Technical|Strategic}`), an `escapeHtml()`'d `.page-title` serif display title, and a mono byline (`Edition #{N} · {date} · {Technical|Strategic}`) — under the static `← Back to Newsletter` control. The mode label is resolved via `MODES[currentMode].label` (not hardcoded).
- **Token-based PREVIEW banner (D-05):** the inline-amber `<div style="background:#f59e0b;…">` was swapped for `<div class="preview-banner">` (Plan 01 CSS); copy `PREVIEW — NOT YET PUBLISHED` and the `status === 'preview'` gate unchanged. `grep -c 'f59e0b'` returns 0.
- **Stale comment corrected (D-03):** the `setMode()` line-79 comment no longer claims the body class "drives CSS variables" — it now states the class is a content-re-render selector only (Phase 11 decoupled the palette to `:root`). Comment-only edit; behavior unchanged.

## Task Commits

Each task was committed atomically (single-repo, normal hooks, no `--no-verify`):

1. **Task 1: Restructure index.html .hero into the minimal D3 header** — `424c91f` (feat)
2. **Task 2: Scope the hero/toggle to the list route in showView() + fix stale setMode() comment** — `6d89072` (feat)
3. **Task 3: Date-append renderList() kicker + magazine header & .preview-banner in renderArticle()** — `9f42bc1` (feat)

**Plan metadata** (this SUMMARY + STATE/ROADMAP) committed separately.

## Files Created/Modified

- `docker/web/site/index.html` — `.hero` block restructured into the minimal D3 header: `.hero-tagline` line removed, `.page-title` class added to `#hero-headline`; the `.mode-toggle` markup (both buttons + subtitle) and all load-bearing IDs preserved verbatim. The `#list-view`/`#newsletter-list`, `#reader-view`/`#newsletter-content`/`.backlink`, nav shell, map/block/status/about views, subscribe section, bottom bar, and font `<link>` are untouched.
- `docker/web/site/app.js` — `showView()` hero/toggle scoped to the `list` route (defensive null-checks intact); `setMode()` stale comment corrected (no behavior change); `renderList()` `.section-label` date-appended + empty-state re-classed to `.entry-preview`; `renderArticle()` magazine header emitted + inline-amber banner swapped for `.preview-banner`. `getModeTitle()`/`getModeContent()`, the router, all fetch/localStorage/map/status code untouched.

## Decisions Made

- **Toggle relocation = scope-via-showView, not a DOM move.** Per UI-SPEC §A ("DOM-home discretion resolved"), the `.mode-toggle` stays inside the `.hero` block and the hero is scoped to `viewName === 'list'`. This satisfies TGL-01 structurally while leaving `setMode()`'s `getElementById('btn-technical'/'btn-strategic'/'mode-subtitle')` targets reachable — zero logic change.
- **Header `<p>`s wrapped in `.article-header`.** The kicker/byline `<p>` elements live inside a `.article-header` `<div>`, so they are NOT direct `<p>` children of `#newsletter-content`. This preserves Plan 01's `#newsletter-content > p:first-of-type` emphasized-lead rule (it continues to match the first BODY paragraph from `marked.parse`, not the header). Verified the `.eyebrow` class (specificity 0,1,0) wins font-family over `article p` (0,0,2), so the kicker renders mono correctly.
- **U+00B7 via `String.fromCharCode(0xB7)`.** The new header strings emit the middle-dot separator via `String.fromCharCode(0xB7)` (toolchain-safe); the pre-existing literal `' · '` escapes elsewhere in `app.js` (renderList latest-date, renderArticle hero call) were left untouched.
- **Empty-state re-classed to `.entry-preview`.** Dropped the inline `color/font-size` in favor of the `.entry-preview` serif class (UI-SPEC permitted this at discretion); copy `No newsletters published yet.` is verbatim.

## Deviations from Plan

None affecting scope or behavior. One verification-window nuance (not a code defect):

- **[Verify-window artifact] Task 3 plan grep `-A14` window too small.** The plan's automated verify for renderList uses `grep -A14 'function renderList' … | grep -E 'section-label.*formatDate'`. The `.section-label` date-append lands at delta 19 from `function renderList` (the function body has the empty-state guard + `updateHero` block ahead of the `.map()`), so the 14-line window misses it. Confirmed the code is correct via the regex alternative `formatDate(n.published_at)` and a `-A30` window (PASS), and via the explicit acceptance-criterion grep for the exact kicker line. No fix needed — the markup is correct; only the plan's grep window underspecified the function length.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `.byline` (article metadata line) renders as `article p` serif, not the UI-SPEC §D mono-14px/`--ink-faint` treatment | `docker/web/site/app.js` (`renderArticle()`) — class consumed; no CSS rule | header `<p class="byline">` | Giving `.byline` (and the `.article-header` wrapper) their exact UI-SPEC §D mono/faint styling requires a `style-shared.css` rule, which **this plan's scope guard explicitly forbids** ("Do NOT edit style-shared.css — its styling is already complete from Plan 01"). Plan 01's SUMMARY shipped `.preview-banner`, `.eyebrow`, `.page-title`, `.entry-preview`, `.section-label` but no `.byline`/`.article-header` rule. The byline shows the correct copy (`Edition #N · {date} · {label}`) and is legible (inherits serif body), but not the precise mono metadata style. **Resolution:** a follow-up CSS rule (1-line `.byline { font-family: var(--mono); font-size: 14px; color: var(--ink-faint); }` + optional `.article-header` spacing) belongs in a Plan-01-style CSS pass / Phase 14 polish (POLISH-01) — it does NOT block TGL-01/TGL-02 or criterion 3's structural deliverables. The `.eyebrow` kicker and `.page-title` display title (the two focal elements) ARE fully styled. |

## Threat Flags

None. The plan's threat register (T-12-03/T-12-04/T-12-05) is fully mitigated: the magazine header `escapeHtml()`'s the only DB-derived string (`title`; `edition_number` is numeric; `MODES[currentMode].label` is a hardcoded constant), `formatDate()` returns a markup-free date string, and the `.preview-banner` swap removes inline style with no dynamic interpolation. `marked.parse(content)` is unchanged — the existing accepted escapeHtml-bypass body path — so the innerHTML injection surface is NOT widened. No new href/attribute sink, no package installs (vanilla-JS SPA, no `package.json`).

## Issues Encountered

The Edit tool repeatedly normalized the literal `' · '` escape in the `renderArticle()` block into the `·` glyph, so a single large block-replace anchored on the `updateHero` line failed three times. Resolved by splitting into surgical edits anchored on lines without the escape and emitting the separator at runtime via `String.fromCharCode(0xB7)`. No impact on output correctness.

## User Setup Required

None — no external service configuration. This plan edits two static frontend files served by the read-only `agentpulse-web` Caddy container; no env vars, no migrations, no dashboard config. Heeds the web static-preview caveat: the `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders that `entrypoint.sh` sed-substitutes at container start were NOT touched.

## Next Phase Readiness

- **Phase 12 markup/JS deliverables complete.** TGL-01 (toggle relocated to the Newsletter list via the list-scoped hero) and TGL-02 wiring (preserved IDs + `.active` + `#mode-subtitle`) land; the list kicker carries the date; the article view has its own escaped magazine header; the PREVIEW banner is token-based. `setMode()` needed zero logic change.
- **One CSS follow-up flagged:** a `.byline`/`.article-header` rule (Known Stubs) — a small CSS-pass item, not blocking. Best folded into Phase 14 polish (POLISH-01) or a Plan-01-style CSS touch-up.
- **No prod deploy** (batch-deploy ships after Phase 14, per CONTEXT). Verification is static/source-level; an optional render check against the running container must account for the entrypoint substitution.
- **Scope discipline:** touched ONLY `index.html` + `app.js`. `style-shared.css` untouched (Plan 01 owns it), `style-base.css` untouched, `.claude/settings.local.json` left unstaged, no file deletions.

## Self-Check: PASSED

- FOUND: `docker/web/site/index.html` (modified)
- FOUND: `docker/web/site/app.js` (modified)
- FOUND: commit `424c91f` (Task 1)
- FOUND: commit `6d89072` (Task 2)
- FOUND: commit `9f42bc1` (Task 3)
- FOUND: `.planning/phases/12-newsletter-section-restyle/12-02-SUMMARY.md`
- Success criteria: `grep -c 'f59e0b' app.js` = 0; `grep -c 'WEEKLY INTELLIGENCE BRIEFING' index.html` = 0; `node -c app.js` = OK — all PASS.

---
*Phase: 12-newsletter-section-restyle*
*Completed: 2026-06-04*
