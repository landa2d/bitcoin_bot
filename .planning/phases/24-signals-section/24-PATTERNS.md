# Phase 24: Signals Section - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 4 (1 new, 3 modified)
**Analogs found:** 4 / 4 (every surface has a strong in-repo precedent)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `supabase/migrations/044_*.sql` (NEW) | migration | CRUD (DDL / anon read-path) | `001_initial_schema.sql` (CREATE VIEW) + `033_economy_map_schema.sql` (anon GRANT) + `028_newsletter_preview.sql` (anon SELECT) | composite-strong (see ⚠ on `security_invoker`) |
| `docker/web/site/app.js` (MODIFIED — add `fetchSignals()`/`renderSignals()`) | component + utility (frontend module) | request-response (anon read) | `loadList()` / `renderList()` pair (newsletter list) | exact |
| `docker/web/site/style-shared.css` (MODIFIED — signal-row styling) | config / styling | n/a | Phase 23 `.row` / `.archive-label` block | exact (reuse) |
| `docker/web/site/index.html` (MODIFIED — replace placeholder `<p>`) | template shell | n/a | existing `#signals` shell (Phase 21) | exact (shell already present) |

---

## Pattern Assignments

### `supabase/migrations/044_*.sql` (migration, anon read-path)

Composite migration: create a **security-definer VIEW** over `source_posts` + `GRANT SELECT … TO anon`. Three precedents combine; **no single in-repo migration does view+anon-grant together**, so assemble from these.

**Base table shape** — `004_core_tables.sql:9-24`. The exact columns the view exposes (`id, title, source_url, source, scraped_at`) and the filter columns (`source_tier`, `source_url`):
```sql
CREATE TABLE IF NOT EXISTS source_posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          TEXT NOT NULL,
    source_url      TEXT,
    source_tier     INTEGER DEFAULT 3,   -- 1=authority, 2=curated, 3=community  → tier-1 = source_tier = 1
    title           TEXT,
    body            TEXT,                 -- D-01: NEVER expose (copyright/leak)
    ...
    metadata        JSONB,                -- D-01: NEVER expose (internal extraction)
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
);
```

**Supporting index already exists** — `005_missing_indexes.sql:24-25` (no new index needed; the view's `WHERE source_tier = 1 … ORDER BY scraped_at DESC` is backed by this):
```sql
CREATE INDEX IF NOT EXISTS idx_source_posts_tier_scraped
    ON source_posts(source_tier, scraped_at DESC);
```

**Current RLS state** — `006_rls_policies.sql:21` (`source_posts` RLS ENABLED, no anon policy = anon fully blocked; D-01 keeps this — the base table is NOT touched by 044):
```sql
ALTER TABLE source_posts ENABLE ROW LEVEL SECURITY;
```

**View-creation precedent** — `001_initial_schema.sql:153-162` (the only `CREATE VIEW` idiom in-repo):
```sql
CREATE OR REPLACE VIEW top_problems_recent
WITH (security_invoker = on) AS
SELECT p.*, pc.theme as cluster_theme
FROM problems p
LEFT JOIN problem_clusters pc ON p.id = ANY(pc.problem_ids)
WHERE p.last_seen > NOW() - INTERVAL '30 days'
ORDER BY p.frequency_count DESC
LIMIT 50;
```

> ⚠ **LOAD-BEARING INVERSION — do NOT copy `security_invoker = on`.** The 001 views use `security_invoker = on`, which runs the view as the *invoking* role (anon). With `source_posts` RLS enabled and no anon policy, an invoker-rights view returns **zero rows for anon** — the feature would silently render the benign empty state forever (a fail-loud violation in disguise). D-01 requires the *opposite*: a **security-definer view** (the Postgres default — either omit the `WITH` clause or write `WITH (security_invoker = off)`). Owned by the migration role (`postgres`, the table owner), it bypasses `source_posts` RLS and returns ONLY the 5 whitelisted columns / tier-1 rows. That column+row ceiling lives in the view body — the frontend selecting 4 columns is NOT the boundary (operator's explicit reasoning: "RLS can't hide columns").

**Anon GRANT precedent** — `033_economy_map_schema.sql:381-386` (PostgREST needs BOTH an RLS pass AND a SELECT grant; for a brand-new object grant explicitly):
```sql
-- PostgREST requires BOTH an RLS pass AND a SELECT GRANT — the grant on the new
-- schema must be explicit (unlike public, where anon already has grants).
GRANT SELECT ON economy_map.blocks TO anon;
```
> For 044 the view lives in the **public** schema (D: standard anon REST, no `Accept-Profile`, unlike `economy_map`). Still emit an explicit `GRANT SELECT ON <view> TO anon` — do not rely on public-schema default privileges for a freshly-created object.

**Anon-read filter precedent** — `028_newsletter_preview.sql:4-9` / `006:38-42` show the `FOR SELECT TO anon USING (…)` idiom. For a security-definer view the filter lives in the view's `WHERE` (not a policy), but these confirm `anon` is the right grantee and the project's "narrow anon read" idiom:
```sql
CREATE POLICY newsletters_anon_read ON newsletters
    FOR SELECT TO anon
    USING (status IN ('published', 'preview'));
```

**View body must encode (D-01/D-02/D-04):** `SELECT id, title, source_url, source, scraped_at FROM source_posts WHERE source_tier = 1 AND source_url IS NOT NULL ORDER BY scraped_at DESC` + a stable tie-break (e.g. `, id DESC` — planner discretion). Idempotency: `CREATE OR REPLACE VIEW` (001 idiom) + `GRANT` is replay-safe.

**Header/idempotency conventions** — `043_economy_map_hub_and_negotiation_blocks.sql:1-28`: every migration opens with a `-- Migration NNN: <one-line purpose>` line, then a multi-line `--` rationale block (what it does, in what order, idempotency note, the D-NN decisions it lands). Match that header style; cite D-01/D-02/D-04 and the "base table stays blocked" invariant.

---

### `docker/web/site/app.js` (component + utility, request-response read)

**Analog:** the newsletter `loadList()` (fetch) / `renderList()` (render) pair — direct template for `fetchSignals()`/`renderSignals()`.

**Anon Supabase client init** (lines 3-7) — reuse the EXISTING `sb` client; the `__SUPABASE_*__` placeholders are `sed`-substituted by `entrypoint.sh` at container start. Do NOT add a second client.
```javascript
const SUPABASE_URL = '__SUPABASE_URL__';
const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';
const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
```

**Fetch pattern** (`loadList()`, lines 502-526) — the public-schema `sb.from(<view>).select(…).order(…)` shape. The view is **public schema**, so NO `.schema('economy_map')` call (that idiom in `loadHub()` is only for the economy_map schema).
```javascript
var { data, error } = await sb
    .from('newsletters')
    .select('*')
    .in('status', ['published', 'preview'])
    .order('edition_number', { ascending: false });

if (error || !data || data.length === 0) {       // ⚠ loadList CONFLATES error+empty — see below
    document.getElementById('newsletter-list').innerHTML = '<p …>No newsletters published yet.</p>';
    return;
}
window.currentNewsletterList = data;
renderList(data);
```
> ⚠ **D-07 deviation from the analog.** `loadList()` collapses `error` and empty into one branch. `fetchSignals()` must **split three cases**: (a) `error` (non-2xx / PostgREST error → missing view or grant) → LOUD inline diagnostic ("Signals feed is temporarily unavailable") **+ `console.error(...)`** (matches the `console.error('loadHub error:', error)` idiom at app.js:745 and `loadBlock` at :978); (b) `200` + `[]` → benign quiet empty state ("No tier-1 signals this week"); (c) rows → render. For the view query select exactly the 5 view columns and `.order('scraped_at', { ascending: false })`, `.limit(<hard cap ~50>)` (D-03).

**Render + indexed-row markup** (`renderList()`, lines 462-500, esp. the `.row` builder 484-499) — the exact row template to mirror. Note: whole `<a>` is the click target; every DB string passes through `escapeHtml()`; `formatDate()` formats the date column.
```javascript
var html = '<p class="archive-label">Archive</p>' + data.map(function(n) {
    var title = getModeTitle(n);
    var sum = extractDistinctExcerpt(getModeContent(n));
    var sumFragment = sum ? '<p class="sum">' + escapeHtml(sum) + '</p>' : '';
    return '<a href="#/edition/' + n.edition_number + '" class="row">' +
        '<span class="num">' + n.edition_number + '</span>' +
        '<span>' +
            '<p class="title">' + escapeHtml(title) + '</p>' +
            sumFragment +
        '</span>' +
        '<span class="date">' + escapeHtml(formatDate(n.published_at)) + '</span>' +
        '</a>';
}).join('');
document.getElementById('newsletter-list').innerHTML = html;
```
> For Signals each row's `href` is the **external** `source_url` (D-06): `target="_blank" rel="noopener noreferrer"`, and the href MUST pass `safeHttpUrl()` first (see Shared Patterns). The newsletter row uses an internal `#/edition/N` hash; Signals diverges to an external link. Row anatomy maps cleanly: date · title (headline) · source-domain. Date column = `formatDate(row.scraped_at)` (D-04). The `↗` hover affordance (D-06) is a CSS/markup addition (see style-shared.css below).

**The innerHTML-sink escape guard** (`escapeHtml()`, lines 665-669) — apply to EVERY DB-derived value at the sink (title, derived hostname):
```javascript
function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}
```

**The URL-scheme allowlist** (`safeHttpUrl()`, lines 674-677) — gate `source_url` through this BEFORE using it as an `href` (escapeHtml does NOT block `javascript:`/`data:`):
```javascript
function safeHttpUrl(url) {
    if (typeof url !== 'string') return null;
    return /^https?:\/\//i.test(url.trim()) ? url : null;
}
```

**Date formatter** (`formatDate()`, lines 679-684) — reuse verbatim on `scraped_at` (D-04 mandates consistency with the newsletter list):
```javascript
function formatDate(isoStr) {
    if (!isoStr) return '';
    return new Date(isoStr).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
}
```

**Hostname derivation (D-05) — net-new, no exact analog.** Derive a www-stripped hostname from `source_url` at render. `new URL(...)` is already used in app.js (`getInitialMode()` :231, `PREVIEW_ENABLED` :69), so the pattern is established; wrap in try/catch (it throws on unparseable input) and fall back to the row's internal `source` value. **NO regex lookbehind** (WR-01). A plain anchored prefix strip is safe:
```javascript
function signalHost(url, fallback) {
    try { return new URL(url).hostname.replace(/^www\./, ''); }  // anchored prefix — NO lookbehind
    catch (e) { return fallback || ''; }
}
// at the sink: escapeHtml(signalHost(row.source_url, row.source))
```

**Integration point — the gated (not premature) fetch** (`ensureLandingDataLoaded()`, lines 451-458). This one-shot runs only when the landing is shown, satisfying Phase 21's "no premature fetch on the RLS-blocked table". Add `fetchSignals()` to the existing `Promise.all`:
```javascript
function ensureLandingDataLoaded() {
    if (landingDataLoaded) return landingDataLoadedPromise;
    landingDataLoaded = true;
    landingDataLoadedPromise = Promise.all([loadList(), loadHub()]);   // ← add fetchSignals() here
    return landingDataLoadedPromise;
}
```
> `route()` (:1394) → `showLanding()` (:364) → `ensureLandingDataLoaded()` is the single load path; `fetchSignals()` returns a Promise (like `loadList`) so it participates in the settle gate that defers deep-link scrolls (WR-01 at :416). Render into `#signals-list` (already in the DOM, index.html:93).

**"View all" expand (D-03) — net-new, no exact analog.** Default cap ~12-15 visible + a "View all / Show more" control revealing up to ~50 inline (NO route). Planner discretion whether to re-query or slice an already-fetched batch (fetching the ~50-cap batch once and slicing is the simpler, single-query path). Build the control with the same string-concatenation + `getElementById` idiom used throughout app.js; bind via an `onclick` handler (the file uses inline `onclick`/`addEventListener` both — e.g. subscribe handlers).

---

### `docker/web/site/style-shared.css` (styling — reuse Phase 23 `.row` family)

**Analog:** the Phase 23 indexed-row block (lines 192-267). The `.row` / `.archive-label` / `.row .num|.title|.sum|.date` selectors are token-only (zero hex) and already do exactly what Signals rows need (grid, baseline-aligned, hairline divider, hover, focus-visible, mobile reflow). **Reuse `class="row"` directly** for signal rows rather than authoring a parallel family.
```css
.row {
    display: grid;
    grid-template-columns: 56px 1fr auto;
    gap: 0 var(--space-lg);
    align-items: baseline;
    padding: var(--space-lg) 0;
    border-bottom: 1px solid var(--line);   /* mockup --line-soft → prod --line */
    text-decoration: none;
    color: inherit;
    transition: padding-left .18s;
}
.row:hover { padding-left: var(--space-sm); }
.row .title { font-family: var(--serif); font-weight: 500; font-size: 19px; … }
.row .date  { font-family: var(--mono);  font-size: 12px; color: var(--ink-faint); white-space: nowrap; }
.row:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; … }
@media (max-width: 600px) { .row { grid-template-columns: 40px 1fr; } … }
```
> **Token-only constraint (RHYTHM-01, carried from 23-PATTERNS).** Any net-new rule (e.g. a `↗` external-link affordance, a source-domain cell, or a "View all" button) MUST use `var(--…)` tokens — **zero hex**. Mockup tokens `--line-soft`/`--violet` do NOT exist in `:root`; map to `--line`/`--accent`. If signal rows need a source-domain segment distinct from `.num`, add a small scoped selector (e.g. `.row .host`) rather than altering the shared `.row` grid that the newsletter list depends on. The `↗` hover affordance (D-06) pairs naturally with the existing `.row:hover` transition.

---

### `docker/web/site/index.html` (template shell — already present)

**Analog/target:** the `#signals` shell (lines 82-96), built in Phase 21 as a static placeholder on the `.prose`/`.wide` axis. Section placement/order/anchor/copy are LOCKED (do not re-open). The only edit: the "Coming soon" placeholder `<p>` (line 89) is the static stand-in; the rendered feed populates the already-present empty `<div class="wide" id="signals-list"></div>` (line 93). **No new `<script>` tag** — render from app.js.
```html
<section id="signals">
  <div class="content-area wide about-stub">
    <div class="prose">
      <p class="eyebrow">Tier-1 Source Links</p>
      <h1 class="page-title">Signals</h1>
      <p class="page-sub">The week's tier-1 sources, newest first</p>
      <div class="about"><p>… Coming soon.</p></div>   <!-- placeholder replaced by feed -->
      <div class="wide" id="signals-list"></div>         <!-- ← render target -->
    </div>
  </div>
</section>
```
> Width is already handled (`style-base.css:326-330`): `#landing .prose` drops the centering + measure cap so landing copy fills the wide band, and `#landing .wide .wide` de-dupes the nested `#signals-list` wrapper. Phase 24 should NOT add new width rules for `#signals-list` (a de-dupe note already lives there). Whether to drop or keep the "Coming soon" `.about` block once the feed renders is planner discretion (cleanest: render the feed into `#signals-list` and let the placeholder paragraph be removed or left as intro copy).

---

## Shared Patterns

### Anon read path (public-schema view, not economy_map)
**Source:** migration `033:381-386` (grant) + `001:153` (view) + app.js `loadList()` (:502).
**Apply to:** migration 044 + `fetchSignals()`. The view is **public schema** → standard anon REST (`sb.from('<view>')`), NO `Accept-Profile`/`.schema()` (that is economy_map-only). PostgREST needs both the GRANT and (for a security-definer view) no RLS block — the definer view bypasses the base-table RLS.

### Fail-loud surfacing (D-07)
**Source:** `console.error` idiom at app.js `loadHub` (:745) / `loadBlock` (:978); the `{ data, error }` destructure everywhere.
**Apply to:** `fetchSignals()`. Three-way split (error→loud+console.error, `[]`→benign empty, rows→render) — this is the deliberate deviation from `loadList`'s conflated `if (error || !data || length===0)` branch. A missing view/grant returns an HTTP error (not `200 []`), so the loud branch fires exactly when the migration is absent/broken.

### XSS / sink discipline
**Source:** `escapeHtml()` (:665) + `safeHttpUrl()` (:674).
**Apply to:** every `innerHTML` sink in `renderSignals()`. `escapeHtml()` on title + derived hostname; `safeHttpUrl()` on `source_url` before it becomes an `href`. (D-02 already excludes null URLs upstream, but `safeHttpUrl()` is the defense-in-depth scheme gate.)

### Browser-compat (served raw, no transpile — WR-01)
**Source:** the `splitSentences()` WR-01 note (app.js:177-191).
**Apply to:** ALL net-new app.js code (`fetchSignals`, `renderSignals`, `signalHost`, view-all handler). A parse-time `SyntaxError` blanks the entire SPA. **NO regex lookbehind.** Use `var`, `function`, ES3-universal constructs (the file is entirely `var`/`function`-based). The `www.`-strip uses an anchored `^www\.` prefix replace, never a lookbehind.

### Token-only styling (RHYTHM-01)
**Source:** Phase 23 `.row` block (style-shared.css:192-267).
**Apply to:** any new signal-row CSS. Zero hex; `var(--line)`/`var(--accent)` not `--line-soft`/`--violet`.

---

## No Analog Found

| File / Sub-feature | Role | Data Flow | Reason / Guidance |
|--------------------|------|-----------|-------------------|
| Composite view+anon-grant in ONE migration | migration | CRUD | No single migration both creates a view AND grants it to anon — assemble from 001 (view) + 033 (grant). Critically, **invert** the 001 `security_invoker` default (use a security-definer view) to satisfy D-01. |
| `signalHost()` hostname derivation | utility | transform | No existing host-from-URL helper; `new URL(...)` usage exists (:69, :231). Net-new but trivial — guard with try/catch, fall back to `source`, no lookbehind. |
| "View all" expand-in-place control | component | event-driven | No prior expand-in-place control in app.js (the `timelineExpanded` flag at :244 is a re-query toggle for the block timeline, a loose conceptual cousin). Net-new; planner picks re-query vs slice. |

---

## Metadata

**Analog search scope:** `supabase/migrations/` (001-043, full scan for VIEW/GRANT/anon/security_invoker), `docker/web/site/` (app.js, index.html, style-shared.css, style-base.css).
**Files scanned:** 4 frontend + ~8 migrations read in full/part; all 43 migrations grep-scanned for view/grant/anon precedent.
**Pattern extraction date:** 2026-06-16
