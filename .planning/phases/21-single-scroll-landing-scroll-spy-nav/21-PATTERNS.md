# Phase 21: Single-Scroll Landing + Scroll-Spy Nav - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 4 (all MODIFIED — zero net-new files)
**Analogs found:** 4 / 4 (in-file analogs; this is an in-file refactor, so every "new" code unit extends an existing pattern in the same file)

> **Nature of this phase:** No new files. Every change extends an existing in-file pattern. This map therefore answers, per change-unit, "which existing block in this same file is the analog the new code must mirror?" — quoting the live excerpt with line numbers. The planner should treat each analog as the house-style template the new code copies, not a foreign architecture to introduce.

## File Classification

| Modified file | Role | Data Flow | Change unit | Closest analog (same file unless noted) | Match Quality |
|---------------|------|-----------|-------------|------------------------------------------|---------------|
| `docker/web/site/app.js` | route/dispatch | event-driven (hashchange) | two-mode `getRoute()` | existing `getRoute()` (:188-209) | exact (extend) |
| `docker/web/site/app.js` | route/dispatch | event-driven | `route()` mode branch | existing `route()` (:1055-1068) | exact (extend) |
| `docker/web/site/app.js` | view-toggle | request-response | `showLanding()`/`showDetail()` | existing `showView()` (:211-235) | exact (refactor) |
| `docker/web/site/app.js` | nav-state | event-driven | scroll-spy `initScrollSpy()` (IO) | mockup `:501-510` + listener-registration idiom (:1075-1100) | role-match (new primitive, house wiring) |
| `docker/web/site/app.js` | nav-state | request-response | detail-route active-tab | existing `setActiveTab()` (:1029-1051) | exact (reuse for detail only) |
| `docker/web/site/app.js` | module-state | — | `landingScrollY` var | existing `timelineExpanded`/`evolutionPollHandle` (:134, :137) | exact (idiom) |
| `docker/web/site/app.js` | loader | request-response (REST) | `loadList`/`loadHub` de-couple from `showView` | existing `loadList()` (:267-268), `loadHub()` (:481-482) | exact (refactor) |
| `docker/web/site/index.html` | markup (nav) | — | bare-anchor nav links | existing `.tabs` block (:21-25) | exact (extend) |
| `docker/web/site/index.html` | markup (sections) | — | `#landing` wrapper + 4 `<section>` | existing `#list-view`/`#map-view`/`#about-view` + `.wide`/`.prose` wrappers (:39-137) | exact (reuse DOM) |
| `docker/web/site/index.html` | markup (Signals shell) | — | static `#signals` placeholder | About-stub prose/eyebrow/title structure (:98-108) | role-match (copy structure, new copy) |
| `docker/web/site/style-base.css` | CSS (scroll) | — | `scroll-behavior` + `scroll-margin-top` + reduced-motion | **NO analog in CSS** → mockup `:231` is the reference | no-analog (see below) |
| `docker/web/site/style-base.css` | CSS (nav active) | — | scroll-spy active state reuse | existing `.tab.active` (:206-211) | exact (reuse, do NOT add new) |
| `docker/web/site/style-base.css` | CSS (rhythm) | — | section-boundary rule | existing `.content-area` border-top (style-shared :131-132) + `.tier-section + .tier-section` (style-shared :235) | exact (extend pattern) |

---

## Pattern Assignments

### `app.js` — two-mode `getRoute()` (route/dispatch, event-driven)

**Analog:** existing `getRoute()` (:188-209) — keep the parse logic VERBATIM, add a `mode` field. Detail patterns are already tested before the bare fallthrough; preserve that order.

**Existing pattern to extend** (`app.js:188-209`):
```javascript
function getRoute() {
    var hash = window.location.hash || '#/';
    if (hash.startsWith('#/map/')) {
        return { view: 'block', slug: hash.split('/')[2] };
    }
    if (hash.startsWith('#/map')) {
        return { view: 'map' };
    }
    if (hash.startsWith('#/status')) {
        return { view: 'status' };
    }
    if (hash.startsWith('#/edition/')) {
        return { view: 'reader', edition: parseInt(hash.split('/')[2]) };
    }
    if (hash.startsWith('#/unsubscribe')) {
        return { view: 'unsubscribe' };
    }
    if (hash.startsWith('#/about')) {
        return { view: 'about' };
    }
    return { view: 'list' };
}
```

**House conventions to respect:**
- `var` (not `const`/`let`) inside functions — the whole file uses `var`.
- Defensive parse already present: `hash.split('/')[2]`, `parseInt(...)`. The new bare-anchor test must be an **anchored allowlist regex** (`/^#(...)$/`) so `#/map/foo` can never match a bare anchor (Pitfall 1 / Security V5 allowlist).
- The detail prefixes (`#/map/`, `#/map`, `#/status`, `#/edition/`, `#/unsubscribe`, `#/about`) keep their `startsWith` order; the bare-anchor + root fallthrough returns `mode:'landing'`. The current `#/map` (no trailing slash) and `#/about` detail prefixes become landing-section anchors — re-home them to the landing branch (their nav links change to bare `#map`/`#about` in index.html anyway).

---

### `app.js` — `route()` mode branch (route/dispatch, event-driven)

**Analog:** existing `route()` (:1055-1068). Branch on `r.mode`: detail → existing dispatch + `setActiveTab`; landing → `showLanding` (IO owns active, do NOT call `setActiveTab`).

**Existing pattern to extend** (`app.js:1055-1068`):
```javascript
function route() {
    window.currentNewsletter = null;
    var r = getRoute();
    setActiveTab(r.view);
    switch (r.view) {
        case 'list': loadList(); break;
        case 'reader': loadEdition(r.edition); break;
        case 'unsubscribe': handleUnsubscribe(); break;
        case 'map': loadHub(); break;
        case 'block': loadBlock(r.slug); break;
        case 'status': loadStatus(); break;
        case 'about': showView('about'); window.scrollTo(0, 0); break;
    }
}
```

**Critical refactor note:** the unconditional `setActiveTab(r.view)` on :1058 must become **detail-only**. On landing, the scroll-spy IO owns `.active` — calling `setActiveTab` there would race the observer and flicker (Anti-Pattern, research :218). Stash `landingScrollY = window.scrollY` only when LEAVING a currently-visible landing (guard on `#landing` not being `display:none`).

---

### `app.js` — `showLanding()` / `showDetail()` (view-toggle, request-response)

**Analog:** existing `showView()` (:211-235). This is the function the refactor splits. The `display:none` view-toggle idiom and the toggle/hero gating block are the house pattern to preserve — re-homed from "list route only" to "landing vs detail".

**Existing pattern being refactored** (`app.js:211-235`):
```javascript
function showView(viewName) {
    document.getElementById('list-view').style.display = viewName === 'list' ? 'block' : 'none';
    document.getElementById('reader-view').style.display = viewName === 'reader' ? 'block' : 'none';
    document.getElementById('map-view').style.display = viewName === 'map' ? 'block' : 'none';
    document.getElementById('block-view').style.display = viewName === 'block' ? 'block' : 'none';
    document.getElementById('status-view').style.display = viewName === 'status' ? 'block' : 'none';
    var aboutView = document.getElementById('about-view');
    if (aboutView) aboutView.style.display = viewName === 'about' ? 'block' : 'none';

    // The Technical/Strategic toggle lives ONLY inside the Newsletter list (TGL-01,
    // D-01). ... Defensive null-checks per PATTERNS §3.
    var showToggle = (viewName === 'list');
    var toggle = document.querySelector('.mode-toggle');
    if (toggle) toggle.style.display = showToggle ? 'inline-flex' : 'none';
    var subtitle = document.getElementById('mode-subtitle');
    if (subtitle) subtitle.style.display = showToggle ? 'block' : 'none';

    var hero = document.querySelector('.hero');
    if (hero) hero.style.display = viewName === 'list' ? 'block' : 'none';
}
```

**House conventions to respect (load-bearing for the refactor):**
- The `el.style.display = cond ? 'block' : 'none'` toggle idiom is THE view-switch mechanism — keep it. `showLanding()` shows `#landing` + hides the 4 detail containers; `showDetail(view)` does the inverse.
- **Defensive null-check idiom** (`var x = document.querySelector(...); if (x) x...`) — every DOM lookup that may be absent is guarded. Replicate for the new `#landing`/`#signals` lookups.
- **Toggle/hero re-homing (Pitfall 5):** the `.mode-toggle`, `#mode-subtitle`, and `.hero` are list-scoped today via `viewName === 'list'`. On the single-scroll landing they belong to the Newsletter section (`#index`) and must be visible whenever the landing is shown. Re-gate `showToggle`/hero to "landing mode" (or pin to `#index`), NOT `viewName === 'list'`.
- The TGL-01 comment ("toggle lives ONLY inside the Newsletter list") is the spec — keep the toggle physically inside `#index` so it never appears on a block/edition detail page.

---

### `app.js` — scroll-spy `initScrollSpy()` (nav-state, event-driven) — NEW primitive, house wiring

**Analog (pattern source):** mockup `.planning/docs/agentpulse-redesign (1).html:501-510` (operator-approved, `rootMargin:'-50% 0px -50% 0px'`).
**Analog (registration idiom):** the existing top-level `window.addEventListener('hashchange', ...)` + visibility listeners (`app.js:1075-1100`) — the new IO setup is registered ONCE at init alongside these, same flat top-level style.

**Existing listener-registration idiom to mirror** (`app.js:1075-1100`, abridged):
```javascript
window.addEventListener('hashchange', route);

// Idle-poll cleanup — a SIBLING listener to the routing one above ...
window.addEventListener('hashchange', function() {
    if (!window.location.hash.startsWith('#/map/')) {
        stopEvolutionPoll();
    }
});

window.addEventListener('visibilitychange', function() { ... });
```

**House conventions the new IO must respect:**
- Section ids passed to `getElementById`/`observe` must be **static literals** matching the locked section array order (LOCKED: Newsletter → Signals → Agent-Economy → About per 21-CONTEXT.md). NEVER pass `location.hash` to `getElementById`/`scrollIntoView` (Security V5 — no hash value reaches a DOM sink).
- Active toggle reuses the existing `.tab` / `data-tab` mechanism (see `setActiveTab` :1042-1044: `el.classList.toggle('active', isActive)` + `aria-current`). The IO's `links.forEach(l => l.classList.toggle('active', ...))` must set/clear `aria-current='page'` the same way `setActiveTab` does (:1045-1049) so NAV-02 a11y parity holds.
- The scroll-spy `sections` array order MUST equal the DOM `<section>` order MUST equal the nav-link order (Pitfall 6) — all three are the one LOCKED order.
- **Pitfall 3 mitigation:** in `showLanding(section)`, set the initial `.active` explicitly from the target section BEFORE the IO takes over (IO fires zero events while `#landing` was `display:none`).

**Mockup pattern to adapt** (reference only — selector must target AgentPulse `.tab[data-tab]`/`href` anchors, not `.nav-links a:not(.sub)`):
```javascript
// .planning/docs/agentpulse-redesign (1).html:501-510 — VERBATIM pattern, adapt selectors
var obs = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
        if (e.isIntersecting) {
            links.forEach(function(l){ l.classList.toggle('active', l.getAttribute('href') === '#' + e.target.id); });
        }
    });
}, { rootMargin: '-50% 0px -50% 0px' });
sections.forEach(function(s){ s && obs.observe(s); });
```

---

### `app.js` — detail-route active tab (nav-state, request-response)

**Analog:** existing `setActiveTab()` (:1029-1051) — KEEP IT, but call it ONLY for detail routes. Its route→tab map is the NAV-02 contract.

**Existing pattern to reuse** (`app.js:1029-1051`):
```javascript
function setActiveTab(view) {
    var VIEW_TO_TAB = {
        list: 'newsletter',
        reader: 'newsletter',
        map: 'map',
        block: 'map',
        status: 'map',
        about: 'about'
    };
    var targetTab = VIEW_TO_TAB[view];
    var tabs = document.querySelectorAll('.tab');
    if (!tabs || !tabs.length) return;
    tabs.forEach(function(el) {
        var isActive = el.dataset.tab === targetTab;
        el.classList.toggle('active', isActive);
        if (isActive) {
            el.setAttribute('aria-current', 'page');
        } else {
            el.removeAttribute('aria-current');
        }
    });
}
```

**House conventions:** `data-tab` keys (`newsletter`/`map`/`about`) are the join between nav markup and active logic. The new Signals nav link needs a `data-tab` key (e.g. `signals`); detail routes never map to it (no detail route lives under Signals in P21), so the map stays `reader→newsletter`, `block/status→map`. The `el.classList.toggle('active', ...)` + `aria-current` pair is the exact mechanism the scroll-spy IO must replicate for landing.

---

### `app.js` — `landingScrollY` module var (module-state)

**Analog:** existing module-scoped vars `timelineExpanded` (:134) and `evolutionPollHandle` (:137).

**Existing idiom to match** (`app.js:134, 137`):
```javascript
// D-11: whether Show all was clicked; reset on each loadBlock() entry; read by the Wave 3 idle poll.
var timelineExpanded = false;

// Interval handle for the block-page Evolution refresh poll (D-05, D-06, D-07).
var evolutionPollHandle = null;
```

**House conventions:** declare `var landingScrollY = 0;` at module top with a one-line `//`-comment explaining intent (matches the commented-declaration style above). This is the operator-locked scroll-restore choice (CONTEXT "Claude's Discretion" → research recommends the module var over `history.scrollRestoration`).

---

### `app.js` — `loadList` / `loadHub` decouple from `showView` (loader, request-response) — TRICKIEST EDIT

**Analog:** existing `loadList()` (:267-268) and `loadHub()` (:481-482). Both call `showView(...)` at the top — that coupling must be removed so the loaders only RENDER into their section container; visibility is owned by `showLanding`/`showDetail`.

**Existing coupling to break** (`app.js:267-268`):
```javascript
async function loadList() {
    showView('list');
    updateHero('AI Agents Pulse', '');
    var { data, error } = await sb
        .from('newsletters')
        .select('*')
        .in('status', ['published', 'preview'])
        .order('edition_number', { ascending: false });
    ...
```

**Existing coupling to break** (`app.js:481-482`):
```javascript
async function loadHub() {
    showView('map');
    // Phase 13 (D-06): the hub header renders inside #map-view .content-area ...
```

**House conventions:**
- Supabase reads stay byte-identical (`sb.from('newsletters').select('*').in('status', [...])` for list; `sb.schema('economy_map')` per D-16 for hub — do NOT add a `.eq('status')` filter, D-17 RLS-is-the-boundary). Phase 21 adds NO new query.
- Wrap the two loaders behind an idempotent `ensureLandingDataLoaded()` guard (call each once) — same "guard a one-time side-effect with a flag" idiom as `timelineExpanded`/`evolutionPollHandle`.
- Drop the `showView('list'/'map')` first line from each loader; `showLanding()` owns container visibility now.

---

### `index.html` — bare-anchor nav links (markup)

**Analog:** existing `.tabs` block (:21-25).

**Existing markup to extend** (`index.html:21-25`):
```html
<div class="tabs">
    <a href="#/" class="tab" data-tab="newsletter">Newsletter</a>
    <a href="#/map" class="tab" data-tab="map">Agent Economy</a>
    <a href="#/about" class="tab" data-tab="about">What is AgentPulse</a>
</div>
```

**House conventions to respect:**
- Keep `class="tab"` + `data-tab` on each `<a>` (the join key for both `setActiveTab` and the scroll-spy IO).
- Change `href` to bare section anchors and **add the Signals link**, in the LOCKED order (Newsletter → Signals → Agent-Economy → About). Per CONTEXT, prefer self-describing semantic ids (e.g. `#newsletter`/`#signals`/`#map`/`#about`) over the mockup's `#index`/`#made` — planner's discretion on exact strings, but nav `href` ↔ section `id` ↔ IO array MUST stay in sync.
- Keep the brand link `<a href="#/" class="brand">` (:17) — `#/` resolves to landing + scrolls to top.
- **No inline event handlers on nav links** — navigation is href-driven (`hashchange` → `route()`). (The existing `onclick="scrollToSubscribe()"` on the Subscribe button and `onclick="setMode(...)"` on the toggle are pre-existing global chrome — leave them; do NOT add new inline handlers for scroll-spy.)

---

### `index.html` — `#landing` wrapper + 4 stacked `<section>` (markup, reuse DOM)

**Analog:** the four existing top-level view containers + their Phase 20 `.wide`/`.prose` axis wrappers (:39-137). REUSE these DOMs as the section bodies — do NOT rebuild (preserves every Phase 12-20 CSS selector + render fn).

**Existing axis-wrapper idiom to preserve** (`index.html:39-55` and :93-99):
```html
<div class="wide">
    <div class="hero"> ... mode-toggle + subtitle ... </div>
</div>
<main>
    <div id="list-view">
        <div class="content-area wide" id="newsletter-list"></div>
    </div>
    ...
    <div id="about-view" style="display:none">
        <div class="content-area about-stub">
            <div class="prose"> ... eyebrow / page-title / page-sub / .about ... </div>
            <div class="wide"> <div class="agent-row"> ...pills... </div> </div>
        </div>
    </div>
</main>
```

**House conventions to respect:**
- **Scope guard (CONTEXT "Must NOT change"):** the Phase-20 `.wide` (1080px tiled) / `.prose` (64ch reading) axis wrappers stay. The new `<section>` wrappers sit AROUND the existing `.wide`/`.prose` blocks — do not retire or alter them. `#index`'s body = the existing `.hero` (:39-49) + `#list-view` (:53-55); `#map` = `#map-view` (:68-70); `#about` = `#about-view` (:93-137).
- Detail containers `#reader-view` (:58-63), `#block-view` (:73-78), `#status-view` (:81-86) stay siblings OUTSIDE `#landing`, shown only in detail mode (keep their `style="display:none"` default).
- Subscribe section + footer (:142-166) stay OUTSIDE `<main>`/landing — always visible, unchanged.
- The `style="display:none"` inline-default on detail containers is the house idiom paired with the JS `showView`/`showDetail` toggle — keep it on detail containers; `#landing` defaults visible.

---

### `index.html` — static `#signals` placeholder shell (markup, new copy)

**Analog (structure to copy):** the About-stub prose intro (`index.html:98-108`) — eyebrow → page-title → page-sub → prose paragraph, on the `.prose` axis inside a `.content-area`.

**Existing structure to mirror** (`index.html:98-108`):
```html
<div class="content-area about-stub">
    <div class="prose">
        <p class="eyebrow">Behind the Briefing</p>
        <h1 class="page-title">What is AgentPulse</h1>
        <p class="page-sub">A newsletter written by a multi-agent system</p>
        <div class="about">
            <p>AgentPulse is a weekly intelligence briefing ...</p>
        </div>
    </div>
    ...
</div>
```

**House conventions to respect (Pitfall 7 / SIGNAL-04):**
- Ship `#signals` as a **pure static shell** — eyebrow + heading + a one-line "coming soon"/empty-state, on the `.prose` axis. **NO Supabase call** for `source_posts` (anon-RLS-blocked until Phase 24; a premature fetch = silent empty feed = fail-loud violation).
- Reuse existing classes (`.eyebrow`, `.page-title`, `.page-sub`, `.prose`, `.content-area`) so no new component CSS is needed. Note `.eyebrow`/`.page-sub` are scoped (`.article-header .eyebrow` :649, `.about-stub .page-sub` :904) — if the Signals shell needs them styled, either nest under an existing scope class or add a minimal `#signals` empty-state rule in style-shared.css (see CSS section).

---

### `style-base.css` — scroll-spy active state reuse (CSS)

**Analog:** existing `.tab.active` (:206-211) — the scroll-spy DOES NOT need a new active-state rule; it toggles the SAME `.active` class on the SAME `.tab` anchors.

**Existing rule to reuse (do NOT duplicate)** (`style-base.css:190-211`):
```css
.tab {
  display:inline-flex;
  ...
  color:var(--ink-soft);
  padding:8px 12px;
  border-radius:var(--radius-sm);
  border:1px solid transparent;  /* matches .active's 1px border → no height shift */
  text-decoration:none;
}
.tab.active {
  color:var(--accent-ink);
  background:var(--accent-soft);
  border-color:#ddd2ff;
  font-weight:600;
}
```

**House convention:** the scroll-spy reuses this exact `.tab` / `.tab.active` pair — adding `.active` via JS yields the existing accent-soft fill. No new CSS for the active state. The `border:1px solid transparent` → `.active` `border-color` swap is deliberate (no height shift on highlight) — preserve.

---

### `style-base.css` — section-boundary rhythm (CSS, extend existing pattern)

**Analog:** the existing major-boundary rule pattern — `.content-area { border-top: 1px solid var(--line-strong); }` (style-shared :131-132) and `.tier-section + .tier-section { border-top: 1px solid var(--line-strong); padding-top: var(--space-xl); }` (style-shared :233-235).

**Existing rhythm pattern to extend** (`style-shared.css:233-235`):
```css
.tier-section + .tier-section { border-top: 1px solid var(--line-strong); padding-top: var(--space-xl); }
```

**House conventions to respect (RHYTHM-01 scope guard):**
- Use the `--line-strong` token for the inter-section rule (not a literal color). Use `--space-*` tokens for padding. The site is 100% token-driven (color audit) — never hardcode `#d8d2c7`.
- Extend the `X + X { border-top }` adjacent-sibling pattern to `#landing > section + section` (one full-strength `1px var(--line-strong)` rule between major landing sections), matching the existing `.tier-section`/`.content-area` major-boundary convention. Do NOT introduce a new visual divider style.
- **Scope guard:** do not alter the Phase-20 width tokens (`--measure`/`--wide`/`--gutter`) or the existing boundary rules — only ADD the landing-section adjacency rule.

---

## Shared Patterns

### `display:none` view-toggle idiom
**Source:** `showView()` (`app.js:211-235`), inline `style="display:none"` defaults (`index.html:58,68,73,81,93`).
**Apply to:** `showLanding()`/`showDetail()`, all section show/hide.
```javascript
document.getElementById('x').style.display = cond ? 'block' : 'none';
```
Every visibility switch in this codebase is a `style.display` toggle, paired with a `style="display:none"` inline default in markup. The two-mode router keeps this — `#landing` vs detail containers.

### Defensive null-check on DOM lookups
**Source:** `showView()` (:217, :225-228, :233), `setActiveTab()` (:1040-1041).
**Apply to:** every new `getElementById`/`querySelector` (`#landing`, `#signals`, IO section lookups).
```javascript
var el = document.getElementById('x'); if (el) el.style.display = ...;
// and: var tabs = document.querySelectorAll('.tab'); if (!tabs || !tabs.length) return;
```

### `var` + commented module-global idiom
**Source:** `timelineExpanded` (:134), `evolutionPollHandle` (:137), `currentMode` (:131).
**Apply to:** `landingScrollY`, any IO/observer handle.
Module-scoped `var` with a one-line `//`-comment stating intent + the governing decision id.

### Active-tab `classList.toggle('active', ...)` + `aria-current`
**Source:** `setActiveTab()` (:1042-1049).
**Apply to:** both detail-route active (reuse `setActiveTab`) AND the scroll-spy IO (replicate the toggle + `aria-current='page'`/`removeAttribute` pair so a11y parity holds).

### Hash-as-allowlist (security)
**Source:** existing `getRoute()` prefix tests (:188-209); the new bare-anchor regex must be anchored `/^#(...)$/`.
**Apply to:** the new landing-section detection. The hash is the only new input path — keep it an allowlist; never let a hash value reach `getElementById`/`scrollIntoView`/`innerHTML`. Section ids passed to DOM APIs are static literals only.

### Token-only CSS (no literals)
**Source:** `:root` tokens (`style-base.css:10-79`), every component rule consumes `var(--…)`.
**Apply to:** all new CSS (`scroll-margin-top: calc(60px + var(--space-md))`, section border `var(--line-strong)`). Color audit is 100% token-driven — no hex literals (`--on-accent`/`--line-strong` exist precisely to avoid `#fff`/`#d8d2c7` literals).

### Sticky-header scoping (scope guard, do NOT regress)
**Source:** `body > header { position:sticky; top:0; z-index:50; }` (`style-base.css:142-149`).
**Apply to:** keep the `body > header` selector EXACTLY (not bare `header`) — this is the maturity-pill overlap fix (MEMORY `260609-ivq`). The new `scroll-margin-top` offsets the anchor JUMP against this sticky header's rendered height (~60px = nav `padding:12px` :155 + ~12.5px mono content); do not touch the sticky rule itself.

---

## No Analog Found

Files/units with no close in-codebase analog — use the mockup + research patterns:

| Change unit | Role | Data Flow | Reason / where to source the pattern |
|-------------|------|-----------|--------------------------------------|
| `style-base.css`: `html { scroll-behavior:smooth }` + `@media (prefers-reduced-motion: reduce){ html{scroll-behavior:auto} }` | CSS (scroll) | — | **No `scroll-behavior`, `scroll-margin`, `scroll-padding`, or `prefers-reduced-motion` rule exists anywhere in style-base.css / style-shared.css today** (verified by grep). Net-new CSS. Source = mockup `.planning/docs/agentpulse-redesign (1).html:231` + research Code Examples (21-RESEARCH.md :294-303). Reduced-motion gate is mandatory (A11Y-01, must-not-regress). |
| `style-base.css`: `#landing > section { scroll-margin-top: calc(60px + var(--space-md)); }` | CSS (scroll) | — | Net-new (no existing scroll-margin rule). Source = research Pitfall 2 + Code Examples. Offset value tunes against the live sticky-header height (~60px) — flagged for live-render measurement (research A7). |
| `app.js`: `IntersectionObserver` scroll-spy | nav-state | event-driven | No existing IO usage in `app.js` (the file uses `setInterval`/event listeners, never IO). The PRIMITIVE is new — but its WIRING (one-time top-level registration, `.tab`/`data-tab`/`.active` toggle, static-literal section ids) extends existing house patterns. Pattern source = mockup `:501-510`. |
| `app.js`: `prefersReducedMotion()` helper | utility | — | Net-new (no `matchMedia` usage today). Only needed IF programmatic `scrollIntoView` is used on deep-link load; prefer the CSS `scroll-behavior` route so this helper may be unnecessary. Source = research :305-311. |

> The closest existing smooth-scroll call is `scrollToSubscribe()` (`app.js:388-390`): `document.getElementById('subscribe-section').scrollIntoView({ behavior: 'smooth' });` — the in-codebase `scrollIntoView` idiom IF the planner chooses JS-driven scroll. But it does NOT branch on reduced-motion (it predates A11Y-01), so a verbatim copy would regress reduced-motion. Research recommends the declarative CSS `scroll-behavior` route instead (reduced-motion-aware for free), making `scrollIntoView`+`prefersReducedMotion()` a fallback only.

---

## Metadata

**Analog search scope:** `docker/web/site/` (app.js, index.html, style-base.css, style-shared.css). Single self-contained static SPA — no cross-service analogs apply.
**Files scanned:** 4 (all in-scope, targeted reads at research-quoted line ranges + grep for sticky/tab/rhythm/scroll selectors).
**Key negative finding:** zero pre-existing `scroll-behavior` / `scroll-margin` / `scroll-padding` / `prefers-reduced-motion` / `IntersectionObserver` in the codebase — these are the only genuinely net-new patterns; everything else extends an in-file analog.
**Pattern extraction date:** 2026-06-11
