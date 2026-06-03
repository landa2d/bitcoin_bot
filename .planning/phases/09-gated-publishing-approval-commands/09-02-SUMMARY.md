---
phase: 09-gated-publishing-approval-commands
plan: 02
subsystem: api
tags: [economy_map, postgrest, rpc, telegram, gato_brain, owner-gate, autonomy-boundary]

# Dependency graph
requires:
  - phase: 09-01
    provides: "publish_block_version watermark amendment (migration 038) — last_synthesized_at advances from synthesized_from_through; the atomic publish/reject RPCs this plan calls"
  - phase: 07
    provides: "economy_map_insert_block_body_version draft writer (GATE-01 source) + the standalone test harness shape mirrored here"
  - phase: 08
    provides: "/map-pending draft inbox + validator_report surfacing (the source of the draft UUIDs operators paste into /map-approve)"
provides:
  - "Owner-gated /map-approve <uuid> command — atomic publish RPC + maturity old→new + live #/map/<slug> confirmation (CMD-03, GATE-02)"
  - "Owner-gated /map-reject <uuid> command — atomic reject RPC + 'returns to next synthesis' confirmation (CMD-04, GATE-03)"
  - "_economy_map_rpc: the FIRST and ONLY parameterized write verb on the /map-* surface (Content-Profile: economy_map, {p_version_id}, fail-loud)"
  - "Explicit GATE-01 verification test (synthesis writes only status='draft')"
affects: [phase-10, deploy, gato_brain]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RPC-POST helper (Content-Profile write profile) as the economy_map write analog of the read-only _economy_map_get (Accept-Profile)"
    - "Owner gate enforced in gato_brain BEFORE any RPC POST — the DB cannot know who the Telegram caller is (SECURITY DEFINER RPC trusts the caller)"
    - "Typed RAISE text preserved through RuntimeError(resp.text) so the single-winner 'already actioned' loser maps to a distinct user message (D-05 case c)"
    - "Standalone+pytest harness that stubs fastapi/pydantic/supabase/anthropic so gato_brain imports in a bare env (no network, no FastAPI app exercised)"

key-files:
  created:
    - tests/test_09_gated_publishing.py
  modified:
    - docker/gato_brain/gato_brain.py

key-decisions:
  - "Read the draft + current block via GET BEFORE the RPC so the approve confirmation can render maturity old→new even though the RPC flips the row to 'published'"
  - "Two separate write handlers (handle_map_approve / handle_map_reject) rather than one parametrized helper — each verb's confirmation copy and lookups differ enough that separate is clearer"
  - "uuid.UUID(arg) strict parse normalizes the version_id to its canonical string form before it ever reaches the parameterized JSON body"

patterns-established:
  - "Owner-gate-then-validate-then-RPC ordering: gate (no RPC for non-owner) → UUID validate (no RPC for malformed) → RPC, so neither a non-owner nor a bad arg can reach the write"
  - "Already-actioned mapping via substring match on the DB's typed RAISE — never a double-publish"

requirements-completed: [GATE-01, GATE-02, GATE-03, GATE-04, CMD-03, CMD-04]

# Metrics
duration: 14min
completed: 2026-06-03
---

# Phase 9 Plan 02: Gated Publishing Approval Commands Summary

**Owner-gated `/map-approve` and `/map-reject` Telegram commands that call the Phase 09-01 atomic publish/reject RPCs through a new parameterized PostgREST RPC-POST helper — the human approval gate the whole project is designed around — with UUID validation, single-winner already-actioned handling, and an explicit GATE-01 draft-only test.**

## Performance

- **Duration:** ~14 min
- **Tasks:** 2 (both TDD-tagged auto tasks)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- Added `_economy_map_rpc` — the FIRST and ONLY write verb on the otherwise read-only `/map-*` surface: POSTs `/rest/v1/rpc/<fn>` with `Content-Profile: economy_map` and parameterized body `{"p_version_id": <uuid>}`, fail-loud `RuntimeError(resp.text)` on non-2xx (preserves the DB's typed RAISE for D-05 case-c matching).
- `/map-approve <uuid>` and `/map-reject <uuid>` both gated on `access_tier == 'owner'` BEFORE any RPC POST (the autonomy boundary / central threat T-09-06), with strict `uuid.UUID(arg)` validation, rich confirmations (approve shows maturity old→new + `https://aiagentspulse.com/#/map/<slug>`), and the distinct "already published/rejected or doesn't exist" message for the concurrent-loser / wrong-id case.
- Threaded the already-computed `access_tier` into the `/chat` `/map-` dispatch (the PATTERNS.md wiring gap T-09-06 called out).
- Explicit GATE-01 test asserts the synthesis writer omits `status` (draft-only) and never targets `blocks`/`published` — GATE-01 is now verified, not assumed.

## Task Commits

1. **Task 1: RPC-POST helper + owner-gated /map-approve and /map-reject + tier-threaded dispatch** — `ef777a3` (feat)
2. **Task 2: Test suite — owner gate, UUID validation, typed errors, GATE-01 draft-only** — `10ee3fd` (test)

_TDD tasks: Task 1 is the GREEN implementation; Task 2 adds the verifying suite. Both verified green (Task 1 ast.parse + grep verify PASS; Task 2 pytest 14/14)._

## Files Created/Modified

- `docker/gato_brain/gato_brain.py` — Added `_economy_map_rpc`, `get_draft_version_by_id`, `get_block_by_slug`, `handle_map_approve`, `handle_map_reject`, `_validate_version_id`; extended `handle_map_command(message, access_tier="free")` with the two gated write branches; threaded `access_tier` into the `/chat` `/map-` dispatch; `import uuid`. `/map-status` and `/map-pending` unchanged and ungated.
- `tests/test_09_gated_publishing.py` — 14-test standalone+pytest suite: GATE-01 draft-only, owner gate (both verbs, refusal + RPC-never-called for non-owner, RPC-called for owner), UUID validation (missing + malformed), already-actioned D-05 case (c), other-failure D-05 case (d), approve confirmation content (maturity old→new + URL), reject confirmation, and read-commands-stay-ungated.

## Decisions Made

- Approve confirmation reads the draft + block rows via GET **before** the RPC (the RPC flips status to published, so a post-RPC read of the draft's `proposed_maturity` would be the same row but reading before keeps the lookup simple and avoids a second round-trip after the write).
- Two distinct write handlers instead of one parametrized helper — the confirmation copy and the lookup needs (approve needs old+new maturity + URL; reject needs only the slug for naming) diverge enough that separate handlers read more clearly. (Planner left this to discretion.)
- D-05 case-(c) detection is a substring match on `not found or not in draft status` against the RuntimeError message, exactly the typed RAISE text in migration 033 §9/§10.

## Deviations from Plan

None — plan executed exactly as written. Test-harness stubbing of `fastapi`/`pydantic`/`supabase` (in addition to the planned `anthropic`/sibling-module stubs) was anticipated by the plan's "mirror test_07's standalone harness; no live network" instruction; those deps are simply absent in the bare test env and were stubbed to allow `import gato_brain`. No production code or scope changed.

## Issues Encountered

- `import gato_brain` initially failed in the bare test env on `fastapi`, then on `anthropic.Anthropic | None` type annotation (the `anthropic` stub had to be a class, not a lambda, to support the `| None` union). Resolved by stubbing `fastapi`/`pydantic`/`supabase` minimally and making the `anthropic.Anthropic` stub a class. No production change.

## User Setup Required

None — no new env var, config, or secret (reuses the existing `SUPABASE_KEY` service_role secret; T-09-10 accepted). Deploy is a separate operator-approved scoped rebuild of `gato_brain` (NOT done here).

## Next Phase Readiness

- The autonomy boundary is now closed end-to-end: synthesis writes only drafts (GATE-01, tested), and only the verified owner can publish/reject via the atomic single-winner RPCs (GATE-02/03/04). The behavior is validated against the Plan 09-01 live RPC via the test suite (no container needed).
- **Deploy step (operator-gated, NOT performed here):** `cd /root/bitcoin_bot/docker && docker compose up -d --build gato_brain`. Behavior is already covered by tests; the rebuild only ships the running container.

---
*Phase: 09-gated-publishing-approval-commands*
*Completed: 2026-06-03*
