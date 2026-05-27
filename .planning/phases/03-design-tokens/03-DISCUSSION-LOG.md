# Phase 3: Design Tokens - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 03-design-tokens
**Areas discussed:** Block-page visual frame

---

## Gray-Area Selection

Four gray areas were surfaced. The user selected **one** for deep discussion and deferred the rest to Claude's discretion with reasoned defaults in CONTEXT.md.

| Gray area | Description | Selected for discussion |
|-----------|-------------|--------------------------|
| Token file organization | Extend `style-shared.css` vs new `style-map.css` | |
| Maturity pill component shape | CSS-only with data attributes vs JS helper | |
| Block-page visual frame | How map pages relate to existing dark/light mode toggle and tier accents | ✓ |
| Standalone preview deliverable | What SC#1's "standalone preview" looks like concretely | |

---

## Block-page visual frame

### Question 1 — Mode inheritance

| Option | Description | Selected |
|--------|-------------|----------|
| Inherit both modes + toggle | Block pages show the same toggle, switch between dark technical and light strategic. Tier accent replaces the per-mode `--accent` variable on map pages, so 'Substrate' renders teal regardless of mode. Feels like the same product; reading-mode preference carries across editions and the map. | ✓ |
| Single neutral mode — light | Map pages run in one mode only (white background, dark text). Tier accent is the only color signal. Toggle hidden on map routes. Cleaner separation; map feels like a 'reference' surface distinct from editions. | |
| Single neutral mode — dark | Same as above but dark background, light text. Matches existing default-on-load technical mode. Tier accent pops harder against dark. | |

**User's choice:** Inherit both modes + toggle (Recommended)
**Notes:** Locks the visual frame so map pages stay "part of the same product." Tier accent must overlay correctly on both `body.technical` and `body.strategic` backgrounds — drove the contrast question below.

---

### Question 2 — Tier accent scope (per-page-type)

| Option | Description | Selected |
|--------|-------------|----------|
| Block page only — hub/status keep mode accent | On `/map/<slug>`, tier color replaces the mode `--accent` throughout (title, pill, section labels). On hub and status pages where all seven blocks coexist, each block tile carries its own tier color only on its pill + tile border; page chrome (top nav, mode toggle) stays mode-default. Avoids visual cacophony on the multi-block surfaces. | ✓ |
| Pill + tile border only — nowhere else | Tier color appears only on the maturity pill and a thin tile/border accent, even on block pages. Section headings, body type, and links stay mode-default. Quietest treatment; pill is the only loud tier signal. | |
| Everywhere on a block page — full takeover | On any `/map/<slug>` page, tier color drives section headings, links, hover states, and the pill. Maximum tier identity per block page. | |

**User's choice:** Block page only — hub/status keep mode accent (Recommended)
**Notes:** Defines the scope contract Phase 4 will follow: per-page-type rules for where `--accent-tier` overrides the mode `--accent`.

---

### Question 3 — Dark-mode contrast handling

| Option | Description | Selected |
|--------|-------------|----------|
| Two-variant tokens — base + on-dark | Each tier ships as two CSS vars: `--accent-teal-base: #0F6E56` (light/strategic mode) and `--accent-teal-on-dark` (brighter variant Claude picks, e.g., ~#2BBF98). A single `--accent-tier` resolves to the right variant per body mode. Keeps pinned values on their designed surface; preserves legibility on dark. | ✓ |
| Use the pinned hex on both modes, as-is | Spec honored literally; muted contrast on dark is acceptable because pill segments still work against their neutral track and section headings remain legible. Simplest token sheet. | |
| Defer dark-mode treatment — light mode only for map pages | Force `/map/*` routes into `body.strategic` regardless of toggle state; hide the toggle on map pages. Keeps the pinned hex on its native surface and avoids the contrast question. Reverses the earlier "inherit both modes" choice. | |

**User's choice:** Two-variant tokens — base + on-dark (Recommended)
**Notes:** The actual on-dark hex values are Claude's discretion for the planner/executor, constrained by (a) preserving the pinned-base hue family and (b) clearing WCAG AA contrast against `#0a0a0f`. Documented in CONTEXT.md D-03 + D-05.

---

### Question 4 — Handling of remaining unselected gray areas

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context | Capture visual-frame decisions plus reasoned defaults for the three unselected areas under "Claude's Discretion" in CONTEXT.md. Defaults: new `style-map.css`; CSS-only pill via data attributes; standalone preview as deployable `tokens-preview.html`. Planner can revisit if any feels wrong. | ✓ |
| Discuss token file organization | Talk through where the new CSS lives — extend `style-shared.css` or new `style-map.css` — since this affects Phase 4 imports. | |
| Discuss maturity pill shape | Talk through CSS-only-with-data-attributes vs JS helper for the pill. | |
| Discuss standalone preview | Talk through what the SC#1 "standalone preview" deliverable looks like. | |

**User's choice:** I'm ready for context (Recommended)
**Notes:** The three deferred gray areas are captured in CONTEXT.md as D-09, D-10, D-11 with explicit reasoning. Planner is free to revisit any of them.

---

## Claude's Discretion

Captured as `D-09`, `D-10`, `D-11` in CONTEXT.md with reasoned defaults the planner can revisit:

- **Token file organization (D-09):** Default — new `docker/web/site/style-map.css`. Planner may extend `style-shared.css` instead.
- **Maturity pill component shape (D-10):** Default — CSS-only with `data-accent` + `data-stage` attributes; no JS helper required. Planner may add a `renderMaturityPill(...)` helper in Phase 4's `app.js` for DRY-ness.
- **Standalone preview deliverable (D-11):** Default — `docker/web/site/tokens-preview.html`, deployed and accessible at `aiagentspulse.com/tokens-preview.html`. Planner may move it out-of-tree if shipping to production feels wrong.

Additional planner discretions (CONTEXT.md "Other Claude discretions"):
- Exact on-dark hex values per tier (constraint: WCAG AA against `#0a0a0f`, preserve hue family)
- Pill segment separator (gap vs shared border)
- Empty-source rendering (default: omit `[source ↗]` link entirely when `source_url` is null)
- `↗` glyph rendering (default: literal Unicode U+2197)

---

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` for future phases:

- Hub seven-block visual shape (Phase 4 owns layout; Phase 3 ships only per-block tile accent treatment)
- Bespoke typography / page chrome (v2 — DSGN-01..03)
- Pill hover/active interactivity (out of scope; pill is informational, not interactive at the block level)
- Per-tier soft/border accents beyond base + on-dark (additive token Phase 4 can introduce if needed)
- SVG icons / non-`↗` glyphs (out of v1)
- CSS-only segment dividers on the pill (planner picks)
- Mode-toggle visibility on `/status` page (Phase 4 choice, defaults to "visible")
