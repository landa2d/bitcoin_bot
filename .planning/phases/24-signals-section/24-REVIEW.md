---
phase: 24-signals-section
reviewed: 2026-06-17
depth: standard
files_reviewed: 4
files_reviewed_list:
  - supabase/migrations/044_signals_anon_view.sql
  - docker/web/site/app.js
  - docker/web/site/style-shared.css
  - docker/web/site/index.html
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 24: Code Review Report

**Reviewed:** 2026-06-17
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 24 signals feed: migration `044_signals_anon_view.sql` (security-definer `public.signals_feed` view + anon GRANT) and the new `fetchSignals()`/`renderSignals()`/`signalHost()` path in `app.js`, plus the CSS/HTML shell changes.

Clean on the high-weight concerns the prompt flagged:
- **Browser-compat: clean.** Only new regex is `/^www\./` (anchored prefix, no lookbehind) — no whole-page-blank risk.
- **CSS: clean.** All five referenced tokens are defined in `style-base.css`. Zero hex.
- **Migration column/row ceiling: structurally sound.** 5-column whitelist + `source_tier = 1 AND source_url IS NOT NULL`; security-definer reasoning correct.
- **`safeHttpUrl` scheme gate present** and correctly skips `javascript:`/`data:` rows.

The one real defect: escaping at the `href` sink is incomplete for attribute context — `escapeHtml` provably does not escape `"`, so a `source_url` with a double-quote breaks out of the `href` attribute. Remaining findings are robustness/fail-loud gaps.

## Critical Issues

### CR-01: Attribute-injection XSS — `escapeHtml(href)` does not escape `"`, allowing breakout in the `href` sink

**File:** `docker/web/site/app.js` (renderSignals href sink; `safeHttpUrl`)

`escapeHtml` is `textNode → div.innerHTML`, which escapes only `&`, `<`, `>`, U+00A0 — **not `"`/`'`**. `safeHttpUrl` only validates the scheme prefix (`/^https?:\/\//i`) and returns the URL body unchanged. So a `source_url` of `https://x.com/" onfocus="alert(1)" autofocus="` passes the gate, survives `escapeHtml`, and renders an injected `onfocus`/`autofocus` handler on the `<a>`. `<`/`>` are escaped (no new tag) but attribute-injection on the anchor is sufficient XSS on this public, raw-served SPA. Real-world likelihood low (tier-1 is curated RSS; needs a literal `"` in the URL) — but a genuine XSS sink with a trivial fix; the same gap is shared by the pre-existing economy_map timeline sink (out of scope, same root cause).

**Fix:** Tighten `safeHttpUrl` to reject URLs containing attribute-breakout/whitespace/control chars (a valid URL percent-encodes these). Single-point fix that also hardens the timeline sink. Optionally also make `escapeHtml` encode `"`/`'`.

## Warnings

### WR-01: Slice-before-filter + empty-string `source_url` → visible count under-runs and "View all (N)" overstates

**File:** `docker/web/site/app.js` (renderSignals); `supabase/migrations/044_signals_anon_view.sql`

The default-visible cap slices BEFORE the safe-URL filter, so a leading unsafe/empty-URL row shrinks the visible set below the cap even when valid rows exist beyond it; "View all (`data.length`)" counts pre-filter rows and overstates. Extreme case: all fetched rows unsafe → zero rows rendered PLUS a "View all (N)" button (benign empty only fires on `data.length === 0`). The view's `source_url IS NOT NULL` also admits `''`.

**Fix:** Filter to safe rows once, then slice/count on the filtered set; (optionally) exclude `source_url = ''` in the view.

### WR-02: A present-but-empty view result is silently shown as a "thin week"

**File:** `docker/web/site/app.js` (three-way split); migration.

The split assumes empty-rows == genuine thin week. A misconfiguration (e.g. `FORCE ROW LEVEL SECURITY` on `source_posts`, wrong predicate, unbackfilled data) could return zero rows with no error and mask as a benign thin week.

**Fix:** Confirm `source_posts` lacks `FORCE ROW LEVEL SECURITY`; optionally `console.warn` on the empty branch for operator visibility.

### WR-03: Frontend ships an error banner to every public visitor if migration 044 is not applied first

**File:** `docker/web/site/app.js`; migration apply ordering.

If `app.js` ships before the view+grant exist, every visitor sees "Signals feed is temporarily unavailable." Blast radius is contained to `#signals` (error does not block `loadList`/`loadHub`).

**Fix:** Treat migration apply as a hard precondition of the frontend cutover.

## Info

### IN-01: `.limit(50)` is an inline magic number while the visible cap is a named constant
Use a named `SIGNALS_FETCH_CEILING = 50`.

### IN-02: `window.currentSignals` global vs. module-scoped convention used elsewhere
Use a module-scoped `var currentSignals;`.

---

## Orchestrator Disposition (2026-06-17)

| Finding | Verified | Disposition |
|---------|----------|-------------|
| **CR-01** (Critical XSS) | **Confirmed real** — `escapeHtml` (textNode→innerHTML) does not escape `"`; `safeHttpUrl` returns the URL unchanged. | **FIXED** before phase verification — `safeHttpUrl` tightened to reject attribute-breakout/whitespace/control chars (escapeHtml on the href kept as defense-in-depth). |
| **WR-01** (slice-before-filter) | Confirmed | **FIXED** — `renderSignals` filters to safe-URL rows before slicing/counting; "View all (N)" counts the safe set; a 0-safe batch shows the benign empty state. |
| **WR-02** (silent empty masking) | **Empirically refuted for this deployment** — the live anon proof returned 5 real tier-1 rows, so the security-definer view bypasses RLS correctly and `source_posts` does NOT have FORCE RLS. | Hardened with a `console.warn` on the 0-row branch (operator telemetry); benign "thin week" UX unchanged. |
| **WR-03** (deploy ordering) | Satisfied this rollout | Migration 044 was applied + proven (anon GET 200, real rows) BEFORE the operator-approved web deploy. Lesson recorded; no code change needed. |
| **IN-01** (magic number) | n/a | Applied — named `SIGNALS_FETCH_CEILING`. |
| **IN-02** (window global) | n/a | Deferred (cosmetic, low value) — `window.currentSignals` retained to keep the fix diff focused. |

_Reviewer: Claude (gsd-code-reviewer) · Depth: standard_
