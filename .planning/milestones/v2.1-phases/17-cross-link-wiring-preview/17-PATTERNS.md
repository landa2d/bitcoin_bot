# Phase 17: cross-link-wiring-preview - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 1 source file edited (`docker/web/site/app.js`) across 3 distinct change sites; 1 file used-not-edited (`docker/web/entrypoint.sh`)
**Analogs found:** 3 / 3 (every change site has an in-file analog; no net-new capability)

> **Scope reminder (from 17-CONTEXT.md `<code_context>`):** this phase edits exactly ONE file — `docker/web/site/app.js`. It writes NOTHING to the DB (no migration / schema / RLS / RPC). `docker/web/entrypoint.sh` is **used unchanged** for the D-02 local-only `service_role` substitution. Every fix reuses an existing `app.js` pattern (`marked.parse`, the existing card-link emission, the conditional body-fetch); there is no new route, component, or DB write. All line numbers below were **verified against the live `app.js`** on 2026-06-08 — they had NOT drifted from the CONTEXT citations.

## File Classification

| Change site (in `docker/web/site/app.js`) | Role | Data Flow | Closest In-File Analog | Match Quality |
|---|---|---|---|---|
| `loadBlock` / `renderBlock` draft-fetch fallback (D-03) — `:539-543` body fetch, `:584-587` render | frontend render path (block page) | request-response (HTTP read) → transform → render | `loadEdition` + `renderArticle` newsletter `status='preview'` fetch/render (`:254-274` / `:221-252`) — the CONTRAST analog; AND the existing same-function published body fetch (`:539-543`) | role-match (preview path) / exact (same-function fetch idiom) |
| `renderHub` hub-intro render + prose block-list trim (D-06a/c) — `:493-499` html assembly, `:496` `HUB_STORYLINE` line | frontend render path (hub landing) | request-response (HTTP read) → transform → render | `renderArticle` (`marked.parse` of a fetched body, `:250`) for the intro; `renderBlock` body section (`:584-587`) for the marked-parse idiom | exact (same `marked.parse` render path) |
| Dormant preview flag gating the draft-fetch (D-04) | frontend config / feature gate | config-read (URL/hash param) | `getInitialMode()` URL-param read (`:49-58`) — `new URL(window.location).searchParams.get('mode')` | exact (same param-read idiom) |
| Cross-link routing (LINK-01) — **no code change**, verify only | router (read-only) | request-response (hash → view) | `getRoute()` `:117-138` + `route()` `:834-847` + `hashchange` `:854` (already resolves `#/map/<slug>` → `loadBlock(slug)`) | n/a — confirmed working, no edit |
| Maturity pills (PREV-01 / Flag F-2) — **no code change**, confirm only | utility (pure render fn) | transform | `renderMaturityPill` `:391-403` + `MATURITY_STAGE` `:38` | n/a — confirmed correct (`emerging→2`, `contested→3`, `nascent→1`) |

---

## Pattern Assignments

### D-03 — Read-only draft-fetch fallback in `loadBlock` (frontend render path, request-response → render)

**Primary analog (the same-function idiom to extend):** the existing conditional published-body fetch at `app.js:535-543`. Today it fetches the body **only when `current_body_version_id` is non-NULL** — which is exactly why an unpublished block renders body-less. D-03 adds an `else` branch (gated by the D-04 flag) that fetches the latest `status='draft'` `block_body_versions` row for that slug.

**Live body-fetch idiom to extend** (`app.js:535-543`):
```javascript
    // Conditionally fetch the published body (D-10 / D-17). Per D-17 NO
    // .eq('status', 'published') — RLS only exposes published versions to anon.
    var bodyMd = null;
    if (blockRes.data.current_body_version_id) {
        var bodyRes = await sb.schema('economy_map').from('block_body_versions').select('body_md').eq('id', blockRes.data.current_body_version_id).single();
        if (!bodyRes.error && bodyRes.data) bodyMd = bodyRes.data.body_md;
    }
```

**D-03 shape (the planner pins exact wording):** add the fallback **after** the existing `if` — when `bodyMd` is still null AND the preview flag is set, fetch the draft by slug. Use the exact same `sb.schema('economy_map')` access (D-16 sets `Accept-Profile` automatically — do NOT hand-build a PostgREST httpx call here; the frontend uses supabase-js, unlike the Python loader in Phase 16). Mirror the **graceful-degrade** posture already used for the timeline (`:531-533`) and the published body (`:542`): a missing/failed draft leaves `bodyMd = null` and renders body-less, never throws.
```javascript
    // D-03 (preview-only): when no published version is pinned, fall back to the
    // latest draft body. Gated by the D-04 flag → DORMANT in prod (no flag set),
    // and a NO-OP for anon even if reached (RLS exposes only status='published').
    if (!bodyMd && PREVIEW_ENABLED) {
        var draftRes = await sb.schema('economy_map')
            .from('block_body_versions')
            .select('body_md')
            .eq('block_slug', slug)
            .eq('status', 'draft')
            .order('created_at', { ascending: false })   // latest draft (append-only versions)
            .limit(1);
        if (!draftRes.error && draftRes.data && draftRes.data.length) bodyMd = draftRes.data[0].body_md;
    }
```
Notes for the planner: (1) confirm the actual append-ordering column on `block_body_versions` (`created_at` vs an `id`/`version` — check `033`/Phase-16 16-PATTERNS §column-contract) before pinning `.order(...)`. (2) Use `.limit(1)` + array (not `.single()`) so zero-draft in prod returns cleanly empty rather than erroring. (3) The `.eq('status','draft')` here is **functional scoping for the draft path**, not the D-17 forbidden `.eq('status','published')` defensive filter — it is the deliberate inverse and only reachable behind `PREVIEW_ENABLED`.

**The render side needs NO change** — `renderBlock` already hides the body section when `bodyMd` is falsy and `marked.parse`'s it when present (`app.js:584-587`):
```javascript
    var bodyHtml = '';
    if (bodyMd) {
        bodyHtml = '<section class="block-body">' + marked.parse(bodyMd) + '</section>';
    }
```
The `marked.parse`-rendered draft body is where the **15 block→block `#/map/<slug>` cross-links** become real `<a href>` elements (LINK-01) — they only exist on the page once the draft body renders, which is the whole point of D-03.

**CONTRAST analog (the rejected mirror — model the fetch-then-render *shape* on it, NOT the mechanism):** the newsletter `status='preview'` path. `loadEdition` (`:254-274`) fetches a non-published row via `.in('status', ['published','preview'])` and `renderArticle` (`:221-252`) shows a `<div class="preview-banner">PREVIEW — NOT YET PUBLISHED</div>` (`:231-234`) then `marked.parse`'s the body (`:250`). This is the closest existing "fetch-and-render a non-published body" pattern in the file. **D-01/D-02 deliberately did NOT mirror it for blocks** — blocks have no `status='preview'` enum value (that exists for `newsletters` only, migration 028); adding one would be a schema/RLS change. So borrow only the *fetch-then-marked.parse* render shape; the access path is the `service_role`-substituted local container + draft-status fetch, not a `preview` status.

---

### D-06a/c — `renderHub` hub-intro render + prose block-list trim (frontend render path, request-response → render)

**Analog:** the `marked.parse` body render in `renderArticle` (`:250`) / `renderBlock` (`:586`). D-06a replaces the `HUB_STORYLINE` line in the hub html assembly with a `marked.parse` of the hub draft body (fetched via the same D-03 fallback, since the hub `blocks` row's `current_body_version_id` is also NULL pre-publish), and D-06c **code-trims** that body so its prose block-list is not duplicated by the cards.

**The exact html-assembly site to edit** (`app.js:493-499`):
```javascript
    var html =
        '<h1 class="page-title">The Agent Economy</h1>' +
        subline +
        '<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>' +
        tierSection(TIER_LABELS.substrate, substrateBlocks) +
        tierSection(TIER_LABELS.behavior, behaviorBlocks) +
        tierSection(TIER_LABELS.frame, frameBlocks);
```
D-06a replaces the `'<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>'` line with `marked.parse(trimmedHubBody)` when a hub draft body is available, with **graceful fallback to the existing `HUB_STORYLINE` constant** when it is not (P15-D-04 / D-06a). The `loadHub` query already selects `current_body_version_id` (`:422`), so the deferred/null detection used by `renderTile` (`:461`) is available — but the hub draft body itself must be fetched the same way as D-03 (by slug `'agent-economy'`, `status='draft'`), gated by `PREVIEW_ENABLED`.

**The trim (D-06c) — exact cut-points from `.planning/docs/00-hub.md` (the loaded hub body):** the hub body's structure is:
- L9-17: title + thesis (KEEP)
- **L19-27: `## How to read this map`** two-tier framing (KEEP — the "intro")
- L29 `---`, then **L31-55: `## Tier 1 — The Substrate` / `## Tier 2 — The Behavior` prose block-list** (the 7 `**[Title →](#/map/<slug>)**` links — **TRIM**, this is the HUB-01 duplication source)
- L56 `---`, then **L58-60: `## The thesis, restated`** (OPTIONAL keep, per Claude's Discretion default)

The trim must operate on the **markdown string before `marked.parse`** (simpler + safer than DOM surgery post-render). Suggested deterministic cut: drop everything from the `## Tier 1` heading up to (and including) the closing `---` before `## The thesis, restated` — i.e. split on the `## Tier 1` heading and on `## The thesis, restated`, keeping the head (thesis + How-to-read) and optionally re-appending the restated-thesis tail. Planner pins the exact regex/split (suggest matching the literal headings `## Tier 1` and `## The thesis, restated`, or a sentinel) and the keep/drop decision on the closing paragraph. **Reason this is in-code not a doc edit:** D-06 chose the code-trim over editing `00-hub.md` + reloading (the rejected variant) so the loaded draft stays untouched and reversible.

**No card-grid change.** The 7 cards already satisfy hub→block click-through — `renderTile` (`:467`) already emits `<a href="#/map/' + encodeURIComponent(b.slug) + '">`. The hub `blocks` row has `tier='hub'`, which the three tier filters (`:450-452`, `substrate`/`behavior`/`frame`) already exclude — so **no hub card** is rendered (correct).

**Existing card-link emission (the hub→block LINK-01 source — confirm, no change)** (`app.js:467-471`):
```javascript
        return '<a href="#/map/' + encodeURIComponent(b.slug) + '" class="' + cls + '">' +
                   '<h3 class="tile-title">' + escapeHtml(b.title) + '</h3>' +
                   '<p class="tile-subtitle">' + escapeHtml(b.subtitle) + '</p>' +
                   dotsRow +
               '</a>';
```

---

### D-04 — Dormant preview flag (frontend config / feature gate, config-read)

**Analog:** `getInitialMode()` URL-param read (`app.js:49-58`) — the file's established "read a flag off the URL" idiom:
```javascript
function getInitialMode() {
    var urlMode = new URL(window.location).searchParams.get('mode');
    if (urlMode && MODES[urlMode]) return urlMode;
    // ...
    return 'technical';
}
```

**D-04 shape:** define a single module-scoped `PREVIEW_ENABLED` near the other Phase-4 constants (`:28-46`), resolved from a URL/hash param (e.g. `?preview=1`) read with the same `new URL(window.location).searchParams.get(...)` idiom, OR a build-time constant. It gates **both** D-03 draft-fetch branches (block + hub). **Double-safe (D-04):** in prod the flag is unset **and** published-only RLS independently suppresses any draft — either alone makes the path a no-op. This is what lets the small render path **ship in `app.js`** (one reviewable `/diff`) while staying dormant in production. Keep it content-scoped: no new route, no new view, no new component — just a boolean read.

---

### LINK-01 routing — confirm only, NO code change

`getRoute()` already maps `#/map/<slug>` → `{ view: 'block', slug }` (`:119-121`), `route()` dispatches `case 'block': loadBlock(r.slug)` (`:843`), and `hashchange` re-runs `route()` (`:854`). So every `marked.parse`-rendered `<a href="#/map/<slug>">` (hub cards + the 22 in-body cross-links) "just works" on click — the real gap LINK-01 closes is the **empty body pre-publish** (fixed by D-03), not routing.

`getRoute()` `:117-124` (confirm-only):
```javascript
function getRoute() {
    var hash = window.location.hash || '#/';
    if (hash.startsWith('#/map/')) {
        return { view: 'block', slug: hash.split('/')[2] };
    }
    if (hash.startsWith('#/map')) {
        return { view: 'map' };
    }
```

### Maturity pills (PREV-01 / Flag F-2) — confirm only, NO code change

`renderMaturityPill` (`:391-403`) + `MATURITY_STAGE` (`:38`) already render the three distinct preview stages: **`emerging→2`, `contested→3`, `nascent→1`** (unknown `|| 1` guard at `:396`). ⚠ **Flag F-2:** the substrate trio renders **`emerging`** (remapped at load, P15-D-01), NOT the literal doc word `building`. Verify against `emerging`/`contested`/`nascent` — do NOT "fix" the pill to say `building`. `nascent` (negotiation-coordination + psychology-disposition) is **pill-only**, no distinct visual treatment (Claude's Discretion default; SC#4 / D-06 OUT).

---

## Shared Patterns

### RLS-is-the-read-boundary → the draft-fetch is a prod no-op (the spine)
**Source:** 15-CONTRACT anon RLS (`033:367-370`, `block_body_versions USING(status='published')`); CONTEXT D-02/D-03.
**Apply to:** both D-03 fetches (block + hub).
- Anon sees only `status='published'` bodies; `service_role` bypasses RLS. The local preview container substitutes the `service_role` key into `__SUPABASE_ANON_KEY__` (D-02) so it alone sees the drafts.
- In prod (anon key + no `PREVIEW_ENABLED` flag) the draft-fetch returns no rows AND is gated off — **double-safe** (D-04). The deployed `app.js` renders byte-for-byte as today.

### D-02 substitution rides the EXISTING mechanism (zero new code)
**Source:** `docker/web/entrypoint.sh:3-4` (used unchanged).
**Apply to:** the local preview container only.
```sh
sed -i "s|__SUPABASE_URL__|${SUPABASE_URL}|g" /srv/app.js
sed -i "s|__SUPABASE_ANON_KEY__|${SUPABASE_ANON_KEY}|g" /srv/app.js
```
- The local container is run with `SUPABASE_ANON_KEY=<service_role>`; the sed at `:4` substitutes it into `app.js:5` (`const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';`). **No edit to `entrypoint.sh`.**
- **Mandatory guard (D-02):** the **deployed** `app.js` keeps the real **anon** key — the `service_role` key NEVER ships. Confirm via branch + `/diff`: `app.js:4-5` still hold the `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders (substitution is env-time, not committed), and only the local run env carries the `service_role` value. The `service_role` = historical failure actor risk is contained to a throwaway local container.
- ⚠ MEMORY gotcha `reference_web_static_preview_substitution`: serving raw `docker/web/site` crashes `app.js` at module-load on the unsubstituted `createClient('__SUPABASE_URL__')`. The preview MUST be the substituted **container** (or a sed'd temp copy), never the raw source dir — this bit Phase 11 human verification.

### supabase-js schema isolation (frontend) — NOT the Python httpx path
**Source:** `app.js` `loadHub`/`loadBlock` (`sb.schema('economy_map').from(...)`, `:419-422`, `:518-519`, `:541`); D-16.
**Apply to:** both D-03 draft fetches.
- Frontend uses `sb.schema('economy_map')` which sets `Accept-Profile` automatically (D-16) — do **not** hand-build the direct-PostgREST httpx call from the Phase-16 loader here (that is the Python-service pattern; the browser uses supabase-js). Never `.in_()` — but the frontend uses `.eq()`/`.in()` array filters which are fine.
- Keep the D-17 posture: no defensive `.eq('status','published')` on the published path (RLS is the boundary). The D-03 `.eq('status','draft')` is the deliberate, flag-gated inverse for the preview path only.

### `marked.parse` is the one body-render path (reuse verbatim, no new capability)
**Source:** `app.js:250` (newsletter), `:586` (block body).
**Apply to:** the hub intro (D-06a) and the draft block bodies (D-03).
- The XSS-via-markdown disposition (T-04-03-01) carries over; the operator publish gate is the compensating control (P15-D-04). No sanitizer is added — same precedent as `renderArticle`/`renderBlock`.

### Graceful-degrade-not-throw on a missing body
**Source:** `app.js:531-533` (timeline), `:542` (published body), `:524-529` (block-not-found).
**Apply to:** both D-03 fetches and the D-06a hub-intro.
- A failed/empty draft fetch leaves `bodyMd`/hub-intro null → renders body-less (block) or falls back to `HUB_STORYLINE` (hub) — never throws, matching the existing conditional-body posture.

### Fail-loud cross-link verification (D-05) — a verification harness, not app code
**Source:** CONTEXT D-05 / `<specifics>` (22 instances, 7 in-scope target slugs, none → `regulation-legal`); MEMORY `feedback_fail_loud_governance`.
**Apply to:** the phase verification step (NOT `app.js`).
- Programmatically extract every `#/map/<slug>` href from the `marked.parse`-rendered hub + 7 bodies; **assert each target slug ∈ the live `blocks` roster, fail-loud on any miss** (guards future content drift) + operator **manual click-through** the full 22-instance set on the local preview. The assertion is trivially green today; it exists to fail-loud on drift and the manual pass eyeballs the rendered pages. This is the last gate before Phase 18 publish.

---

## No Analog Found

None. Every Phase-17 change site extends an existing `app.js` pattern:
- D-03 draft-fetch → extends the same-function conditional body fetch (`:535-543`); the newsletter `preview` path (`:254-274`/`:221-252`) is the contrast model for fetch-then-render shape.
- D-06a hub intro → reuses `marked.parse` (`:250`/`:586`); D-06c trim is a pre-parse string operation with deterministic cut-points already located in `00-hub.md` (L31-55).
- D-04 flag → reuses `getInitialMode()`'s URL-param read (`:49-58`).
- D-02 substitution → reuses `entrypoint.sh:3-4` verbatim.

**Adaptation deltas the planner must bridge (not missing analogs):**
1. The Phase-16 loader used **direct PostgREST httpx** with `Content-/Accept-Profile` headers; the frontend uses **supabase-js `sb.schema('economy_map')`** instead — do not cross the wires.
2. There is no `status='preview'` for `block_body_versions` (newsletters-only, migration 028) — the draft path keys off `status='draft'` + the local `service_role` key + the `PREVIEW_ENABLED` flag, NOT a preview status.
3. The append-ordering column on `block_body_versions` for "latest draft" must be confirmed (`created_at` vs `id`/version) before pinning the `.order(...)` clause.

## Metadata

**Analog search scope:** `docker/web/site/app.js` (lines 1-160, 190-310, 385-615, 825-870 — all cited regions verified against live), `docker/web/entrypoint.sh` (full), `.planning/docs/00-hub.md` (full — for the D-06c trim cut-points), `.planning/phases/16-content-load-unpublished/16-PATTERNS.md` (format/findings reuse).
**Files scanned:** 4 (1 source file across 4 non-overlapping reads, 1 entrypoint, 1 hub body, 1 prior pattern map).
**Pattern extraction date:** 2026-06-08
