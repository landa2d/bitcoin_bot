# Phase 22: Per-Section Visual Fixes - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 4 modified (`app.js`, `index.html`, `style-shared.css`, `style-base.css`) + 3 net-new artifacts (maturity legend, About `made-cols`, `.approval` callout)
**Analogs found:** 7 / 7 — every change has an in-codebase analog; the mockup supplies FORM only (token-mapped, never copied verbatim)

> Frontend-only phase. Single hand-authored CSS, no build step. `style-base.css` loads first (`:root` tokens + serif body win the cascade); `style-shared.css` is the legacy component layer. **RHYTHM-01:** token-only color — the mockup's `--violet` / `--violet-soft` / `--line-soft` / hardcoded `#2d2585` do NOT exist in prod; map to `--accent` / `--accent-soft` / `--line` (see Shared Patterns → Token Mapping). All DB-derived strings stay `escapeHtml`'d; no stored-data mutation.

## File Classification

| Modified file / Net-new artifact | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app.js` `renderArticle` header (HEAD-01) | component (DOM string builder) | transform (render) | itself — `.article-header` at `app.js:430-435` (drop eyebrow line) | exact (self-edit) |
| `app.js` `getModeTitle` suffix strip (HEAD-01) | utility (accessor) | transform | itself — `getModeTitle` at `app.js:563-566` (add defensive regex) | exact (self-edit) |
| `app.js` `renderHub`/`tierSection` legend insert (GRID-02) | component | transform (render) | `renderMaturityPill` at `app.js:578-590` (5-seg pill) | exact |
| `style-shared.css` `.grid` 2→3 col + breakpoints (GRID-01) | config (CSS rule) | n/a | existing `.grid` `:261-266` + `@640px` `:339-343` | exact (self-edit) |
| Net-new maturity **legend** markup + `.legend` CSS (GRID-02) | component + config | transform | `renderMaturityPill` markup `:587-589` + `.maturity-pill`/`.seg` CSS `:192-212` | exact |
| `index.html` `#about` `made-cols` rewrite (AGENTS-01) | component (static markup) | n/a | existing `.agent-row` markup `index.html:131-152` | role-match (restructure) |
| Net-new `made-cols`/`.agent`/`.idx`/`.dot`/`.approval` CSS (AGENTS-01) | config (CSS rule) | n/a | `.agent-row`/`.agent-pill`/`.an`/`.ad` CSS `:921-958` | role-match (port tokens) |

---

## Pattern Assignments

### HEAD-01 — `renderArticle` header de-dup + `getModeTitle` strip (`app.js`, component+utility, transform)

**Analog:** itself — the change is a deletion (drop eyebrow) + a defensive regex add. No external pattern needed; the byline already carries everything.

**Current header builder** (`app.js:428-435`) — the **exact strip site**. Line `:432` (the `.eyebrow`) is DROPPED; line `:434` (the `.byline`) is KEPT verbatim (D-01/D-02):
```javascript
var sep = ' ' + String.fromCharCode(0xB7) + ' ';          // U+00B7 middot
var modeLabel = MODES[currentMode].label;                 // 'Technical' | 'Strategic' — resolved, never hardcoded
var header =
    '<div class="article-header">' +
        '<p class="eyebrow">Edition #' + data.edition_number + sep + modeLabel + '</p>' +   // ← :432 DELETE THIS LINE
        '<h1 class="page-title">' + escapeHtml(title) + '</h1>' +                            // ← H1 = headline only
        '<p class="byline">Edition #' + data.edition_number + sep + date + sep + modeLabel + '</p>' +  // ← :434 KEEP verbatim
    '</div>';
```

**Title source** (`app.js:563-566`) — the strip applies HERE so it covers BOTH `data.title` and `data.title_impact` (D-03). Apply the regex unconditionally (no-op when absent):
```javascript
function getModeTitle(data) {
    if (currentMode === 'strategic' && data.title_impact) return data.title_impact;
    return data.title;
}
```
- `title` flows into the H1 via `var title = getModeTitle(data);` at `renderArticle` `app.js:409`, then `escapeHtml(title)` at `:433`. Stripping inside `getModeTitle` is the single chokepoint for both modes — escape order is preserved (strip the raw string, THEN `escapeHtml`).
- **D-04 (Phase-19 discipline):** confirm the stored `newsletters.title` / `title_impact` bytes for a known edition (e.g. 30) BEFORE writing the regex. Brief's ` — Edition #\d+ \| .*$` is a STARTING pattern, not confirmed — match the real separator (em-dash vs `—`, `|` vs `·`, date format). No storage mutation.

**CSS — no change.** `.article-header .eyebrow` (`style-shared.css:649-651`) becomes dead (harmless); `.article-header .page-title` `:652-654` and `.article-header .byline` `:655-661` are unchanged. The `.article-header { margin-bottom: var(--space-xl) }` `:646-648` wrapper stays.

---

### GRID-01 — tier grid 2→3 col + responsive breakpoints (`style-shared.css`, config)

**Analog:** itself — column-count + breakpoint change, NOT a rebuild (the card grid is fully built). Markup (`renderHub`/`tierSection`/`renderTile`, `app.js:726-803`) does NOT change.

**Current grid** (`style-shared.css:261-266`) — change `repeat(2, 1fr)` → `repeat(3, 1fr)` (D-06):
```css
.grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);   /* → repeat(3, 1fr) */
    gap: var(--space-md);
    margin-top: var(--space-sm);
}
```

**Current collapse rule** (`style-shared.css:339-343`) — the single `@640px` 1-col rule is REPLACED by 3→2 (≤880px) → 1 (≤600px). Planner's call whether to consolidate here or add media queries (D-06 / discretion):
```css
@media (max-width: 640px) {
    .grid {
        grid-template-columns: 1fr;
    }
}
```
- Mockup target (`agentpulse-redesign (1).html:171-173, 216-217, 224`): `.map-grid` is `repeat(3,1fr)` desktop → `repeat(2,1fr)` `@880px` → `1fr` `@600px`. Same shape, mapped onto the prod `.grid` class.

**`.card-deferred` stays full-width** (`style-shared.css:317-319`) — D-08, KEEP unchanged; `frame`/`regulation-legal` spans all 3 columns:
```css
.card-deferred {
    grid-column: 1 / -1;
}
```
- The `behavior` tier has 4 blocks → wraps 3+1 in 3-col (acceptable, mockup does the same). Deferred detection (`!b.current_body_version_id`, `app.js:734`) is UNCHANGED.

---

### GRID-02 — maturity legend (net-new markup + `.legend` CSS; component+config, transform)

**Analog:** `renderMaturityPill` markup + `.maturity-pill`/`.seg` CSS. The legend is a STATIC 5-seg copy of the real pill + label — that equality IS the requirement (D-07). NOT the mockup's 3-bar sketch.

**Pill markup to mirror** (`app.js:587-589`) — exactly 5 `.seg`; a legend at `data-stage="1"` shows `■ □ □ □ □`:
```javascript
return '<div class="maturity-pill" data-stage="' + stage + '" aria-label="' + label + '">' +
           '<span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span>' +
       '</div>';
```

**Pill CSS the legend's scale must equal** (`style-shared.css:192-212`):
```css
.maturity-pill { display: inline-flex; gap: var(--space-xs); vertical-align: middle; }
.maturity-pill .seg {
    display: inline-block; width: 18px; height: 8px;
    background: var(--line-strong); border: none; border-radius: var(--radius-dot);
}
.maturity-pill[data-stage="1"] .seg:nth-child(-n+1) { background: var(--accent); border-color: var(--accent); }
/* …2,3,4 … */
.maturity-pill[data-stage="5"] .seg:nth-child(-n+5) { background: var(--accent); border-color: var(--accent); }
```

**Insert site** — the `.prose` hub header trio (`app.js:795-800`); legend goes ONCE under the `page-title`, INSIDE `.prose`, NOT per-tier (D-07):
```javascript
var html =
    '<div class="prose">' +
        '<h1 class="page-title">The Agent Economy</h1>' +
        subline +                       // ← legend inserts here (after title, before/after subline — planner's call)
        hubIntroHtml +
    '</div>' +
    tierSection(TIER_LABELS.substrate, substrateBlocks) +   // grids render OUTSIDE .prose on the wide band
    tierSection(TIER_LABELS.behavior, behaviorBlocks) +
    tierSection(TIER_LABELS.frame, frameBlocks);
```

**Legend FORM reference** (mockup `agentpulse-redesign (1).html:369-375` markup, `:158-165` CSS) — port the LABEL/layout idea but emit a **real 5-seg `.maturity-pill data-stage="1"`** (not the mockup's `.bar`), so the legend's scale literally matches the cards:
```css
/* mockup .legend CSS — FORM only; map --violet → --accent, keep mono/uppercase chrome */
.legend { display:flex; align-items:center; gap:14px; margin-top:16px;
          font-family:var(--mono); font-size:11px; letter-spacing:.08em;
          text-transform:uppercase; color:var(--ink-faint); }
```
- New class name (e.g. `.legend`) is Claude's discretion (D-07). Form: `Maturity  ■ □ □ □ □   nascent → established`. Use `--space-*` tokens for gap, `--mono`/`--ink-faint` for the labels (matches `.tier-label` chrome at `:217-225`). The 5 segments reuse `.maturity-pill`/`.seg` — do NOT invent a second bar system.
- **D-09:** fill comes from stored `MATURITY_STAGE[b.maturity]` (`app.js:583`); "fill matches stored value" is ALREADY TRUE. No schema change, no new query — `renderHub`'s single `sb.schema('economy_map')` read (`app.js:609-613`) is unchanged.

---

### AGENTS-01 — About grid → `made-cols` (`index.html` markup + net-new CSS; component+config)

**Analog (markup):** existing `.agent-row` block (`index.html:131-152`) — same `name + description` data, restructured into pipeline (numbered) + supporting (bulleted) columns.

**Current About markup** (`index.html:131-152`) — the uniform 5-pill row REPLACED by `made-cols`:
```html
<div class="wide">
    <div class="agent-row">
        <div class="agent-pill">
            <span class="an">Processor</span>
            <span class="ad">Background scheduler — scrapes sources, runs the pipelines, and posts.</span>
        </div>
        <!-- Analyst / Research / Newsletter / Gato — 5 uniform pills -->
    </div>
</div>
```

**De-dup site** (`index.html:126`) — D-11: pull the "nothing is published without human approval" clause OUT of intro P2 once it lives in the `.approval` callout:
```html
<p class="body-soft">…Every model call is metered against a per-agent wallet, so the cost of producing an edition is itself part of what we track — and nothing is published without human approval.</p>
```

**Target shape** (mockup `agentpulse-redesign (1).html:429-490`) — LEFT numbered 01–04 pipeline (Processor/Analyst/Research/Newsletter), RIGHT bulleted supporting (Gato/LLM proxy/web front end), + violet `.approval` callout (D-10):
```html
<div class="made-cols">
  <div>
    <p class="made-head">The pipeline · in order</p>
    <div class="agent"><span class="idx">01</span><span><p class="name">Processor</p><p class="desc">…</p></span></div>
    <!-- 02 Analyst / 03 Research / 04 Newsletter -->
  </div>
  <div>
    <p class="made-head">The supporting layer</p>
    <div class="agent"><span class="dot"></span><span><p class="name">Gato</p><p class="desc">…</p></span></div>
    <!-- LLM proxy / web front end -->
    <div class="approval"><strong>Nothing publishes without human approval.</strong> Every edition is drafted by the system and shipped only after an operator signs off.</div>
  </div>
</div>
```

**Analog (CSS) — port token-anchored styling from** `.agent-row`/`.agent-pill`/`.an`/`.ad` (`style-shared.css:921-958`). These already prove the token discipline; the new `.agent`/`.idx`/`.name`/`.desc` rules inherit the same `--mono` name / `--serif`-or-soft desc / `--ink-*` colors:
```css
.agent-row {                                   /* :923 — analog for .made-cols grid container */
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: var(--space-md);
    margin: var(--space-lg) 0;
}
.agent-pill { border: 1px solid var(--line); border-radius: var(--radius-btn);  /* :933 */
    background: var(--surface); padding: var(--space-md); display: flex; flex-direction: column; }
.agent-pill .an { font-family: var(--mono); font-size: 13px; font-weight: 600; color: var(--accent-ink); }  /* :943 — name */
.agent-pill .ad { font-family: var(--serif); font-size: 14px; font-weight: 400;  /* :951 — desc */
    color: var(--ink-soft); margin-top: var(--space-xs); line-height: 1.4; }
```

**FORM reference** (mockup `:188-204`) — port to tokens (RHYTHM-01), do NOT copy hardcoded values:
```css
.made-cols { display:grid; grid-template-columns:1fr 1fr; gap:0 48px; margin-top:1.5rem; }   /* gap → --space-2xl */
.agent { display:grid; grid-template-columns:26px 1fr; gap:0 14px; align-items:baseline;
         padding:14px 0; border-bottom:1px solid var(--line-soft); }                          /* --line-soft → --line */
.agent .idx  { font-family:var(--serif); font-size:14px; color:var(--ink-faint); }
.agent .dot  { width:6px; height:6px; border-radius:50%; background:var(--violet); display:inline-block; }  /* --violet → --accent */
.agent .name { font-family:var(--mono); font-size:14px; font-weight:500; margin:0; }
.agent .desc { font-size:14px; color:var(--ink-soft); margin:3px 0 0; line-height:1.5; }
.approval { margin-top:2.25rem; padding:18px 20px; background:var(--violet-soft);            /* --violet-soft → --accent-soft */
            border-radius:12px; font-size:15px; color:#2d2585; line-height:1.55; }            /* #2d2585 → --accent-ink OR new token */
```
- Collapses 2-col → 1-col `@880px` (mockup `:218`). Prod mobile breakpoint precedent: `@media (max-width: 600px)` at `style-shared.css:962`.
- **D-12 (operator accuracy review):** mockup folds Gato Brain into "Gato". v2.0 locked "eight cooperating services" + Gato (Telegram) vs Gato Brain (middleware). Use the mockup's draft copy but SURFACE the Gato/Gato-Brain wording + service-count as an operator-reviewable point at plan/verify — do not silently drop Gato Brain. Copy only; structure (pipeline/supporting split) is locked.

---

## Shared Patterns

### Token Mapping (RHYTHM-01 — applies to ALL net-new CSS)
**Source of truth:** `style-base.css:13-21` `:root`. The mockup's palette tokens DO NOT exist in prod — map every one:

| Mockup token / literal | Prod token (`style-base.css`) | Where it bites |
|---|---|---|
| `--violet` | `--accent` (#5b3df5, `:19`) | `.bar.on`, `.dot`, hover |
| `--violet-soft` | `--accent-soft` (#efeaff, `:20`) | `.approval` background |
| `#2d2585` (hardcoded) | `--accent-ink` (#4a2fd6, `:21`) — OR add a token **only if needed** | `.approval` text color |
| `--line-soft` | `--line` (#e7e2da, `:17`) or `--line-strong` (`:18`) | `.agent` border-bottom |
| `48px`, `26px`, `14px`, `1.5rem` (raw px) | `--space-2xl`/`--space-lg`/`--space-md`… (`:57-63`) | all gaps/padding |

Confirmed absent in prod: NO `--violet`, NO `--violet-soft`, NO `--line-soft`. `style-base.css:11` comment: "ONE violet accent (COLOR-01/02)". The `.approval` `#2d2585` is the ONLY genuine RHYTHM-01 risk (no exact token) — planner adds a token or uses `--accent-ink` per D-07/discretion.

### Resolved-constant labels (no hardcoding)
**Source:** `MODES` (`app.js:11-26`), `MATURITY_STAGE` (`:38`), `TIER_LABELS` (`:41`).
**Apply to:** HEAD-01 byline (`MODES[currentMode].label` → 'Technical'/'Strategic', already at `app.js:429,434`); GRID-02 legend fill (`MATURITY_STAGE`). Reuse the constants — never re-hardcode the labels.

### escapeHtml on every DB string
**Source:** `escapeHtml` (`app.js:542-546`).
**Apply to:** any DB-derived string written into markup (titles, block titles/subtitles). Already applied at `app.js:433,742,743`. HEAD-01: strip the raw title in `getModeTitle` FIRST, then `escapeHtml` at the H1 sink. Legend/About labels are static literals — no escape needed, but keep the idiom for any dynamic value.

### `.prose` (narrow) vs `.wide` (tiled) axes
**Source:** Phase-20 axes — `.prose`/`.wide` + `--measure`/`--wide`/`--gutter` (`style-base.css:112+`).
**Apply to:** GRID-02 legend goes INSIDE the `.prose` header wrap (`app.js:796-800`); tier grids stay OUTSIDE on the wide band (`:801-803`). AGENTS-01 intro prose stays in `.prose` (`index.html:120-129`); `made-cols` sits in the `.wide` block (`index.html:130`). Do NOT regress the Phase-20 width axes or Phase-21 scroll-spy.

---

## No Analog Found

None. Every change has an in-codebase analog:
- HEAD-01 → self-edit of `renderArticle`/`getModeTitle`.
- GRID-01 → self-edit of `.grid` + `@640px`.
- GRID-02 legend → `renderMaturityPill` + `.maturity-pill`/`.seg`.
- AGENTS-01 → `.agent-row`/`.agent-pill`/`.an`/`.ad` (port) + mockup FORM (token-mapped).

The mockup is FORM reference only — its placeholder taxonomy (Discovery/Orchestration), palette tokens, and raw-px values are NOT adopted; canonical block list comes from `economy_map`, copy from the operator accuracy bar.

## Metadata

**Analog search scope:** `docker/web/site/` (`app.js`, `index.html`, `style-shared.css`, `style-base.css`) + `.planning/docs/agentpulse-redesign (1).html` (FORM reference).
**Files scanned:** 5
**Line numbers verified:** all citations confirmed against live files. Corrections vs CONTEXT: legend insert `.prose` block is `app.js:795-800` (confirmed); CONTEXT's `app.js:430-435` header is `:430-435` (confirmed, eyebrow `:432`, byline `:434`); `style-shared.css:921-958` About analog (confirmed); `index.html:131-152` agent-row (confirmed); intro-P2 approval clause at `index.html:126` (confirmed).
**Pattern extraction date:** 2026-06-11
