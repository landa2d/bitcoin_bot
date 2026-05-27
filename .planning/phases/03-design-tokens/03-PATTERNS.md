# Phase 3: Design Tokens — Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 3 (1 new stylesheet + 1 new standalone preview HTML + 1 single-line edit to index.html)
**Analogs found:** 3 / 3 (all role-match against existing per-feature stylesheets + the SPA shell)
**Existing site assets scanned:** `docker/web/site/index.html` (77 lines), `style-shared.css` (518 lines), `style.css` (160), `style-builder.css` (153), `style-impact.css` (153), `app.js` (314), `Caddyfile`, `entrypoint.sh`
**Codebase grep results (first-in-tree confirmation):**

| Pattern | grep query | Hits | Status |
|---------|------------|------|--------|
| `data-*` attribute selectors in CSS | `grep -n 'data-' docker/web/site/*.css` | 0 | first in-tree |
| `:not(...)` selectors in CSS | `grep -n ':not(' docker/web/site/*.css` | 0 | first in-tree |
| `:nth-child(...)` selectors in CSS | `grep -n 'nth-child' docker/web/site/*.css` | 0 | first in-tree |

---

## Headline finding: three first-in-tree CSS patterns + a clean per-feature-stylesheet precedent

Before per-file pattern assignment, the planner must internalize two things:

1. **Per-feature stylesheet pattern is well-established.** `style.css`, `style-builder.css`, and `style-impact.css` all show the "small file that adds variables-and-rules layered on top of `style-shared.css`" shape. The new `style-map.css` follows this convention exactly — *no new infrastructure, no build step, no inheritance gymnastics*. The CONTEXT.md D-09 default ("ship a new `style-map.css`") aligns with three existing siblings.

2. **The three CSS mechanisms the maturity pill + timeline-entry rules need have ZERO precedent in the existing site CSS.** A repo-wide grep confirms:
   - No `data-*` attribute selectors anywhere in `docker/web/site/*.css`
   - No `:not(...)` selectors anywhere
   - No `:nth-child(...)` selectors anywhere

   The CONTEXT.md D-10 contract (`[data-stage="3"] .seg:nth-child(-n+3) { background: var(--accent-tier); }`) and the D-11 / "Other Claude discretions" empty-source rule (`.timeline-entry:not([data-source]) ...`) introduce all three patterns at once. There is no analog to lift; the planner / executor **invents these CSS mechanisms** the same way Phase 2 invented `CREATE SCHEMA` / `CREATE TYPE` / `CREATE TRIGGER`. The patterns themselves are CSS standards — the novelty is purely *in-tree*.

   This is not a problem; it is a callout. Future contributors looking at `docker/web/site/*.css` will see attribute-selector and structural-selector CSS for the first time in `style-map.css`. The file should carry a short comment header explaining the data-attribute contract (block-tier → accent via `data-accent`; pill fill via `data-stage` + `nth-child`) so the next maintainer doesn't wonder where the magic comes from.

For everything else (`:root` / body-class variable blocks, the per-feature stylesheet shape, the `<link>` injection point in `index.html`, the mode-toggle markup, the `setMode` JS contract), concrete analogs exist and are quoted line-by-line below.

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|----------------|---------------|
| **CREATE** `docker/web/site/style-map.css` | per-feature stylesheet (CSS variables + component rules) | CSS-variable resolution by body-class + data-attribute | `style-shared.css` lines 7–49 (body-class variable blocks), `style-builder.css` (per-feature stylesheet layered atop a shared base) | **role-match** for stylesheet shape; **no in-tree analog** for `data-*` / `:nth-child` / `:not()` selectors (CSS-standard, but novel here) |
| **CREATE** `docker/web/site/tokens-preview.html` | standalone deployable static HTML (verification artifact for ROADMAP SC#1) | static markup, served directly by Caddy `file_server` before SPA `try_files` fallback | `docker/web/site/index.html` (only existing HTML; same `<head>` + body-class + mode-toggle shape) | **partial** — `index.html` is a SPA shell; `tokens-preview.html` is intentionally NOT a SPA shell (no `app.js`, no Supabase). Borrow the head/body/mode-toggle structure but strip the SPA wiring. |
| **MODIFY** `docker/web/site/index.html` | single-line `<link>` injection inside `<head>` | static asset declaration | `docker/web/site/index.html` line 7 (the existing `<link rel="stylesheet" href="/style-shared.css">` — the new line sits adjacent to it) | **exact** — copy the existing line's syntax verbatim, replace the href |

---

## Pattern Assignments

### 1. `docker/web/site/style-map.css` (stylesheet, CSS-variable resolution)

This is a composite stylesheet: four sub-patterns assembled in one file. Each sub-pattern has its own analog (or its own first-in-tree status). Assemble the file in this order, with `═══` section dividers between sections matching the convention of Phase 2's migration sections.

---

#### 1a. File header + comment block (style)

**Analog:** `docker/web/site/style-shared.css` lines 1–5, `style-builder.css` lines 1–3, `style-impact.css` lines 1–3.

**`style-shared.css` line 1:**
```css
/* === AgentPulse — Unified Styles === */
```

**`style-builder.css` lines 1–3:**
```css
/* === AgentPulse Builder Mode — Colors Only === */

body.builder {
```

**Recommendation:** Open with a header that names the file's role AND its data-attribute contract, since the data-attribute contract is the first-in-tree mechanism the next maintainer needs to know. Example:

```css
/* === AgentPulse — Economy-Map Design Tokens === */
/* Layered onto style-shared.css. Activates only inside elements
   carrying data-accent="teal|purple|coral|gray". Pages without
   data-accent see no change (edition pages are unaffected).
   Markup contract:
     <div data-accent="teal" data-stage="3"> ... </div>   — block wrapper
     <span class="seg"></span> × 5                         — pill segments
     <article class="timeline-entry" data-source="https://...">  — timeline entry
*/
```

---

#### 1b. Tier-accent token variables (the `--accent-{teal,purple,coral,gray}-{base,on-dark}` block)

**Analog (style — body-class variable block):** `style-shared.css` lines 7–49.

**Exact block to mirror in shape (lines 7–27 — the technical block):**
```css
body.technical {
    --accent: #00e5a0;
    --bg: #0a0a0f;
    --text-primary: #ffffff;
    --text-secondary: rgba(255, 255, 255, 0.85);
    --text-body: #ffffff;
    --text-hint: rgba(255, 255, 255, 0.7);
    --border: rgba(255, 255, 255, 0.08);
    --toggle-bg: rgba(255, 255, 255, 0.06);
    --toggle-inactive: rgba(255, 255, 255, 0.85);
    --btn-bg: #00e5a0;
    --btn-text: #0a0a0f;
    --bar-bg: rgba(0, 229, 160, 0.06);
    --bar-border: rgba(0, 229, 160, 0.15);
    --bar-text: rgba(255, 255, 255, 0.85);
    --btn-secondary-border: rgba(0, 229, 160, 0.3);
    --blockquote-bg: rgba(255, 255, 255, 0.03);
    --code-bg: rgba(255, 255, 255, 0.08);
    --pre-bg: rgba(255, 255, 255, 0.04);
    --input-bg: rgba(255, 255, 255, 0.04);
}
```

**Strategic block (lines 29–49) — same structure, different values:**
```css
body.strategic {
    --accent: #7c3aed;
    --bg: #ffffff;
    /* ... */
}
```

**Pattern to invent (style-map.css):** TOKN-01 hex values (`#0F6E56` teal, `#534AB7` purple, `#993C1D` coral, `#5F5E5A` gray) live as `--accent-*-base` custom properties on a globally-scoped block (`:root` is the natural home — `:root` is unused in `style-shared.css` so picking it does not collide). The four `-on-dark` variants are Claude's discretion (D-03 / D-05); they live in the same `:root` block or under `body.technical` if scoping by mode is cleaner. Example shape:

```css
/* Tier accent tokens — TOKN-01 (base) + on-dark variants for body.technical contrast */
:root {
    --accent-teal-base:   #0F6E56;  /* substrate, designed for white */
    --accent-purple-base: #534AB7;  /* behavior, designed for white  */
    --accent-coral-base:  #993C1D;  /* psychology, designed for white */
    --accent-gray-base:   #5F5E5A;  /* regulation / frame, designed for white */

    --accent-teal-on-dark:   /* TBD by planner — WCAG AA against #0a0a0f, teal-hue family */ ;
    --accent-purple-on-dark: /* TBD by planner — WCAG AA against #0a0a0f, purple-hue family */ ;
    --accent-coral-on-dark:  /* TBD by planner — WCAG AA against #0a0a0f, coral-hue family */ ;
    --accent-gray-on-dark:   /* TBD by planner — WCAG AA against #0a0a0f, gray-hue family */ ;
}
```

**Constraint for `-on-dark` values (from CONTEXT.md D-05 + `<specifics>`):**
- Preserve the pinned-base hue family (teal stays teal, etc.)
- WCAG AA contrast against `#0a0a0f` (technical-mode background): ≥ 4.5:1 for any text use; ≥ 3:1 for the maturity-pill segments (non-text use)
- Document the chosen hex + measured contrast in PLAN.md so future audits can verify (per CONTEXT.md `<specifics>`)

---

#### 1c. `--accent-tier` resolution by body-class × `data-accent` (the mode-aware override mechanism)

**Analog (the layering mechanism, NOT the selector syntax):** `style-shared.css` lines 7–49.

The existing `style-shared.css` resolves `--accent` two ways: `body.technical { --accent: #00e5a0; }` and `body.strategic { --accent: #7c3aed; }`. The Phase 3 mechanism extends this with a second axis (`data-accent`):

```css
/* Pattern (no in-tree precedent — first use of attribute selectors in site CSS): */

/* Strategic (light) mode: pinned-base hex on every data-accent value */
body.strategic [data-accent="teal"]   { --accent-tier: var(--accent-teal-base);   }
body.strategic [data-accent="purple"] { --accent-tier: var(--accent-purple-base); }
body.strategic [data-accent="coral"]  { --accent-tier: var(--accent-coral-base);  }
body.strategic [data-accent="gray"]   { --accent-tier: var(--accent-gray-base);   }

/* Technical (dark) mode: on-dark variants on every data-accent value */
body.technical [data-accent="teal"]   { --accent-tier: var(--accent-teal-on-dark);   }
body.technical [data-accent="purple"] { --accent-tier: var(--accent-purple-on-dark); }
body.technical [data-accent="coral"]  { --accent-tier: var(--accent-coral-on-dark);  }
body.technical [data-accent="gray"]   { --accent-tier: var(--accent-gray-on-dark);   }
```

**Critical detail from CONTEXT.md D-05 (the `psychology = coral` override):** The selector key is **`data-accent`** (the `blocks.accent` column value, per Phase 2 D-23 — already populated as `teal|purple|coral|gray`), **NOT** `data-tier`. The `psychology-disposition` block has `tier = behavior` but `accent = coral`; if Phase 3 keyed off `data-tier` it would render Psychology as purple. The planner / executor **must use `data-accent`**. Surface this loudly in PLAN.md.

**Scope contract from CONTEXT.md D-02 (which surfaces apply tier color where):**
- On `/map/<slug>` (single-block surface): `--accent-tier` overrides `--accent` throughout the block's wrapper (title, pill, section labels, links, hover). Phase 4 sets `data-accent` on the *page-wrapper* element so the whole block page inherits it.
- On `/map` (hub) and `/status` (denser snapshot): each block's `data-accent` is scoped to **just the block's pill + tile border**. Page chrome (top nav, mode toggle) stays mode-default. Phase 4 sets `data-accent` only on each tile, not on the page wrapper.
- Existing edition pages (no `data-accent`): completely unchanged. Per CONTEXT.md D-06.

Phase 3's CSS does not need to know which page-type it's on; it only needs the `[data-accent="..."]` selector. Phase 4 controls scope by where it places the attribute.

---

#### 1d. Maturity pill component (`.maturity-pill` + `.seg` + `[data-stage]` rules)

**Analog (component-CSS style):** none in-tree for `data-*` or `:nth-child(...)`. **First in-tree.**

**Markup contract from CONTEXT.md D-10 (the contract Phase 4 emits):**
```html
<div class="maturity-pill"
     data-accent="teal"
     data-stage="3"
     aria-label="Maturity: contested (3 of 5)">
    <span class="seg"></span>
    <span class="seg"></span>
    <span class="seg"></span>
    <span class="seg"></span>
    <span class="seg"></span>
</div>
```

**CSS pattern to invent:**
```css
/* Maturity pill — five segments, left-to-right fill keyed off data-stage */
.maturity-pill {
    display: inline-flex;
    /* gap vs shared border: planner picks per CONTEXT.md "Other Claude discretions"
       — pick one and apply consistently; document in PLAN.md */
    gap: 2px;                /* example — or 0 with a 1px right border on .seg */
    /* width / height: pill dimensions are Phase 3's call (informational only,
       not interactive — per CONTEXT.md <deferred>); pick something readable
       across hub/block/status — same component, one source of truth (TOKN-02) */
}

.maturity-pill .seg {
    /* unfilled segment: neutral border, transparent fill — uses style-shared.css's
       --border variable so it inherits mode (dark mode = subtle white border,
       light mode = subtle black border, per style-shared.css lines 14 + 36) */
    background: transparent;
    border: 1px solid var(--border);
    /* width / height per segment — planner picks consistent values */
}

/* Left-to-right fill by stage. data-stage="N" fills first N segments. */
.maturity-pill[data-stage="1"] .seg:nth-child(-n+1) { background: var(--accent-tier); border-color: var(--accent-tier); }
.maturity-pill[data-stage="2"] .seg:nth-child(-n+2) { background: var(--accent-tier); border-color: var(--accent-tier); }
.maturity-pill[data-stage="3"] .seg:nth-child(-n+3) { background: var(--accent-tier); border-color: var(--accent-tier); }
.maturity-pill[data-stage="4"] .seg:nth-child(-n+4) { background: var(--accent-tier); border-color: var(--accent-tier); }
.maturity-pill[data-stage="5"] .seg:nth-child(-n+5) { background: var(--accent-tier); border-color: var(--accent-tier); }
```

**Why `nth-child(-n+N)` (not `:nth-child(N)` repeated):** `-n+N` matches "child 1 through N" — exactly the left-to-right fill semantics. Single selector per stage; trivially auditable.

**Variable resolution:** `var(--accent-tier)` resolves through the mechanism in §1c. Since the pill carries `data-accent="teal"`, the `body.{technical,strategic} [data-accent="teal"]` rules set `--accent-tier` on the pill itself, and `.seg` inherits it.

**Five maturity stages from REQUIREMENTS.md SCHM-05:** `nascent`(1) → `emerging`(2) → `contested`(3) → `consolidating`(4) → `mature`(5). Phase 4 maps `blocks.maturity` enum → `data-stage` integer; Phase 3 does not need to know the enum names.

**Hover / interactive states explicitly out of scope (CONTEXT.md `<deferred>`):** the pill is informational at the block level. No `:hover` / `:active` rules.

---

#### 1e. `.timeline-entry` (two-line format + `↗` source link + empty-source rule)

**Analog (two-line text component):** No exact analog. The closest sibling concept is `style-shared.css` lines 205–238 (the `.article-entry` block in list view — `.section-label` + `.entry-title` + `.entry-preview` stack). The structural shape (a small composed component with line-level rules) is the same, but the timeline-entry's format is novel.

**`.article-entry` reference (style-shared.css lines 205–239):**
```css
.article-entry {
    margin-bottom: 20px;
}

.section-label {
    font-family: 'Courier New', monospace;
    font-size: 13px;
    font-weight: 400;
    color: var(--accent);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 6px;
}

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

**Format contract from CONTEXT.md `<specifics>` + REQUIREMENTS.md TOKN-03 + build spec v2 §8.3:**
```
<event_date> · <what_shifted>
<why_it_mattered>   [source ↗]
```

**Markup contract (recommend — Phase 4 will emit this):**
```html
<article class="timeline-entry" data-source="https://example.com/post">
    <div class="timeline-line1">
        <time class="timeline-date">2026-05-15</time>
        <span class="timeline-sep">·</span>
        <span class="timeline-what">What shifted goes here</span>
    </div>
    <div class="timeline-line2">
        <span class="timeline-why">Why it mattered, one line.</span>
        <a class="timeline-source" href="https://example.com/post">source ↗</a>
    </div>
</article>

<!-- Empty source variant — note absent data-source attribute -->
<article class="timeline-entry">
    <div class="timeline-line1">
        <time class="timeline-date">2026-05-15</time>
        <span class="timeline-sep">·</span>
        <span class="timeline-what">What shifted goes here</span>
    </div>
    <div class="timeline-line2">
        <span class="timeline-why">Why it mattered, occupies full second line.</span>
        <!-- no .timeline-source rendered -->
    </div>
</article>
```

**CSS rules:**
```css
/* Timeline entry — two-line format, fixed per TOKN-03 */
.timeline-entry {
    margin-bottom: 14px;  /* tighter than .article-entry — denser context */
    font-family: 'Courier New', monospace;  /* inherits TOKN-04 body font */
    line-height: 1.5;
}

.timeline-entry .timeline-line1 {
    font-size: 15px;
    color: var(--text-primary);
    margin-bottom: 2px;
}

.timeline-entry .timeline-date {
    color: var(--text-secondary);  /* the anchor; muted — date-as-anchor per spec §8.3 */
}

.timeline-entry .timeline-sep {
    color: var(--text-hint);
    margin: 0 6px;
}

.timeline-entry .timeline-what {
    color: var(--text-primary);  /* the lede */
}

.timeline-entry .timeline-line2 {
    font-size: 14px;
    color: var(--text-body);
    display: flex;
    justify-content: space-between;
    gap: 12px;
}

.timeline-entry .timeline-why {
    flex: 1;  /* takes available width; wraps if long */
}

.timeline-entry .timeline-source {
    color: var(--accent-tier, var(--accent));  /* tier accent if present, else mode accent */
    text-decoration: none;
    flex-shrink: 0;
    white-space: nowrap;
}

.timeline-entry .timeline-source:hover {
    text-decoration: underline;
}

/* Empty-source graceful degradation (per CONTEXT.md "Other Claude discretions"):
   when source_url is null, the entry has no data-source attribute and the
   .timeline-source span is omitted from markup. Why-it-mattered takes the
   full second line — no special CSS needed because flex:1 already handles it.
   This selector is documentary only — it lets future eyes see the rule
   intentionally exists. */
.timeline-entry:not([data-source]) .timeline-source {
    display: none;  /* defensive — should never render in the first place */
}
```

**`↗` glyph (per CONTEXT.md "Other Claude discretions"):** literal Unicode U+2197 in the markup (`source ↗`), not an SVG or icon font. Build spec §8.3 pins the glyph; the markup contract delivers it.

**Wrap behavior:** `.timeline-why { flex: 1 }` + container max-width 720px (inherited from `style-shared.css` `.container`, line 60) means long `why_it_mattered` strings wrap inside the second line, with the source link staying right-anchored. The standalone-preview's "long-text" sample (CONTEXT.md D-11) exercises this.

---

### 2. `docker/web/site/tokens-preview.html` (standalone deployable static HTML)

**Analog:** `docker/web/site/index.html` (the only existing HTML file). The new preview borrows the head/body/mode-toggle structure but **strips the SPA wiring** (no `app.js`, no Supabase, no list-view / reader-view containers). Per CONTEXT.md `<specifics>`: "The `tokens-preview.html` page deliberately bypasses the SPA … It's a static file served by Caddy's `file_server` (which matches before `try_files` falls back to `index.html`)."

**`index.html` lines 1–9 (head + body open — exact shape to mirror):**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentPulse Intelligence Brief</title>
    <link rel="stylesheet" href="/style-shared.css">
</head>
<body class="technical">
```

**`index.html` lines 25–28 (mode-toggle markup — exact shape to mirror; `setMode` referenced):**
```html
<div class="mode-toggle">
    <button class="toggle-btn active" id="btn-technical" onclick="setMode('technical')">Technical</button>
    <button class="toggle-btn" id="btn-strategic" onclick="setMode('strategic')">Strategic</button>
</div>
```

**`app.js` lines 42–67 (the `setMode` function the preview must reimplement inline, since the preview does not load `app.js`):**
```js
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
    /* … re-render hooks not needed in preview … */
}
```

**Pattern for the preview:** ship a **minimal inline `<script>`** that implements the body-class swap (`document.body.classList.remove(...).add(...)`) — the preview only needs the CSS-variable resolution, not localStorage / URL param / re-render hooks. Example skeleton:
```html
<script>
function setMode(mode) {
    document.body.classList.remove('technical', 'strategic');
    document.body.classList.add(mode);
    document.getElementById('btn-technical').classList.toggle('active', mode === 'technical');
    document.getElementById('btn-strategic').classList.toggle('active', mode === 'strategic');
}
</script>
```

**Required sections per CONTEXT.md D-11 + `<specifics>`:**
1. **4×2 grid of tier accent swatches** (4 accents × 2 modes = 8 swatches). Each swatch is a small colored tile with the hex value rendered as a label. The 2-mode dimension is implicit (the toggle switches body class; both states are visible by clicking the toggle), OR the preview shows both modes simultaneously by nesting two `.preview-mode-block` sections that each force a body-class via a wrapping `<div class="technical">…</div>` block (with the `--accent-*` resolution scoped to it). Planner picks; both satisfy SC#1.
2. **4 accents × 5 pill stages = 20 pill renders.** Lay out as a 4×5 grid (rows = accents, columns = stages). Each cell renders one `<div class="maturity-pill" data-accent="…" data-stage="…">…</div>` with five `<span class="seg">` children.
3. **3 timeline-entry samples:**
   - Normal: short `why_it_mattered`, present `source_url` → `data-source="…"` set, `<a class="timeline-source">source ↗</a>` rendered.
   - Source-null: no `data-source` attribute, no `<a class="timeline-source">` in markup — `why_it_mattered` takes full second line.
   - Long-text: `why_it_mattered` long enough to wrap; source link stays right-anchored.
4. **Mode-toggle button identical to edition pages** — same `.mode-toggle` + `.toggle-btn` markup; same `setMode('technical')` / `setMode('strategic')` `onclick` handlers; inline `<script>` reimplements `setMode`.

**`<head>` must load:**
```html
<link rel="stylesheet" href="/style-shared.css">
<link rel="stylesheet" href="/style-map.css">
```
Both load via root-relative paths (Caddy `root * /srv` serves them at `/style-shared.css` and `/style-map.css`).

**Deploy-path verification (from Phase 1 §1 + Caddyfile lines 11–12):** Caddy's `try_files {path} /index.html` falls back to the SPA shell **only when a static file does not exist for `{path}`**. Because `tokens-preview.html` exists at `/srv/tokens-preview.html`, requests to `/tokens-preview.html` resolve via `file_server` and bypass the SPA fallback. **No Caddyfile changes required.**

**No Supabase credentials needed:** per CONTEXT.md `<canonical_refs>`: "Phase 3's preview page does not need Supabase credentials; tokens render from static markup." The preview never queries; `entrypoint.sh`'s `sed` substitution on `app.js` does not touch the preview.

---

### 3. `docker/web/site/index.html` (single `<link>` injection — exact one-line edit)

**Analog (the line being mirrored):** `docker/web/site/index.html` line 7.

**Existing line (line 7):**
```html
    <link rel="stylesheet" href="/style-shared.css">
```

**Edit:** add **one** new `<link>` directly after line 7 (before `</head>` on line 8). The edit MUST NOT introduce any other change to `index.html`.

**New line:**
```html
    <link rel="stylesheet" href="/style-map.css">
```

**Result (target state, lines 1–10):**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentPulse Intelligence Brief</title>
    <link rel="stylesheet" href="/style-shared.css">
    <link rel="stylesheet" href="/style-map.css">
</head>
<body class="technical">
```

**Why the `<link>` is safe to load on every page:** `style-map.css`'s active CSS only fires inside elements carrying `data-accent="…"`. Existing edition pages (`#/edition/N`) and the list view (`#/`) do not emit `data-accent` anywhere — Phase 4 introduces it only on map-page wrappers and tiles. The stylesheet is therefore inert on existing pages (per CONTEXT.md D-06 + "Integration Points"). The single load-everywhere `<link>` is simpler to verify than a conditional JS injection (D-09's option B), so the planner's default is the safe choice.

**No other file changes in `docker/web/site/`:** `app.js` is untouched (Phase 4 will add hash-route branches; Phase 3 does not). `Caddyfile` is untouched. `entrypoint.sh` is untouched.

---

## Shared Patterns

### Mode-toggle inheritance (applies to: `style-map.css` indirectly; `tokens-preview.html` directly)

**Source:** `style-shared.css` lines 157–193 (the `.mode-toggle` + `.toggle-btn` + `.mode-subtitle` block), `index.html` lines 25–29 (the markup), `app.js` lines 42–78 (the `setMode` function).

**Style block — `style-shared.css` lines 159–184:**
```css
.mode-toggle {
    display: inline-flex;
    background: var(--toggle-bg);
    border-radius: 8px;
    padding: 3px;
    gap: 2px;
}

.toggle-btn {
    font-family: 'Courier New', monospace;
    font-size: 15px;
    font-weight: 400;
    padding: 8px 20px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--toggle-inactive);
    cursor: pointer;
    transition: all 0.3s;
}

.toggle-btn.active {
    background: var(--accent);
    color: var(--btn-text);
    font-weight: 700;
}
```

**Apply to:**
- `tokens-preview.html` — uses these exact CSS classes (no changes to the toggle's appearance; just the existing `.mode-toggle` + `.toggle-btn` markup). Inline `<script>` reimplements `setMode` minimally (see §2 above).
- `style-map.css` — does NOT redefine the toggle. The toggle remains a `style-shared.css` concern. `style-map.css` only adds map-specific tokens; the toggle continues to use `--accent` (mode accent, NOT tier accent) per CONTEXT.md D-02 ("page chrome (top nav, mode toggle, body type colors) stays mode-default").

### Mode-transition CSS (inherited automatically)

**Source:** `style-shared.css` lines 68–73:
```css
.mode-transitioning,
.mode-transitioning *,
.mode-transitioning *::before,
.mode-transitioning *::after {
    transition: background-color 0.4s ease, color 0.4s ease, border-color 0.4s ease !important;
}
```

**Apply to:** all Phase 3 elements automatically. When the mode toggle adds `mode-transitioning` to `<body>` for 400ms, the existing `*` cascade catches all map-page elements (pill segments, timeline-entry text, tier-accent swatches), so background / color / border transitions happen for free. `style-map.css` adds **no transition rules** — it inherits this one.

### Existing typography inheritance (TOKN-04 — "no bespoke typography")

**Source:** `style-shared.css` line 52 (`body { font-family: 'Courier New', monospace; }`), line 142 (`.hero-headline { font-family: Georgia, serif; }`), line 60 (`.container { max-width: 720px; }`).

**Apply to:** every Phase 3 element. `style-map.css` adds **no `font-family` rules** outside what TOKN-03 already implies (the timeline-entry's monospace body). The Georgia serif headline / 720px container are inherited via the existing element hierarchy and `.container` class — Phase 4 wraps map pages in `<div class="container">` and the rest follows. Per CONTEXT.md D-08 + ROADMAP SC#4.

### Variable-cascade contract

**Source:** `style-shared.css` lines 7–49 (the dual-mode variable blocks define `--accent`, `--bg`, `--text-primary`, `--text-secondary`, `--text-body`, `--text-hint`, `--border`, `--toggle-bg`, `--toggle-inactive`, `--btn-bg`, `--btn-text`, `--bar-bg`, `--bar-border`, `--bar-text`, `--btn-secondary-border`, `--blockquote-bg`, `--code-bg`, `--pre-bg`, `--input-bg`).

**Apply to:** every rule in `style-map.css` that needs a mode-aware color **other than the tier accent itself** uses one of the existing variables, not a new value. Specifically:
- `.maturity-pill .seg` unfilled border → `var(--border)`
- `.timeline-entry .timeline-date` (date/anchor, muted) → `var(--text-secondary)`
- `.timeline-entry .timeline-sep` (the `·` separator) → `var(--text-hint)`
- `.timeline-entry .timeline-what` (lede) → `var(--text-primary)`
- `.timeline-entry .timeline-why` → `var(--text-body)`
- `.timeline-entry .timeline-source` → `var(--accent-tier, var(--accent))` (cascade: tier accent if set, mode accent otherwise — defensive default for entries rendered outside a `data-accent` wrapper)

This honors CONTEXT.md D-08: "The new `--accent-tier` is the only override; everything else (background, body text color, borders) inherits the body-mode variables — `TOKN-04` honored."

---

## No Analog Found

| File | Mechanism | Reason | Mitigation |
|------|-----------|--------|------------|
| `style-map.css` | `[data-accent="…"]` attribute selectors | No `data-*` selectors anywhere in `docker/web/site/*.css` (grep confirmed) | CSS standard; trivial to write. Add comment header in the file explaining the contract (see §1a). |
| `style-map.css` | `:nth-child(-n+N)` structural selectors | No `:nth-child` in any existing site CSS (grep confirmed) | CSS standard. The `-n+N` form is the canonical way to express "first N siblings". |
| `style-map.css` | `:not([data-source])` negation pseudo-class | No `:not(...)` in any existing site CSS (grep confirmed) | Defensive-documentary only — the `display: none` fallback should never trigger because Phase 4 omits the `<a class="timeline-source">` from markup when `source_url` is null. The selector exists as a comment-supporting rule, not a critical mechanism. |
| `tokens-preview.html` | Standalone (non-SPA) HTML file at site root | Only existing HTML file is `index.html`, which IS the SPA shell. No prior non-SPA HTML in `docker/web/site/`. | Caddy's `file_server` serves any static file at `/<name>.html` before `try_files` falls back to the SPA (confirmed Phase 1 §1 + Caddyfile lines 11–12). The new file simply has to exist; no infra change. |

None of these gaps block the phase. All four are CSS / HTML standards that the executor writes directly; the callouts above ensure the planner names them in PLAN.md so the executor isn't surprised by their first-in-tree-ness.

---

## Metadata

**Analog search scope:** `docker/web/site/` (full directory: 6 files), `docker/web/Caddyfile`, `docker/web/entrypoint.sh`, `docker/web/Dockerfile` (via Phase 1 §1 extract).

**Files read:**
- `docker/web/site/index.html` (full — 77 lines)
- `docker/web/site/style-shared.css` (full — 518 lines)
- `docker/web/site/style.css` (full — 160 lines)
- `docker/web/site/style-builder.css` (full — 153 lines)
- `docker/web/site/style-impact.css` (full — 153 lines)
- `docker/web/site/app.js` (full — 314 lines)
- `docker/web/Caddyfile` (full — 21 lines)
- `docker/web/entrypoint.sh` (full — 7 lines)

**Grep queries run (first-in-tree confirmation):**
- `grep -n 'data-' docker/web/site/*.css` → 0 hits
- `grep -n ':not(' docker/web/site/*.css` → 0 hits
- `grep -n 'nth-child' docker/web/site/*.css` → 0 hits

**Build-spec sections cross-referenced:** §1 (storyline + per-block accent mapping, including the `psychology = coral` deliberate distinction), §6 (renderer contract — hash routes confirmed), §8 (design tokens — pinned hex 8.1, pill semantics 8.2, timeline format 8.3, inheritance 8.4).

**Pattern extraction date:** 2026-05-27

---

*Phase: 03-design-tokens. Read by `gsd-planner` next; planner authors PLAN.md(s) referencing these excerpts directly in plan actions.*
