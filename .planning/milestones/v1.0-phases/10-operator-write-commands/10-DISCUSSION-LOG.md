# Phase 10: Operator Write Commands - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 10-operator-write-commands
**Areas discussed:** /map-synth cross-service trigger, /map-assign append-only reassignment, /map-entry argument ergonomics, WR-01 duplicate-draft index

---

## /map-synth cross-service trigger

### Trigger mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| DB request-queue + short poll | gato_brain INSERTs a request row; processor short-interval schedule job drains it, runs synthesize_block bypassing is_block_eligible. No new port; fits no-broker/DB-polling architecture. Async ack. | ✓ |
| HTTP trigger endpoint on processor | Give processor a FastAPI port; gato_brain POSTs synchronously. Adds an HTTP surface/port to a pure-loop service; 30–60s Sonnet call = fragile synchronous Telegram wait. | |
| Replicate synthesis in gato_brain | Port synthesize_block + synth_identity + Sonnet call into gato_brain. Rejected by DRY + identity-file location. | |

**User's choice:** DB request-queue + short poll
**Notes:** Captured as D-01. Processor confirmed to have no HTTP surface (schedule loop, pgrep healthcheck).

### Open-draft handling

| Option | Description | Selected |
|--------|-------------|----------|
| Refuse with a pointer | Respect the one-open-draft invariant; if a draft is pending, point to /map-pending. "Ignoring N and T" bypasses only eligibility, not the open-draft guard. WR-01 index is the race backstop. | ✓ |
| Force a second draft | Always create a new draft. Violates the invariant, conflicts with the WR-01 unique index. | |
| Supersede the old draft, then synth | Auto-reject the existing draft and re-synth. Silently discards an unreviewed draft — against the human-gated spine. | |

**User's choice:** Refuse with a pointer
**Notes:** Captured as D-02.

### Request lifecycle / observability

| Option | Description | Selected |
|--------|-------------|----------|
| Status lifecycle + fail-loud | Request row carries pending→processing→done(version_id)/failed(error); gato_brain validates + acks synchronously; failed synth queryable (pipeline_runs fail-loud pattern). | ✓ |
| Fire-and-forget | Bare request row, deleted after run, no status. A failed forced-synth vanishes silently — violates fail-loud governance. | |
| You decide | Planner chooses within fail-loud + structural constraints. | |

**User's choice:** Status lifecycle + fail-loud
**Notes:** Captured as D-03.

---

## /map-assign append-only reassignment

### Reassignment model

| Option | Description | Selected |
|--------|-------------|----------|
| Mutable lifecycle pointer on original | Add nullable mutable reassigned_to_entry_id (trigger-exempt) + reassigned_from_entry_id on copy, set atomically by an RPC; content stays append-only; unsorted reads filter reassigned_to_entry_id IS NULL. Same precedent as block_body_versions status/published_at. | ✓ |
| Pure append-only, exclude via view/RPC | Zero mutation; exclude originals referenced as reassigned_from via NOT-EXISTS subquery. Literally 100% append-only but PostgREST can't express the anti-join; subquery cost on every unsorted read. | |
| You decide | Planner picks within append-only-content + structural constraints. | |

**User's choice:** Mutable lifecycle pointer on original
**Notes:** Captured as D-04.

### Reassigned-copy provenance

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve event_date + source; confidence authoritative | Copy original event_date/what_shifted/why_it_mattered/source_url/source_edition_id + reassigned_from link; tag_confidence NULL or 1.0 (operator authoritative); target slug allowlist + must-be-unsorted validation. | ✓ |
| Stamp event_date = today | Treat reassignment moment as the event date. Loses original timing, breaks newest-first fidelity. | |
| You decide | Planner chooses copied fields + confidence semantics. | |

**User's choice:** Preserve event_date + source; confidence authoritative
**Notes:** Captured as D-05.

---

## /map-entry argument ergonomics

| Option | Description | Selected |
|--------|-------------|----------|
| Stateless single-shot with delimiter | `/map-entry <slug> <what_shifted> \| <why_it_mattered>`; both required; usage hint if malformed (satisfies SC2 "prompts for" without session state); event_date=today, source/confidence NULL. | ✓ |
| Conversational follow-up prompt | Two-turn: bot asks why_it_mattered after what_shifted. Introduces conversation_state machinery into the write path; statefully fragile. | |
| You decide | Planner picks parse format + defaults. | |

**User's choice:** Stateless single-shot with delimiter
**Notes:** Captured as D-06.

---

## WR-01 duplicate-draft index (now in scope)

| Option | Description | Selected |
|--------|-------------|----------|
| Own migration + benign-skip in processor | Partial unique index as its own operator-approved migration (per the todo's "own approved migration track"); synthesize_block keeps block_has_open_draft fast-path + catches 23505 as a logged benign skip. | ✓ |
| Bundle into one Phase 10 migration | Fold the index with synth_requests/reassign schema. Couples an independent guard to feature schema; muddies scoped-deploy/rollback. | |
| You decide | Planner decides packaging + violation-handling path. | |

**User's choice:** Own migration + benign-skip in processor
**Notes:** Captured as D-07. WR-01 folded from the deferred Phase 7 review todo.

---

## Claude's Discretion

- Synth-poll cadence + synth-request table column set (within D-01/D-03 constraints).
- tag_confidence value for the reassigned copy (NULL vs 1.0) and /map-entry (NULL).
- /map-entry delimiter + usage-hint wording.
- /map-tension RPC vs direct PATCH — RPC is the default (D-08); blocks.live_tension is freely mutable.
- Separate vs parametrized handlers; new RPC names/signatures; generalized _economy_map_rpc signature;
  migration grouping of the non-WR-01 schema changes.
- All confirmation/emoji wording (must cover the D-10 typed-error cases distinctly).

## Deferred Ideas

- Bespoke per-command card UIs — out of scope; /map-pending + /map-status remain the surfaces.
- Per-block synthesis threshold tuning — v2; /map-synth is the manual escape hatch.
- A general HTTP/control surface on the processor — rejected for /map-synth (D-01).
- Reviewed-not-folded: IN-01..04 from the WR-01 todo (synthesis-input/read-helper quality notes,
  unrelated to the write commands; IN-04 already resolved as Phase 9 D-01).
