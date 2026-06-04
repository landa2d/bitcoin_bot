# Phase 4: Hub, Block, and Status Renderer — Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 3 (1 JS, 1 HTML, 1 CSS — all extensions, not new files)
**Analogs found:** 3 / 3 (all in-tree; same files Phase 4 will modify)

---

## Headline finding: every Phase 4 file already exists; Phase 4 extends in place

There are **zero net-new files** in Phase 4. The phase touches three existing files:

| File | Action | Existing precedent inside the same file |
|------|--------|------------------------------------------|
| `docker/web/site/app.js` | extend | `getRoute()` / `route()` / `showView()` / `loadList()` / `loadEdition()` / `renderArticle()` / `setMode()` / `updateHero()` — every new function in Phase 4 has a same-file precedent |
| `docker/web/site/index.html` | extend | `#list-view` / `#reader-view` view-container pattern under `<main>`; `nav-left` cluster |
| `docker/web/site/style-map.css` | extend | `[data-accent]` + `.maturity-pill` + `.timeline-entry` token surface already shipped (Phase 3) — Phase 4 adds layout selectors below the existing token rules |

Phase 4 does **not** invent new architecture; it extends the SPA router, the DOM view-container pattern, and the design-token surface that Phases 1–3 locked. The pattern source-of-truth is the file Phase 4 is editing. The planner should treat the existing functions/markup/selectors as the analog and emit code that matches their shape exactly.

---

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `docker/web/site/app.js` | router + view loaders + renderers (SPA controller) | request-response (hashchange → supabase-js read → DOM render) | same-file: `getRoute()`/`route()` (router), `loadList()`/`loadEdition()` (loader), `renderList()`/`renderArticle()` (renderer), `setMode()` (visibility-toggle), `updateHero()` (hero update) | **exact** — same file, same patterns |
| `docker/web/site/index.html` | DOM containers + nav surface (SPA shell) | static markup | same-file: `<div id="list-view">` and `<div id="reader-view">` under `<main>`; `.nav-left` cluster | **exact** |
| `docker/web/site/style-map.css` | layout CSS (extending the token surface) | static stylesheet | same-file: existing `[data-accent]` + `.maturity-pill` + `.timeline-entry` rules; cross-file: `style-shared.css` `.content-area` and `.back-link` | **exact** (in-file token pattern) + **role-match** (cross-file layout pattern) |

---

## Pattern Assignments

### `docker/web/site/app.js` (router + loaders + renderers)

The new code in `app.js` is composite — six distinct sub-patterns, each with a same-file analog. Each is laid out below in the order the new code should be emitted.

---

#### 1. Module-level constant declarations (HUB_STORYLINE, MATURITY_STAGE, TIER_LABELS, etc.)

**Analog:** `app.js` lines 11–26 — the `MODES` object at module top.

**Pattern excerpt** (lines 11–26):
```javascript
const MODES = {
    technical: {
        contentField: 'content_markdown',
        titleField: 'title',
        label: 'Technical',
        subtitle: 'Architecture, code, implementation',
        dbPref: 'builder'
    },
    strategic: {
        contentField: 'content_markdown_impact',
        titleField: 'title_impact',
        label: 'Strategic',
        subtitle: 'Markets, strategy, implications',
        dbPref: 'impact'
    }
};
```

**What to copy:** Place new map-related constants at module top in the same idiom — `const` declarations, single-purpose objects, no `let` or `var`. Phase 4 needs:
- `HUB_STORYLINE` — string constant (D-12). Add comment `// Editorial: edit this string + PR + redeploy to update`.
- `STATUS_PAGE_HEADER` — string constant (specifics §"Editorial copy that lives in `app.js`").
- `MATURITY_STAGE` — enum-to-integer map (specifics §"Phase 4 maturity-stage mapping"): `{ nascent: 1, emerging: 2, contested: 3, consolidating: 4, mature: 5 }`.
- `TIER_LABELS` — `{ substrate: 'SUBSTRATE', behavior: 'BEHAVIOR', frame: 'FRAME' }` (D-13).
- `LIVE_TENSION_PLACEHOLDER` — `'TBD — set via /map-tension'` (specifics §"Live-tension placeholder string").

---

#### 2. Router branch extension — `getRoute()` and `route()`

**Analog:** `app.js` lines 89–98 (`getRoute()`) and lines 299–307 (`route()`).

**Pattern excerpt** (lines 89–98):
```javascript
function getRoute() {
    var hash = window.location.hash || '#/';
    if (hash.startsWith('#/edition/')) {
        return { view: 'reader', edition: parseInt(hash.split('/')[2]) };
    }
    if (hash.startsWith('#/unsubscribe')) {
        return { view: 'unsubscribe' };
    }
    return { view: 'list' };
}
```

**Pattern excerpt** (lines 299–307):
```javascript
function route() {
    window.currentNewsletter = null;
    var r = getRoute();
    switch (r.view) {
        case 'list': loadList(); break;
        case 'reader': loadEdition(r.edition); break;
        case 'unsubscribe': handleUnsubscribe(); break;
    }
}
```

**What to copy:** Add `hash.startsWith('#/map/')` (block-page; longer prefix first), `hash.startsWith('#/map')` (hub), and `hash.startsWith('#/status')` branches. Match the `{ view: 'block', slug: hash.split('/')[2] }` shape. Add `case 'map':`, `case 'block':`, `case 'status':` in the `route()` switch. Match the existing `var r = getRoute()` idiom — no `const`, no destructuring, no `async/await` at the router level (the loader functions themselves are `async`).

**Ordering note:** `#/map/<slug>` must match **before** `#/map` because `startsWith('#/map')` would otherwise swallow it. Phase 1 FINDINGS.md §1 documents this hash-router precedent.

---

#### 3. View visibility toggle — `showView()` extension

**Analog:** `app.js` lines 100–104.

**Pattern excerpt** (lines 100–104):
```javascript
function showView(viewName) {
    document.getElementById('list-view').style.display = viewName === 'list' ? 'block' : 'none';
    document.getElementById('reader-view').style.display = viewName === 'reader' ? 'block' : 'none';
}
```

**What to copy:** Add three lines for the new views — `map-view`, `block-view`, `status-view`. Same `style.display = ... ? 'block' : 'none'` ternary. No fancy state machine; the function stays a literal enumeration of every view container. D-03 + Discretion item "exact `setMapToggleVisibility()` mechanism": the simplest implementation is to add `document.querySelector('.mode-toggle').style.display = (viewName === 'list' || viewName === 'reader') ? 'inline-flex' : 'none';` (and the same for `.mode-subtitle`) inside `showView()` — keeps the visibility decision co-located with the other view toggles.

---

#### 4. Supabase query + render pair — `loadHub()`, `loadBlock(slug)`, `loadStatus()`

**Analog:** `app.js` lines 135–152 (`loadList()`) and lines 173–193 (`loadEdition()`).

**Pattern excerpt — list loader** (lines 135–152):
```javascript
async function loadList() {
    showView('list');
    var { data, error } = await sb
        .from('newsletters')
        .select('*')
        .in('status', ['published', 'preview'])
        .order('edition_number', { ascending: false });

    if (error || !data || data.length === 0) {
        document.getElementById('newsletter-list').innerHTML =
            '<p style="color:var(--text-secondary);font-size:15px;padding:20px 24px;">No newsletters published yet.</p>';
        updateHero('AI Agents Pulse', '');
        return;
    }

    window.currentNewsletterList = data;
    renderList(data);
}
```

**Pattern excerpt — single-row loader** (lines 173–193):
```javascript
async function loadEdition(editionNumber) {
    showView('reader');

    var { data, error } = await sb
        .from('newsletters')
        .select('*')
        .eq('edition_number', editionNumber)
        .in('status', ['published', 'preview'])
        .single();

    if (error || !data) {
        document.getElementById('newsletter-content').innerHTML =
            '<p style="color:var(--text-secondary);">Edition not found.</p>';
        updateHero('Edition Not Found', '');
        return;
    }

    window.currentNewsletter = data;
    renderArticle(data);
    window.scrollTo(0, 0);
}
```

**What to copy:**
- Each loader is `async function`, calls `showView(...)` first, awaits the supabase-js query, error-guards with `if (error || !data) { ... return; }`, calls `updateHero(...)` on the error branch, stashes data on `window.currentXxx` for re-render, then calls the renderer.
- For map queries, replace `sb.from('newsletters')` with `sb.schema('economy_map').from('blocks')` / `.from('block_body_versions')` / `.from('timeline_entries')`. The `.schema('economy_map')` call is the supabase-js mechanism for `Accept-Profile: economy_map` (Phase 1 FINDINGS §3, Phase 2 D-09).
- **Specifically for Phase 4:**
  - `loadHub()` → single query: `sb.schema('economy_map').from('blocks').select('*').order('sort_order', { ascending: true })`. Group by `tier` in JS after the query (D-13). Stash on `window.currentBlocks`.
  - `loadBlock(slug)` → two parallel queries via `Promise.all`: (a) `sb.schema('economy_map').from('blocks').select('*').eq('slug', slug).single()`, (b) `sb.schema('economy_map').from('timeline_entries').select('*').eq('block_slug', slug).order('event_date', { ascending: false }).limit(30)`. If `block.current_body_version_id`, also fetch the body: `sb.schema('economy_map').from('block_body_versions').select('body_md').eq('id', block.current_body_version_id).single()`. Don't add status filters in JS — RLS already filters (D-17). Stash on `window.currentBlock` and `window.currentTimelineEntries`.
  - `loadStatus()` → single query: same shape as `loadHub()` but selecting only the columns the status row needs (`slug, title, subtitle, accent, tier, sort_order, maturity, last_synthesized_at`). Group by `tier` (D-15).
- **Hero updates per route:** Match the `updateHero(...)` calls used by `loadList()` (line 118) and `renderArticle()` (line 162). D-02 specifies the per-route headlines: hub → `HUB_STORYLINE` + `'updated ' + last-touched timestamp`; block → `block.title` + `('synthesized ' + last_synthesized_at)`; status → `'Maturity Snapshot'` + `'updated ' + NOW()`.

---

#### 5. Renderers — `renderHub()`, `renderBlock()`, `renderStatus()`

**Analog:** `app.js` lines 107–133 (`renderList()`) and lines 156–171 (`renderArticle()`).

**Pattern excerpt — list renderer** (lines 107–133):
```javascript
function renderList(data) {
    if (!data || data.length === 0) {
        document.getElementById('newsletter-list').innerHTML =
            '<div class="content-area"><p style="color:var(--text-secondary);font-size:15px;">No newsletters published yet.</p></div>';
        updateHero('AI Agents Pulse', '');
        return;
    }

    // Update hero with site title and latest edition date
    var latest = data[0];
    var latestDate = formatDate(latest.published_at);
    updateHero('AI Agents Pulse', 'Latest: Edition #' + latest.edition_number + ' · ' + latestDate);

    var html = data.map(function(n) {
        var title = getModeTitle(n);
        var content = getModeContent(n);
        var excerpt = content.replace(/[#*_\[\]`>]/g, '').substring(0, 150) + '...';

        return '<div class="article-entry">' +
            '<div class="section-label">EDITION #' + n.edition_number + '</div>' +
            '<a href="#/edition/' + n.edition_number + '" class="entry-title">' + escapeHtml(title) + '</a>' +
            '<p class="entry-preview">' + escapeHtml(excerpt) + '</p>' +
            '</div>';
    }).join('');

    document.getElementById('newsletter-list').innerHTML = html;
}
```

**Pattern excerpt — article renderer** (lines 156–171):
```javascript
function renderArticle(data) {
    var title = getModeTitle(data);
    var content = getModeContent(data);
    var date = formatDate(data.published_at || data.created_at);

    // Update hero with edition info
    updateHero(title, 'Edition #' + data.edition_number + ' · ' + date);

    var banner = '';
    if (data.status === 'preview') {
        banner = '<div style="background:#f59e0b;color:#000;padding:10px 16px;border-radius:6px;margin-bottom:16px;font-weight:600;text-align:center;">PREVIEW — NOT YET PUBLISHED</div>';
    }

    var rendered = marked.parse(content);
    document.getElementById('newsletter-content').innerHTML = banner + rendered;
}
```

**What to copy:**
- String-concatenated HTML built via `data.map(function(n) { return '<div ...>' + ... + '</div>'; }).join('')`. **Do NOT introduce template literals** — the file uses single-quoted strings + `+` concatenation throughout (lines 120–130). Maintain consistency.
- **Always call `escapeHtml(...)` on any DB string** rendered into the DOM (lines 127–128 of `renderList()`). All seven `economy_map.blocks` fields (`title`, `subtitle`, `live_tension`) must pass through `escapeHtml(...)`. The only exception is `body_md` — render it via `marked.parse(content)` (line 169 of `renderArticle()` is the precedent; D-18 names it).
- **`renderHub()` emits markup matching the Phase 3 visual contract.** The hub layout (D-13, D-14) is three sections (substrate / behavior / frame) with `<h2 class="tier-label">SUBSTRATE</h2>` headings (new selector — Phase 4 owns), inside each section the blocks render as `<a href="#/map/{slug}" data-accent="{accent}" class="block-tile">...</a>`. Each tile contains `<h3 class="tile-title">{title}</h3>`, `<p class="tile-subtitle">{subtitle}</p>`, and the maturity pill emitting **the exact `tokens-preview.html` markup** for the pill component (see "Maturity pill markup" below).
- **`renderBlock()` emits the block-page composition** (D-08): `<header class="block-header" data-accent="{accent}"><h1>{title}</h1><div class="maturity-pill"...></div></header>` → `<section class="block-tension">...</section>` (only if `live_tension !== LIVE_TENSION_PLACEHOLDER`, per D-10) → `<section class="block-body">{marked.parse(body_md)}</section>` (only if `current_body_version_id !== null`, per D-10) → `<section class="evolution">...timeline entries...</section>` (always). Each `.timeline-entry` matches the Phase 3 markup exactly (see "Timeline entry markup" below). Append a `<button class="timeline-show-all">Show all (N entries) ↓</button>` if `entries.length === 30` (D-11). Optionally include a `<a href="#/map" class="back-link">← Map</a>` (discretion: yes per the "back to map" affordance default).
- **`renderStatus()` emits one row per block.** Tier grouping (D-15) — same three sections as the hub, same `TIER_LABELS`. Each row: `<div class="status-row" data-accent="{accent}"><div class="maturity-pill"...></div><div class="status-title">{title}</div><div class="status-subtitle">{subtitle}</div><time class="status-synth">{last_synthesized_at ? 'synthesized ' + formatDate(last_synthesized_at) : 'never synthesized'}</time></div>` (D-15 — no links per v1; planner picks exact DOM order).
- **Maturity pill markup** — emit exactly 5 `<span class="seg"></span>` children regardless of stage; the CSS (style-map.css line 71–75) keys the fill off `data-stage`. See `tokens-preview.html` lines 78–82 for the canonical markup:
  ```html
  <div class="maturity-pill" data-accent="teal" data-stage="3" aria-label="Maturity: contested (3 of 5)">
    <span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span>
  </div>
  ```
  Use `MATURITY_STAGE[block.maturity]` to resolve `data-stage`. `data-accent` repeats `block.accent` (the CSS resolves `--accent-tier` either from the ancestor or the pill itself — both work; tokens-preview.html line 78 sets it on the pill for safety).
- **Timeline entry markup** — `tokens-preview.html` lines 114–125:
  ```html
  <article class="timeline-entry" data-source="https://example.com/post">
    <div class="timeline-line1">
      <time class="timeline-date">2026-05-15</time>
      <span class="timeline-sep">·</span>
      <span class="timeline-what">Anthropic publishes Constitutional AI v2 framework</span>
    </div>
    <div class="timeline-line2">
      <span class="timeline-why">Shifts the alignment conversation from oversight to training-time constraints.</span>
      <a class="timeline-source" href="https://example.com/post">source ↗</a>
    </div>
  </article>
  ```
  If `source_url` is null, **omit** both the `data-source` attribute and the `<a class="timeline-source">` element entirely (style-map.css lines 91–94 + 143–148 document the contract; tokens-preview.html lines 127–137 show the source-null variant).

---

#### 6. Hero update (carried forward unchanged)

**Analog:** `app.js` lines 82–85.

**Pattern excerpt:**
```javascript
function updateHero(title, dateText) {
    document.getElementById('hero-headline').textContent = title || '';
    document.getElementById('hero-date').textContent = dateText || '';
}
```

**What to copy:** Nothing — this function works as-is for all three map routes. Phase 4 just calls it from the new loaders with the per-route headlines spelled out in D-02. The `.hero` block stays in `index.html` on all routes (D-02). No changes to `updateHero()` itself.

---

#### 7. Idle poll lifecycle — `setInterval` / `clearInterval` / `visibilitychange` / `hashchange`

**Analog:** None in `app.js` (it has zero `setInterval` / `visibilitychange` calls today). The hashchange listener at line 314 (`window.addEventListener('hashchange', route)`) is the only existing reactive subscription.

**Pattern excerpt — existing hashchange wiring** (line 314):
```javascript
window.addEventListener('hashchange', route);
```

**What to emit (D-05, D-06, D-07 — no in-file analog, treat as a first-in-file precedent):**
```javascript
var evolutionPollHandle = null;

function startEvolutionPoll(slug) {
    stopEvolutionPoll();
    evolutionPollHandle = setInterval(function() {
        if (document.visibilityState !== 'visible') return;
        pollEvolution(slug);   // re-runs the timeline query, diffs vs DOM
    }, 60000);
}

function stopEvolutionPoll() {
    if (evolutionPollHandle) {
        clearInterval(evolutionPollHandle);
        evolutionPollHandle = null;
    }
}

window.addEventListener('hashchange', function() {
    if (!window.location.hash.startsWith('#/map/')) stopEvolutionPoll();
});
window.addEventListener('visibilitychange', function() {
    // Interval keeps running but the guard above skips when hidden.
    // Optionally: trigger an immediate refresh on becoming visible.
});
```

**Notes for the planner:**
- The poll is **block-page-scoped** (D-06): `loadBlock(slug)` calls `startEvolutionPoll(slug)` at the end; `loadHub`/`loadStatus`/`loadList`/`loadEdition` do **not** start it; the `hashchange` listener clears it on any navigation away.
- The poll **re-queries only `timeline_entries`** — not blocks, not block_body_versions (D-06).
- The poll respects the show-all expand state (D-11): keep that state in a module-level var (e.g., `var timelineExpanded = false;`) reset to `false` on every `loadBlock(slug)` call; the poll reads it to decide between `.limit(30)` and unbounded.
- **No Realtime** (D-05). Do not import or initialize `sb.channel(...)` anywhere.

---

#### 8. Init / DOMContentLoaded (unchanged)

**Analog:** `app.js` lines 309–314.

**Pattern excerpt:**
```javascript
document.addEventListener('DOMContentLoaded', function() {
    setMode(currentMode);
    route();
});

window.addEventListener('hashchange', route);
```

**What to copy:** Nothing — the init block already calls `route()` which now dispatches the new views. No changes needed unless the planner adds the poll-lifecycle hashchange listener as a sibling (recommended — keeps idle-poll cleanup separate from main routing).

---

### `docker/web/site/index.html` (DOM containers + nav surface)

#### 1. New view containers under `<main>`

**Analog:** `index.html` lines 33–45 — the existing `#list-view` and `#reader-view` containers under `<main>`.

**Pattern excerpt:**
```html
<main>
    <!-- List view -->
    <div id="list-view">
        <div class="content-area" id="newsletter-list"></div>
    </div>

    <!-- Reader view -->
    <div id="reader-view" style="display:none">
        <div class="content-area">
            <a href="#/" class="back-link">&larr; All editions</a>
            <article id="newsletter-content"></article>
        </div>
    </div>
</main>
```

**What to copy:** Add three more sibling `<div>`s under `<main>` matching the same pattern — `<div id="map-view" style="display:none"></div>`, `<div id="block-view" style="display:none"></div>`, `<div id="status-view" style="display:none"></div>`. Each wraps a `<div class="content-area">` for the `.content-area` border-top + spacing rule (style-shared.css lines 197–201). Optionally include a `<a href="#/map" class="back-link">← Map</a>` inside the block view's content-area (matching the `← All editions` link at line 42).

Inner structure stays empty in static markup — renderers inject HTML via `innerHTML`, same as `renderList()` / `renderArticle()` (matches discretion item "DOM containers: extend `<main>`").

---

#### 2. "Map" text link in the nav-left cluster

**Analog:** `index.html` lines 14–17 — the `.nav-left` cluster with the `.nav-dot` + `.nav-logo` spans.

**Pattern excerpt:**
```html
<nav class="top-nav">
    <div class="nav-left">
        <span class="nav-dot"></span>
        <span class="nav-logo">AGENTPULSE</span>
    </div>
    <button class="btn-subscribe-primary" onclick="scrollToSubscribe()">SUBSCRIBE</button>
</nav>
```

**What to copy:** Append a quiet `<a href="#/map" class="nav-map-link">Map</a>` inside `.nav-left` after the `.nav-logo` span (D-04). Style it via a new selector in style-shared.css or style-map.css with `color: var(--text-secondary); text-decoration: none; margin-left: 16px; font-family: 'Courier New', monospace;` — D-04 explicitly says NOT a primary button, NOT a toggle button. No `onclick` — it's a plain anchor; the hashchange listener picks it up.

---

### `docker/web/site/style-map.css` (layout CSS extending the token surface)

#### 1. New layout selectors — placement and idiom

**Analog (in-file):** `style-map.css` lines 45–148 — the existing `.maturity-pill` and `.timeline-entry` blocks. Each starts with a `/* ── Name ── */` divider, follows with a `/* Markup contract: ... */` block comment specifying the markup Phase 4 must emit, then defines the selectors.

**Pattern excerpt — markup-contract comment style** (lines 45–53):
```css
/* ── Maturity Pill ──────────────────────────────────────────── */
/* Markup contract:
   <div class="maturity-pill" data-accent="teal" data-stage="3"
        aria-label="Maturity: contested (3 of 5)">
     <span class="seg"></span> × 5
   </div>
   Single source of truth across hub / block / status (TOKN-02).
   Informational only — no hover / interactive states.
*/
```

**What to copy:** Every new selector group Phase 4 adds (block-tile, tier-label, block-header, block-tension, block-body, evolution, timeline-show-all, status-row) opens with a `/* ── Name ── */` divider and a `/* Markup contract: ... */` comment showing the HTML the renderer emits. Each comment ties back to the relevant Phase 4 decision (D-13/D-14 for `.block-tile`, D-09 for `.block-header`, D-10 for `.block-tension` / `.block-body`, D-11 for `.timeline-show-all`, D-15 for `.status-row`).

---

#### 2. Tier-accent left-border stripe on block tiles

**Analog (in-file):** lines 34–43 (`body.technical [data-accent="teal"]` etc.) — the `--accent-tier` resolution mechanism that block-tile + block-header + status-row reuse via `data-accent`.

**Pattern excerpt** (lines 39–43):
```css
/* Technical (dark) mode — on-dark variants on every data-accent value */
body.technical [data-accent="teal"]   { --accent-tier: var(--accent-teal-on-dark);   }
body.technical [data-accent="purple"] { --accent-tier: var(--accent-purple-on-dark); }
body.technical [data-accent="coral"]  { --accent-tier: var(--accent-coral-on-dark);  }
body.technical [data-accent="gray"]   { --accent-tier: var(--accent-gray-on-dark);   }
```

**What to copy:** Phase 4 layout selectors reference `var(--accent-tier)` — never the raw `--accent-teal-base` etc. The cascade is: `body.technical` / `body.strategic` × `[data-accent=...]` resolves `--accent-tier`, then `.block-tile { border-left: 3px solid var(--accent-tier); }` consumes it (D-14: "Tier accent renders as a **left-border stripe**"). Same for `.status-row { border-left: 3px solid var(--accent-tier); }`. **Do NOT** hardcode `border-left: 3px solid #4FCBA8;` — always go through `--accent-tier`.

---

#### 3. Cross-file layout precedent

**Analog (cross-file):** `style-shared.css` lines 197–252 — `.content-area` (border-top + padding), `.article-entry` (margin-bottom), `.section-label` (uppercase + letter-spacing + tiny size), `.entry-title` (Georgia serif + 18px), `.entry-preview` (Courier + 15px), `.back-link` (Courier + accent color).

**Pattern excerpts** (style-shared.css lines 219–239):
```css
.entry-title {
    font-family: Georgia, serif;
    font-size: 18px;
    font-weight: 400;
    color: var(--text-primary);
    text-decoration: none;
    display: block;
    margin-bottom: 6px;
}

.entry-title:hover {
    color: var(--accent);
}

.entry-preview {
    font-family: 'Courier New', monospace;
    font-size: 15px;
    font-weight: 400;
    color: var(--text-body);
    line-height: 1.5;
}
```

**What to copy:** New typography in Phase 4 layout selectors mirrors these. `.tile-title` (used inside `.block-tile`) inherits the same Georgia 18px treatment; `.tile-subtitle` inherits the Courier 15px treatment. `.tier-label` matches `.section-label` exactly (`font-family: 'Courier New'; font-size: 13px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--accent);` — see lines 209–217). The block-page `<h1>` inside `.block-header` matches `.hero-headline` (Georgia, 29px — lines 141–147) for hierarchy consistency. **TOKN-04 is still in force:** no new font families, no new font sizes outside the existing palette. Only layout (flex, grid, spacing, borders).

---

#### 4. File-organization decision

Per the Discretion item: **extend `style-map.css`** rather than creating a new `style-hub.css`. The file is currently 148 lines (token surface only); even with eight new selector groups it should stay under ~300 lines, well below the threshold for splitting. Keeping all map-surface CSS in one file matches the in-file analog pattern (the existing `.maturity-pill` and `.timeline-entry` rules live in the same file). If the file passes ~300 lines after Phase 4 additions, the planner may split — but the default is to extend.

---

## Shared Patterns

### Pattern: `async function loadXxx() { showView(...); var { data, error } = await sb...; if (error || !data) return; render(data); }`

**Source:** `app.js` lines 135–152 (`loadList`) and lines 173–193 (`loadEdition`)
**Apply to:** All three new loaders — `loadHub()`, `loadBlock(slug)`, `loadStatus()`.

All Phase 4 loaders follow the identical four-step shape:
1. Call `showView(...)` to flip visibility.
2. Await the supabase-js query (`sb.schema('economy_map').from(...).select(...).execute()` — but supabase-js v2 returns a Promise directly from `.select()`/`.order()`/`.limit()`; no `.execute()` is needed; see lines 137–141 of `loadList`).
3. Error-guard `if (error || !data) { renderEmpty(); updateHero(...); return; }`.
4. Stash on `window.currentXxx`, then call `renderXxx(data)`.

---

### Pattern: Always escape DB strings; only `body_md` goes through `marked.parse()`

**Source:** `app.js` line 127–128 (`escapeHtml(title)` in `renderList`), line 169 (`marked.parse(content)` in `renderArticle`)
**Apply to:** All renderers.

Every DB-sourced string going to `innerHTML` passes through `escapeHtml(str)` (defined at lines 274–278). The only exception is `block_body_versions.body_md`, which goes through `marked.parse(body_md)` (D-18). The `live_tension` field must be `escapeHtml`'d — it's plain text not markdown.

---

### Pattern: View-container visibility lives in `showView()`, not scattered

**Source:** `app.js` lines 100–104
**Apply to:** All new views.

The single function `showView(viewName)` enumerates every view container by id and sets `style.display = ... ? 'block' : 'none'`. Phase 4 adds three lines to this function — does **not** introduce a parallel visibility helper. The mode-toggle visibility (D-03) folds into the same function (see Pattern Assignment #3 above).

---

### Pattern: Supabase-js calls go through the existing `sb` client at line 7

**Source:** `app.js` line 7
**Apply to:** Every Phase 4 query.

No new client construction. No direct PostgREST. No fetch with manual `Accept-Profile` header. `sb.schema('economy_map').from(...)` is the **only** path. Phase 1 FINDINGS §3 + Phase 2 D-09 lock this. RLS already filters drafts and `'unsorted'` entries (D-17) — do not add redundant `.eq('status', 'published')` or `.neq('block_slug', 'unsorted')` filters in JS.

---

### Pattern: Markup matches `tokens-preview.html` exactly for `.maturity-pill` and `.timeline-entry`

**Source:** `tokens-preview.html` lines 78–82 (pill), lines 115–125 (timeline entry with source), lines 128–137 (timeline entry without source)
**Apply to:** Hub renderer (pill in each tile), block renderer (pill in header + timeline entries in evolution), status renderer (pill in each row).

Phase 3 ships the visual contract; Phase 4 emits markup. The renderers' job is to produce structure that satisfies the existing CSS selectors. **The pill always has exactly 5 `<span class="seg"></span>` children.** The timeline entry has a `data-source="..."` attribute and `<a class="timeline-source">` child only when `source_url` is non-null.

---

## No Analog Found

| Concern | Why no analog | Mitigation |
|---------|---------------|------------|
| `setInterval` + `visibilitychange` lifecycle for idle poll | `app.js` has zero `setInterval` / `visibilitychange` usage today | Treat Pattern Assignment #7 (Idle poll lifecycle) as a first-in-file precedent. The shape is shown explicitly in this PATTERNS.md; the planner should consult MDN if uncertain about `visibilityState` semantics. |
| `sb.schema('economy_map')` against the anon client | `app.js` has only `sb.from('newsletters')` calls today | Phase 1 FINDINGS §3 + Phase 2 D-09 document the supabase-js v2 mechanism. `tokens-preview.html` doesn't exercise it. The planner should verify in dev that `.schema('economy_map').from('blocks').select('*')` actually emits the `Accept-Profile: economy_map` header — Phase 2 prerequisite §4.5 (exposed-schemas allowlist) must already be true. |
| Diffing a re-queried list against the rendered DOM (D-06 poll diff) | No DOM-diffing pattern exists in `app.js` (renderers always replace `innerHTML` wholesale) | Simplest approach for Phase 4: have `pollEvolution()` just re-call the timeline query and overwrite `document.getElementById('evolution-entries').innerHTML = ...` — wholesale replacement is consistent with the existing renderer idiom (lines 132, 170). If flicker is a concern, escalate to a hash-of-entries comparison; but the simpler approach should be the default. |

---

## Metadata

**Analog search scope:**
- `docker/web/site/app.js` (314 lines) — full read
- `docker/web/site/index.html` (78 lines) — full read
- `docker/web/site/style-map.css` (148 lines) — full read
- `docker/web/site/style-shared.css` (518 lines) — full read
- `docker/web/site/tokens-preview.html` (169 lines) — full read
- `supabase/migrations/033_economy_map_schema.sql` (421 lines) — full read (for schema field-name confirmation)
- `.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md` — read (architecture lock)
- `.planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md` — read (D-01..D-20)
- `.planning/phases/02-economy-map-schema-seven-block-seed/02-PATTERNS.md` — partial read (Phase 2 pattern surface confirmation)

**Files scanned in codebase:** 9 (focused — Phase 4 surface is contained to 3 files in `docker/web/site/`)

**Pattern extraction date:** 2026-05-27

**Key principle for executor:** Every new function in Phase 4 has a same-file precedent in `app.js`. Match the existing idiom (var, no template literals, async loaders + sync renderers, `showView` + `updateHero` + supabase-js + escapeHtml + marked) exactly. The Phase 3 design tokens are already shipped — Phase 4 emits markup; it does not author new visual treatments. Layout selectors are the only net-new CSS; everything else is structural reuse.
