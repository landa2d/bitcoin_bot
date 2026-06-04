# Phase 13: Agent Economy Grid - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-04
**Phase:** 13-agent-economy-grid
**Areas discussed:** Restyle scope; Deferred-block rule (surfaced as a remaining editorial decision)

---

## Gray areas presented (operator selected which to discuss)

| Area | Selected to discuss |
|------|--------------------|
| DEFERRED rule | (not initially — resolved in wrap-up as editorial decision) |
| Restyle scope | ✓ |
| Tier accents | (defaulted — COLOR-02 pre-locks) |
| Section header | (defaulted — mirrors Phase 12 D-07) |

---

## Restyle scope

### Q1 — overall scope

| Option | Description | Selected |
|--------|-------------|----------|
| Hub grid + block detail | Restyle hub grid AND single-block detail reading view (full Agent Economy section, like Phase 12 list+article); status handled separately | ✓ |
| Hub grid only | Just MAP-01..04; block detail + status stay dark/Courier, deferred to later | |
| Everything in style-map.css | Hub + block + status all restyled, retire dark theme entirely | |

**User's choice:** Hub grid + block detail
**Notes:** Batch-deploy means anything left on dark `style-map.css` ships broken; clicking a block from the new grid must not drop into a dark/Courier page. → D-01.

### Q2 — orphaned `#/status` disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Light de-dark pass | Strip dark bg / Courier / tier-accent so a deep-link renders on the light system; no redesign | ✓ |
| Leave deferred | Not nav-reachable; accept it renders dark on deep-link, fix later | |
| Full restyle now | Treat like block detail, full pass | |

**User's choice:** Light de-dark pass
**Notes:** `#/status` is no longer a nav tab (3 tabs = Newsletter / Agent Economy / About) — deep-link-only. Shares `style-map.css` rules with the in-scope views, so de-darkening is cheap insurance. → D-02.

### Q3 — block-detail treatment depth

| Option | Description | Selected |
|--------|-------------|----------|
| Restrained system pass | Adopt serif/light system, dots for pill, keep existing structure (header/tension/body/timeline) restyled not redesigned | ✓ |
| Full magazine treatment | Mirror Phase 12's richer article (mono kicker, display title, lead, blockquotes) on the block body | |
| You decide (UI-SPEC) | Leave depth to UI-SPEC | |

**User's choice:** Restrained system pass
**Notes:** Block detail is a reference reading view (only 2 of 7 have bodies); no second magazine treatment to keep consistent. → D-03.

---

## Deferred-block rule (MAP-04) — surfaced in wrap-up as an editorial decision

| Option | Description | Selected |
|--------|-------------|----------|
| No synthesized body | `current_body_version_id is null` → DEFERRED. Today 5/7. Self-updating, honest, on-brand. | ✓ |
| Fixed editorial list | Hardcode which block(s) are DEFERRED (e.g. regulation-legal). Today ~1/7; matches mockup but diverges from real state. | |
| Maturity = nascent | `maturity === 'nascent'` → DEFERRED. Today 6/7. | |

**User's choice:** No synthesized body
**Notes:** Raised because PROJECT.md keeps editorial framing in human hands and the live data (2/7 synthesized, no `status` column) makes "one deferred" impossible to derive cleanly. Operator accepted the 5-of-7-deferred consequence as an honest snapshot of a young living map. → D-04 / D-04a.

---

## Claude's Discretion

- **Tier accents (D-05)** — defaulted to collapsing the 4 tier colors to the single violet (COLOR-02 already locks "one accent only"); operator did not select this for discussion and did not object. Tiers distinguished only by mono section label.
- **Section header (D-06)** — defaulted to a serif page-title + mono sub-line mirroring Phase 12's D-07 minimal header, storyline kept as a one-line frame; exact treatment to UI-SPEC.
- **`style-map.css` disposition** — delete-and-fold vs lighten-in-place left to planner/UI-SPEC.
- **Grid CSS structure** — per-section grid vs continuous grid, odd-count/full-width-deferred flow, mobile 1-col; default to the mockup's per-section + full-width mechanism (intent, not copied markup).
- **Exact gap / radius / hover-lift / DEFERRED tag styling** — UI-SPEC within the Phase 11 token system.

## Deferred Ideas

- Full `#/status` redesign + re-linking into nav — out of scope (deep-link-only; not needed).
- A real `status`/`deferred` data column — explicitly not added (frontend-only); DEFERRED derived from data.
- Negotiation-as-block / richer Regulation frame — v-next backend/content evolution.
- Site-wide spacing/radius polish + About page → Phase 14.
- Dark mode (DARK-01) → v-next.
- 7 pending backend todos reviewed, none folded (all v1.0 backend follow-ups, no frontend overlap).
