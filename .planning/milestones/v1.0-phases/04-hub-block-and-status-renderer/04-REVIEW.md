---
phase: 04-hub-block-and-status-renderer
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - docker/web/site/app.js
findings:
  critical: 0
  warning: 6
  info: 4
  total: 10
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-05-28
**Depth:** standard
**Status:** issues_found (re-review after CR-01 fix)

## Summary

Re-review of `docker/web/site/app.js` following the fix for **CR-01** (the
`timeline_entries.source_url` `javascript:`/`data:` URL XSS vector). This pass was
scoped to the single file that received the fix; the prior review's `index.html` and
`style-map.css` were not re-read (the fix touched only `app.js`).

**CR-01 is RESOLVED.** A module-level `safeHttpUrl()` allowlist helper was added
(lines 330-333) and both DOM sinks in the timeline render path now consume the
validated URL. Details and verification below.

The six Warnings and four Info items from the prior review all sit in the
**router / poll-lifecycle** code, none of which the CR-01 fix touched — they still
stand unchanged. They range from a confirmed (but currently latent) slug-prefix poll
race down to cosmetic/semantic nits. None are security-critical; none block on their own,
but the router parsing fragility (WR-01/02/04) and the slug-prefix poll guard (WR-03)
should be fixed before the slug set grows.

## CR-01 Verification (RESOLVED)

**Finding (prior):** `renderTimelineEntries()` emitted DB-supplied `source_url` into an
anchor `href` (and a mirrored `data-source` attribute) through `escapeHtml()` only.
`escapeHtml()` HTML-entity-encodes but does not validate the URL scheme, so a
`javascript:alert(document.cookie)` / `data:text/html,...` `source_url` survived
escaping and produced a clickable script-executing anchor. The timeline path is *not*
behind the Phase 9 publish gate and is surfaced live via the 60s poll, so the unsafe
value reached the DOM without an approval step.

**Fix applied (verified correct and complete):**

- `safeHttpUrl(url)` (lines 330-333) returns `null` for non-strings and for any value
  whose trimmed form does not match `^https?:\/\/` (case-insensitive); otherwise returns
  the URL. This is an allowlist (http/https only), which is the correct shape — it rejects
  `javascript:`, `data:`, `vbscript:`, `file:`, and every other scheme by construction
  rather than blocklisting known-bad ones.
- `renderTimelineEntries()` (lines 560-561) computes `var safeUrl = safeHttpUrl(e.source_url)`
  and `var hasSource = safeUrl !== null`. The earlier `length > 0` test that let
  whitespace-only / non-URL strings through is gone.
- The anchor `href` (line 574) now interpolates `escapeHtml(safeUrl)`, emitted only when
  `hasSource`.
- The `data-source` attribute (line 580) is likewise gated on `hasSource` and uses
  `escapeHtml(safeUrl)` — the second sink the prior review called out is fixed too.
- The misleading "all escaped" comment was corrected (lines 557-564) to state the URL is
  both scheme-validated and HTML-escaped.

**No remaining unsafe URL sink in the timeline render path.** Confirmed by tracing all three
callers of `renderTimelineEntries()`: initial render (`renderBlock`, line 536), the
"Show all" expand (`expandTimeline`, line 595), and the 60s idle poll repaint
(`pollEvolution`, line 710) all funnel through the single hardened function, so they
inherit the gate — there is no second render path to miss. The only other DB-derived `href`
in the file is the hub tile (line 411), which targets an internal `#/map/` route built from
`encodeURIComponent(b.slug)`, not a raw external scheme, so it is not a `javascript:` sink.
The two `marked.parse()` sites (lines 216, 526) remain accepted residual risk under
T-04-03-01 (Phase 9 publish gate is the compensating control) and are out of scope for this
finding.

**Defense-in-depth note (not a blocker):** `safeHttpUrl` validates the trimmed string but
returns the *original* (untrimmed) value, so `"  https://example.com"` is passed through with
leading whitespace. Browsers strip leading/trailing whitespace from `href` during URL
resolution and a leading-space value cannot reintroduce a dangerous scheme, so this is not
exploitable — but returning `url.trim()` would be marginally cleaner. Optional.

## Warnings

_All six carry over unchanged from the prior review — the CR-01 fix did not touch the
router or poll-lifecycle code._

### WR-01: Router slug extraction includes the query string and any extra path segments

**File:** `docker/web/site/app.js:118` (`getRoute`)
**Issue:**
`return { view: 'block', slug: hash.split('/')[2] };` takes everything after `#/map/` up to
the next `/` as the slug, verbatim. For `#/map/governance?x=1` the slug becomes
`governance?x=1`; for `#/map/foo/bar` it silently drops `bar`. The slug is then used in
`.eq('slug', slug)` (line 458) and in the poll race-guard `startsWith('#/map/' + slug)`
(line 699). A query string or fragment appended to a map link (e.g. a shared URL with an
analytics param) breaks the DB lookup and the guard. It is also asymmetric with the tile
href, which is `encodeURIComponent(b.slug)` (line 411) — the route does NOT
`decodeURIComponent`, so any slug that percent-encodes would also fail to match. Slugs are
currently hyphen-only so this is latent, but the parsing is fragile.

**Fix:** Strip query/extra segments and decode:

```js
if (hash.startsWith('#/map/')) {
    var rest = hash.slice('#/map/'.length).split('?')[0].split('/')[0];
    return { view: 'block', slug: decodeURIComponent(rest) };
}
```

### WR-02: Empty slug route (`#/map/`) silently hits the "Block not found" path

**File:** `docker/web/site/app.js:117-119, 445`
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

**File:** `docker/web/site/app.js:699` (`pollEvolution`)
**Issue:**
`if (!window.location.hash.startsWith('#/map/' + slug)) return;` is a **prefix** test, not an
exact-slug test. If two slugs ever share a prefix (e.g. a future `governance` and an existing
`governance-accountability`), a poll started for `governance` would keep firing on the
`governance-accountability` page and repaint that page's `#evolution-entries` with the wrong
block's timeline. The current 7-block seed has no prefix collisions, so this is latent — but
the guard's intent ("am I still on the page I started polling for?") is not what the code
checks. The same loose match is in the cleanup listener (line 769) and the visibilitychange
listener (line 782), though those only check `#/map/` so are merely over-broad, not wrong.

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
(the `#/map/` branch above already handles block routes).

### WR-05: "Show all" button shown when a block has exactly 30 entries (false positive)

**File:** `docker/web/site/app.js:537-539` (render) and `:705/:715` (poll repaint)
**Issue:**
The "Show all" affordance is gated on `entries.length === 30`, used as a proxy for "the cap was
hit, there may be more." When a block has *exactly* 30 timeline entries, the button appears but
`expandTimeline()` re-runs the unbounded query and renders the same 30 rows — the button then
removes itself with no visible change. Cosmetic, but it misrepresents that more data exists.

**Fix:** Query one extra row to disambiguate cap-hit from exact-30. Fetch `.limit(31)`, show the
button only when `data.length > 30`, and render `data.slice(0, 30)` in the collapsed view. Update
the `loadBlock` query (line 459), the render gate (line 537), and the poll gate/repaint
(lines 705, 715) consistently.

### WR-06: Poll repaint never removes the "Show all" button when collapsed and entries fall to/under the cap

**File:** `docker/web/site/app.js:714-727` (`pollEvolution`)
**Issue:**
The poll's button-sync logic only *adds* a button (when collapsed, `data.length === 30`, and no
button exists) or *removes* it (when expanded). There is no branch that removes a stale button
when collapsed and `data.length < 30`. Today timeline entries are insert-only so the count never
shrinks, which is why this is a Warning rather than a bug with a live trigger — but the repaint
logic does not actually keep the button "in sync with the (possibly changed) result" as its
comment claims (line 711). If a row is ever deleted/filtered out, a dangling button persists.

**Fix:** Add the symmetric removal:

```js
if (!timelineExpanded && data.length < 30 && btn) {
    btn.remove();
}
```

## Info

### IN-01: `escapeHtml` URL-guarantee comments (RESOLVED by CR-01 fix)

**File:** `docker/web/site/app.js:557-564`
**Issue (prior):** Comments stated `source_url` is "escaped" and conflated HTML-entity escaping
with URL-scheme safety. **Resolved:** the corrected comment block now states the URL is
"both scheme-validated (`safeHttpUrl`) and HTML-escaped" and explains the `javascript:`/`data:`
drop. Documentation now matches the control. Retained here only to record the prior IN-01 is
closed; no action.

### IN-02: `route()` resets `window.currentNewsletter` but not `window.currentBlock` / list state

**File:** `docker/web/site/app.js:742-743`
**Issue:** `route()` nulls only `window.currentNewsletter` on every navigation.
`window.currentBlock`, `window.currentTimelineEntries`, and `window.currentStatusBlocks`
persist across views. No current bug (the visibilitychange guard also checks the hash and
`evolutionPollHandle`), but the asymmetric cleanup is a latent foot-gun if a future handler
reads `window.currentBlock` without a hash re-check. Consider clearing block state on
non-block routes for consistency.

### IN-03: `formatDate` produces locale-dependent output used inside `<time>` without a `datetime` attribute

**File:** `docker/web/site/app.js:335-340, 565` (timeline), `653` (status)
**Issue:** Timeline and status timestamps render `formatDate()` output (e.g. "May 15, 2026")
inside `<time>` elements with no machine-readable `datetime` attribute, and the value depends
on the viewer's locale. Accessibility/semantics nit, not a correctness bug. Consider
`<time datetime="<ISO>">`.

### IN-04: `loadEdition` parses edition number with `parseInt` and no NaN guard

**File:** `docker/web/site/app.js:127, 220`
**Issue:** `#/edition/abc` yields `parseInt('abc') === NaN`, which flows into
`.eq('edition_number', NaN)`. This is pre-existing (not Phase 4 code) and the `.single()`
error path renders "Edition not found," so it degrades gracefully — noted only for
completeness since it sits adjacent to the new routes.

---

_Reviewed: 2026-05-28 (re-review after CR-01 fix)_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
