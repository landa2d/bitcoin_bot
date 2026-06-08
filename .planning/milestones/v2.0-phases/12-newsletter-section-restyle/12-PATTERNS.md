# Phase 12: Newsletter Section Restyle - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 4 (all RESTYLE-IN-PLACE — no new files)
**Analogs found:** 4 / 4 (each surface's analog IS its own current implementation)

> **Framing for the planner/executor:** This phase modifies existing surfaces in place. There is no "copy from another file" analog — the closest analog for each rule/function block is the **current state of that same block**. This map pairs each **current** excerpt with its **UI-SPEC target** so the executor sees current → target side by side. All target values resolve to Phase 11 `:root` tokens (verified present in `style-base.css` lines 10-66) or the locked `.page-title` / `.eyebrow` display classes (`style-base.css` lines 82-97). No new tokens, no second font.

---

## Line-Number Verification (drift check vs CONTEXT/UI-SPEC)

All function anchors cited in CONTEXT.md / UI-SPEC.md were verified against the real files. Result: **cited line numbers are accurate.** One minor correction below.

| Cited (CONTEXT/UI-SPEC) | Real | Status |
|---|---|---|
| `setMode()` `app.js:68` | line 68 | EXACT |
| `updateHero()` `app.js:108` | line 108 | EXACT |
| `showView()` `app.js:138` | line 138 | EXACT |
| `renderList()` `app.js:164` | line 164 | EXACT |
| `renderArticle()` `app.js:217` | line 217 | EXACT |
| `MODES` const `app.js:11` | line 11 | EXACT |
| `getModeTitle()` `app.js:356` / `getModeContent()` `:361` | 356 / 361 | EXACT (DO NOT TOUCH) |
| `index.html` `.hero` block "lines ~32–42" | `.hero` opens at **line 33**, closes line 42 (comment `<!-- Hero area -->` is line 32) | CORRECTED: block is **33–42** |

**File line counts (so the executor reads non-overlapping ranges):** `app.js` = 836 lines, `index.html` = 121 lines, `style-shared.css` = 425 lines, `style-base.css` = 249 lines. All under 2000 — single-read files.

---

## File Classification

| Surface (modified in place) | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `docker/web/site/app.js` (render fns) | component (view renderer) | transform (data → DOM string) | itself (current `renderList`/`renderArticle`/`updateHero`/`showView`) | self / in-place |
| `docker/web/site/index.html` (`.hero` + view containers) | component (static markup) | request-response (route → view) | itself (current `.hero` block) | self / in-place |
| `docker/web/site/style-shared.css` (legacy component rules) | config (CSS) | transform (token → render) | itself (current `.hero`/`.mode-toggle`/`.entry-*`/`article` rules) | self / in-place |
| `docker/web/site/style-base.css` (`:root` + display classes) | config (CSS token layer) | n/a | read-only reference; new Newsletter rules may be appended | self / reference |

---

## Pattern Assignments

### FILE 1 — `docker/web/site/app.js` (view renderer, transform)

The render functions emit DOM strings; restyle their **markup output** (and add the date to the list kicker), keeping all fetch/router/mode logic intact.

#### 1a. `setMode()` — KEEP VERBATIM, element IDs must survive the relocation (lines 68-104)

This is the load-bearing reuse. The relocated toggle pill + hint line MUST keep the IDs `btn-technical`, `btn-strategic`, `mode-subtitle` so this function needs **zero logic change**. Current:

```javascript
function setMode(mode) {
    if (!MODES[mode]) return;
    currentMode = mode;
    localStorage.setItem('agentpulse_mode', mode);
    // Update URL param without reload
    var url = new URL(window.location);
    url.searchParams.set('mode', mode);
    history.replaceState({}, '', url);
    // Body class (drives CSS variables)
    document.body.classList.remove('technical', 'strategic');
    document.body.classList.add(mode);
    // Toggle buttons
    document.getElementById('btn-technical').classList.toggle('active', mode === 'technical');
    document.getElementById('btn-strategic').classList.toggle('active', mode === 'strategic');
    // Mode subtitle
    document.getElementById('mode-subtitle').textContent = MODES[mode].subtitle;
    // Transition
    document.body.classList.add('mode-transitioning');
    setTimeout(function() {
        document.body.classList.remove('mode-transitioning');
    }, 400);
    // Re-render current article if loaded (without refetching)
    if (window.currentNewsletter) {
        renderArticle(window.currentNewsletter);
    }
    // Re-render list if visible
    if (window.currentNewsletterList && document.getElementById('list-view').style.display !== 'none') {
        renderList(window.currentNewsletterList);
    }
}
```

**Target:** UNCHANGED. The `.active` class it toggles (line 83-84) drives the filled-accent active segment; the `mode-subtitle` textContent (line 87) drives the hint-line copy. **Caveat for the executor:** the line-91 `mode-transitioning` 400ms animation is retained (Interaction Contract row 5). NOTE the comment on line 79 ("Body class (drives CSS variables)") is now **stale** — Phase 11 decoupled palette to `:root`; the body class only re-renders content. CONTEXT D-03 says do not reintroduce it as a theme selector. The executor may correct the stale comment but must not change the behavior.

#### 1b. `updateHero()` — keep signature (lines 108-111)

```javascript
function updateHero(title, dateText) {
    document.getElementById('hero-headline').textContent = title || '';
    document.getElementById('hero-date').textContent = dateText || '';
}
```

**Target:** still writes the minimal-header page-title + metadata line. If the executor renames the hero DOM nodes (`hero-headline`/`hero-date`) during the D3 header restructure, **update these two `getElementById` targets to match.** It is called from many loaders (`loadList` :197, `renderList` :168/:175, `renderArticle` :223, plus map/status/block loaders) — keep the 2-arg `(title, dateText)` contract so the non-Newsletter callers (which Phase 13 owns) keep working. The list-view copy is fed by `renderList()` (see 1d).

#### 1c. `showView()` — the hero/toggle visibility gating to extend (lines 138-160)

This is the DOM-home mechanism the UI-SPEC resolves (Component Contract A, "DOM-home discretion resolved"). Current:

```javascript
function showView(viewName) {
    document.getElementById('list-view').style.display = viewName === 'list' ? 'block' : 'none';
    document.getElementById('reader-view').style.display = viewName === 'reader' ? 'block' : 'none';
    document.getElementById('map-view').style.display = viewName === 'map' ? 'block' : 'none';
    document.getElementById('block-view').style.display = viewName === 'block' ? 'block' : 'none';
    document.getElementById('status-view').style.display = viewName === 'status' ? 'block' : 'none';
    var aboutView = document.getElementById('about-view');
    if (aboutView) aboutView.style.display = viewName === 'about' ? 'block' : 'none';

    // Hide the technical/strategic mode toggle on map routes and the About page
    // (D-03). The body class stays so the --accent-tier cascade still resolves;
    // only the toggle UI and its subtitle are hidden. Defensive null-checks per PATTERNS §3.
    var hideToggle = (viewName === 'map' || viewName === 'block' || viewName === 'status' || viewName === 'about');
    var toggle = document.querySelector('.mode-toggle');
    if (toggle) toggle.style.display = hideToggle ? 'none' : 'inline-flex';
    var subtitle = document.getElementById('mode-subtitle');
    if (subtitle) subtitle.style.display = hideToggle ? 'none' : 'block';

    // About is a standalone top-level section — hide the newsletter hero so the
    // stub reads clean. Phase 14 (ABOUT-01) builds the full page.
    var hero = document.querySelector('.hero');
    if (hero) hero.style.display = viewName === 'about' ? 'none' : 'block';
}
```

**Target (UI-SPEC Component Contract A + "What This Replaces" final row):** repurpose `.hero` as a **list-scoped** minimal header. Today the hero/toggle show on `list` AND `reader` (the `hideToggle` set excludes only map/block/status/about, and the `hero` shows on everything except `about`). The TGL-01 requirement is the toggle ends up **only** in the Newsletter list. Resolved mechanism: show the hero/header (and therefore the toggle pill it now contains) on the `list` route only — the `reader` view carries its own magazine header (1e). The existing defensive null-checks (`if (toggle)`, `if (subtitle)`, `if (hero)`) are the established pattern — **preserve them.** Do NOT regress the map/block/status hero behavior (Phase 13 owns it). The current `.querySelector('.mode-toggle')`/`'.hero'` selectors will move with the markup — keep them resolving to the relocated nodes.

#### 1d. `renderList()` — restyle row template + ADD THE DATE to the kicker (lines 164-190)

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

**Targets (UI-SPEC Component Contract C + Copywriting):**
- The `.section-label` kicker copy `'EDITION #' + n.edition_number` MUST become `EDITION #{N} · {date}` — append `' · ' + formatDate(n.published_at)` (the `·` U+00B7 separator pattern already used on line 175 for the hero metadata). This is the one **markup/data** change in this function (D-04 / Copywriting row "List-row kicker").
- Row anatomy (`<div class="article-entry">` → `.section-label` → `.entry-title` link → `.entry-preview`) is **preserved** — restyle happens in CSS (FILE 3), not here.
- Excerpt truncation `.substring(0, 150)` is **kept verbatim** (UI-SPEC §C "Excerpt length — discretion resolved: keep the existing ~150-char truncation").
- The `'AI Agents Pulse'` / `'Latest: Edition #...'` `updateHero` strings are **locked** (Copywriting rows) — keep wording.
- Empty-state line `No newsletters published yet.` is **locked** (restyle the inline `color:var(--text-secondary);font-size:15px;` into serif/`--ink-soft` — note this currently uses a legacy bridge alias and an inline style; the planner decides whether to move it to a CSS class).
- `getModeTitle()` / `getModeContent()` calls UNCHANGED (out of scope).

#### 1e. `renderArticle()` — restyle PREVIEW banner; the magazine header is the bigger lift (lines 217-232)

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

**Targets (UI-SPEC Component Contract D + "What This Replaces"):**
- **PREVIEW banner — restyle, do not rebuild.** Current inline amber (`background:#f59e0b;color:#000;...border-radius:6px;...`) → UI-SPEC §D: `background: var(--accent-soft)`, `color: var(--ink)`, `border-left: 3px solid var(--accent)`, `border-radius: var(--radius)` (10px), `padding: var(--space-sm) var(--space-md)`, mono 12.5px/600 UPPERCASE label. Copy `PREVIEW — NOT YET PUBLISHED` is **unchanged**. Recommend moving from the inline `style="..."` to a CSS class (e.g. `.preview-banner` in FILE 3/4) so it consumes tokens; the `status === 'preview'` gate stays.
- **Magazine header (C2 / D-05):** the article currently relies on the shared `.hero` for its title (via `updateHero` line 223). With the hero scoped to the **list** route (1c), the reader view needs its own magazine header (mono kicker `Edition #{N} · {Technical|Strategic}` via `.eyebrow`, serif display title via `.page-title`, mono byline `Edition #{N} · {date} · {Technical|Strategic}`). The `currentMode` global resolves the `{Technical|Strategic}` label (use `MODES[currentMode].label`). This is **DOM-home discretion** (UI-SPEC §D + §A resolution) — the executor emits this header into `#reader-view`, under the existing `← Back to Newsletter` control already present in the static markup (index.html line 53). The lead-paragraph emphasis is a **CSS-only** rule (`#newsletter-content > p:first-of-type`) — no change to `marked.parse(content)`.
- `marked.parse(content)` and `getModeTitle/Content` calls UNCHANGED.
- Edition-not-found copy `Edition not found.` (in `loadEdition` line 246) is **locked** — restyle into serif only.

#### OUT OF SCOPE in app.js (do NOT touch)

`getModeTitle()` (356-359), `getModeContent()` (361-364), `getInitialMode()` (49-58), `getRoute()` (115-136), `loadList()`/`loadEdition()` fetch logic, the entire map/block/status/poll machinery (lines 366-755), `setActiveTab()` (764-786), `route()`/init (790-835). These are explicitly excluded by the UI-SPEC scope map.

---

### FILE 2 — `docker/web/site/index.html` (static markup, request-response)

#### 2a. Global `.hero` block — restructure to the minimal D3 header (lines 33-42)

```html
    <!-- Hero area -->
    <div class="hero">
        <p class="hero-tagline">WEEKLY INTELLIGENCE BRIEFING</p>
        <h1 class="hero-headline" id="hero-headline"></h1>
        <p class="hero-date" id="hero-date"></p>
        <div class="mode-toggle">
            <button class="toggle-btn active" id="btn-technical" onclick="setMode('technical')">Technical</button>
            <button class="toggle-btn" id="btn-strategic" onclick="setMode('strategic')">Strategic</button>
        </div>
        <p class="mode-subtitle" id="mode-subtitle">Architecture, code, implementation</p>
    </div>
```

**Targets (UI-SPEC §"What This Replaces" rows 1-3 + Component Contracts A & B):**
- **Drop** `.hero-tagline` (`WEEKLY INTELLIGENCE BRIEFING`) entirely (D-07 picks D3, not D1's eyebrow+title).
- `.hero-headline` → minimal serif page-title (apply the locked `.page-title` class; `updateHero` writes `AI Agents Pulse` into it). The `id="hero-headline"` must stay reachable by `updateHero` (or rename both sides in tandem — see 1b).
- `.hero-date` → mono 14px metadata line (`Latest: Edition #{N} · {date}`); `id="hero-date"` likewise.
- **Toggle relocation (TGL-01):** the `.mode-toggle` (with its two `#btn-technical`/`#btn-strategic` buttons) + `.mode-subtitle` (`#mode-subtitle`) move so they live **only** in the Newsletter list. UI-SPEC §A resolution: keep them inside this hero block but make the hero render on the `list` route only (via `showView()` 1c) — that structurally satisfies TGL-01. **The `onclick="setMode('technical')"` / `onclick="setMode('strategic')"` wiring and all three element IDs are preserved verbatim** so `setMode()` (1a) needs no change. Reform the two `.toggle-btn` buttons into the segmented accent pill A1 (filled-accent active segment) via CSS (FILE 3).
- The list-view container (`#list-view` → `#newsletter-list`, lines 46-48) and reader-view container (`#reader-view` → `← Back to Newsletter` backlink + `<article id="newsletter-content">`, lines 51-56) are the render sinks — their IDs are **load-bearing** (referenced by `renderList`/`renderArticle`); do not rename.

**Deliberately untouched in index.html:** the nav `<header>` shell (lines 16-29, Phase 11), `#map-view`/`#block-view`/`#status-view`/`#about-view` (lines 59-87, Phase 13/14), the subscribe section + bottom bar (lines 91-112), the `<script>` tags + font `<link>` (line 9 already loads Source Serif 4 400/600+italic and IBM Plex Mono 400/600 — no font change).

---

### FILE 3 — `docker/web/site/style-shared.css` (legacy component rules, transform)

This is where the bulk of the restyle lands. Each current rule below maps to a UI-SPEC target. **All targets resolve to `:root` tokens present in `style-base.css` lines 10-66.** Prefer raw `--ink*/--line*/--accent*` tokens over the bridge aliases (`--text-*`/`--border`/etc.) per UI-SPEC §"Design System" note.

#### 3a. `.hero` + hero text rules (lines 42-71)

```css
.hero { padding: 40px 0 24px; text-align: center; }

.hero-tagline {
    font-family: var(--mono); font-size: 14px; font-weight: 400;
    color: var(--accent); letter-spacing: 2px; text-transform: uppercase;
    margin-bottom: 12px;
}
.hero-headline {
    font-family: Georgia, serif; font-size: 29px; font-weight: 400;
    color: var(--text-primary); margin-bottom: 8px;
}
.hero-date {
    font-family: var(--mono); font-size: 15px; font-weight: 400;
    color: var(--text-secondary); margin-bottom: 28px;
}
```

**Target:** `.hero-tagline` rule is **removed** (markup dropped in 2a). `.hero-headline` → locked `.page-title` (serif `clamp(30px,5vw,46px)`/600, `--ink`); if kept as `.hero-headline`, restyle to match `.page-title`. `.hero-date` → mono 14px/400 `--ink-faint` (UI-SPEC §B metadata line; the off-grid `40px`/`28px`/`12px` paddings → 4px-grid: top `--space-xl` 32px, title→meta `--space-sm` 8px, meta→toggle `--space-md` 16px). Keep `text-align: center` (UI-SPEC §B "centered").

#### 3b. `.mode-toggle` + `.toggle-btn` + `.mode-subtitle` (lines 75-109) → segmented accent pill A1

```css
.mode-toggle {
    display: inline-flex; background: var(--toggle-bg);
    border-radius: 8px; padding: 3px; gap: 2px;
}
.toggle-btn {
    font-family: var(--mono); font-size: 15px; font-weight: 400;
    padding: 8px 20px; border-radius: 6px; border: none;
    background: transparent; color: var(--toggle-inactive);
    cursor: pointer; transition: all 0.3s;
}
.toggle-btn.active {
    background: var(--accent); color: var(--btn-text); font-weight: 700;
}
.mode-subtitle {
    font-family: var(--mono); font-size: 13px; font-weight: 400;
    color: var(--text-hint); letter-spacing: 0.5px; margin-top: 10px;
}
```

**Targets (UI-SPEC §"What This Replaces" rows 2-3 + Component Contract A):**
- `.mode-toggle` (wrapper): `background: var(--surface)`, `border: 1px solid var(--line-strong)`, `border-radius: var(--radius)` (10px, was off-set 8px), `padding: var(--space-xs)` (4px, was off-grid 3px), `gap: 0`.
- `.toggle-btn` (segment): mono **12.5px** (was 15px), `padding: 8px 20px` (Phase 11 literal — kept), `border-radius: var(--radius-btn)` (8px, was 6px). Inactive: `background: transparent`, `color: var(--ink-soft)`, `font-weight: 400`.
- `.toggle-btn.active`: `background: var(--accent)`, `color: #fff`, `font-weight: 600` (was **700** — corrected to 600 per the 2-weight policy).
- `.mode-subtitle` → hint line: mono **11px**/400 (was 13px), `color: var(--ink-faint)`, `margin-top: var(--space-sm)` (8px, was off-grid 10px), **not** uppercased, drop `letter-spacing`. Same `#mode-subtitle` ID preserved (1a/2a).
- NOTE: the mobile `@media` rule at **line 409** (`.toggle-btn { font-size: 14px; padding: 7px 16px; }`) carries an off-grid `7px 16px` — the executor should reconcile this with the new pill (drop the 14px override or re-snap to grid; UI-SPEC §Spacing flags the retired `7px 16px`).

#### 3c. `.article-entry` / `.section-label` / `.entry-title` / `.entry-preview` (lines 121-155) → B1 rows

```css
.article-entry { margin-bottom: 20px; }

.section-label {
    font-family: var(--mono); font-size: 13px; font-weight: 400;
    color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase;
    margin-bottom: 6px;
}
.entry-title {
    font-family: Georgia, serif; font-size: 18px; font-weight: 400;
    color: var(--text-primary); text-decoration: none; display: block;
    margin-bottom: 6px;
}
.entry-title:hover { color: var(--accent); }

.entry-preview {
    font-family: var(--mono); font-size: 15px; font-weight: 400;
    color: var(--text-body); line-height: 1.5;
}
```

**Targets (UI-SPEC §"What This Replaces" rows 4-7 + Component Contract C, the TYPE-01 heart):**
- `.article-entry`: drop `margin-bottom: 20px` (off-grid); use `padding: var(--space-lg) 0` (24px) + `border-bottom: 1px solid var(--line)`; add `.article-entry:last-child { border-bottom: none; }`. **Rows, not cards** — no surface fill, no box border, no row radius.
- `.section-label`: mono **11px**/**600** (was 13px/400), `color: var(--ink-faint)` (was `--accent` — list-row kicker is rationed to `--ink-faint`, UI-SPEC §Color reserved-list point 6), `letter-spacing: .2em`, UPPERCASE kept. `margin-bottom: var(--space-xs)` (4px, kicker→title).
- `.entry-title`: serif **20px/600** (was Georgia 18px/400), `color: var(--ink)`, `letter-spacing: -.01em`, `text-decoration: none`, `display: block`; gap `var(--space-sm)` (8px, title→excerpt). Hover → `--accent-ink` (color only).
- `.entry-preview`: **`var(--serif)` 18px/400/1.5 `--ink-soft`** — migrated FROM `var(--mono)` 15px. **This is success-criterion-3 / TYPE-01 line item #1.**

#### 3d. `article` prose rules (lines 162-270) → serif body + magazine D-05

This whole block is the TYPE-01 migration core. Current state of each rule and its target:

```css
article h2 { font-family: var(--mono); font-size: 15px; font-weight: 700;
    color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase;
    margin-top: 28px; margin-bottom: 12px; }
article h3 { font-family: var(--mono); font-size: 15px; font-weight: 700;
    color: var(--accent); letter-spacing: 1.5px; text-transform: uppercase;
    margin-top: 20px; margin-bottom: 8px; }
article p { font-family: var(--mono); font-size: 15px; color: var(--text-body);
    line-height: 1.5; margin-bottom: 16px; }
article ul, article ol { margin-bottom: 16px; padding-left: 24px;
    font-family: var(--mono); font-size: 15px; color: var(--text-body); line-height: 1.5; }
article li { margin-bottom: 8px; }
article strong { color: var(--text-primary); }
article blockquote { border-left: 3px solid var(--accent); padding: 12px 16px;
    margin: 20px 0; background: var(--blockquote-bg); color: var(--text-body); }
article a { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
article code { padding: 2px 6px; border-radius: 3px; font-size: 0.9em;
    background: var(--code-bg); color: var(--accent); }
article pre { border-radius: 4px; padding: 16px; overflow-x: auto;
    margin: 16px 0; background: var(--pre-bg); }
article pre code { background: transparent; padding: 0; }
article table { width: 100%; border-collapse: collapse; margin: 16px 0;
    font-family: var(--mono); font-size: 15px; }
article th { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border);
    color: var(--accent); font-weight: 700; font-size: 13px;
    letter-spacing: 0.5px; text-transform: uppercase; }
article td { padding: 8px 12px; border-bottom: 0.5px solid var(--border);
    color: var(--text-body); line-height: 1.4; }
article tr:last-child td { border-bottom: none; }
```

**Targets (UI-SPEC TYPE-01 checklist + Component Contract D + Color §):**

| Rule | Current | Target |
|---|---|---|
| `article h2` | mono 15px UPPERCASE **700** `--accent` | serif **24px/600/1.2** `--ink`, no uppercase (single serif heading, TYPE-03) |
| `article h3` | mono 15px UPPERCASE **700** `--accent` | serif **20px/600/1.25** `--ink` (same serif step as list title; only margin differs from h2) |
| `article p` | **mono** 15px | **serif** 18px/400/**1.62** `--ink-soft` (TYPE-01) |
| `article ul, ol` | **mono** 15px | **serif** 18px/400/1.62 `--ink-soft` (TYPE-01) |
| `article li` | inherits mono | serif via the ul/ol rule |
| `article strong` | `--text-primary` | `--ink` (prefer raw token) |
| `article blockquote` | teal-era `--accent` left, `12px 16px`, `--blockquote-bg` | `border-left: 3px solid var(--accent)`, `background: var(--accent-soft)`, `padding: var(--space-md)` (16px), `border-radius: var(--radius-sm)` (7px), serif text `--ink` |
| `article a` | `--accent` underline, offset 2px | `--accent-ink` text, `text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px; text-decoration-color: var(--accent-soft)` at rest → `--accent-ink` on hover (UI-SPEC link treatment) |
| `article code` | radius **3px**, `--accent`, `padding 2px 6px` | mono 14px, `--accent-ink` text, `background: var(--line)`, `padding: 4px 8px` (4px-grid), `border-radius: var(--radius-sm)` (7px) |
| `article pre` | radius **4px**, `--pre-bg` | `background: var(--line)`, `padding: var(--space-md)` (16px), `border-radius: var(--radius)` (10px), `overflow-x: auto` |
| `article pre code` | transparent, no padding | KEEP (no own bg/padding) |
| `article table` | mono 15px | container unchanged; cell fonts change below |
| `article th` | mono 13px UPPERCASE **700** `--accent` | mono is ALLOWED on `th` (label row) — KEEP `var(--mono)` but **600** (not 700), 13px UPPERCASE `--accent-ink` |
| `article td` | **mono** (via table) 15px `--text-body` | **serif** 16px/400 `--ink-soft` (data reads as prose — TYPE-01) |
| `article tr:last-child td` | border-bottom: none | KEEP |

**New rule to ADD (D-05 emphasized lead):** `#newsletter-content > p:first-of-type { font-size: 20px; line-height: 1.45; color: var(--ink); }` (serif, one step up from body; reuses the 20px list-title step at weight 400). No markdown/content change.

**Mono allowed-after-this-phase (do NOT serif-convert):** list/article kicker, metadata/byline/hint lines, toggle segment labels, inline `code`/`pre`, table `th` (header labels). Mono **never** on `article p`/`li`/`td`/`.entry-preview` after this phase.

#### Untouched in style-shared.css

`.container` (20-25), `.mode-transitioning` (29-34), `.content-area` (113-117 — but verify the `border-top`/`padding-top` reads correctly under the relocated header; planner discretion), the entire subscribe section + bottom bar (272-397), and the mobile `@media` block (401-424, except the `.toggle-btn` reconciliation noted in 3b).

---

### FILE 4 — `docker/web/site/style-base.css` (token layer + display classes, READ-ONLY reference)

**Do not modify the `:root` token block or the locked display classes.** This file is the source of truth the executor references. New Newsletter rules MAY be appended here (or in style-shared.css) per planner discretion. Key reference excerpts already verified present:

**Tokens the targets consume (lines 10-66):** `--bg #faf8f5`, `--surface #ffffff`, `--ink #1a1916`, `--ink-soft #55514a`, `--ink-faint #8a857c`, `--line #e7e2da`, `--line-strong #d8d2c7`, `--accent #5b3df5`, `--accent-soft #efeaff`, `--accent-ink #4a2fd6`; serif/mono stacks (49-50); space `--space-xs..3xl` (53-59); radius `--radius:10 / --radius-sm:7 / --radius-btn:8 / --radius-dot:3` (62-65). Bridge aliases (`--text-*`, `--border`, `--toggle-bg`, `--blockquote-bg`, `--code-bg`, `--pre-bg`, etc.) at 30-46 — slated for eventual retirement; prefer raw tokens in new rules.

**Locked display classes to REUSE (do not redefine):**

```css
.page-title {
  font-family:var(--serif); font-size:clamp(30px, 5vw, 46px);
  font-weight:600; line-height:1.12; letter-spacing:-.015em;
}
.eyebrow {
  font-family:var(--mono); font-size:11px; font-weight:600;
  text-transform:uppercase; letter-spacing:.2em; color:var(--accent-ink);
}
```

- `.page-title` → minimal-header title (D-07) AND article display title (D-05).
- `.eyebrow` → article kicker (`--accent-ink`, one accent kicker per reading screen). The **list-row** kicker uses `--ink-faint` instead (rationed accent) — so it is the `.section-label` rule (3c), NOT the `.eyebrow` class, OR `.eyebrow` with a color override.
- `.backlink` (197-212) is the Phase 11 `← Back to Newsletter` control already in `#reader-view` — the magazine header sits under it; **do not restyle.**

---

## Shared Patterns

### Token consumption (applies to FILE 3 + any new FILE 4 rules)
**Source:** `style-base.css :root` (lines 10-66).
**Apply to:** every restyled rule. Use raw `--ink*/--line*/--accent*/--space-*/--radius*` tokens; the bridge aliases (`--text-primary`, `--toggle-bg`, `--blockquote-bg`, etc.) still resolve but are retirement-slated. No literal hexes except where Phase 11 already locked them (white `#fff` on the active segment; the active-tab `#ddd2ff` is Phase-11-only, not used here).

### Defensive null-checks before DOM mutation (applies to FILE 1)
**Source:** `app.js` `showView()` lines 151-159 (`var toggle = document.querySelector(...); if (toggle) ...`).
**Apply to:** any new/edited render code that touches relocated nodes. The established pattern is query-then-`if`-guard; preserve it through the hero/toggle relocation.

### `·` (U+00B7) metadata separator (applies to FILE 1)
**Source:** `app.js` line 175 / 223 (`' · '`).
**Apply to:** the new list-row kicker date (`EDITION #N · {date}`) and the article byline (`Edition #N · {date} · {Technical|Strategic}`). Reuse the exact `' · '` literal — consistent with Phase 11 and the existing hero strings. Surrounding spaces required.

### Mode label resolution (applies to FILE 1 article header)
**Source:** `app.js` `MODES` const (lines 11-26) — `MODES[currentMode].label` yields `'Technical'`/`'Strategic'`; `.subtitle` yields the hint copy.
**Apply to:** the article kicker/byline `{Technical|Strategic}` token and the hint line. Do NOT hardcode the strings — source from `MODES` (Copywriting Contract: "sourced verbatim from `MODES`").

### marked.parse + escapeHtml render idiom (context, unchanged)
**Source:** `renderArticle()` line 230-231 (`marked.parse` → `innerHTML`), `renderList()` line 184 (`escapeHtml(title)`).
**Apply to:** unchanged — the new magazine-header markup the executor prepends to `#newsletter-content` (or emits into `#reader-view`) must `escapeHtml()` any DB-derived string (title, edition_number is numeric) the same way the list rows do. `marked.parse(content)` stays the only escapeHtml-bypass path (existing precedent).

---

## No Analog Found

None. Every surface this phase touches is an in-place restyle of an existing, located implementation. There is no file lacking an analog — the "analog" for each is its own current state, excerpted above. The planner should drive each plan's actions from the current → target pairings here, not from RESEARCH.md generic patterns.

---

## Metadata

**Analog search scope:** `docker/web/site/` (the entire frontend — 4 source files + `style-map.css` which is Phase 13, untouched).
**Files scanned:** 4 read in full (`app.js` 836 lines, `index.html` 121, `style-shared.css` 425, `style-base.css` 249) + 2 planning contracts (12-CONTEXT, 12-UI-SPEC) + 1 inherited contract (11-UI-SPEC).
**Pattern extraction date:** 2026-06-04

---

## PATTERN MAPPING COMPLETE

**Phase:** 12 - newsletter-section-restyle
**Files classified:** 4 (all restyle-in-place; 0 new files)
**Analogs found:** 4 / 4 (each surface = its own current implementation)

### Coverage
- Surfaces with in-place analog (current → target pairing): 4
- Surfaces needing an external analog: 0
- Surfaces with no analog: 0

### Key Patterns Identified
- **Every target value resolves to a Phase 11 `:root` token or a locked display class** (`.page-title`/`.eyebrow`) — no new tokens, no second font, weights 400/600 only.
- **`setMode()` is reused verbatim** — the toggle relocation is purely markup/CSS; the three element IDs (`btn-technical`/`btn-strategic`/`mode-subtitle`) and the `onclick` wiring MUST survive so the dual-mode re-render logic needs zero change.
- **TYPE-01 serif conversion is the load-bearing CSS edit** — `article p`/`ul`/`ol`/`td` and `.entry-preview` migrate `var(--mono)` → `var(--serif)`; mono stays only on kicker/metadata/byline/hint/labels/`code`/`pre`/`th`.
- **DOM-home for the toggle** = scope the existing `.hero` to the `list` route via `showView()` (the article view grows its own magazine header), satisfying TGL-01 without regressing the map/status hero Phase 13 owns.
- **Off-grid/700-weight legacy values are corrected** — `.article-entry` 20px margin → `--space-lg` divided rows; active toggle / h2 / h3 / th drop 700 → 600; code/pre radii 3/4px → the locked 7/10 set; PREVIEW banner amber `#f59e0b` → `--accent-soft` + `--accent` rule.

### Line-Number Drift Found
One correction: the `index.html` `.hero` block is **lines 33–42** (CONTEXT said "~32–42"; line 32 is the `<!-- Hero area -->` comment). All `app.js` function anchors (`:68/:108/:138/:164/:217/:356/:361`, `MODES :11`) verified EXACT.

### File Created
`/root/bitcoin_bot/.planning/phases/12-newsletter-section-restyle/12-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Each plan's action section can cite the current excerpt + target from the per-file pairings above (e.g. "restyle `.entry-preview` style-shared.css:149-155 from `var(--mono)` 15px → `var(--serif)` 18px/400/1.5 `--ink-soft`").
