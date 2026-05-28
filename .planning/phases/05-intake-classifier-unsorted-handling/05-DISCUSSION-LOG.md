# Phase 5: Intake Classifier + `unsorted` Handling - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 5-intake-classifier-unsorted-handling
**Areas discussed:** Emit trigger, Entry composition, Below-floor + failure handling, Idempotency

---

## Emit trigger (how/when classification fires)

| Option | Description | Selected |
|--------|-------------|----------|
| Processor poller | Scheduled job in the processor polls finalized editions; decoupled from newsletter generation; fits existing arch | ✓ |
| Inline at edition finalize | Newsletter service classifies right after save; instant but couples classifier failures to the pipeline | |
| Only on publish/approve | Classify only at published status; can combine as a state gate | |

**User's choice:** Processor poller (Recommended)
**Notes:** Residual sub-decision — *which* edition state counts as "finalized" — defaulted to finalized/published (not in-progress/held) to avoid ingesting from abandoned drafts; exact status value flagged for the researcher to confirm against `public.newsletters` (D-02).

---

## Entry composition (source of timeline prose fields)

| Option | Description | Selected |
|--------|-------------|----------|
| Extract + classify-only | Prose fields from verified event fields; LLM does only block_slug + tag_confidence; keeps grounding, cheaper | ✓ |
| Classifier composes prose too | One call classifies + writes prose; fewer parts but reintroduces fabrication risk | |
| Hybrid | Extract source/date/what_shifted; LLM composes why_it_mattered + classifies | |

**User's choice:** Extract + classify-only (Recommended)
**Notes:** Preserves the Phase D 0-fabrication property by not generating new ungrounded prose.

---

## Below-floor + classifier-failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Flagged, never dropped | Below floor → unsorted (conf recorded); error → unsorted with NULL conf; floor config-tunable, default 0.6 | ✓ |
| Unsorted on low-conf, skip on error | Cleaner unsorted, but persistent classifier outage = silent drops | |
| Hardcode floor at 0.6 | Same routing, threshold as code constant (redeploy to tune) | |

**User's choice:** Flagged, never dropped (Recommended)
**Notes:** Matches the project's silence-is-the-enemy / fail-loud design. Best-guess slug for below-floor entries is NOT persisted (no spare column on the locked Phase 2 schema) — operator re-decides later (D-07).

---

## Idempotency (exactly-once emission under append-only + reprocessing)

| Option | Description | Selected |
|--------|-------------|----------|
| Existence check on source_edition_id | Pre-emit check whether entries already carry that source_edition_id; skip if so; no new infra | ✓ |
| Per-event idempotency key | Hash(source_edition_id + event signature) per INSERT; handles regenerated editions | |
| Mark edition 'classified' | Flag on the edition row; requires a public.newsletters column | |

**User's choice:** Existence check on source_edition_id (Recommended)
**Notes:** Accepted trade-off — an edition regenerated with different events won't re-emit (re-emission would risk duplicating the map).

## Claude's Discretion

- DeepSeek classifier prompt text + JSON output schema (follow `MULTISOURCE_EXTRACTION_PROMPT` pattern).
- Poller interval / `schedule` slot; batch-vs-single LLM call per event.
- The allowed block-slug label set passed to the classifier (likely all 7 from `economy_map.blocks`).

## Deferred Ideas

- `/map-assign` and the rest of `/map-*` operator commands — Phase 10.
- Persisting below-floor best-guess slug — deferred (would require Phase 2 schema change).
- Per-block synthesis on new timeline entries — Phase 7.
