# Phase 8: Validation Sentinels - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 8-validation-sentinels
**Areas discussed:** Structure sentinel vs WR-02, requires_attention storage, Tension-preserved detection, Telegram card surfacing

---

## Structure sentinel vs. Phase 7 WR-02 fix

| Option | Description | Selected |
|--------|-------------|----------|
| Move structure to a sentinel (annotate) | Remove the skeleton-heading raise from parse_synthesis_output; VLDT-04 sentinel writes structure_missing + requires_attention; draft lands | ✓ |
| Keep WR-02 hard gate; VLDT-04 redundant | parse keeps raising on missing headings; sentinel ~never fires; skip stays silent | |

**User's choice:** Move structure to a sentinel (annotate, recommended).
**Notes:** Resolves the conflict between the Phase 7 WR-02 gate (which blocks) and Phase 8's annotate-not-block thesis. parse_synthesis_output keeps raising only on empty-body/invalid-maturity. Planner must swap `test_parse_output_raises_on_missing_skeleton`.

---

## requires_attention storage

| Option | Description | Selected |
|--------|-------------|----------|
| Key inside validator_report jsonb | No migration; computed pre-insert, written atomically into the append-only column | ✓ |
| New boolean column (migration 038) | Queryable/indexable, but a schema change on the append-only table + trigger update | |

**User's choice:** Key inside validator_report jsonb (recommended).
**Notes:** Consistent with migration-caution; /map-pending fetches ≤7 drafts so no index needed.

### requires_attention semantics (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Any sentinel fires (rollup) | true if any of the four sentinels raises a concern | ✓ |
| Maturity jump only (literal ROADMAP) | tracks only the VLDT-03 maturity-jump guard | |
| Serious subset | rolls up tension/structure/maturity; length is informational-only | |

**User's choice:** Any sentinel fires (rollup, recommended).
**Notes:** One "needs a careful human look" signal the card headline keys off. Matches "silence is the enemy."

---

## Tension-preserved detection (VLDT-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic heuristic | section present + char floor + not placeholder/verbatim-echo; no extra LLM | ✓ |
| LLM judge | second Sonnet call per block; catches shallow-but-present; doubles per-block cost | |
| Hybrid | deterministic gate, LLM only on borderline length | |

**User's choice:** Deterministic heuristic (recommended).
**Notes:** Cheap, fail-loud; operator review catches subtle shallowness. LLM judge deferred as a v2 upgrade.

---

## Telegram card flag surfacing (VLDT-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Headline marker + indented detail list | ⚠ REQUIRES ATTENTION headline + per-flag detail; serious first; ✓ clean for unflagged | ✓ |
| Compact one-line flag badges | terse badges, detail deferred to per-draft card | |
| Detail only on requires_attention drafts | flagged drafts get detail; clean drafts collapse with no positive signal | |

**User's choice:** Headline marker + indented detail list (recommended).
**Notes:** Extends Phase 6 `handle_map_pending`; render-only, read-only-by-construction preserved.

---

## Claude's Discretion

- Markdown heading-section splitter approach (extract live-tension section body; detect heading presence).
- Exact `validator_report` key names and per-flag card wording (as long as the locked concepts hold).
- One composable `run_sentinels(...)` helper vs. separate functions.
- Char-vs-word for length floor (char count chosen as discretion default); cold-start → length N/A.

## Deferred Ideas

- LLM judge for "present but shallow" tension trivialization — v2 sentinel upgrade, deferred for cost.
- Phase 07 review-followup todo (WR-01 UNIQUE index, IN-04 watermark contract) — reviewed, left for Phase 9/10.
