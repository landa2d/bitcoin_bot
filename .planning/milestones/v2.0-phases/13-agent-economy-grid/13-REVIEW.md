---
phase: 13-agent-economy-grid
reviewed: 2026-06-04T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/web/site/app.js
  - docker/web/site/index.html
  - docker/web/site/style-shared.css
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-04
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 13 re-rendered the Agent Economy hub as a tier-grouped 2-column card grid (with a
full-width DEFERRED variant), de-darkened the block-detail and status views onto the
serif/light single-accent system, and completed the deletion of `style-map.css` by folding
its rules into `style-shared.css`. The change is well-scoped and the core focus areas are
clean:

- **RLS / D-17 boundary respected.** No `.eq('status', …)` filter was added to `loadHub`,
  `loadBlock`, or `loadStatus`. The only `status`-string occurrences in app.js are comments
  documenting the deliberate absence. Verified via `grep -nE "\.eq\(['\"]status"`.
- **CSS cascade is intact after the `style-map.css` deletion.** Every `var(--…)` token
  consumed by `style-shared.css` is defined in `style-base.css:root` (diffed the used-set
  against the defined-set — zero orphans). The retired `--accent-tier` /
  `--accent-*-base` tokens are referenced only in comments, never in live declarations.
  Braces balance (114/114); `node --check app.js` passes.
- **`index.html` links only `style-base.css` + `style-shared.css`** — the `style-map.css`
  `<link>` was removed.
- **Dead `data-accent` attributes fully removed** from `renderMaturityPill`, `renderTile`,
  `renderBlock` header, and `renderStatusRow`. The `block-tile` class was correctly renamed
  to `card`, and `.tile-title` / `.tile-subtitle` are re-scoped under `.card` in CSS to
  match the new markup.
- **DEFERRED logic is correct.** `data-stage="0"` matches none of the
  `[data-stage="1..5"]` fill rules, so all five segments fall back to `--line-strong`
  (empty dots). The deferred path passes `renderMaturityPill(b, true)`, which never touches
  the (null-for-deferred) `b.maturity`, avoiding an `escapeHtml(null)`. `card-deferred`
  spans the row via `grid-column: 1 / -1`.

One cross-cutting WARNING about the `escapeHtml()` implementation is recorded below: it does
not encode double quotes, so it is unsafe in HTML *attribute* context. This is **not
exploitable through the Phase 13 changes** (the one attribute sink Phase 13 modified —
`aria-label` — is fed by the Postgres `maturity` enum, which cannot hold a quote), but it is
a latent foot-gun the next attribute sink will step on, and it is worth fixing while this
file is open. Three INFO items cover a deployed dangling stylesheet link, a media-query
breakpoint inconsistency, and a benign always-on "Show all" edge.

## Warnings

### WR-01: `escapeHtml()` does not encode quotes — unsafe for HTML attribute context

**File:** `docker/web/site/app.js:355-359` (definition); sinks at `app.js:400`, `app.js:634`, `app.js:640`
**Issue:**
`escapeHtml()` uses the DOM `textNode` → `innerHTML` trick, which encodes only `&`, `<`,
and `>` — it does **not** encode `"` (verified empirically). Its output is therefore safe
in element-text context but unsafe when interpolated into a double-quoted HTML attribute.
Phase 13 routes one Supabase string field through `escapeHtml()` into an attribute value:

```js
// app.js:400 — aria-label is a double-quoted attribute
'<div class="maturity-pill" data-stage="' + stage + '" aria-label="' + label + '">'
// where label = 'Maturity: ' + escapeHtml(b.maturity) + ' (' + stage + ' of 5)'
```

A `b.maturity` value containing `"` would break out of `aria-label` and inject arbitrary
attributes (e.g. `onmouseover=…`) onto the `<div>`. The deployed CSP allows
`script-src 'self' 'unsafe-inline'` (`docker/web/Caddyfile:19`), so an injected inline
handler **would execute** — CSP is not a mitigation here.

**Why this is a WARNING, not a BLOCKER for Phase 13:** `b.maturity` is a real Postgres
`ENUM` (`supabase/migrations/033_economy_map_schema.sql:46`), so the database cannot store a
quote in it — the Phase-13 sink is not attacker-reachable today. The other two attribute
sinks (`href` / `data-source` at `app.js:634` / `:640`, fed by `safeHttpUrl(source_url)`
which only validates the `https?://` prefix and would pass a URL like
`https://x/"onmouseover=…`) are **pre-existing and unchanged in this phase**, and
`source_url` is operator-curated content gated by the Phase 9 publish approval
(threat T-04-03-01).

**Fix:** Make `escapeHtml()` attribute-safe so every current and future sink is covered:
```js
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
```
This is a single-function change that closes the attribute-context gap without altering any
text-node call site.

## Info

### IN-01: Deleting `style-map.css` left a dangling `<link>` in a deployed file

**File:** `docker/web/site/tokens-preview.html:8`
**Issue:** `tokens-preview.html` still contains `<link rel="stylesheet" href="/style-map.css">`.
The Dockerfile `COPY site/ /srv/` ships this file, and the Caddyfile serves `/srv`, so the
preview page now issues a 404 for the deleted stylesheet and renders unstyled. It is not in
the Phase 13 review scope and not part of the production SPA, but the deletion left it
broken.
**Fix:** Either remove the `style-map.css` link from `tokens-preview.html` (it is a
dev-only token preview), or exclude `tokens-preview.html` from the Docker `COPY` so the dev
artifact is not deployed. Low priority.

### IN-02: Hub grid mobile breakpoint (640px) differs from the global responsive block (600px)

**File:** `docker/web/site/style-shared.css:321` vs `style-shared.css:860`
**Issue:** The new card `.grid` collapses to one column at `max-width: 640px`, matching the
nav-shell breakpoint in `style-base.css:217`, but the long-standing site responsive block
(container padding, bottom bar, subscribe form) triggers at `max-width: 600px`. Between
601–640px the grid is single-column while the rest of the layout is still in desktop mode.
Cosmetic only, no broken rendering.
**Fix:** Optional — align the card-grid breakpoint to 600px, or document the 640px choice as
intentional (it mirrors the nav breakpoint).

### IN-03: "Show all" button shows even when exactly 30 (uncapped) entries exist

**File:** `docker/web/site/app.js:597-599` (and the poll mirror at `app.js:776`)
**Issue:** The button render is gated on `entries.length === 30`, which cannot distinguish a
hit-the-`limit(30)`-cap result from a coincidental exactly-30 unbounded result. In the
latter case the button appears and `expandTimeline()` re-fetches the same 30 rows. Harmless
(idempotent), pre-existing, and not touched by Phase 13 — noted for completeness.
**Fix:** Optional — fetch `limit(31)`, render the first 30, and show the button only when 31
rows came back (a true "more exist" signal).

---

_Reviewed: 2026-06-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
