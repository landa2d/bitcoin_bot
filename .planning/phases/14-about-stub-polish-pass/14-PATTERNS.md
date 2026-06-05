# Phase 14: About Stub + Polish Pass - Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 3 (1 markup, 2 CSS) — `index.html` `#about-view`, `style-shared.css`, `style-base.css` (token reference only)
**Analogs found:** 5 / 5 surfaces (every net-new/modified surface has an in-cascade analog)

> **Live cascade only.** The live stylesheet order is `style-base.css` (tokens + display classes, first) → `style-shared.css` (component rules), confirmed at `index.html:10-11`. The orphaned `style.css` / `style-builder.css` / `style-impact.css` have NO `<link>` and are EXCLUDED from analog selection and from the radius sweep (their `6px` radii at `style.css:126/136` are out of scope — do NOT edit).
>
> **This is a frontend-only, hand-authored-CSS phase with no build step.** "Pattern assignments" here mean: which existing CSS rule the executor copies token usage / property structure from, plus the exact current state of every literal POLISH-01 must re-anchor. The mockup (`agentpulse-redesign-mockup.html`) is an *intent reference, not markup to copy* — ports go through the analog, not the mockup.

---

## File Classification

| New/Modified Surface | Role | Data Flow | Closest Analog (in live cascade) | Match Quality |
|----------------------|------|-----------|----------------------------------|---------------|
| `#about-view` markup (`index.html:79-86`) | component (static view) | render-only | existing `.about-stub` markup it replaces (`index.html:79-86`) + `.article-header` structure (`style-shared.css:628-643`) | exact (same container) |
| `.about p` / `.body-soft` prose (net-new CSS, `style-shared.css`) | component (serif body prose) | render-only | `article p` (`style-shared.css:597-604`) / `.block-body p` (`:382-390`) | exact (same serif-body role) |
| `.agent-row` / `.agent-pill` / `.an` / `.ad` (NET-NEW CSS, `style-shared.css`) | component (surface-card grid) | render-only | economy-grid `.card` (`style-shared.css:253-266`) + `.grid` (`:243-248`) | role-match (surface card, no left-stripe/hover/link) |
| Radius sweep — 3× `6px` → token (`style-shared.css:765/808/852`) | config (radius normalization) | render-only | `.tab` `var(--radius-sm)` (`style-base.css:163`), `.subscribe` `var(--radius-btn)` (`style-base.css:186`) | exact (role-identical chrome) |
| Vertical-rhythm sweep — loose/off-grid spacing → `--space-*` (`style-shared.css` + `style-base.css`) | config (spacing normalization) | render-only | existing `--space-*` token consumers, e.g. `.article-entry padding: var(--space-lg) 0` (`:140`), `.grid gap: var(--space-md)` (`:246`) | exact (same token vocabulary) |

---

## Pattern Assignments

### 1. `#about-view` markup (component, render-only) — `index.html:79-86`

**Analog (structure to reuse):** the existing `.about-stub` container it replaces + the magazine `.article-header` eyebrow→title rhythm.

**Current stub markup to REPLACE (`index.html:79-86`):**
```html
<div id="about-view" style="display:none">
    <div class="content-area about-stub">
        <p class="eyebrow">What is AgentPulse</p>
        <h1 class="page-title">A multi-agent intelligence platform for the AI agent economy.</h1>
        <p class="about-lede">Autonomous agents ingest and synthesize what is happening across the agent economy; every consequential publication stays gated by human review. <em>Full overview coming in Phase 14.</em></p>
        <a href="#/" class="backlink">&larr; Back to Newsletter</a>
    </div>
</div>
```
**Reuse, do NOT recreate:** the `#about-view` wrapper, `.content-area about-stub` container, `.eyebrow`, `.page-title`, and the `← Back to Newsletter` backlink (`index.html:84` — preserve verbatim, NAV-03). **Replace** the `.about-lede` placeholder line (the `<em>Full overview coming in Phase 14.</em>` text) with: eyebrow ("Behind the Briefing") → `.page-title` ("What is AgentPulse") → page-sub → 3 prose paragraphs → `.agent-row`. Copy is operator-reviewable per D-02/D-03 (see 14-UI-SPEC.md Copywriting Contract).

**Display classes already defined (`style-base.css`) — reuse verbatim, no new CSS:**
```css
.page-title {                                  /* style-base.css:82-88 */
  font-family:var(--serif);
  font-size:clamp(30px, 5vw, 46px);
  font-weight:600;
  line-height:1.12;
  letter-spacing:-.015em;
}
.eyebrow {                                     /* style-base.css:90-97 */
  font-family:var(--mono);
  font-size:11px;
  font-weight:600;
  text-transform:uppercase;
  letter-spacing:.2em;
  color:var(--accent-ink);
}
```

**Container rhythm already defined (`style-base.css:232-248`) — the About stack inherits this:**
```css
.about-stub { padding-top:var(--space-2xl); }            /* :232-234 */
.about-stub .page-title { margin-top:var(--space-md); }  /* :235-237 */
.about-stub .backlink { font-size:12.5px; }              /* :246-248 */
```
Note: `.about-lede` (`style-base.css:238-245`) is the placeholder lede class — once the placeholder paragraph is removed it may become orphaned; the new prose uses `.about p` / `.body-soft` (see #2), not `.about-lede`.

**Page-sub** ("A newsletter written by a multi-agent system") has no existing class — mono 14px/400 `--ink-faint`. Closest existing rule is the magazine `.article-header .byline` (`style-shared.css:637-643`), reuse its exact property set:
```css
.article-header .byline {                      /* style-shared.css:637-643 — page-sub analog */
    font-family: var(--mono);
    font-size: 14px;
    font-weight: 400;
    color: var(--ink-faint);
    margin: var(--space-xs) 0 0;
}
```

---

### 2. `.about p` / `.body-soft` prose (net-new CSS, serif body) — `style-shared.css`

**Analog:** `article p` (the Phase-12 reading-view serif body) — the canonical TYPE-01 serif-body rule the About paragraphs must match.

**Core serif-body pattern to copy (`style-shared.css:597-604`):**
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
The verbatim twin at `.block-body p` (`style-shared.css:382-390`) confirms this is the established pattern ("copies the Phase 12 `article p` serif migration verbatim"). Port it for `.about p`: serif 18px/1.62, `--ink` for P1 primary text / `--ink-soft` for the `.body-soft` P2/P3 (per UI-SPEC Color table), **`margin-bottom: var(--space-md)`** (16px token, not the raw `16px` literal — the executor should land it on the token).

**Inline-link pattern (if About prose links) — copy `article a` (`style-shared.css:663-669`):**
```css
article a {
    color: var(--accent-ink);
    text-decoration: underline;
    text-decoration-thickness: 1px;
    text-underline-offset: 2px;
    text-decoration-color: var(--accent-soft);
}
```

---

### 3. `.agent-row` / `.agent-pill` / `.an` / `.ad` (NET-NEW component) — `style-shared.css`

**Analog:** the economy-grid `.card` (MAP-02 surface card) + its `.grid` container. This is the closest existing surface-card-in-a-grid. **Port the token usage from `.card`/`.grid`, NOT the mockup's dark/standalone `.agent-pill` styles.** Key DIVERGENCES from `.card` are called out below (no left-accent stripe, no hover lift, no link semantics, denser padding).

**Grid-container analog — copy token structure from `.grid` (`style-shared.css:243-248`):**
```css
.grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-md);          /* ← reuse this 16px token gap */
    margin-top: var(--space-sm);
}
```
`.agent-row` target (UI-SPEC §Component Inventory): `display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:var(--space-md); margin:var(--space-lg) 0;` — same `--space-md` gap rhythm as `.grid`, but `auto-fit/minmax` (responsive collapse) instead of the fixed 2-col.

**Surface-card analog — copy token structure from `.card` (`style-shared.css:253-266`):**
```css
.card {
    background: var(--surface);          /* ← reuse: pill bg */
    border: 1px solid var(--line);       /* ← reuse: pill 1px hairline border */
    border-left: 3px solid var(--accent);/* ✗ DROP — no left stripe on .agent-pill (reserved for economy MAP-02) */
    border-radius: var(--radius);        /* → CHANGE to var(--radius-btn) (8px) on .agent-pill */
    padding: 20px 20px 16px;             /* → CHANGE to var(--space-md) var(--space-md) (16px tokens) — off-grid 20px is a POLISH-01 target too */
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    text-decoration: none;               /* ✗ DROP — .agent-pill is not an <a> */
    color: inherit;
    cursor: pointer;                     /* ✗ DROP — static, non-interactive (no hover/click, UI-SPEC Interaction Contract) */
    transition: .18s ease;               /* ✗ DROP — no hover lift */
}
```
**Do NOT port** `.card:hover` (`:286-290`, the translateY lift + shadow) or `.card:focus-visible` (`:292-295`) — the pills are static informational, not links (keeps them visually distinct from the clickable economy cards).

**`.agent-pill` target (UI-SPEC):** `border:1px solid var(--line); border-radius:var(--radius-btn); background:var(--surface); padding:var(--space-md) var(--space-md);`

**`.an` (agent name, mono chrome) — analog is `.card .tile-title` swapped serif→mono.** The mono-label vocabulary already exists in `.section-label` (`style-shared.css:148-156`) / `.brand` (`style-base.css:124-135`). Target: `font-family:var(--mono); font-size:13px; font-weight:600; color:var(--accent-ink);` (13px sits in the locked 11–14px mono band; `--accent-ink` matches the eyebrow/kicker accent role).

**`.ad` (one-line role, serif caption) — analog is `article td` (the 16px serif card-caption step) shrunk to 14px:**
```css
article td {                            /* style-shared.css:717-725 — serif-caption analog */
    padding: 8px 12px;
    border-bottom: 0.5px solid var(--line);
    font-family: var(--serif);
    font-size: 16px;
    font-weight: 400;
    color: var(--ink-soft);
    line-height: 1.45;
}
```
Target `.ad`: `font-family:var(--serif); font-size:14px; color:var(--ink-soft); margin-top:var(--space-xs); line-height:1.4;` (14px is the UI-SPEC-resolved step — serif reading caption, NOT a body paragraph, NOT mono; `--ink-soft` matches `article td`).

**Porting checklist (from UI-SPEC §Component Inventory — enforce all 5):** (1) every color = a `:root` token, no literal hex; (2) radius = `var(--radius-btn)`, not the mockup's `8px` literal; (3) gaps/padding/margins = `--space-*` tokens, not the mockup's `12/14/16/24px` literals; (4) name = mono-chrome / description = serif-reading (TYPE-01/02); (5) no `data-accent` / per-pill tint — all five pills share the single `--accent-ink` (Phase-13 single-accent discipline).

---

### 4. Radius sweep (config, D-05) — 3× `6px` → role token, all in `style-shared.css`

**Analog (the role-correct radius tokens):** chrome already radiused at 7px / 8px in `style-base.css`:
```css
.tab { ... border-radius:var(--radius-sm); ... }   /* style-base.css:163 — inputs/small pills = 7px */
.subscribe { ... border-radius:var(--radius-btn); }/* style-base.css:186 — buttons = 8px */
```

**The THREE off-token literals to snap (exact current state):**

| Element | Selector | Line | Current declaration | Target |
|---------|----------|------|---------------------|--------|
| Subscribe email input | `#subscribe-email` | **765** | `border-radius: 6px;` | `var(--radius-sm)` (7px) |
| Submit button | `#subscribe-btn` | **808** | `border-radius: 6px;` | `var(--radius-btn)` (8px) |
| Secondary button | `.btn-subscribe-secondary` | **852** | `border-radius: 6px;` | `var(--radius-btn)` (8px) |

```css
#subscribe-email {                /* style-shared.css:759-769 */
    ...
    border-radius: 6px;           /* :765 → var(--radius-sm) */
    ...
}
#subscribe-btn {                  /* style-shared.css:801-813 */
    ...
    border-radius: 6px;           /* :808 → var(--radius-btn) */
    ...
}
.btn-subscribe-secondary {        /* style-shared.css:844-854 */
    ...
    border-radius: 6px;           /* :852 → var(--radius-btn) */
    ...
}
```

**Net-new `.agent-pill` radius:** `var(--radius-btn)` (8px) — already on-token, no reconciliation.

**Confirmation gate (D-05):** after the snap, run `grep -n border-radius docker/web/site/style-shared.css docker/web/site/style-base.css` and verify every value is `var(--radius)` / `var(--radius-sm)` / `var(--radius-btn)` / `var(--radius-dot)` (the one `50%` is the brand `.dot` at `style-base.css:140` — allowed). No raw px radius may remain in the live cascade. **All other `border-radius` in the live cascade are already tokenized** (confirmed: `style-shared.css:80/90/119/203/258/515/658/679/685` all use `var(--radius*)`).

---

### 5. Vertical-rhythm sweep (config, D-04) — loose/off-grid spacing → `--space-*`

**Analog (the token vocabulary to land on):** existing `--space-*` consumers, canonically `.article-entry { padding: var(--space-lg) 0; }` (`style-shared.css:140`) and `.grid { gap: var(--space-md); }` (`:246`). Magnitude is the UI-SPEC's call (one step tighter where loose); these are the exact current literals the sweep re-anchors.

**Off-grid / loose literals to re-anchor (exact current state — UI-SPEC §Spacing-sweep table):**

| Surface | Selector / Line | Current declaration | Target token |
|---------|-----------------|---------------------|--------------|
| `#subscribe-section` padding | `style-shared.css:733-734` | `padding: 40px 0;` | `var(--space-xl) 0` → 32px |
| `.content-area` padding | `style-shared.css:130-134` | `padding: 0 0 32px;` + `padding-top: 20px;` | `0 0 var(--space-xl)` + `padding-top: var(--space-lg)` → 32 / 24 |
| `.card` padding | `style-shared.css:258` | `padding: 20px 20px 16px;` | `var(--space-lg) var(--space-lg) var(--space-md)` → 24/24/16 |
| `.tier-label` margin | `style-shared.css:223` | `margin: var(--space-xl) 0 12px;` | `var(--space-xl) 0 var(--space-sm)` → 32/0/8 |
| `.section-label`-family bottom margins | `style-shared.css:768`, `:821` | `margin-bottom: 12px;` / `margin-top: 12px;` | `var(--space-sm)` → 8px |
| In-content H2 margin | `style-shared.css:406` | `margin: 32px 0 12px;` | `var(--space-xl) 0 var(--space-sm)` → 32/0/8 |
| `article h3` bottom margin | `style-shared.css:584` | `margin-bottom: 12px;` | `var(--space-sm)` → 8px |
| `article blockquote` margin | `style-shared.css:656` | `margin: 20px 0;` | `var(--space-lg) 0` → 24px (consistency over micro-tighten — keep reading-view generous) |

Exact current declarations (for executor reference):
```css
.content-area {                   /* style-shared.css:130-134 */
    padding: 0 0 32px;
    border-top: 0.5px solid var(--border);
    padding-top: 20px;            /* :133 — 20px off-grid → var(--space-lg) */
}
#subscribe-section {              /* style-shared.css:733-737 */
    padding: 40px 0;              /* :734 — 40px between xl/2xl → var(--space-xl) */
    ...
}
.tier-label { ... margin: var(--space-xl) 0 12px; }   /* :223 — 12px → var(--space-sm) */
.card { ... padding: 20px 20px 16px; ... }            /* :258 — 20px → var(--space-lg) */
```

**Net-new About spacing (agent-pill block) — all on-token from birth:** `.agent-row gap:var(--space-md)` (16px), `.agent-row margin:var(--space-lg) 0` (24px), `.about p margin-bottom:var(--space-md)` (16px). The eyebrow→title→page-sub→prose stack inherits the existing `.about-stub` rhythm (`style-base.css:232-237`).

**Hairline exemption (UI-SPEC):** the `0.5px` borders (`.content-area:132`, `#subscribe-section:736`, `.bottom-bar:833`, `#subscribe-email:764`) are border *widths*, not spacing — exempt from the 4px rule (same exemption Phase 11 took for `1px`). Optional `0.5px`→`1px` normalization is out of POLISH-01's required scope.

**Already-conformant (do NOT touch):** Phase-11 chrome paddings `.tab 8px 12px` (`style-base.css:162`), `.subscribe 8px 16px` (`:187`), `.nav 12px var(--space-lg)` (`:118`) are 4px-conformant and locked.

---

## Shared Patterns

### Token-only authoring (applies to ALL net-new + swept CSS)
**Source:** `style-base.css:10-66` (`:root`)
**Apply to:** every rule the executor adds or edits — no literal hex, no raw px radius, no off-grid spacing literal.
```css
:root {
  --bg:#faf8f5; --surface:#ffffff;
  --ink:#1a1916; --ink-soft:#55514a; --ink-faint:#8a857c;
  --line:#e7e2da; --line-strong:#d8d2c7;
  --accent:#5b3df5; --accent-soft:#efeaff; --accent-ink:#4a2fd6;
  --serif:'Source Serif 4', Georgia, serif;
  --mono:'IBM Plex Mono', ui-monospace, monospace;
  --space-xs:4px; --space-sm:8px; --space-md:16px; --space-lg:24px;
  --space-xl:32px; --space-2xl:48px; --space-3xl:64px;
  --radius:10px; --radius-sm:7px; --radius-btn:8px; --radius-dot:3px;
}
```

### Single-accent discipline (COLOR-02)
**Source:** Phase-13 economy grid — single `--accent` / `--accent-ink`, no `data-accent`, no per-tier/per-card tint (`style-shared.css:184-185` note, `.card` uses one `--accent` stripe).
**Apply to:** `.agent-pill` roster — all five `.an` names use the SAME `--accent-ink`; no per-agent color. The accent appears only on the eyebrow + the five pill names (the one net-new accent surface, justified in UI-SPEC §Color item 8). Description (`.ad`) and pill border stay neutral `--ink-soft` / `--line`.

### Serif-reading vs mono-chrome split (TYPE-01/02)
**Source:** `article p` serif body (`style-shared.css:597`) vs `.section-label` / `.brand` mono chrome (`style-shared.css:148`, `style-base.css:124`).
**Apply to:** About prose + `.ad` = serif (reading content); `.an` + eyebrow + page-sub = mono (UI chrome). No monospace body, no serif chrome — exactly 2 weights (400 / 600).

### Cascade-order / hand-authored CSS convention
**Source:** `index.html:10-11` (`style-base.css` first, `style-shared.css` second).
**Apply to:** all new rules land in `style-shared.css` (the component layer); `style-base.css` is edited only for token-referenced spacing literals if any chrome padding is in scope (none required this phase). No build step — edits are direct. Section placement within `style-shared.css` is mechanical planner discretion.

---

## No Analog Found

None. Every surface has an in-cascade analog:
- The net-new `.agent-pill` maps to economy-grid `.card` + `.grid` (role-match: surface card in a grid).
- The net-new `.about p` / page-sub / `.ad` map to `article p` / `.article-header .byline` / `article td` respectively (exact serif-body / mono-metadata / serif-caption roles).
- Both POLISH-01 sweeps re-anchor existing literals onto the existing `:root` token set — no novel pattern.

---

## Metadata

**Analog search scope:** `docker/web/site/` live cascade only — `style-base.css` (248 lines, read in full), `style-shared.css` (884 lines, targeted reads of `.content-area`/`.section-label`/`.tier-label`/`.grid`/`.card`, `.block-body`/`article` prose, `#subscribe-*` form, `.btn-subscribe-secondary`), `index.html` (`#about-view` markup + cascade `<link>`s).
**Files scanned:** 3 (2 CSS + 1 HTML). Orphaned `style.css`/`style-builder.css`/`style-impact.css` deliberately excluded (not in cascade).
**Pattern extraction date:** 2026-06-05
