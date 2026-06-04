# Phase 13: Agent Economy Grid - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 4 modified (no new files) — `app.js`, `style-map.css`, `style-shared.css`/`style-base.css` (target homes), `index.html`
**Analogs found:** 5 / 5 (every Phase 13 change has an already-shipped Phase 12 analog in the same files)

> **The single strongest analog is Phase 12 (newsletter-section-restyle), already merged.** Phase 12 restyled the newsletter list + article views onto the same serif/light Phase 11 design system that Phase 13 must apply to the hub grid + block detail. Every pattern below points at the EXACT, already-merged Phase 12 implementation the executor replicates. **Do not invent new patterns — copy the shipped ones.**
>
> **Critical structural difference from Phase 12:** Phase 12 had no separate dark CSS file to fold — its legacy rules were *already* in `style-shared.css`, so its de-dark was an edit-in-place. Phase 13 has a **separate 348-line `style-map.css`** that is `<link>`ed last in `index.html` (cascade winner). The CSS-disposition decision (delete-and-fold vs lighten-in-place) is therefore a genuinely new planner call this phase — see Shared Pattern §CSS-DISPOSITION.

---

## File Classification

| Modified surface | Role | Data Flow | Closest Analog (already shipped) | Match Quality |
|------------------|------|-----------|----------------------------------|---------------|
| `app.js` `renderHub()` (`:430`) + `renderTile()` (`:447`) | render function (DOM template) | request-response (read blocks → HTML) | `app.js` `renderList()` (`:168`) + list-row template | role-match (list→grid) |
| `app.js` `renderMaturityPill()` (`:391`) | render function (shared component) | transform (enum → dots markup) | itself — reused verbatim, only CSS color source changes | exact (no JS change needed except deferred flag) |
| `app.js` `renderBlock()` (`:540`) | render function (DOM template) | request-response (read block+body+timeline → HTML) | `app.js` `renderArticle()` (`:221`) — the Phase 12 magazine reader | exact (article ↔ block reading view) |
| `app.js` `renderStatus()` (`:672`) | render function (DOM template) | request-response | `renderHub()`/`renderList()` (sibling tier-grouped renderer) | role-match |
| `style-map.css` (348 lines) | CSS layer (legacy dark theme) | n/a | Phase 12 in-place migration of `article`/`.article-entry` prose in `style-shared.css` (commit `4cf4a78`) | role-match (de-dark migration) |
| `index.html` `#map-view`/`#block-view`/`#status-view` | markup container | n/a | already-correct Phase 11 markup; cascade-order control (line 10-12) | exact (no markup change expected) |

---

## Pattern Assignments

### `app.js` `renderHub()` + `renderTile()` (render function, request-response) — MAP-01..04

**Analog:** `app.js` `renderList()` (`:168`) — the Phase 12 newsletter list renderer + its `.article-entry` row template, paired with `style-shared.css` `.article-entry` / `.section-label` / `.entry-title` / `.entry-preview` rules (`:139`–`:179`).

**Current `renderTile()` markup the executor restyles** (`app.js:447`–`453`):
```javascript
function renderTile(b) {
    return '<a href="#/map/' + encodeURIComponent(b.slug) + '" data-accent="' + escapeHtml(b.accent) + '" class="block-tile">' +
               '<h3 class="tile-title">' + escapeHtml(b.title) + '</h3>' +
               '<p class="tile-subtitle">' + escapeHtml(b.subtitle) + '</p>' +
               renderMaturityPill(b) +
           '</a>';
}
```
- **Whole-anchor click target preserved** (`<a class="block-tile">` is the link) — CLAUDE.md convention, D-14. Keep this exactly when it becomes `.card`.
- **`data-accent="..."` attribute is RETIRED** (D-05): the per-tier cascade machinery dies with the dark theme. The executor SHOULD drop the `data-accent` attribute from the emitted markup (it is dead once `style-map.css`'s `[data-accent]` selectors are gone). Removing it is the cleanest expression of D-05; keeping it inert is acceptable but pointless.
- **DEFERRED branch is NEW logic** (MAP-04, D-04): `renderTile()` must branch on `!b.current_body_version_id`. The query already selects `current_body_version_id` (`loadHub` `:415`). Add a `deferred` flag → emit the full-width modifier (`.card-deferred` / `grid-column:1/-1`), the `· DEFERRED` mono tag, and pass the flag down so the pill renders empty (see next pattern). **Do NOT add a `.eq('status',…)` filter** — the deferred state is derived in JS from a column already in the result set (CLAUDE.md / D-17: RLS is the boundary).

**Closest shipped row template to copy structure from — `renderList()`'s `.article-entry`** (`app.js:186`–`190`):
```javascript
return '<div class="article-entry">' +
    '<div class="section-label">EDITION #' + n.edition_number + ' · ' + formatDate(n.published_at) + '</div>' +
    '<a href="#/edition/' + n.edition_number + '" class="entry-title">' + escapeHtml(title) + '</a>' +
    '<p class="entry-preview">' + escapeHtml(excerpt) + '</p>' +
    '</div>';
```
Mirror this discipline: every DB string `escapeHtml`'d, the section-label/title/desc role split, the mono `·` (U+00B7) metadata separator. The hub card is the same idea — serif 20px/600 title (`.entry-title` is already exactly that), serif 18px/400 `--ink-soft` description (`.entry-preview` is exactly that). **The `.entry-title` (`style-shared.css:158`) and `.entry-preview` (`:173`) rules ARE the target type for `.tile-title` / `.tile-subtitle`** — copy their property blocks verbatim into the card rules.

**Grid wrapper is NEW** (MAP-01/03): `renderHub()`'s `tierSection()` (`app.js:462`) currently joins tiles directly under `<section class="tier-section">`. Add a grid container (`display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:8px`) — planner discretion on `.tier-section{display:grid}` vs a child `.grid` div (UI-SPEC §2). The `<h2 class="tier-label">` label must sit ABOVE the grid, not inside it. MAP-03 grouping is **already satisfied structurally** — do not re-derive it.

**Hub header is NEW in-content markup** (D-06): today `renderHub()` calls `updateHero(HUB_STORYLINE, dateText)` (`:436`) writing to the shared `.hero`, but Phase 12 scoped `.hero` to the **list route only** in `showView()` (`app.js:162`–`163` — `hero.style.display = viewName === 'list' ? 'block' : 'none'`). So the hub header is now invisible via `updateHero()`. The executor must render the header **inside `#map-view .content-area`** as the first elements `renderHub()` writes. Reuse the Phase 11 `.page-title` class (`style-base.css:82`) for "The Agent Economy", a mono sub-line (14px/400 `--ink-faint`) for the optional "updated {date}" (the `latest`/`dateText` computation at `app.js:434`–`435` already exists — reuse it; omit the stamp entirely when all null), then the existing `HUB_STORYLINE` `<div class="hub-storyline">` (`app.js:473`).

> **Orphan-class note:** `.hub-storyline` (emitted at `app.js:473`) has **NO CSS rule anywhere** (confirmed: absent from `style-shared.css`, `style-base.css`, and `style-map.css`). It renders as unstyled body text today. Phase 13 must add a rule for it: serif 18px/400 `--ink-soft`, line-height 1.55 (UI-SPEC). This is a real gap, not a restyle.

**Hub empty-state to restyle** (`app.js:421`): `Map data unavailable.` is inline-styled with the retired `var(--text-secondary)` alias. Restyle into serif `--ink-soft` (copy unchanged).

---

### `app.js` `renderMaturityPill()` (shared component, transform) — MAP-02, MAP-04

**Analog:** itself — reused verbatim across hub + block + status (it already is the single source of truth, `app.js:391`). **No structural JS change** except the DEFERRED override.

**Current** (`app.js:391`–`396`):
```javascript
function renderMaturityPill(b) {
    var stage = MATURITY_STAGE[b.maturity] || 1;
    return '<div class="maturity-pill" data-accent="' + escapeHtml(b.accent) + '" data-stage="' + stage + '" aria-label="Maturity: ' + escapeHtml(b.maturity) + ' (' + stage + ' of 5)">' +
               '<span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span>' +
           '</div>';
}
```

**Changes (all driven by UI-SPEC §4, D-05):**
- **Drop `data-accent`** from the emitted markup (the cascade it fed is retired). The pill no longer needs a per-tier color source.
- **DEFERRED override (NEW):** accept a deferred flag (e.g. `renderMaturityPill(b, deferred)`); when set, emit `data-stage="0"` and `aria-label="Maturity: deferred (not yet synthesized)"`. `data-stage="0"` matches none of the `[data-stage="1".."5"]` fill selectors → all 5 segs fall through to the empty default (correct by construction — UI-SPEC §Color "empty dots").
- **CSS-only changes (in `style-map.css` `.maturity-pill .seg`, `:61`–`:75`):** empty seg `background: transparent` → `--line-strong`; fill `var(--accent-tier)` → `var(--accent)`; `border-radius: 2px` → `3px` (`--radius-dot`); remove the dark `border: 1px solid var(--border)` (or set to `--line-strong`). **Delete the entire `body.technical|strategic [data-accent]{--accent-tier:…}` cascade** (`style-map.css:33`–`43`) and the `:root` per-tier hexes (`:18`–`31`).

This pill is consumed by `renderHub`→`renderTile` (`:451`), `renderBlock`→`headerHtml` (`:547`), and `renderStatus`→`renderStatusRow` (`:687`) — one CSS edit recolors all three views.

---

### `app.js` `renderBlock()` (render function, request-response) — D-03 (restrained system pass)

**Analog (the strongest in the phase):** `app.js` `renderArticle()` (`:221`) — the Phase 12 magazine reader — paired with the Phase 12 `article p/ul/ol/li/h2/h3/a/code/blockquote` prose rules in `style-shared.css` (`:190`–`:342`, commit `4cf4a78` "migrate article prose to serif").

**The exact TYPE-01 serif-prose migration to replicate — Phase 12's `article p`** (`style-shared.css:210`–`217`):
```css
article p {
    font-family: var(--serif);
    font-size: 18px;
    font-weight: 400;
    color: var(--ink-soft);
    line-height: 1.62;
    margin-bottom: 16px;
}
```
The block-body's prose (`.block-body p/ul/ol/li`) must land on this **identical** rule set (D-03). Today `.block-body p` (`style-map.css:275`) inherits dark Georgia/Courier via the legacy file; the migration is mono/Georgia → `var(--serif)` 18px/1.62 `--ink-soft`. **Mechanism:** because `marked.parse()` output is wrapped in `<section class="block-body">` (NOT `<article>`), the existing `article p` rules do NOT reach it. The executor either (a) scopes new `.block-body p/ul/ol/li/h2` rules mirroring the `article` block, or (b) adds `.block-body` to the `article p` selector list. **Planner discretion** — option (a) keeps the magazine layer Newsletter-only (D-03 "no second magazine treatment"), which is the intent.

**In-content H2 — copy Phase 12's `article h2`** (`style-shared.css:190`–`198`): serif 24px/600/1.2. Replaces the current `.block-body h2` Georgia 21px (`style-map.css:269`).

**In-content links — copy Phase 12's `article a`** (`style-shared.css:276`–`286`): `--accent-ink` underline. The block body's markdown anchors reuse this exactly.

**Current `renderBlock()` 4-part structure to KEEP (restyle, not redesign)** (`app.js:540`–`582`): header (`<header class="block-header" data-accent=…>` + `<h1>` + pill) → tension (`<section class="block-tension">`, gated against `LIVE_TENSION_PLACEHOLDER` at `:553`) → body (`<section class="block-body">` + `marked.parse`) → Evolution (`<section class="evolution">`). **Markup stays; only the CSS de-darkens** (and `data-accent` on `.block-header` `:545` becomes dead → drop it). The `live_tension` placeholder gate (`:553`) is KEPT verbatim — tension hidden on all 7 blocks today.

**Header H1:** restyle to serif **24px/600** (Phase 11 heading step — UI-SPEC: reads *smaller* than the hub `.page-title` display hero, so the reading-view title does not compete with the section hero). Replaces the inherited dark Georgia 29px.

**Tension card:** light surface + 3px `--accent` left stripe + serif italic 18px/1.6 — the closest shipped analog is Phase 12's `article blockquote` (`style-shared.css:266`–`274`, `border-left:3px solid var(--accent)` + `--accent-soft` bg + serif). Copy its stripe/surface treatment.

**Evolution "Show all" button** (`.timeline-show-all`, `style-map.css:300`): de-dark to mono 12.5px, `--radius-btn` (8px, from `4px`), `--line` border, `--accent-ink` text, `--surface` hover (replacing `rgba(255,255,255,.02)`). Closest shipped button-chrome analog: the `.backlink`/`.tab` mono chrome in `style-base.css` (`:153`, `:197`) and the de-darkened `--surface`/`--line` pattern throughout Phase 11.

**Empty timeline state** (`renderTimelineEntries`, `app.js:591`): `No timeline entries yet.` inline-styled `var(--text-secondary)` → restyle to `--ink-soft` serif (copy unchanged).

---

### `app.js` `renderStatus()` (render function, request-response) — D-02 (light de-dark pass only)

**Analog:** `renderHub()`/`renderList()` — `renderStatus()` (`:672`) is the sibling tier-grouped renderer (identical `tierSection()` helper, `:697`). **No layout redesign** — strip dark/Courier/per-tier only.

**Current `renderStatusRow()` markup to keep** (`app.js:682`–`692`): keeps flex layout, `data-accent` (now dead → drop). CSS de-dark in `style-map.css` `.status-row`/`.status-*` (`:321`–`:348`):
- `.status-row` stripe `var(--accent-tier)` → `var(--accent)`; row sits on `--bg`; keep `12px 20px 12px 24px` padding + 3px left stripe.
- `.status-title` Georgia 17px → serif **18px/400 `--ink`** (body step).
- `.status-subtitle` `'Courier New' 14px` → serif **18px/400 `--ink-soft`** (TYPE-01 — descriptive prose becomes serif).
- `.status-synth` `'Courier New' 13px` → mono **14px `--ink-faint`** (metadata stays mono chrome — lands on the locked 14px mono step).
- `.tier-label` shared with the hub — change once, both benefit (UI-SPEC §7).

The `.status-title` target is the same property pattern as Phase 12's `article p`/`.entry-preview` serif body. Status empty-state (`app.js:652`, `Status data unavailable.`) restyled, copy unchanged.

---

## Shared Patterns

### CSS-DISPOSITION (the one genuinely new planner decision)

**Source contrast:** Phase 12 had its legacy rules *inside* `style-shared.css` and migrated them in-place (commits `4cf4a78`, `abedebb`, `2c5ab6a` — all single-file `style-shared.css` edits, no file added/deleted). Phase 13 has a **separate `style-map.css`** (`index.html:12`, loaded LAST → highest-precedence among the three `<link>`s).

**Apply to:** the whole `style-map.css` file (348 lines).

**Cascade-order control** (`index.html:10`–`12`):
```html
<link rel="stylesheet" href="/style-base.css">    <!-- :root tokens + .page-title/.eyebrow + nav, loaded FIRST -->
<link rel="stylesheet" href="/style-shared.css">  <!-- Phase 12 newsletter list + article prose -->
<link rel="stylesheet" href="/style-map.css">     <!-- the dark theme to retire, loaded LAST -->
```
Two mechanical options (UI-SPEC "What This Replaces" — planner discretion):
1. **Delete-and-fold:** move the de-darkened map/block/status rules into `style-shared.css` (joining the newsletter rules), delete `style-map.css`, drop the `<link>` at `index.html:12`. Cleanest end-state; matches the Phase 12 "all component rules live in style-shared.css" topology.
2. **Lighten-in-place:** rewrite `style-map.css` rules onto the light tokens, keep the file + `<link>`. Lower-risk diff, but leaves a vestigial "map" file whose name no longer means "dark theme."

**Hard requirements either way:** nothing dark, no `'Courier New'`, no `Georgia` literal, no per-tier hex (`--accent-teal-*` etc.), no `[data-accent]`/`--accent-tier` cascade survives. The retired `--accent-teal-base` etc. (`:18`–`31`) and the `body.technical|strategic [data-accent]` cascade (`:33`–`43`) are DELETED, not lightened. **Hand-authored CSS, no build step** (CLAUDE.md) — disposition is purely which file the lightened rules land in.

### Token Inheritance (do NOT re-define)

**Source:** `style-base.css` `:root` (`:10`–`66`).
**Apply to:** every Phase 13 rule.

All tokens already exist: `--bg #faf8f5`, `--surface #fff`, `--ink #1a1916`, `--ink-soft #55514a`, `--ink-faint #8a857c`, `--line #e7e2da`, `--line-strong #d8d2c7`, `--accent #5b3df5`, `--accent-ink #4a2fd6`, `--serif`, `--mono`, `--space-* (4px grid)`, `--radius / -sm / -btn / -dot (10/7/8/3)`. Phase 13 **consumes** these — declares no new tokens. The legacy aliases (`--text-secondary` etc., `style-base.css:30`–`46`) that the current inline empty-states reference are already bridged onto the light palette, so an un-restyled inline `var(--text-secondary)` will not look dark — but the empty-states should still migrate to the canonical `--ink-soft` per the copy contract.

### Single-Accent / Per-Tier Retirement (COLOR-02, D-05)

**Source:** Phase 11 COLOR-02 lock + the 4-item accent reservation list in `13-UI-SPEC.md` §Color.
**Apply to:** card left-borders (3px `--accent`, → `--accent-ink` on hover), filled progress dots (`--accent`), in-content links (`--accent-ink`). **Never** a second hue; **never** per-tier color. The `data-accent` attribute is dropped from `renderTile`/`renderBlock`/`renderStatusRow` markup; the `[data-accent]`/`--accent-tier` cascade is deleted from CSS. Tiers are distinguished ONLY by their mono `.tier-label`.

### Serif-Prose Migration (TYPE-01)

**Source:** Phase 12 `article p/ul/ol/li/h2/h3/a` rules (`style-shared.css:190`–`342`, commit `4cf4a78`).
**Apply to:** block-body markdown prose (D-03). Serif 18px/1.62 body, serif 24px/600 H2, `--accent-ink` links. Mono survives ONLY on chrome/labels/metadata/code (`.tier-label`, `.status-synth`, `source ↗`, `· DEFERRED` tag, "EVOLUTION" heading, "Show all" button). No monospace body paragraphs anywhere (CLAUDE.md / TYPE-01).

### Minimal-Header Pattern (D-06, mirrors Phase 12 D-07)

**Source:** Phase 12 `.hero`/`.hero-headline`/`.hero-date` (`style-shared.css:47`–`68`) + the `.page-title`/`.eyebrow` base classes (`style-base.css:82`–`97`) + the `showView()` list-scoping (`app.js:162`).
**Apply to:** the hub header. Because Phase 12 scoped `.hero` to the list route, the hub renders its OWN header inside `#map-view .content-area` (NOT via `updateHero()`). Reuse `.page-title` verbatim; the mono sub-line copies the `.hero-date` treatment (14px/400 `--ink-faint`). This is the exact list↔hub mirror the orchestrator flagged.

### Security Invariants (preserve — do not regress)

**Source:** existing `app.js` comments (CR-01 `safeHttpUrl` `:364`; D-16/D-17 RLS-is-the-boundary `:411`, `:491`).
**Apply to:** all four render functions. Keep `escapeHtml()` on every DB string; keep `safeHttpUrl()` gating on timeline `source_url`; the `marked.parse()` body path stays the sole escape-bypass (precedent: `renderArticle` `:250`). **Never add `.eq('status',…)` / defensive status filters** to the `economy_map` queries — RLS is the boundary (CLAUDE.md). DEFERRED is derived in JS from `current_body_version_id`, not a filter.

---

## No Analog Found

| Surface | Role | Data Flow | Reason |
|---------|------|-----------|--------|
| 2-column CSS grid (`display:grid;repeat(2,1fr)`) + `grid-column:1/-1` full-width DEFERRED + `@media(max-width:640px){1fr}` | CSS layout | n/a | No existing grid in the codebase — every current list (newsletter `.article-entry`, map `.block-tile`) is a vertical stack. **Use the mockup's `.grid`/`.card.span2` mechanism as intent** (`.planning/docs/agentpulse-redesign-mockup.html`, cited in CONTEXT §canonical_refs) — NOT copied class names. This is the one structurally-novel piece; everything else has a shipped analog. |
| `.hub-storyline` CSS rule | CSS | n/a | Class is emitted (`app.js:473`) but **has no rule anywhere** — renders as plain body text today. New rule needed (serif 18px/400 `--ink-soft`, 1.55), not a restyle. |
| `· DEFERRED` tag + full-width card variant | CSS + JS branch | n/a | Brand-new MAP-04 affordance. Mono 11px/600 UPPERCASE `--ink-faint` chrome (closest type analog: `.section-label`, `style-shared.css:148`); the full-width mechanism has no codebase precedent (mockup intent). |

---

## Metadata

**Analog search scope:** `docker/web/site/` (app.js, index.html, style-base.css, style-shared.css, style-map.css); git log for Phase 12 commits.
**Files scanned:** 5 source files + git history (Phase 12 commit range `f5389b2`..`45a56b5`).
**Key finding:** Phase 12 is a near-perfect template — list↔hub and article↔block-detail map 1:1, and the serif-prose / minimal-header / single-accent patterns are already merged in `style-shared.css`/`style-base.css`. The two genuinely-new pieces are the **CSS grid layout** (no codebase precedent → mockup intent) and the **`style-map.css` disposition** (Phase 12 had no separate dark file → new planner call).
**Pattern extraction date:** 2026-06-04
