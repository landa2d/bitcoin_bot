# Phase 26: Continuity & Exemplar Context - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 26-continuity-exemplar-context
**Areas discussed:** Exemplar provenance, Exemplar selection, Continuity metadata, Verification

---

## Area selection (multiSelect)

| Option | Description | Selected |
|--------|-------------|----------|
| Exemplar provenance | operator_written vs any published edition as the exemplar source | ✓ |
| Exemplar selection | which paragraphs become voice anchors; count | ✓ |
| Continuity metadata | theme field / fallback, weeks_ago source, corpus depth | ✓ |
| Verification | live trigger vs fixture test vs both | ✓ |

**User's choice:** all four areas.

---

## Exemplar provenance

| Option | Description | Selected |
|--------|-------------|----------|
| operator_written, then fallback | operator_written pool, fall back to any-published if empty + WARNING | partial ✓ |
| operator_written ONLY (strict) | operator_written only; empty → exemplars=[] (Phase E degrades) | |
| Any published edition | spec 07 literal: most-recent 2 published regardless of authorship | |

**User's choice:** operator_written=true pool (option 1's pool definition — the 7 editions), **but** replace the fallback-to-any-published with **skip-and-surface**: when the operator pool is empty, the voice dimension is reported as a not-scored verdict the eval surfaces, NOT a quiet substitution. Keep the WARNING.
**Notes:** "make it a not-scored verdict the eval reports, not a substitution it makes quietly." Stronger fail-loud stance than the recommendation. Drove CONTEXT D-01..D-04. Also implies Phase E's `score:0`/"No exemplars" sentinel must become "not scored," closing the CTX-05 silent-zero gap.

---

## Exemplar selection

**Q1 — which paragraphs:**

| Option | Description | Selected |
|--------|-------------|----------|
| Document order, front-loaded | qualifying paras in order, fills to cap; favors opening essay + bridge | ✓ |
| Lead/opening section only | only the opening essay before the first '---' | |
| Even spread per edition | sample open/mid/close for stylistic range | |

**Q2 — count / span:**

| Option | Description | Selected |
|--------|-------------|----------|
| 8 paras / recent 2 editions | spec 07 default; balanced anchor vs judge token cost | ✓ |
| 6 paras / recent 2 editions | leaner / cheaper | |
| 12 paras / recent 3 editions | stronger/broader anchor, heavier judge prompt | |

**User's choice:** Document order, front-loaded; cap 8 paras from the 2 most-recent operator editions (expand to a 3rd to reach cap). → CONTEXT D-05, D-06.

---

## Continuity metadata

**Q1 — theme field / fallback:**

| Option | Description | Selected |
|--------|-------------|----------|
| lead_theme, else first sentence | derive theme from opening when lead_theme absent | |
| lead_theme, else null/omit | only show authored theme; rely on opening_excerpt otherwise | ✓ |
| lead_theme, else title | fall back to the title column | |

**Q2 — weeks_ago:**

| Option | Description | Selected |
|--------|-------------|----------|
| published_at date diff | round((now − published_at)/7d); fallback to edition-number gap on null | partial ✓ |
| Edition-number gap | current − that edition number (assumes weekly cadence) | |
| Omit weeks_ago | drop the field entirely | |

**User's choice:** theme = lead_theme else null (never derive). weeks_ago = published_at diff, **but on null published_at OMIT for that edition** (no edition-number-gap fallback — it reintroduces cadence error on held/test rows likely to have null timestamps). → CONTEXT D-07..D-09.
**Notes:** Added a scope item — "while backfilling lead_theme on the 7 operator-written editions, confirm their published_at is clean in the same pass." Captured as the D-12/D-13 data-hygiene backfill (operator-confirmed candidate themes for editions 25–28, applied via MCP).

---

## Verification

| Option | Description | Selected |
|--------|-------------|----------|
| Both: fixture test + live trigger | deterministic loader + degrade-path coverage AND one live end-to-end generation | ✓ |
| Fixture/unit test only | deterministic only; CTX-04/05 unproven on real data | |
| Live trigger only | end-to-end only; degrade paths untested | |

**User's choice:** Both. → CONTEXT D-15..D-18.
**Notes:** Scout confirmed `block_pipeline.enabled=false` but `ab_comparison=true`, so Phase E runs via the A/B path (`:2269`) — the live trigger is viable without flipping `enabled`.

## Claude's Discretion

- Paragraph-splitting heuristic (blank-line split vs markdown block parse), as long as headers/lists excluded + ≥40-word filter.
- Internal output dict key naming, as long as existing consumer keys are satisfied.
- Representation of the "not scored" marker (bool flag / sentinel / enum), as long as it's unambiguously distinct from "scored 0" and "corpus empty."

## Deferred Ideas

- None — discussion stayed within phase scope. Downstream consumers (judge, edition_evals table, deterministic gate, rewrite loop, sequencer wiring, Gato surfacing) are already scoped as Phases 27–31.
