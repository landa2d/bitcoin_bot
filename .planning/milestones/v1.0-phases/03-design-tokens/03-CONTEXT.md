# Phase 3: Design Tokens - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the minimal CSS (and at most a small vanilla-JS pill helper) that encodes the three information-bearing visual elements — **tier accent colors**, the **maturity pill component**, and the **timeline entry format** — as shared assets the Phase 4 renderer will consume. No bespoke typography, no page chrome; everything else inherits the existing `docker/web/site/` defaults (Courier New body, Georgia headlines, container max-width 720px). The phase delivers (a) a deployable stylesheet/JS asset, (b) a `body.technical` + `body.strategic` mode resolution for tier accents, and (c) a standalone preview that proves the tokens render correctly before Phase 4 wires them into hash routes.

**Out:** Hub/block/status page layouts (Phase 4), Supabase queries (Phase 4), the seven-block visual shape on the hub beyond the per-block pill + tier accent (Phase 4), any Telegram command surfacing or operator UX (Phases 6/9/10).

</domain>

<decisions>
## Implementation Decisions

### Mode integration (the visual frame Phase 4 consumes)
- **D-01:** Block, hub, and status pages **inherit both existing body modes** (`body.technical` — dark `#0a0a0f` bg, mint `#00e5a0` mode-accent; `body.strategic` — white bg, purple `#7c3aed` mode-accent) and **show the existing mode toggle** in the same position as on edition pages. The user's reading-mode preference carries across editions and the map; the map is not a separately-themed surface.
- **D-02:** **Scope of tier accent replacement:** on a single block page (`/map/<slug>`), the tier accent replaces the mode `--accent` throughout the page (title, pill, section labels, links, hover). On the **hub and status pages** where all seven blocks coexist, the tier color appears only on each block's **pill + tile border**; page chrome (top nav, mode toggle, body type colors) stays mode-default. Rationale: avoids visual cacophony on multi-block surfaces; preserves "this is one product" feel.
- **D-03:** **Two-variant tier tokens** ship to handle the contrast asymmetry between the pinned hex (calibrated for white) and the dark technical-mode background. Each tier gets a `-base` variable (the pinned hex from TOKN-01, used in light/strategic mode) **and** a `-on-dark` variable (a brighter/lighter variant used in technical mode). A single `--accent-tier` resolves to the right variant via `body.technical [data-tier="..."]` and `body.strategic [data-tier="..."]` selectors. The pinned `TOKN-01` hex values are honored verbatim on the surface they were designed for; legibility on dark is preserved.

### Tier accent application contract (mechanism for Phase 4)
- **D-04:** Phase 4 sets the block tier on a wrapper element via `data-tier="substrate|behavior|psychology|frame"`. Phase 3 ships CSS rules of the form `[data-tier="substrate"] { --accent-tier: var(--accent-teal); } body.technical [data-tier="substrate"] { --accent-tier: var(--accent-teal-on-dark); }` — Phase 4 does not compute colors, it just sets the tier attribute.
- **D-05:** Mapping of block tier → accent variable:
  - `substrate` → `--accent-teal` (`#0F6E56` base; on-dark variant TBD by planner/executor — pick a lighter/desaturated teal that maintains WCAG AA against `#0a0a0f`)
  - `behavior` → `--accent-purple` (`#534AB7` base; on-dark variant TBD same constraint)
  - `psychology` → `--accent-coral` (`#993C1D` base; on-dark variant TBD same constraint)
  - `frame` → `--accent-gray` (`#5F5E5A` base; on-dark variant TBD same constraint)
  - **Note for planner/executor:** the seeded block table (Phase 2 D-23) assigns `psychology-disposition` to the `behavior` tier *for taxonomy purposes* but the spec (§1) explicitly says "Psychology = coral (deliberately distinct)". Phase 3 must honor the **color-by-block-slug** override: `payments-settlement`, `identity-trust`, `memory-context` → teal; `autonomy-control`, `governance-accountability` → purple; `psychology-disposition` → **coral** (overriding its behavior tier); `regulation-legal` → gray. The simplest expression is `data-accent="teal|purple|coral|gray"` on the wrapper, populated by Phase 4 from `blocks.accent` (which is already seeded per Phase 2 D-23). Use `data-accent`, not `data-tier`, as the CSS selector.
- **D-06:** The existing edition pages (`#list-view`, `#reader-view`) are unaffected by Phase 3 changes. Tier-accent rules apply only inside elements carrying `data-accent`; pages without that attribute see the existing `body.technical`/`body.strategic` `--accent` unchanged.

### Carrying forward from Phase 1 + Phase 2
- **D-07:** Map pages will be added as **hash routes** in the existing `docker/web/site/app.js` (no new Caddyfile route, no new container) per Phase 1 §3 + §5. Phase 3's CSS must therefore work as a stylesheet linked from the same `index.html` that the SPA already uses, OR loaded conditionally on map routes (see D-09 for the file-organization default).
- **D-08:** The existing dark/light mode variables in `style-shared.css` (`--accent`, `--bg`, `--text-primary`, `--text-secondary`, `--border`) are the reference pattern for how Phase 3's tier accent should layer in. The new `--accent-tier` is the only override; everything else (background, body text color, borders) inherits the body-mode variables — `TOKN-04` honored.

### Claude's Discretion
The user opted to capture the three remaining gray areas as reasoned defaults the planner can revisit. These are open implementation decisions with sensible starting points:

- **Token file organization (D-09):** Default — ship a new `docker/web/site/style-map.css` containing the four tier tokens, the maturity-pill rules, the timeline-entry rules, and the `data-accent` selectors. Loaded via a new `<link>` tag in `index.html` alongside `style-shared.css` (or, if the planner prefers, only included on map routes via a JS-driven `<link>` injection — pick whichever is simpler to verify). Rationale: keeps the existing 518-line `style-shared.css` focused on the chrome that *every* page uses; isolates map-specific tokens for easier future v2 refactor; avoids any risk of accidentally affecting edition pages. Planner may instead choose to extend `style-shared.css` if the savings are negligible and the loaded-everywhere posture is preferred — that choice is on the table.
- **Maturity pill component shape (D-10):** Default — **CSS-only with data attributes**. Markup contract: `<div class="maturity-pill" data-accent="teal" data-stage="3" aria-label="Maturity: contested (3 of 5)"><span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span></div>`. CSS uses `[data-stage="3"] .seg:nth-child(-n+3) { background: var(--accent-tier); }` patterns. No JS helper required — Phase 4 just emits the five `<span>` segments and sets the two data attributes. Rationale: matches existing vanilla-JS-no-build-step posture; trivially testable in the standalone preview; no runtime dependency. Planner may add a `renderMaturityPill(slug, accent, stage)` helper in `app.js` if it reduces duplication across hub/block/status — but the CSS contract stays the same.
- **Standalone preview deliverable (D-11):** Default — `docker/web/site/tokens-preview.html` is a deployable, standalone HTML file (not behind a hash route) that imports `style-shared.css` + `style-map.css` and renders every token surface: a 4×2 grid of tier accent swatches (light + dark mode), all 5 maturity-pill states for each of the 4 accents, three sample timeline entries (one normal, one with `source_url=NULL` to show graceful degradation, one with very long `why_it_mattered` to show wrap behavior), and a body-mode toggle button identical to edition pages. Accessible at `aiagentspulse.com/tokens-preview.html` for the operator to spot-check, and used as the verification artifact for ROADMAP success criterion 1. Rationale: deployable means the operator can review it on the real Caddy stack, not just locally; isolated path keeps it off the SPA hash router. Planner may instead choose an out-of-tree preview under `.planning/phases/03-design-tokens/preview.html` if shipping a preview page to production feels wrong — but the deployable option lets the operator review on the real surface and avoids a separate verification step.

Other Claude discretions for the planner:
- Exact on-dark hex values for each tier (D-05 lists the constraint: WCAG AA against `#0a0a0f`; pinned-base hue preserved). Pick numerically and document in the planning artifact.
- Whether the maturity pill segments are separated by a gap or share a border (visual nicety; pick one and apply consistently).
- Empty-source rendering for timeline entries: default — when `source_url` is null/empty, omit the `[source ↗]` link entirely and let `<why_it_mattered>` occupy the full second line. Document this in the CSS as a `:not([data-source])` rule or equivalent.
- Whether the `↗` glyph is the literal Unicode character (U+2197) or a Unicode-with-fallback strategy — pinned spec says `↗`, prefer the literal.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Build spec (source of truth)
- `.planning/docs/economy-map-build-spec-v2.md` §8 — Design tokens: pinned hex values (8.1), maturity-pill semantics + "single source of truth across hub/block/status" (8.2), timeline entry format (8.3), "everything else inherits" constraint (8.4).
- `.planning/docs/economy-map-build-spec-v2.md` §1 — Tier → accent mapping including the deliberate `psychology = coral` override (Psychology is in the Behavior taxonomy but gets coral, not purple — see D-05).
- `.planning/docs/economy-map-build-spec-v2.md` §6 — Renderer contract; Phase 3 ships the tokens Phase 4 consumes.

### Project / milestone context
- `.planning/PROJECT.md` — "Constraints" section pins the no-build-step / vanilla-JS+CSS posture for the web service. "Out of scope" pins "bespoke typography / page chrome for v1".
- `.planning/REQUIREMENTS.md` §"Design tokens (v1 — only what encodes information)" — `TOKN-01..04`: tier accents, maturity pill, timeline format, inheritance. These are the formal requirements for this phase.
- `.planning/ROADMAP.md` §"Phase 3: Design Tokens" — Goal, dependency (Phase 1), four success criteria (SC1 = standalone preview; SC2 = pill shared; SC3 = timeline pinned; SC4 = no bespoke typography), `UI hint: yes`.

### Phase 1 outputs (immediately upstream)
- `.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md` §3 — Confirms block pages are added as hash routes in the existing `docker/web/site/app.js` (no sibling route). Phase 3 CSS must work in that context.
- `.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md` §5 — Bridge to Phase 4; explicitly states "CSS / token integration depends on Phase 3 landing first — Phase 3 ships the maturity pill component and tier accent CSS variables; Phase 4 consumes them."

### Phase 2 outputs (data shape)
- `.planning/phases/02-economy-map-schema-seven-block-seed/02-CONTEXT.md` D-23 — Seven blocks' tier + accent column values (`teal|purple|coral|gray`). Phase 3's `data-accent` selectors must accept these exact strings.

### Existing codebase (the assets being extended)
- `docker/web/site/style-shared.css` (518 lines) — The reference stylesheet. Lines 7–49 define the `body.technical` and `body.strategic` variable blocks Phase 3 layers onto. Lines 51–57 set the global body font + container width Phase 3 inherits per `TOKN-04`.
- `docker/web/site/index.html` (77 lines) — The single shell document. Phase 3 adds a new `<link rel="stylesheet" href="/style-map.css">` here (or via JS injection on map routes per D-09).
- `docker/web/site/app.js` (314 lines) — The SPA. Phase 3 doesn't modify it; Phase 4 will. The mode-toggle handler (`setMode` function called from `index.html` line 27) is the existing pattern Phase 3 preserves.
- `docker/web/Caddyfile` — SPA fallback `try_files {path} /index.html`. A standalone `/tokens-preview.html` (if shipped per D-11) is matched as a static file *before* the fallback fires, so it serves directly without the SPA — confirmed by Phase 1 §1.
- `docker/web/entrypoint.sh` — Runtime `sed` substitution for `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` in `app.js`. Phase 3's preview page does not need Supabase credentials; tokens render from static markup.

### Style precedents (to mirror, not copy verbatim)
- `docker/web/site/style.css` (160 lines), `style-builder.css` (153 lines), `style-impact.css` (153 lines) — Existing per-mode stylesheet pattern. Phase 3's new `style-map.css` follows the same conventions (CSS variables on `:root` or body classes, no preprocessor, no autoprefixer).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`body.technical` / `body.strategic` variable blocks** in `style-shared.css` (lines 7–49) are the reference for how mode-dependent variables work. The new `--accent-tier` resolution uses the same pattern: a `--accent-tier` rule under each body class for each `[data-accent="..."]` element.
- **The existing `--accent` variable** (`#00e5a0` technical, `#7c3aed` strategic) is left untouched for chrome elements (nav dot, subscribe button, edition page accents). Phase 3 introduces `--accent-tier` as an *additional* variable scoped to map-page wrappers, not a replacement for `--accent`.
- **Container max-width 720px** (`style-shared.css` line 60) and **Courier New body / Georgia headlines** (lines 52, 142) are inherited verbatim per `TOKN-04` — Phase 3 adds **no typography rules**.
- **The mode toggle** (HTML at `index.html` lines 25–28; CSS at `style-shared.css` lines 159–184; JS at `app.js` `setMode`) is the existing user-facing mode-switch contract. Phase 3 preserves it on map pages — no new toggle component, no hiding.

### Established Patterns
- **No build step, no preprocessor.** The site is plain HTML + vanilla JS + plain CSS. Phase 3 follows: no Sass, no PostCSS, no CSS modules. Just CSS custom properties and class selectors.
- **CSS custom properties layered by body class.** `body.technical { --accent: ... }` and `body.strategic { --accent: ... }` is the established mechanism for mode-dependent theming. Phase 3 uses the same mechanism, scoped to `data-accent` elements.
- **Per-feature stylesheet.** `style.css`, `style-builder.css`, `style-impact.css` are loaded per-edition-type. Phase 3 adds `style-map.css` following the same precedent.

### Integration Points
- **`index.html` `<head>` block** — one new `<link rel="stylesheet" href="/style-map.css">` tag added before `app.js` runs. The `<link>` always loads (it's small and gated by `data-accent` selectors so it never affects non-map pages).
- **Phase 4's `app.js` hash route handlers** — when Phase 4 lands `getRoute()` branches for `#/map`, `#/map/<slug>`, `#/status`, it will emit DOM nodes with `data-accent="teal|purple|coral|gray"` and `data-stage="1..5"` attributes. Phase 3's CSS is the contract that turns those attributes into visible tokens.
- **No changes to existing files in Phase 3**, beyond a single `<link>` line in `index.html`. New files: `style-map.css`, `tokens-preview.html` (per D-11 default).

</code_context>

<specifics>
## Specific Ideas

- **The `psychology = coral` override is a spec-level deliberate choice** (build spec §1: "Psychology = coral (deliberately distinct — it is the block that differentiates this map)"). The planner must implement coloring keyed off `blocks.accent` column values (per Phase 2 D-23: `teal|purple|coral|gray`), **not** off `blocks.tier` — otherwise Psychology would render purple. Use `data-accent="..."` on the wrapper, populated from `blocks.accent`. This is the kind of detail downstream agents will get wrong if not surfaced loudly.
- **The on-dark variants are Claude's discretion but constrained.** The planner picks specific hex values that (a) preserve the pinned-base hue family, (b) clear WCAG AA contrast against `#0a0a0f` (the technical-mode background — contrast ratio ≥ 4.5:1 for text use, ≥ 3:1 for large or non-text use including pill segments). Document the chosen values + their measured contrast in the PLAN.md so future audits can verify.
- **The standalone preview is the verification artifact for SC#1.** It must include all 4 accents × 5 pill stages = 20 pill renders, plus a body-mode toggle so the operator can visually confirm the on-dark variants work in technical mode. Three timeline-entry samples (normal, source-null, long-text) exercise the format's edge cases.
- **The `tokens-preview.html` page deliberately bypasses the SPA** because the standalone-preview spec says "render correctly" — meaning without Phase 4's JS having to run. It's a static file served by Caddy's `file_server` (which matches before `try_files` falls back to `index.html`).
- **No JS is strictly required.** A small `renderMaturityPill(slug, accent, stage)` helper in `app.js` may make Phase 4 cleaner, but the CSS contract is the single source of truth. Phase 3's deliverable is CSS-first; any JS lives in Phase 4.

</specifics>

<deferred>
## Deferred Ideas

- **Hub seven-block visual shape (cards vs grid vs timeline-of-tiles)** — Phase 4 owns the layout. Phase 3 ships only the per-block tile *accent treatment* (tier-colored border or top-stripe), not the tile dimensions or arrangement. If Phase 4 needs a `.block-tile` utility class, it adds it in `style-map.css` at that point.
- **Bespoke typography / page chrome (DSGN-01..03)** — already in REQUIREMENTS.md v2. Phase 3 honors `TOKN-04` strictly; no font-family changes, no spacing tokens beyond what the pill + timeline structure inherently need.
- **Hover/active states for the maturity pill** — the pill is informational, not interactive at the block level (per build spec §8.2). Phase 3 ships a static visual; hover/click affordances are out of scope until/unless a future phase needs them.
- **Per-tier dark-mode soft accents / borders** — the two-variant tokens (base + on-dark) are the minimum needed. If Phase 4 discovers it needs `--accent-tier-soft` (e.g., for a low-emphasis border or hover state), that's an additive token Phase 4 can introduce in `style-map.css` at that time.
- **SVG icons or arrow glyphs beyond `↗`** — out of v1. The single `↗` glyph in the timeline format is the only icon shipped by this phase.
- **CSS-only segment dividers (lines between maturity stops on the pill)** — purely visual detail; planner picks. If divided segments read clearer than continuous fill, pick the divided variant; if continuous fill reads more like a "progress" indicator, pick continuous. Document the choice in PLAN.md.
- **The mode-toggle visibility on `/status` page** — the status page is a denser snapshot. Whether the toggle appears there is a Phase 4 choice (it inherits the same chrome by default; Phase 4 may hide it if the dense layout feels cluttered). Phase 3 does not lock this.

</deferred>

---

*Phase: 03-design-tokens*
*Context gathered: 2026-05-27*
