# Phase 20: Width Tokens & Centering Foundation - Research

**Researched:** 2026-06-10
**Domain:** Frontend CSS layout (hand-authored, no build step) — width tokens, centering, color tokenization, section rhythm for the AgentPulse web SPA
**Confidence:** HIGH (whole surface is local, statically traceable; every claim below carries file:line evidence)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Adopt mockup/brief width values verbatim: `--measure: 64ch` (prose), `--wide: 1080px` (wide container), `--gutter: clamp(1.25rem, 5vw, 3.5rem)` (responsive side padding via `padding-inline`). These REPLACE the current single `.container { max-width:720px }`. Class shape from the brief: `.prose { max-width:var(--measure); margin-inline:auto; padding-inline:var(--gutter) }` and a wide container (`max-width:var(--wide); margin-inline:auto; padding-inline:var(--gutter)`). **Reconcile naming to `--wide` / `.wide`** (preferred — shorter, matches mockup's emitted markup), NOT the brief's `--container-wide` / `.container-wide`.
- **D-02:** The sticky nav widens to `--wide` (1080px) so brand/tabs align to the same left/right edges as the wide content below — ONE centered axis. Matches mockup's `<nav class="nav wide">`. Nav is currently `max-width:880px` in `style-base.css:125`.
- **D-03:** Follow the brief's explicit map: edition body + the "What is AgentPulse" intro → `--measure` (prose); newsletter list, Agent Economy map, Signals, agent-card grid → `--wide`. On article pages prose stays narrow but centered.
- **D-04:** Boundary bands (hero headline/date/mode-toggle, edition-page header/metadata) default to: reading copy (hero subtitle, edition header text) in prose width; the band sits on the wide centered axis. Researcher/planner resolves exact hero/header treatment — keep it centered, never left-pinned.
- **D-05:** Full-strength rule (`--line-strong`-weight, 1px) between MAJOR route sections; `0.5px` hairline (`--line`) for WITHIN-section separations. Researcher maps "major vs within" per route. Applied site-wide but owned + verified HERE.
- **D-06:** VERIFY-FIRST. The current `.container` is already `max-width:720px; margin:0 auto` (centered), so the "pinned center-left" gutter cause is NOT the obvious one and must be pinpointed before the fix is applied — likely route-specific. Research MUST identify the actual left-pin site and confirm it, then apply `.prose`/`.wide` there. (Phase-19 lesson: do not assume the cause; reproduce it.)

### Claude's Discretion
- Exact CSS class names and where the two wrappers are applied in `app.js` (per-route class application) — planner decides, honoring D-01..D-06.
- Whether to retire the legacy `.container` (720px) entirely or repurpose it as `.prose`.
- The single stray hardcoded `#fff` (`style-shared.css:100`, `color:#fff`) and the nav's `color:#fff` — tokenize or leave as intentional on-accent white per RHYTHM-01 judgment.

### Deferred Ideas (OUT OF SCOPE)
None new from this discussion. Per-route visual fixes (Phase 21), excerpts (Phase 22), Signals feed itself (Phase 23), responsive/a11y pass (Phase 24 — RESP-01/A11Y-01 owned there). Single-page-scroll landing (WIDTH-F1) deferred — separate routes are locked.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WIDTH-01 | Two coexisting, both-centered max-widths: narrow prose (`--measure`, ~60–70 char) for copy + wider container (`--wide`) for tiled content. No dead left gutter on wide viewports. | D-06 root cause traced (single `.container` 720px wraps ALL routes incl. the wide map grid → §"D-06 Root Cause"). Token + class plan + per-route apply-map in §"WIDTH-01 Plan". |
| RHYTHM-01 | Token-only color (no hardcoded hex on loaded routes) + section-rhythm hierarchy (1px `--line-strong` between major sections, 0.5px `--line` within). Verified holistically HERE. | Exhaustive color audit (§"RHYTHM-01 Color Audit"): only 3 literal-color sites on loaded routes, all on-accent white. Section-rhythm map per route in §"D-05 Section Rhythm". |
</phase_requirements>

## Summary

This is a pure CSS/layout phase against a fully local, statically-traceable surface: `docker/web/site/` (`index.html`, `style-base.css`, `style-shared.css`, `app.js`). No build step (the web Dockerfile just `COPY site/ /srv/` — `docker/web/Dockerfile`), no framework, no package install. The only deploy-time mutation is the Supabase URL/key `sed` substitution in `entrypoint.sh:3-4` — confirming the "prod differs from repo only by substitution" claim. **Because nothing is installed, there is no Package Legitimacy Audit, no Environment Availability audit, and no Validation Architecture section (Nyquist disabled for this run).**

**D-06 is fully solved by static trace, and the cause is exactly what the operator suspected — NOT the obvious one.** The `.container` rule (`style-shared.css:20-25`) IS centered (`margin:0 auto`), so it is not the left-pin culprit by itself. The real defect: in `index.html:30`, a SINGLE `<div class="container">` (max-width **720px**) wraps the hero AND `<main>` AND every route's content-area — including the Agent Economy map's 3-tier card grid. So the wide tiled surfaces are crammed into a 720px column and then centered, leaving a large empty band on BOTH sides on a wide monitor (visually read as a "dead left gutter"). There is no route-specific width override fighting the container — the container itself is the single constraining axis for everything. The fix is structural: split that one 720px wrapper into a narrow `.prose` axis (reading copy) and a wide `.wide` axis (tiled content), both centered, applied per-route.

**RHYTHM-01 is nearly already satisfied.** An exhaustive grep of every loaded file found only THREE hardcoded color literals that render on live routes, and all three are intentional on-accent white text: `style-base.css:36` (`--btn-text:#fff`, a token value), `style-base.css:190` (`.subscribe color:#fff`), and `style-shared.css:100` (`.toggle-btn.active color:#fff`). Every other color flows from the `:root` token system. Two non-color literals exist (`style-base.css:114` translucent header bg `rgba(250,248,245,.86)`, `style-base.css:178` active-tab border `#ddd2ff`) — both are documented locked UI-SPEC literals, out of RHYTHM-01's "surface color" scope. The section-rhythm hierarchy mostly exists (0.5px hairlines already at `style-shared.css:132/730/747/844`) and just needs a consistent "1px `--line-strong` between major sections" rule established.

**Primary recommendation:** Add the three width tokens to `style-base.css :root`, add `.prose` + `.wide` class definitions there, widen the nav from 880px → `--wide`, restructure `index.html` so the nav and each route-view carry the right wrapper class, and apply `.prose`/`.wide` to the JS-emitted innerHTML wrappers in `app.js`. Retire the legacy `.container` (720px) by repurposing it — see the explicit retire-vs-keep recommendation below. Establish a single `section + section`-style major-rule and keep the existing 0.5px hairlines for within-section rows. The color audit is already green except for the three intentional on-accent whites — recommend leaving them (they are correct, accessible white-on-violet).

## Architectural Responsibility Map

This is a single-tier (browser/static) phase, but the *capabilities within the front end* still map to two clear owners — the **CSS token/class layer** (where the foundation lives) and the **JS render layer** (where per-route classes get applied to dynamic innerHTML). Getting this split right is the core of the apply-map.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Width tokens (`--measure`/`--wide`/`--gutter`) | CSS `:root` (style-base.css) | — | Tokens are the single source; they belong with the existing color/spacing tokens in `style-base.css:10-66`, which loads FIRST and wins the cascade. |
| `.prose` / `.wide` class definitions | CSS (style-base.css) | — | Reusable display classes belong beside the existing display classes (`.page-title`, `.eyebrow`) in style-base.css. |
| Static-markup wrapper application (nav, hero, about, route shells) | HTML (index.html) | — | The 5 route-view `.content-area` divs + hero + nav are static in `index.html:13-118`; their wrapper class is set here, not in JS. |
| Dynamic innerHTML wrapper application (list rows, map grid, article body) | JS render layer (app.js) | CSS | The content INSIDE each `.content-area` is emitted by `renderList`/`renderHub`/`renderArticle`/`renderBlock`/`renderStatus`. Whether prose-vs-wide is achieved by the static `.content-area` class or by an inner wrapper the renderer emits is the key design decision (see §"WIDTH-01 Plan, app.js"). |
| Color tokenization (RHYTHM-01) | CSS (both files) | JS inline styles | Color lives in CSS; the only JS color refs are already token-based (`var(--ink-soft)` etc. — app.js:281/337/499/702/827/888). No JS literal colors to fix. |
| Section rhythm rules (D-05) | CSS (both files) | — | Border/separator rules are CSS-only; no JS involvement. |

## Standard Stack

**No external packages. No installs. No build.** This phase edits four hand-authored files in `docker/web/site/`. The only runtime dependencies are the two already-loaded CDN scripts (`@supabase/supabase-js@2`, `marked.min.js` — `index.html:146-147`), neither of which this phase touches.

| "Library" | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Native CSS custom properties (`var()`) | CSS Custom Properties Level 1 (universally supported) | Width tokens, color tokens | Already the project's established token system (`style-base.css:10-66`). [CITED: project CLAUDE.md "Single hand-authored CSS, no build step"] |
| `margin-inline` / `padding-inline` (CSS Logical Properties) | Widely supported (Chrome 87+, Safari 14.1+, Firefox 66+, all evergreen) | Centering + symmetric gutters in one declaration | The brief + mockup both use them (`agentpulse-redesign (1).html:47`). Equivalent to `margin-left/right:auto` + `padding-left/right`. [VERIFIED: mockup `.wide`/`.prose` definitions, agentpulse-redesign (1).html:46-48] [CITED: MDN — logical properties are baseline-widely-available] |
| `clamp()` | Universally supported | Responsive `--gutter` | Already used in the codebase (`style-base.css:83` `.page-title font-size:clamp(...)`). [VERIFIED: style-base.css:83] |
| `ch` unit | Universally supported | `--measure: 64ch` readable line length | Already used in the codebase (`.about-lede max-width:60ch`, style-base.css:249). [VERIFIED: style-base.css:249] |

**Installation:** None. No `npm install`, no `pip install`, no `cargo`. Edit files; rebuild the `web` service via scoped compose (orchestrator-owned, see Deploy section).

### Package Legitimacy Audit

**Not applicable.** This phase installs zero external packages. No registry interaction, no `package.json` change, no postinstall scripts. The two CDN `<script>` tags already present in `index.html` are unchanged by this phase.

## Architecture Patterns

### System Architecture Diagram (the centering data-flow, current vs target)

```
CURRENT (the dead-gutter defect):

  <body>
    └─ <header><nav class="nav"> ........ max-width:880px; margin:0 auto   (centered, narrower axis)
    └─ <div class="container"> .......... max-width:720px; margin:0 auto   ◄── THE SINGLE CONSTRAINT
         ├─ .hero (toggle/headline) ....... inherits 720px
         └─ <main>
              ├─ #list-view  .content-area .......... 720px  ◄ list crammed
              ├─ #reader-view .content-area #article  720px  ◄ prose OK-ish but pinned to 720
              ├─ #map-view   .content-area .grid ..... 720px  ◄ WIDE GRID crammed into 720 → big side bands
              ├─ #block-view .content-area #block ..... 720px
              ├─ #status-view .content-area ........... 720px
              └─ #about-view .content-area ............ 720px
         └─ #subscribe-section / footer ............... 720px

  Result on a 1440px monitor: ~720px column centered → ~360px empty on EACH side.
  Two different axes (nav 880 vs body 720) make the chrome and content edges NOT line up.


TARGET (two centered axes):

  <body>
    └─ <header><nav class="nav wide"> ... max-width:1080px (--wide); margin-inline:auto  ◄ same axis as content
    └─ <main>  (the single .container 720px wrapper is RETIRED / repurposed)
         ├─ list  → .wide   (rows on 1080 axis)            ┐
         ├─ map   → .wide   (3-tier card grid on 1080)     ├ tiled surfaces, WIDE centered
         ├─ status→ .wide                                  ┘
         ├─ reader→ .wide band, inner .prose (64ch) body   ┐
         ├─ block → .wide band, inner .prose body          ├ reading copy, NARROW centered, on wide axis
         └─ about → .wide band, inner .prose intro + .wide agent grid ┘
         └─ hero  → .wide band, prose-width headline/toggle, centered

  Result: nav edges == content edges (one axis); wide grids fill 1080; prose stays 64ch but centered.
```

The reader can trace: a request enters at `index.html` → `app.js route()` dispatches by hash → a `loadX()` fetches → a `renderX()` writes innerHTML into the route's `.content-area`. The width axis is decided by which wrapper class wraps that `.content-area` (or its inner content). Today they all inherit the one 720px `.container`; the fix gives each route the correct axis.

### Recommended Structure (where each change lands)

```
docker/web/site/
├── style-base.css        # ADD: --measure/--wide/--gutter to :root (~after line 66)
│                         # ADD: .prose + .wide class defs (~near .page-title, line 79-97)
│                         # EDIT: .nav max-width 880px → var(--wide)  (line 125)
├── style-shared.css      # EDIT/RETIRE: .container (line 20-25) — repurpose as .prose OR remove
│                         # ADD: major-section rule (`--line-strong` 1px) where D-05 maps it
│                         # (color audit: NO literal-color fixes required — see audit)
├── index.html            # EDIT: <nav class="nav"> → <nav class="nav wide">  (line 16)
│                         # EDIT: restructure the single .container wrapper (line 30) →
│                         #       per-route .wide / .prose wrappers (lines 30-144)
└── app.js                # EDIT (if inner-wrapper approach): renderHub/renderArticle/renderBlock
                          # emit .prose around reading copy; .wide stays on the static shell.
                          # NO color changes (all JS inline styles already token-based).
```

### Pattern 1: Wide band + inner prose (the mockup's centering idiom)

**What:** A full-width-axis section gets `.wide` (centers the 1080 band + applies gutters); reading copy INSIDE it gets `.prose` (caps the line length at 64ch). The mockup does exactly this.
**When to use:** Any route that mixes wide tiled content with narrow reading copy — the map (prose intro + wide grid), about (prose intro + wide agent grid), reader/block (prose body, optionally on a wide band).
**Example:**
```html
<!-- Source: agentpulse-redesign (1).html:363-368 (mockup, INTENT only — do not lift markup) -->
<section id="map" class="wide">      <!-- centers 1080 band + gutters -->
  <div class="prose">                <!-- caps the eyebrow/title/lede to 64ch -->
    <p class="eyebrow">The map</p>
    <h2 class="section-title">The agent economy</h2>
    <p class="lede">Capability is solved...</p>
  </div>
  <div class="map-grid">...</div>    <!-- spans the full 1080 wide band -->
</section>
```
Note the mockup's `.prose` is JUST `max-width: var(--measure)` (no auto-margin) because it sits inside a `.wide` that already establishes the centered axis (`agentpulse-redesign (1).html:48`). The brief's `.prose` is the standalone form WITH `margin-inline:auto; padding-inline:var(--gutter)` (`REDESIGN_CC_BRIEF.md:81`). **Decide which `.prose` you need per usage:** standalone prose page (reader/block, where there is no `.wide` parent) needs the brief's full form; prose-inside-wide (map/about intro) needs only the `max-width`. Recommend defining `.prose` as the **standalone full form** (`max-width:var(--measure); margin-inline:auto; padding-inline:var(--gutter)`) and, where prose sits inside a `.wide` that already pads, the double padding is acceptable (it just narrows the prose slightly) OR add a scoped `.wide > .prose { padding-inline:0 }` reset. The planner should pick one; the simplest robust choice is the brief's full `.prose` everywhere and accept that a `.prose` nested in `.wide` is centered within the wide band.

### Pattern 2: One centered axis for chrome + content (D-02)

**What:** Nav and content share the same `--wide` max-width so their left/right edges align.
**When to use:** Always — it is the whole point of D-02.
**Example:**
```css
/* Source: style-base.css:120-127 (current) — change ONE line */
.nav {
  display:flex; align-items:center; gap:var(--space-md);
  padding:12px var(--space-lg);
  max-width:var(--wide);   /* was 880px — D-02 */
  margin:0 auto;
}
```
Keep `margin:0 auto` (equivalent to `margin-inline:auto`). The nav already centers; only the cap changes. **Do NOT** touch the `body > header` sticky rule (`style-base.css:111-118`) — see Pitfall 1.

### Anti-Patterns to Avoid
- **Re-introducing a `body.technical`/`body.strategic` palette block:** explicitly forbidden — it would override `:root` by specificity (`style-shared.css:6-9`). The `body` class is render-selector-only now (app.js:149-153 comment).
- **Putting width tokens in `style-shared.css`:** they must go in `style-base.css :root` so they load FIRST and are available to both files (style-base loads before style-shared — `index.html:10-11`).
- **Using a bare `header` selector:** the `body > header` scoping is load-bearing (maturity-overlap fix). See Pitfall 1.
- **Lifting the mockup's single-scroll markup:** the mockup is one scrolling page with IntersectionObserver scroll-spy (`agentpulse-redesign (1).html:500-510`). Separate routes are LOCKED (WIDTH-F1 deferred, STATE.md:98). Reproduce the centering INTENT, not the markup.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Centering a max-width column | JS that measures viewport and sets left-margin | `margin-inline:auto` (or `margin:0 auto`) | Native, reflows free, already the codebase idiom (`.container`, `.nav`). |
| Symmetric responsive side padding | Media-query ladder of fixed paddings | `padding-inline: clamp(1.25rem,5vw,3.5rem)` | One declaration, fluid, matches D-01 verbatim. |
| Readable line length | Pixel max-widths guessed per breakpoint | `max-width: 64ch` | `ch` tracks the font; 64ch ≈ 60–70 chars in Source Serif 4 (the success-criterion target). |
| Theme colors | New hex values per component | The existing `:root` tokens (`--bg`/`--surface`/`--ink*`/`--line`/`--line-strong`/`--accent*`) | RHYTHM-01 is already 99% token-only; reusing tokens IS the requirement. |

**Key insight:** This entire phase is "use the platform" — there is nothing to build, only tokens to add and a single over-broad wrapper to split. The risk is not complexity, it is regression of the five separate routes and the maturity-overlap fix.

## D-06 Root Cause (the central research mandate — VERIFY-FIRST, traced not assumed)

**Method:** Static cascade trace of every loaded route. The site loads ONLY `style-base.css` then `style-shared.css` (`index.html:10-11`); the other CSS files (`style.css`, `style-builder.css`, `style-impact.css`) are NOT linked and are legacy/unloaded (confirmed: only two `<link rel="stylesheet">` in index.html). So the cascade is exactly those two files plus the JS-emitted inline styles (all token-based).

### The actual left-pin site: a SINGLE 720px `.container` wraps everything

`index.html:30` opens `<div class="container">` and it does not close until `index.html:144` — AFTER the hero, all six route-views inside `<main>`, the subscribe section, and the footer. The rule:

```css
/* style-shared.css:20-25 */
.container { max-width: 720px; width: 100%; margin: 0 auto; padding: 0 24px; }
```

So **every** route's content is capped at 720px and centered. The `.container` is genuinely centered (`margin:0 auto`) — confirming the operator's D-06 hypothesis that the obvious "not centered" cause is WRONG. The defect is that 720px is far too narrow for the tiled surfaces, so on a wide monitor a centered 720px column leaves a large empty band on each side. Read on a wide screen, that reads as a "dead left gutter."

### Per-route confirmation (file:line evidence)

| Route | DOM path | What constrains width | Left-pin mechanism | Evidence |
|-------|----------|----------------------|--------------------|----------|
| **Hero band** (list only) | `.container > .hero` | inherits `.container` 720px; `.hero` has `text-align:center` only, no own width | Centered 720px column; fine for prose but the band itself is only 720 wide | index.html:30,33; style-shared.css:20,47 |
| **Newsletter list** | `.container > main > #list-view > .content-area#newsletter-list` | `.container` 720px; `.content-area` has padding only, NO width (`style-shared.css:130-134`) | 720px centered → list rows never use available width | index.html:30,46; style-shared.css:20,130 |
| **Agent Economy map** (`#map-view .content-area`) | `.container > main > #map-view > .content-area` (innerHTML from renderHub) | `.container` 720px; `.grid` is `repeat(2,1fr)` (style-shared.css:254-259) inside that 720 | **The worst offender:** a 2-col card grid squeezed into 720px and centered → biggest visual side-band on wide screens. The grid wants to be wide; the container forbids it. | index.html:30,58-60; style-shared.css:20,254 |
| **Edition/article** (`#newsletter-content`) | `.container > main > #reader-view > .content-area > article` | `.container` 720px; `article` has no own width | 720px centered. This is the route where 720 is *closest* to right, but it is pinned to 720, not the readable 64ch, and shares the wrong axis with the nav (880). | index.html:30,50-55 |
| **Block detail** (`#block-content`) | `.container > main > #block-view > .content-area > #block-content` | `.container` 720px | Same as article — reading column pinned to 720, not 64ch. | index.html:30,63-68 |
| **About / "What is"** | `.container > main > #about-view > .content-area.about-stub` | `.container` 720px; `.agent-row` is `auto-fit minmax(150px,1fr)` (style-shared.css:914-919) inside 720 | Agent grid crammed into 720 and centered; intro prose also 720 not 64ch. | index.html:30,83-117; style-shared.css:914 |
| **Status** | `.container > main > #status-view > .content-area` | `.container` 720px | 720 centered rows. | index.html:30,71-76 |
| **Subscribe / footer** | `.container > #subscribe-section`, `.container > footer.bottom-bar` | `.container` 720px | 720 centered. | index.html:30,121-142 |

**Conclusion (D-06):** There is NO route-specific width override, NO asymmetric margin, NO flex/grid mis-alignment fighting the container. The single 720px `.container` in `index.html:30` is the sole left-pin mechanism, and it is centered — exactly the "not the obvious one" cause the operator flagged. The secondary symptom is a **two-axis mismatch**: nav is centered at 880px (`style-base.css:125`) while content is centered at 720px (`style-shared.css:20`), so chrome and content edges do not line up even where both are centered. The fix (D-02 + WIDTH-01) collapses both onto the one `--wide` axis and gives reading copy its own `--measure` axis.

**Why a plain "widen .container to 1080" is wrong:** it would make the reading column (article/block/about intro) 1080px wide — way past the readable 64ch line length, failing success-criterion #2. That is precisely why TWO axes are needed, not one wider one.

## WIDTH-01 Plan (tokens + classes + per-route apply-map)

### 1. Tokens — add to `style-base.css :root` (after the spacing/radius block, ~line 66)

```css
/* Width tokens (WIDTH-01, D-01) — two coexisting centered axes. */
--measure: 64ch;                          /* prose column — ~60–70 char lines */
--wide: 1080px;                           /* wide container — list/map/signals/grids */
--gutter: clamp(1.25rem, 5vw, 3.5rem);    /* responsive side padding (padding-inline) */
```
**Naming (D-01 resolution):** use `--wide` / `.wide`, NOT the brief's `--container-wide` / `.container-wide`. [VERIFIED: mockup uses `--wide`/`.wide`, agentpulse-redesign (1).html:30,47]

### 2. Class definitions — add to `style-base.css` near the display classes (~line 79-97)

```css
/* Centered prose column (WIDTH-01) — reading copy, capped line length. */
.prose { max-width: var(--measure); margin-inline: auto; padding-inline: var(--gutter); }

/* Centered wide container (WIDTH-01) — anything tiled. */
.wide  { max-width: var(--wide); margin-inline: auto; padding-inline: var(--gutter); }
```
Put them in `style-base.css` (loads first, available to both files). [CITED: REDESIGN_CC_BRIEF.md:80-84 for the class shape; naming swapped to `.wide` per D-01]

### 3. Legacy `.container` (720px) — RECOMMEND: repurpose, do not silently delete

`.container` (`style-shared.css:20-25`) is referenced in `index.html:30` and in a responsive override `style-shared.css:954` (`@media(max-width:600px){.container{padding:0 16px}}`). **Recommendation: retire it as a width axis but keep a thin compatibility shim** — change `index.html` to use `.wide`/`.prose` per route (below), and either (a) DELETE the `.container` rule + its `:954` mobile override and remove the class from markup, or (b) repurpose `.container` to alias `.prose` for any leftover reference. **Preferred (cleanest, lowest-surprise): option (a) — remove `.container` entirely and restructure index.html.** The class appears in exactly one markup site (`index.html:30`) and one CSS override (`:954`), so removal is fully bounded. Document the removal so a later phase does not resurrect a 720px assumption. (D-01 says these tokens "REPLACE the current single `.container`.")

### 4. Nav (D-02) — one line in `style-base.css:125`

```css
/* style-base.css:125 */
max-width: var(--wide);   /* was 880px — D-02: nav on the same centered axis as content */
```
And add the `wide` class in markup for clarity/parity with the mockup (optional, since the `.nav` rule alone now caps at `--wide`): `index.html:16` `<nav class="nav">` → `<nav class="nav wide">`. If you add the class, the `.wide` padding-inline would double with `.nav`'s own `padding:12px var(--space-lg)` — so EITHER keep `.nav` padding and do not add `.wide` to the nav (just change the max-width), OR add `.wide` and drop `.nav`'s horizontal padding. **Recommend: change ONLY `.nav` max-width to `var(--wide)` and do NOT add the `.wide` class to the nav** — avoids the double-padding and the comment update is minimal. (The mockup's `nav.wide` works because its `.nav` has no padding; ours does.)

### 5. Per-route APPLY-MAP (D-03/D-04)

Two viable application strategies — pick ONE and apply consistently:

- **Strategy A (markup-only, simplest):** restructure `index.html` so each route-view's `.content-area` is wrapped by (or replaced with) a `.wide` or `.prose` div. No app.js change. The renderers keep writing into the same `.content-area`; only its wrapper/axis changes.
- **Strategy B (renderer-aware):** keep `.content-area` neutral, and have each `renderX()` emit a `.prose`/`.wide` wrapper around its innerHTML. Touches app.js.

**Recommend Strategy A** — it keeps app.js untouched (lower risk, the renderers are dense and well-commented), and the prose-vs-wide split is structural, not data-dependent. The only place app.js *might* need a touch is wrapping the map's prose intro vs its grid (renderHub emits both into one `.content-area`); see the note below.

| Surface | Axis (D-03/D-04) | Where to apply | Notes |
|---------|------------------|----------------|-------|
| Nav / header chrome | `--wide` | `style-base.css:125` max-width | One centered axis (D-02). |
| Hero band (headline/date/toggle) | `--wide` band, prose-width copy | `index.html:33` wrap `.hero` in `.wide`; the headline/toggle are centered (`.hero text-align:center`) within | D-04: band on wide axis, copy reads narrow via the existing centered text-align. Hero is list-route only (app.js:233-234). |
| Newsletter list | `--wide` | `index.html:45-47` — wrap `#list-view`/`.content-area` in `.wide` | Tiled rows. |
| Edition / article body | `--prose` | `index.html:50-55` — make `#reader-view`'s content `.prose` (and the back-link sits with it) | D-03: prose stays narrow, centered. 64ch line length = success-criterion #2. |
| Block detail body | `--prose` | `index.html:63-68` — `#block-view` content `.prose` | Reading view. |
| About intro ("What is") | `--prose` for prose, `--wide` for the agent grid | `index.html:83-117` — the `.about` prose block → `.prose`; the `.agent-row` grid → `.wide` (or wrap the whole `.content-area.about-stub` in `.wide` and the prose paragraphs in an inner `.prose`) | D-03 explicitly: intro → measure; agent-card grid → wide. |
| Agent Economy map | `--wide` band; prose intro inside | `index.html:58-60` — wrap `#map-view`'s `.content-area` in `.wide`; **for the prose intro vs wide grid split, the cleanest is a small app.js touch:** in `renderHub` (app.js:670-676) wrap the `<h1>`+subline+`hub-storyline` in a `.prose` div and leave the `tierSection` grids at wide. Alternatively accept the hub header rendering at wide width (it is short — title + one-line storyline — and reads acceptably wide). | D-03: map grid → wide. The grid itself is `style-shared.css:254` (currently 2-col; the 3-col change is **Phase 21 GRID-01, NOT this phase** — do not change column count here). |
| Status | `--wide` | `index.html:71-76` — `#status-view` content `.wide` | Tiled rows. |
| Subscribe section / footer | `--wide` (or `--prose` for the form) | `index.html:121-142` — wrap in `.wide`; the subscribe form already has `max-width:400px` (style-shared.css:765) and centers itself | Keep centered; the form's own max-width handles the input column. |

**Scope guard:** This phase introduces the width axes and applies the wrappers. It does NOT change grid column counts, headers, excerpts, or add Signals — those are Phases 21–23. The map stays 2-col here; GRID-01 makes it 3-col next phase on top of this `--wide` foundation.

### 6. app.js application points (only if Strategy B or the map-intro touch)

- `renderHub` (app.js:670-678): writes `<h1>...subline...hubIntroHtml...tierSection(...)` into `#map-view .content-area`. If splitting prose intro from wide grid, wrap the header trio in `<div class="prose">...</div>` here.
- `renderArticle` (app.js:314-322) / `renderBlock` (app.js:772-817): write the article/block body. If using Strategy A, these are untouched (the `.prose` wrapper is the static `.content-area` ancestor). If Strategy B, wrap their composed innerHTML in `.prose`.
- `renderList` (app.js:257-264), `renderStatus` (app.js:942-947): write rows into the `.wide`-wrapped `.content-area`. Untouched under Strategy A.

All JS innerHTML inline styles are already token-based (app.js:281/337/499/702/827/888) — no color changes needed in app.js.

## RHYTHM-01 Color Audit (exhaustive — token-only verified holistically HERE)

**Method:** grep for every hex / `rgb()` / `rgba()` / `hsl()` / CSS-named color across all loaded files (`style-base.css`, `style-shared.css`, `app.js` inline styles, `index.html` inline styles). Named-color grep returned NONE. Results below are the COMPLETE set of color literals.

### Color literals that render on loaded routes

| File:Line | Literal | Context | Token mapping / disposition |
|-----------|---------|---------|------------------------------|
| style-base.css:12-21 | `#faf8f5` … `#4a2fd6` | The `:root` token **definitions** themselves (`--bg`,`--surface`,`--ink`,`--ink-soft`,`--ink-faint`,`--line`,`--line-strong`,`--accent`,`--accent-soft`,`--accent-ink`) | **Correct as-is** — these ARE the token source. Not a violation; they are the single definition site RHYTHM-01 wants everything to reference. |
| style-base.css:36 | `--btn-text:#fff` | A token value (on-accent button text) | **Leave** — intentional on-accent white; it is a *named token* (`--btn-text`), consumed by `#subscribe-btn` (style-shared.css:823). Tokenized already (just happens to resolve to white). |
| style-base.css:190 | `.subscribe { color:#fff }` | White wordmark text on the solid violet Subscribe button | **Intentional on-accent white** (RHYTHM-01 judgment). Recommend: leave literal OR alias to `--btn-text` for consistency with :36. Both are correct; aliasing is tidier. White-on-`--accent` is the accessible pairing. |
| style-shared.css:100 | `.toggle-btn.active { color:#fff }` | White text on the active (filled `--accent`) mode-toggle segment | **Intentional on-accent white** (the stray `#fff` CONTEXT.md D-discretion calls out). Recommend: leave OR alias to `--btn-text`. Same on-accent-white case as :190. |

### Non-color and locked-literal sites (out of "surface color" scope)

| File:Line | Literal | Why it is NOT a RHYTHM-01 violation |
|-----------|---------|--------------------------------------|
| style-base.css:114 | `background:rgba(250,248,245,.86)` | **Documented locked UI-SPEC literal** — the translucent sticky-header bg, deliberately NOT a token (it is `--bg` at 86% alpha for the backdrop-blur). Comment at :100-102 marks it locked. Leave. |
| style-base.css:178 | `.tab.active border-color:#ddd2ff` | **Documented locked UI-SPEC literal** — the active-tab border, locked at :101-102. Leave. |
| style-shared.css:299 | `box-shadow: 0 8px 24px rgba(26,25,22,.07)` | A shadow (`--ink` at 7% alpha), not a surface color. Could be tokenized but is cosmetic shadow, not theme color. Out of scope; leave. |

### Audit verdict

**RHYTHM-01 "no surface uses a hardcoded color" is effectively ALREADY TRUE.** The only literal surface/text colors are three on-accent whites (`:36` token, `:190`, `style-shared.css:100`), all of which are the correct, accessible white-on-violet pairing. **Recommendation: alias the two raw `#fff` (style-base.css:190, style-shared.css:100) to `--btn-text` (or a new `--on-accent:#fff` token) so the audit reads 100% token-only, OR document them as intentional on-accent literals.** Either satisfies the success criterion; aliasing makes "token-only" literally true and is the lower-risk choice for "verified holistically." The locked UI-SPEC literals (`:114`, `:178`) stay as-is by prior decision. All JS inline styles are already token-based (app.js:281/337/499/702/827/888 use `var(--text-secondary)`/`var(--ink-soft)`). No literal colors in index.html (the only `style=` attrs are `display:none`, index.html:50/58/63/71/83).

## D-05 Section Rhythm (major vs within, per route)

**Principle (D-05):** 1px `--line-strong` rule between MAJOR sections; 0.5px `--line` hairline WITHIN a section. The mockup encodes this as `section + section { border-top: 1px solid var(--rule) }` for major boundaries (`agentpulse-redesign (1).html:88`) and `border-bottom: 1px solid var(--line-soft)` on rows (`:119/134`).

### What already exists (do not duplicate)

| Existing rule | File:Line | Current weight/color | Role |
|---------------|-----------|----------------------|------|
| `.content-area` top rule | style-shared.css:132 | `0.5px solid var(--border)` | Separates chrome from content — borderline major; see recommendation. |
| `.article-entry` bottom | style-shared.css:141 | `1px solid var(--line)` | List-row divider — WITHIN (should be hairline 0.5px per D-05). |
| `article td` bottom | style-shared.css:730 | `0.5px solid var(--line)` | Table-row hairline — WITHIN. ✓ already correct. |
| `#subscribe-section` top | style-shared.css:747 | `0.5px solid var(--border)` | Section boundary — MAJOR candidate (should be 1px `--line-strong`). |
| `.bottom-bar` top | style-shared.css:844 | `0.5px solid var(--bar-border)` | Footer boundary — MAJOR candidate. |
| `body > header` bottom | style-base.css:117 | `1px solid var(--line)` | Sticky-nav bottom edge — MAJOR (chrome boundary). ✓ weight is 1px; color is `--line` not `--line-strong`. |

### Recommended per-route mapping

| Route | MAJOR separators (1px `--line-strong`) | WITHIN separators (0.5px `--line`) |
|-------|----------------------------------------|------------------------------------|
| **All routes (chrome)** | Nav bottom edge (style-base.css:117 — consider `--line-strong` for full strength); the subscribe-section top (style-shared.css:747 → bump to 1px `--line-strong`); footer top (style-shared.css:844 → 1px `--line-strong`) | — |
| **Newsletter list** | hero↔list boundary (the `.content-area` top rule, style-shared.css:132 — bump to 1px `--line-strong` as the hero↔body major rule) | `.article-entry` row dividers (style-shared.css:141 → 0.5px `--line` to read as within-section hairlines) |
| **Agent Economy map** | Between tier sections (substrate↔behavior↔frame). Today `.tier-label` has only top margin (style-shared.css:216-224), no rule. Add a major top rule on `.tier-section + .tier-section` (the `tierSection` wrapper is `<section class="tier-section">`, app.js:636) | card-internal dividers (none currently; cards are bordered boxes — leave) |
| **Edition / block / about (prose)** | header↔body (article-header bottom margin exists; optionally a major rule); about: between prose intro and agent grid | `article td` (already 0.5px ✓); list rows within sections |
| **Status** | between tier sections (same `.tier-section + .tier-section` rule) | status rows within a tier (the `.status-row` has only `border-left` accent; no inter-row rule — leave or add 0.5px) |

**Concrete recommended additions:**
```css
/* Major section rule (D-05) — full-strength between major route sections. */
.tier-section + .tier-section { border-top: 1px solid var(--line-strong); padding-top: var(--space-xl); }
/* Bump the chrome-boundary rules from 0.5px hairline to the major weight. */
#subscribe-section { border-top: 1px solid var(--line-strong); }      /* was 0.5px (:747) */
.bottom-bar       { border-top: 1px solid var(--line-strong); }       /* was 0.5px (:844) */
```
```css
/* Within-section hairline (D-05) — demote the list-row divider to 0.5px. */
.article-entry { border-bottom: 0.5px solid var(--line); }            /* was 1px (:141) */
```
**Note:** `0.5px` borders render as hairlines on retina/high-DPI but may round to 0 or 1px on 1x displays (browser-dependent). The codebase already relies on `0.5px` extensively (`:132/730/747/844`), so this is an established, accepted choice — keep consistent with it. The planner should treat the exact bumps above as the recommended D-05 baseline and verify holistically on the live render (per the success criterion "section rhythm reads as a hierarchy").

## Common Pitfalls

### Pitfall 1: Regressing the `body > header` maturity-overlap fix
**What goes wrong:** Changing the sticky-header selector from `body > header` back to bare `header`, or adding a new `header { position:sticky }` rule, re-sticks the in-content `<header class="block-header">` (emitted by renderBlock, app.js:773) to viewport-top, riding the maturity pill up over the nav.
**Why it happens:** The block reading view emits a nested `<header>` (app.js:773); a bare `header` type selector matches it too.
**How to avoid:** Touch ONLY `.nav` max-width (style-base.css:125). Do NOT edit the `body > header { position:sticky... }` rule (style-base.css:111-118). [CITED: style-base.css:103-109 scope comment; STATE.md:88 quick-task 260609-ivq]
**Warning signs:** Maturity pill overlapping the nav on a block page after the change.

### Pitfall 2: Cascade order — width tokens unavailable in style-shared.css
**What goes wrong:** Defining `--measure`/`--wide`/`--gutter` in `style-shared.css` (or after it) means rules in `style-base.css` that reference them resolve to `initial`/invalid.
**Why it happens:** `style-base.css` loads FIRST (index.html:10-11); custom properties are available globally once defined, but defining them in the later file and consuming in the earlier file at parse time is fragile.
**How to avoid:** Put ALL new tokens in `style-base.css :root` alongside the existing ones. [CITED: style-base.css:1-6 "Loaded FIRST"; index.html:10-11]

### Pitfall 3: Double-padding from nesting `.prose` inside `.wide` (or `.wide` on the padded `.nav`)
**What goes wrong:** `.wide` and `.prose` both apply `padding-inline:var(--gutter)`; nesting them doubles the side padding. Adding `.wide` to `.nav` (which already has `padding:12px var(--space-lg)`) also doubles.
**Why it happens:** Both wrappers carry gutters by design (for standalone use).
**How to avoid:** For prose-inside-wide (map/about intro), either accept the slight extra inset (the prose just centers within the wide band) or add `.wide > .prose { padding-inline: 0 }`. For the nav, change only `.nav` max-width and do NOT add the `.wide` class (per §WIDTH-01.4). [VERIFIED: mockup's `.prose` is bare `max-width` precisely because it nests in `.wide`, agentpulse-redesign (1).html:48]

### Pitfall 4: Widening the reading column past readability
**What goes wrong:** Applying `.wide` (1080px) to the article/block/about-intro body makes lines ~140 chars — fails success-criterion #2 (60–70 char target).
**Why it happens:** Treating "kill the gutter" as "make everything wide."
**How to avoid:** Reading copy gets `.prose` (64ch); only tiled surfaces get `.wide`. This is the whole reason for two axes (D-03). [CITED: ROADMAP success criterion #2]

### Pitfall 5: Scope creep into Phases 21–23
**What goes wrong:** Changing the map grid to 3 columns (GRID-01), de-duping the edition header (HEAD-01), fixing excerpts (EXCERPT-01), or adding Signals here.
**Why it happens:** The mockup shows all of these together; it is tempting to do them while in the files.
**How to avoid:** This phase is width tokens + centering + color-token + rhythm ONLY. Map stays 2-col (style-shared.css:254 unchanged). [CITED: 20-CONTEXT.md domain "NOT in scope"; ROADMAP Phase 21-23]

### Pitfall 6: Deploy from a worktree builds stale code
**What goes wrong:** A scoped `docker compose up -d --build web` run from a worktree builds the worktree's (possibly stale) `site/` instead of main-tree code.
**Why it happens:** Compose `cd`s to the absolute main-tree compose path; worktree executors can build stale code.
**How to avoid:** Deploy is orchestrator-owned, run from the main tree, scoped to the `web` SERVICE key (`docker compose ... web`, NOT the `agentpulse-web` container_name), NO `--delete`, prod↔main drift check + operator approval first. [CITED: MEMORY.md reference_web_compose_service_name, reference_scoped_rebuild_worktree_unsafe; 20-CONTEXT.md Deploy]

## Code Examples (verified patterns)

### Centered dual-axis containers
```css
/* Source: agentpulse-redesign (1).html:46-48 (mockup) + REDESIGN_CC_BRIEF.md:80-84 (brief), reconciled to .wide naming per D-01 */
.prose { max-width: var(--measure); margin-inline: auto; padding-inline: var(--gutter); }
.wide  { max-width: var(--wide);    margin-inline: auto; padding-inline: var(--gutter); }
```

### Nav onto the wide axis (D-02)
```css
/* Source: style-base.css:120-127 — change ONE line (max-width) */
.nav { display:flex; align-items:center; gap:var(--space-md);
  padding:12px var(--space-lg);
  max-width:var(--wide);  /* was 880px */
  margin:0 auto; }
```

### Major-section rule (D-05)
```css
/* Source: mockup pattern agentpulse-redesign (1).html:88 (`section + section { border-top }`),
   adapted to this SPA's .tier-section wrappers (app.js:636) and --line-strong token. */
.tier-section + .tier-section { border-top: 1px solid var(--line-strong); padding-top: var(--space-xl); }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single 720px `.container` for all content | Two centered axes: `--measure` prose + `--wide` tiled | This phase | Kills the dead gutter; aligns chrome+content edges. |
| Nav 880px / content 720px (two mismatched axes) | One `--wide` (1080px) axis for both | This phase (D-02) | Chrome and content edges line up. |
| Mixed 0.5px/1px borders ad hoc | Deliberate rhythm: 1px `--line-strong` major, 0.5px `--line` within | This phase (D-05) | Visual hierarchy reads as intended. |

**Deprecated/outdated:** The `.container` 720px axis (style-shared.css:20) is being retired/repurposed. The legacy `style.css`/`style-builder.css`/`style-impact.css` files remain UNLOADED (not linked in index.html) — do not touch them; they are dead weight from the pre-Phase-11 dark theme.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `64ch` in Source Serif 4 at 18px yields ~60–70 chars/line | WIDTH-01 / success-crit #2 | `ch` is the width of "0"; actual char count varies by font metrics. If lines come out too long/short, tune `--measure` (e.g. 60ch/68ch) at verification. Low risk — `ch` is the standard idiom and 64ch is the operator-chosen verbatim value (D-01). |
| A2 | `0.5px` hairlines render visibly on the operator's display | D-05 | On 1x displays some browsers round 0.5px to 0 (invisible) or 1px. The codebase already uses 0.5px throughout (:132/730/747/844), so this matches existing accepted behavior — but "reads as a hierarchy" is verified holistically on the live render. |
| A3 | Strategy A (markup-only wrappers in index.html) cleanly achieves the prose-vs-wide split for the map without an app.js touch | WIDTH-01 apply-map | renderHub writes BOTH the prose intro and the wide grid into one `.content-area` (app.js:670-678). A pure markup wrapper makes the whole map-view one axis. Achieving prose-intro + wide-grid likely needs a small app.js wrap in renderHub. Flagged in the apply-map; planner decides. Medium-low risk — acceptable fallback is rendering the short hub header at wide width. |
| A4 | Removing `.container` entirely (option a) has no other consumers | WIDTH-01.3 | grep found `.container` in exactly index.html:30 and style-shared.css:20,954. If a later/legacy file references it, removal could regress — but those files are unloaded. Verified bounded. Low risk. |

## Open Questions

1. **Prose-vs-wide on the map: markup-only or small app.js touch?**
   - What we know: renderHub emits header + grid into one `.content-area` (app.js:670-678).
   - What's unclear: whether the operator wants the hub header (title + one-line storyline) constrained to 64ch prose or allowed to sit at wide width.
   - Recommendation: small app.js wrap of the header trio in `.prose` for consistency with the mockup; or accept wide header (it is short). Planner picks; both satisfy D-03 (the GRID is what must be wide).

2. **On-accent white: alias to a token or leave literal?**
   - What we know: three on-accent whites (style-base.css:36 token, :190, style-shared.css:100), all correct white-on-violet.
   - What's unclear: whether "token-only verified holistically" requires zero raw `#fff` or accepts documented on-accent literals.
   - Recommendation: alias the two raw `#fff` to `--btn-text` (or add `--on-accent:#fff`) so the audit is literally 100% token-only — lowest-risk reading of the success criterion. Operator discretion per CONTEXT.md.

3. **Hero band treatment (D-04 deferred to researcher/planner).**
   - Recommendation: wrap `.hero` in `.wide` (band on the wide axis), keep its `text-align:center` so headline/date/toggle read centered and narrow within the band. No new prose wrapper needed — the hero content is already short and centered.

## Project Constraints (from CLAUDE.md)

- **Single hand-authored CSS, NO build step.** Edit files directly; the web Dockerfile only `COPY site/ /srv/`. [VERIFIED: docker/web/Dockerfile]
- **`style-base.css` loads FIRST** so its `:root` + serif body win over `style-shared.css`. New tokens go in style-base.css. [VERIFIED: index.html:10-11]
- **`body > header` (not bare `header`)** scopes the sticky chrome — do not regress the 260609-ivq maturity-overlap fix. [VERIFIED: style-base.css:103-118]
- **Deployed `/srv/app.js` differs from repo ONLY by the `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` substitution** — not a real divergence. [VERIFIED: docker/web/entrypoint.sh:3-4]
- **Frontend-only; all LLM via llm-proxy; economy_map via PostgREST + Accept-Profile** — none of these apply to this CSS phase (no backend, no schema, no LLM). [CITED: CLAUDE.md Constraints]
- **GSD workflow enforcement:** file edits go through a GSD command (this is a planned phase). [CITED: CLAUDE.md GSD Workflow Enforcement]
- **Deploy discipline:** scoped `docker compose ... web` (SERVICE key), no `--delete`, prod↔main drift check + operator approval, orchestrator-owned (worktree-unsafe). [CITED: MEMORY.md + 20-CONTEXT.md Deploy]

## Sources

### Primary (HIGH confidence)
- `docker/web/site/index.html` (full) — DOM structure, the single `.container` wrapper (`:30`), per-route view shells, the only two CSS links, inline styles (all `display:none`).
- `docker/web/site/style-base.css` (full) — `:root` tokens (`:10-66`), nav (`:120-127`, max-width 880px at `:125`), `body > header` sticky scope (`:103-118`), color literals (`:36/114/178/190`).
- `docker/web/site/style-shared.css` (full) — `.container` 720px (`:20-25`), `.content-area` (`:130`), grids (`:254/914`), borders/hairlines (`:132/141/730/747/844`), the `#fff` literal (`:100`).
- `docker/web/site/app.js` (full) — per-route render/loaders, innerHTML emission points, all inline styles token-based (`:281/337/499/702/827/888`).
- `docker/web/Dockerfile`, `docker/web/entrypoint.sh` — no build step; Supabase-substitution-only prod divergence.
- `.planning/docs/REDESIGN_CC_BRIEF.md` §TASK 2 (`:69-89`) — the prescribed recipe + apply-map + dead-gutter description.
- `.planning/docs/agentpulse-redesign (1).html` (`:28-48`) — `--measure:64ch`/`--wide:1080px`/`--gutter`, `.wide`/`.prose` defs, `nav.wide`, `section + section` major rule (`:88`).
- `.planning/phases/20-width-tokens-centering-foundation/20-CONTEXT.md` — locked decisions D-01..D-06.
- `.planning/ROADMAP.md` Phase 20 (`:99-114`) — goal + 4 success criteria.
- `.planning/STATE.md` — 260609-ivq maturity-overlap fix (`:88`), Phase 19 outcome, no-typographer note (`:46/63`).

### Secondary (MEDIUM confidence)
- MDN logical properties / `clamp()` / `ch` baseline support (training knowledge cross-checked against in-codebase usage at style-base.css:83,249) — these features are already used in the repo, so support is empirically confirmed for the target browsers.

### Tertiary (LOW confidence)
- None. Every claim is backed by a file:line in the local codebase.

## Metadata

**Confidence breakdown:**
- D-06 root cause: HIGH — statically traced end-to-end; single `.container` 720px wrapper confirmed as the sole left-pin, and it IS centered (matching the operator's "not the obvious cause" directive).
- WIDTH-01 plan: HIGH — token values are operator-locked verbatim; class shape from brief+mockup; apply-map grounded in exact DOM file:lines.
- RHYTHM-01 color audit: HIGH — exhaustive grep, complete literal set enumerated, only 3 intentional on-accent whites on loaded routes.
- D-05 section rhythm: MEDIUM-HIGH — existing separators enumerated; the major-vs-within mapping is a recommended baseline to be verified holistically on the live render (per the success criterion).
- Pitfalls: HIGH — each tied to a documented file:line constraint or a saved MEMORY lesson.

**Research date:** 2026-06-10
**Valid until:** ~30 days (stable — local CSS surface, no fast-moving external dependency). Re-verify only if `index.html`/`app.js`/the two CSS files change before planning.

## RESEARCH COMPLETE

**Phase:** 20 - Width Tokens & Centering Foundation
**Confidence:** HIGH

### Key Findings
- **D-06 SOLVED (traced, not assumed):** A single `<div class="container">` (max-width **720px**, `style-shared.css:20`) opened at `index.html:30` wraps the hero, ALL six route-views, subscribe, and footer. It IS centered (`margin:0 auto`) — confirming the operator's "not the obvious cause" hypothesis. The dead gutter is the wide map grid + lists crammed into a centered 720px column; secondary symptom is a two-axis mismatch (nav 880px vs content 720px). No route-specific override is the culprit.
- **WIDTH-01 plan is concrete:** add `--measure:64ch`/`--wide:1080px`/`--gutter:clamp(1.25rem,5vw,3.5rem)` + `.prose`/`.wide` to `style-base.css :root`; widen `.nav` max-width 880px→`var(--wide)` (one line, `:125`); apply `.wide`/`.prose` per-route via markup restructure in index.html (Strategy A, app.js untouched except an optional small renderHub wrap for the map's prose intro). Naming reconciled to `--wide`/`.wide` (D-01). Recommend removing the legacy `.container` entirely (bounded: 2 references).
- **RHYTHM-01 is ~already satisfied:** exhaustive audit found only 3 color literals on loaded routes, all intentional on-accent white (style-base.css:36 token, :190, style-shared.css:100). Recommend aliasing the two raw `#fff` to `--btn-text` for literal token-only. Two locked UI-SPEC literals (:114, :178) stay. All app.js inline styles already token-based.
- **D-05 baseline mapped:** 1px `--line-strong` between major sections (tier sections, subscribe/footer tops, chrome boundary); 0.5px `--line` within (list rows, table rows). Concrete rule additions provided.
- **Landmines flagged:** do NOT touch `body > header` (maturity-overlap fix), do NOT widen the reading column to 1080 (use `.prose`), do NOT scope-creep into 3-col map / header / excerpts / Signals (Phases 21-23), deploy is orchestrator-owned worktree-unsafe scoped `web` rebuild.

### File Created
`.planning/phases/20-width-tokens-centering-foundation/20-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Zero external packages — native CSS only; all features already used in-repo. |
| Architecture (D-06 + apply-map) | HIGH | Fully traced end-to-end with file:line evidence; single constraining axis confirmed. |
| Pitfalls | HIGH | Each tied to a documented constraint or saved MEMORY lesson. |

### Open Questions
1. Map prose-intro vs wide-grid: markup-only (whole map wide) vs small renderHub app.js wrap (prose intro). Recommend the small wrap; both satisfy D-03.
2. On-accent white: alias the two raw `#fff` to a token (recommended) vs leave as documented literals. Operator discretion.
3. Hero band (D-04): wrap `.hero` in `.wide`, keep `text-align:center`. Recommended.

### Ready for Planning
Research complete. The planner has the D-06 root cause, the exact token/class additions with file:line targets, a per-route apply-map, the full color audit, the section-rhythm mapping, and the scope guards. Planner can now create PLAN.md files.
