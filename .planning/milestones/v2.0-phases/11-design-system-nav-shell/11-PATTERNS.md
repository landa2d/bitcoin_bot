# Phase 11: Design System + Nav Shell - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 5 (4 modified + 1 new)
**Analogs found:** 5 / 5 (in-place transform — the analog IS the current code)

> **Read this first (executor):** This phase is an **in-place restyle + nav-shell addition** of a vanilla-JS SPA — no React/Tailwind/build step. Every file except `style-base.css` already exists, so the "closest analog" is **the current code being transformed**. The mockup (`agentpulse-redesign-mockup.html`) is the **intent reference only — do NOT copy its `data-view` markup or `go()` click router**; the real router is hash-driven. All visual values are locked in `11-UI-SPEC.md` — do not re-derive hex/sizes/spacing here.

---

## File Classification

| File | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|------|---------|------|-----------|----------------|---------------|
| `docker/web/site/style-base.css` | **NEW** | config (design-token + nav-shell stylesheet) | n/a (static) | `style-shared.css` `body.technical` var block + mockup `:root`/`header`/`.nav`/`.tab` | role-match (token layer) |
| `docker/web/site/index.html` | modify | view (SPA shell markup) | request-response (hash route) | itself — current `.top-nav` + `.hero` + back-links | exact (self-transform) |
| `docker/web/site/app.js` | modify | controller (hash router) | event-driven (`hashchange`) | itself — `getRoute()`/`route()`/`showView()`/`setMode()` | exact (self-transform) |
| `docker/web/site/style-shared.css` | modify (retire blocks) | config (stylesheet) | n/a (static) | itself — `body.technical`/`body.strategic` blocks + `.top-nav`/`.back-link` | exact (self-transform) |
| `docker/web/site/style-map.css` | **note only — do NOT touch** | config (stylesheet) | n/a | itself | deferred to P12/P13 |

**Cross-cutting conventions to preserve (apply to ALL files):**
1. **Hand-authored CSS, no build step** — load order in `index.html` is the cascade control.
2. **CSS custom properties drive theme** — move palette to `:root`, never re-introduce a `body.x`-scoped palette.
3. **Defensive null-checks** on every `getElementById`/`querySelector` before use (see `showView` lines 145-149).
4. **Unicode glyphs, no icon lib** — `←` U+2190, `·` U+00B7, `↗`.
5. **Active state derived from ROUTE, not click** — hook into `route()`, mirror the mockup's `parent` map but drive it from `getRoute()`.

---

## Pattern Assignments

### `docker/web/site/style-base.css` (NEW — config / token + nav-shell layer)

**Analog A (what it replaces):** the dark var block in `style-shared.css` lines 7-49.
**Analog B (intent reference — values locked in UI-SPEC):** mockup `:root` + `header`/`.nav`/`.brand`/`.dot`/`.tabs`/`.tab`/`.subscribe`.

**Token block — REPLACE the dark `body.technical` block (`style-shared.css` 7-27) with a `:root` light palette.** The current (being-retired) source of the var pattern:
```css
/* style-shared.css:7-27 — RETIRED. Note the body.x scoping (the bug to fix) + dark hex */
body.technical {
    --accent: #00e5a0;
    --bg: #0a0a0f;
    --text-primary: #ffffff;
    ...
}
```
New `:root` (hex/names locked in UI-SPEC §Color; mockup `:root` lines 11-26 is the verbatim intent — trim to the 11 tokens the SPEC declares + add `--accent-soft #efeaff`, `--accent-ink #4a2fd6`, `--ink-soft #55514a`, `--ink-faint #8a857c`, `--line-strong #d8d2c7`):
```css
/* mockup:11-26 — intent reference for the :root the executor authors */
:root{
  --bg:#faf8f5; --surface:#ffffff;
  --ink:#1a1916; --ink-soft:#55514a; --ink-faint:#8a857c;
  --line:#e7e2da; --line-strong:#d8d2c7;
  --accent:#5b3df5; --accent-soft:#efeaff; --accent-ink:#4a2fd6;
  --serif:'Source Serif 4', Georgia, serif;
  --mono:'IBM Plex Mono', ui-monospace, monospace;
}
```
Add the spacing tokens (`--space-xs..3xl`) and radius tokens (`--radius`, `--radius-sm`, `--radius-btn`, `--radius-dot`) from UI-SPEC §Spacing/§Radius.

**Body typography — REPLACE the `Courier New` body rule.** Current (being-retired):
```css
/* style-shared.css:51-57 — RETIRED: Courier body font + 1.6 lh */
body {
    font-family: 'Courier New', monospace;
    background: var(--bg);
    color: var(--text-primary);
    line-height: 1.6;
}
```
New body = serif 18px / 1.62 (UI-SPEC §Typography; mockup `body` lines 29-36 is the intent: `font-family:var(--serif); line-height:1.62; font-size:18px`).

**Sticky nav-shell styles (THE deliverable).** Mockup `header` + `.nav` + `.tab` (lines 40-75) is the intent reference — adapt class names to whatever markup `index.html` emits, snap paddings to the 4px grid per UI-SPEC §Spacing (nav `14px`→`12px`, tab `7px 13px`→`8px 12px`, subscribe `9px 16px`→`8px 16px`):
```css
/* mockup:40-69 — intent reference for the sticky shell (snap paddings per UI-SPEC) */
header{ position:sticky;top:0;z-index:50;
  background:rgba(250,248,245,.86);
  backdrop-filter:saturate(140%) blur(10px);
  border-bottom:1px solid var(--line); }
.nav{ display:flex;align-items:center;gap:18px; padding:14px 24px; }
.brand{ font-family:var(--mono);font-weight:600;font-size:14px;
  letter-spacing:.08em;color:var(--ink); }
.dot{ width:9px;height:9px;border-radius:50%;background:var(--accent); }
.tab{ font-family:var(--mono);font-size:12.5px;font-weight:500;  /* SPEC: rest weight 400, not 500 */
  letter-spacing:.02em;color:var(--ink-soft);
  padding:7px 13px;border-radius:7px;border:1px solid transparent; }
.tab.active{ color:var(--accent-ink);background:var(--accent-soft);
  border-color:#ddd2ff;font-weight:600; }
.subscribe{ font-family:var(--mono);font-size:12px;font-weight:600;letter-spacing:.06em;
  background:var(--accent);color:#fff;border:none;border-radius:8px;padding:9px 16px; }
.subscribe:hover{ background:var(--accent-ink); }
```
> **UI-SPEC override of the mockup:** tab/back-control **rest weight is 400, not 500** (500 is removed). Active tab, brand, Subscribe = 600.

**Back-control style (replaces `.back-link`).** Mockup `.backlink` lines 100-106:
```css
/* mockup:100-106 — intent reference for "← Back to [section]" */
.backlink{ display:inline-flex;align-items:center;gap:7px;
  font-family:var(--mono);font-size:12.5px;color:var(--ink-soft);
  background:none;border:none; }
.backlink:hover{ color:var(--accent-ink) }
```

**Display/eyebrow type classes (ship the CSS, D-02).** Mockup `.eyebrow` (83-87, 11px mono 600 uppercase accent) + `.page-title` (88-93, `clamp(30px,5vw,46px)` serif 600). Ship these classes; do NOT restructure the hero DOM to use them (Phase 12).

**Responsive nav (D-03).** Mockup media query lines 205-210 — adopt as intent:
```css
/* mockup:205-210 — D-03 mobile nav wrap (adapt class names) */
@media(max-width:640px){
  .tabs{ order:3;flex-basis:100%;overflow-x:auto }
  .nav{ flex-wrap:wrap }
}
```

---

### `docker/web/site/index.html` (modify — view / SPA shell)

**Analog:** itself. Six concrete edits, all grounded in the current 97-line file.

**Edit 1 — add Google-Fonts `<link>` to `<head>` (after line 6, before the stylesheet links).** Current `<head>`:
```html
<!-- index.html:3-9 — current head, NO font link, NO style-base.css -->
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentPulse Intelligence Brief</title>
    <link rel="stylesheet" href="/style-shared.css">
    <link rel="stylesheet" href="/style-map.css">
</head>
```
Insert the UI-SPEC §Font-Loading block verbatim (Source Serif 4 + IBM Plex Mono, **weights 400 & 600 only** — NOT the mockup's 400;500;600;700) and add `<link rel="stylesheet" href="/style-base.css">` **FIRST**, before `style-shared.css`. Load order is the cascade control (D-04). CSP already whitelists `fonts.googleapis.com`/`fonts.gstatic.com` (`docker/web/Caddyfile:19`) — zero infra change.

**Edit 2 — REPLACE `.top-nav` (lines 13-20) with the sticky 3-tab `<header>`.** Current (being-removed):
```html
<!-- index.html:13-20 — REMOVED: brand + Map text-link + Subscribe, no tabs -->
<nav class="top-nav">
    <div class="nav-left">
        <span class="nav-dot"></span>
        <span class="nav-logo">AGENTPULSE</span>
        <a href="#/map" class="nav-map-link">Map</a>
    </div>
    <button class="btn-subscribe-primary" onclick="scrollToSubscribe()">SUBSCRIBE</button>
</nav>
```
Replace with brand + 3 tabs (`Newsletter` · `Agent Economy` · `What is AgentPulse`, copy locked in UI-SPEC §Copywriting) + Subscribe. The `.nav-map-link` "Map" is **deleted** (NAV-04 — its destination is the Agent Economy tab). **Subscribe button MUST keep `onclick="scrollToSubscribe()"`** (NAV-01 — reuse the existing flow, line 19 already does this). Tabs are hash links (`href="#/"`, `#/map`, `#/about`) so the real router drives them — NOT the mockup's `data-view` + `go()` click handler.

**Edit 3 — recolor (do NOT restructure) the `.hero`.** Leave lines 23-32 structurally intact (D-02 — `hero-headline`/`hero-date`/`.mode-toggle`/`mode-subtitle` stay); they recolor automatically once `:root` replaces the dark palette. Do not move the toggle (Phase 12).

**Edit 4 — swap `← All editions` back-link (line 43).** Current:
```html
<!-- index.html:43 — reader view back-link -->
<a href="#/" class="back-link">&larr; All editions</a>
```
→ `← Back to Newsletter` (UI-SPEC §Nav back-control + §Copywriting).

**Edit 5 — swap `← Map` back-link (line 56).** Current:
```html
<!-- index.html:56 — block view back-link -->
<a href="#/map" class="back-link">&larr; Map</a>
```
→ `← Back to the map`. (Status view `#/status` renders its back-control via JS/markup → also `← Back to the map`.)

**Edit 6 — preserve everything else.** View containers (`list-/reader-/map-/block-/status-view`, lines 35-65), subscribe section (68-83), bottom bar (86-89), and the three `<script>` tags (93-95) are untouched.

---

### `docker/web/site/app.js` (modify — controller / hash router)

**Analog:** itself. The router already runs on load + every `hashchange`; the active-tab function hooks in. **No new routing library.**

**Hook point 1 — `getRoute()` (lines 115-133) is the route source. DO NOT change it** (the `#/about` case is added in Phase 14; until then it falls through to `list` — a local-only no-op under batch-deploy):
```js
// app.js:115-133 — existing hash→view map; the route→tab fn reads from this
function getRoute() {
    var hash = window.location.hash || '#/';
    if (hash.startsWith('#/map/'))    return { view: 'block', slug: hash.split('/')[2] };
    if (hash.startsWith('#/map'))     return { view: 'map' };
    if (hash.startsWith('#/status'))  return { view: 'status' };
    if (hash.startsWith('#/edition/'))return { view: 'reader', edition: parseInt(hash.split('/')[2]) };
    if (hash.startsWith('#/unsubscribe')) return { view: 'unsubscribe' };
    return { view: 'list' };
}
```

**Hook point 2 — add a route→active-tab function, call it inside `route()` (lines 742-753).** Current `route()`:
```js
// app.js:742-753 — runs on load AND on every hashchange (line 760). Add the tab-sync call here.
function route() {
    window.currentNewsletter = null;
    var r = getRoute();
    switch (r.view) {
        case 'list': loadList(); break;
        case 'reader': loadEdition(r.edition); break;
        case 'unsubscribe': handleUnsubscribe(); break;
        case 'map': loadHub(); break;
        case 'block': loadBlock(r.slug); break;
        case 'status': loadStatus(); break;
    }
}
```
Add `setActiveTab(r.view)` (or pass `r`) inside `route()`. Implement `setActiveTab` using the **UI-SPEC route→tab table verbatim** — `list`/`reader`→Newsletter, `map`/`block`/`status`→Agent Economy, `about`→What is AgentPulse, `unsubscribe`→none. This mirrors the mockup's `parent={newsletter:'newsletter',article:'newsletter',map:'map',block:'map',about:'about'}` map (mockup script lines 380-382) but is **driven by `getRoute()`, not a click**. Follow the defensive-null-check idiom from `showView`:
```js
// app.js:145-149 — the null-check convention to copy for tab + back-control wiring
var toggle = document.querySelector('.mode-toggle');
if (toggle) toggle.style.display = isMapRoute ? 'none' : 'inline-flex';
var subtitle = document.getElementById('mode-subtitle');
if (subtitle) subtitle.style.display = isMapRoute ? 'none' : 'block';
```

**Hook point 3 — `route()` registration is already wired; do NOT duplicate.** Load + hashchange already call `route()`:
```js
// app.js:755-760 — existing wiring; setActiveTab runs automatically via route()
document.addEventListener('DOMContentLoaded', function() {
    setMode(currentMode);
    route();
});
window.addEventListener('hashchange', route);
```

**Hook point 4 — `setMode()` (lines 68-104) keeps the body class for CONTENT re-render only.** Per the Planner Note in CONTEXT.md: after decoupling, `body.technical`/`body.strategic` **no longer drive theme** (the new palette lives under `:root`). Keep the class toggle (lines 79-80) so `renderArticle`/`renderList` re-render (lines 96-103) — but it is a content switch, not a theme switch:
```js
// app.js:79-80 — keep this class toggle (drives content re-render), but it no longer themes
document.body.classList.remove('technical', 'strategic');
document.body.classList.add(mode);
```

**Hook point 5 — `scrollToSubscribe()` (lines 283-285) is reused verbatim by the new Subscribe button (NAV-01). DO NOT build a new mechanism:**
```js
// app.js:283-285 — the existing subscribe flow the nav Subscribe button must invoke
function scrollToSubscribe() {
    document.getElementById('subscribe-section').scrollIntoView({ behavior: 'smooth' });
}
```
> Top-level fn so an inline `onclick="scrollToSubscribe()"` reaches it — same precedent as `expandTimeline` (line 588 comment confirms this idiom).

---

### `docker/web/site/style-shared.css` (modify — RETIRE blocks; hard constraint per D-04)

**Analog:** itself. **These deletions are NOT optional** — their higher specificity (`body.technical`) overrides `:root`, so COLOR-01/TYPE-01 never take effect unless removed.

**Retire 1 — dual dark palettes (lines 7-49).** Delete BOTH `body.technical` (7-27) and `body.strategic` (29-49) var blocks. These are the teal/violet mode-flip the SPEC §"What This Replaces" retires:
```css
/* style-shared.css:7-9, 29-31 — DELETE both blocks (dark hex + dual-accent mode flip) */
body.technical { --accent: #00e5a0; --bg: #0a0a0f; --text-primary: #ffffff; ... }
body.strategic { --accent: #7c3aed; --bg: #ffffff; --text-primary: #0a0a0f; ... }
```

**Retire 2 — `Courier New` body font (line 52).** Delete the `font-family: 'Courier New', monospace` from the `body` rule (lines 51-57) — `style-base.css` provides serif body. Courier survives on dozens of component rules in this file (`.hero-tagline`, `.section-label`, `.entry-preview`, `article p/ul/table`, subscribe inputs, etc., lines 100-489); leaving those rough between phases 11-14 is **expected & acceptable** (D-01 batch-deploy — Phase 12 owns the newsletter views). Phase 11 only MUST kill the `body`-level Courier so it does not cascade as the default.

**Retire 3 — `.top-nav` family + `.back-link` (lines 77-122, 243-252).** The new `style-base.css` nav-shell + back-control supersede these. They can be deleted or left dead (load order puts `style-base.css` first; deletion is cleaner). Current:
```css
/* style-shared.css:77-83 — superseded by sticky <header> in style-base.css */
.top-nav { display:flex; justify-content:space-between; align-items:center;
           padding:16px 0; border-bottom:0.5px solid var(--border); }
/* style-shared.css:243-250 — superseded by .backlink in style-base.css */
.back-link { font-family:'Courier New', monospace; font-size:15px;
             color:var(--accent); text-decoration:none; margin-bottom:20px; }
```

> **Preserve:** the reset (`*` line 3) and `.mode-transitioning` (68-73). Do NOT chase every Courier/dark reference in this file — that is the smallest-blast-radius rule (D-01/D-04). The `--accent`, `--border`, etc. var *references* throughout will simply resolve from `:root` now.

---

### `docker/web/site/style-map.css` (NOTE ONLY — do NOT touch this phase)

**Analog:** itself. Per CONTEXT.md + UI-SPEC §"What This Replaces" (footnote) + D-04: **tier-accent cleanup is DEFERRED to Phase 13.** The four-way tier palette (`:root` lines 18-31) and the `body.technical/strategic [data-accent]` cascade (lines 33-43) stay in place this phase. The only Phase-11-relevant line is `.nav-map-link` (lines 160-170) — its markup is removed from `index.html`, leaving these CSS rules as harmless dead selectors (clean up in P13 with the rest of the map styles). **Do not plan any edit to this file in Phase 11.**

---

## Shared Patterns

### Theme via CSS custom properties (the core transform)
**Source (retired):** `style-shared.css:7-49` — palette scoped under `body.technical/strategic`.
**New home:** `style-base.css` `:root` — one light palette, mode-decoupled.
**Apply to:** all files. **Never** re-introduce a `body.x`-scoped palette; that higher specificity is exactly the bug D-04 forbids.

### Defensive null-checks before DOM use
**Source:** `app.js:145-149` (`showView`) — `var x = document.querySelector(...); if (x) x.style...`.
**Apply to:** the new `setActiveTab` (tab elements) and any back-control wiring in `app.js`.

### Route-derived active state (not click-derived)
**Source (intent):** mockup script lines 377-382 (`parent` map).
**Real driver:** `getRoute()` (`app.js:115`) called inside `route()` (`app.js:742`) on load + `hashchange` (`app.js:760`).
**Apply to:** nav active-tab toggling. Use the UI-SPEC route→tab table verbatim.

### Reuse the existing subscribe flow
**Source:** `scrollToSubscribe()` (`app.js:283-285`); already invoked by `index.html:19` and `:88`.
**Apply to:** the new nav Subscribe button — `onclick="scrollToSubscribe()"`, no new mechanism (NAV-01).

### Load-order-as-cascade-control (no build step)
**Source:** `index.html:7-8` — plain `<link>` tags, order = cascade.
**Apply to:** add `style-base.css` **first**, before `style-shared.css`/`style-map.css` (D-04).

### Font loading via Google Fonts `<link>` (zero infra)
**Source:** `docker/web/Caddyfile:19` CSP already whitelists `style-src ... https://fonts.googleapis.com` + `font-src https://fonts.gstatic.com`.
**Apply to:** `index.html` `<head>` — UI-SPEC §Font-Loading block, **400 & 600 only** (the mockup's `<link>` line 9 requests 400;500;600;700 — trim to 400;600 per the weight policy).

---

## No Analog Found

None. Every file is an in-place transform of existing code or (for `style-base.css`) a token layer whose patterns come directly from the retired `style-shared.css` block + the locked mockup `:root`/nav. No file needs to fall back to RESEARCH.md.

---

## Metadata

**Analog search scope:** `docker/web/site/` (full read of `index.html`, `app.js`, `style-shared.css`, `style-map.css`), `docker/web/Caddyfile` (CSP), `.planning/docs/agentpulse-redesign-mockup.html` (intent reference).
**Files scanned:** 6.
**Pattern extraction date:** 2026-06-04.
