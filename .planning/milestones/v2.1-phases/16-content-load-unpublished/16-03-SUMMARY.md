---
phase: 16-content-load-unpublished
plan: 03
subsystem: database
tags: [supabase, postgres, economy_map, postgrest, rls, anon, draft-load]

# Dependency graph
requires:
  - phase: 16-content-load-unpublished (Plan 01)
    provides: migration 043 applied live — hub + negotiation FK targets exist
  - phase: 16-content-load-unpublished (Plan 02)
    provides: the standalone PostgREST body loader + its DOCS_DIR override + idempotency
provides:
  - "All 8 canonical bodies present in economy_map.block_body_versions as status='draft'"
  - "SC#1 before/after anon evidence (zero new published rows) in 16-LOAD-EVIDENCE.md"
  - "LOAD-03 per-slug disposition record (first-publish / rewrite / stale-draft-corrected)"
affects: [17-cross-link-wiring-preview, 18-gated-batch-publish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Orchestrator-owned live loader run (host-side, not docker-exec, not worktree) for the content load"
    - "Stale-draft correction via the purpose-built reject_block_version RPC (status-only supersede; canonical-body-rewrite), never a raw body UPDATE"
    - "SC#1 proven by a real anon-key before/after published-body read, not RLS reasoning alone (D-07)"

key-files:
  created:
    - .planning/phases/16-content-load-unpublished/16-LOAD-EVIDENCE.md
  modified: []

key-decisions:
  - "DEVIATION (operator-approved): 3 in-scope slugs held stale 2026-06-04 drafts the plan didn't anticipate; the loader would have silently skipped them. Resolved by reject_block_version() (draft→superseded) on the 3, then loading — so all 8 canonical bodies land. Fully LOAD-03 compliant (no raw UPDATE)."
  - "Live loader run + reject RPC are orchestrator-owned, human-gated (blocking checkpoints), run host-side with direct PostgREST."

patterns-established:
  - "When a one-shot loader meets pre-existing foreign drafts, supersede-then-load via reject_block_version is the trigger-legal correction (not delete, not raw UPDATE, not silent skip)"

requirements-completed: [LOAD-01, LOAD-03]

# Metrics
duration: ~40min
completed: 2026-06-08
---

# Phase 16 / Plan 03: Live draft load + SC#1 evidence Summary

**All 8 canonical bodies loaded into economy_map.block_body_versions as drafts (substrate trio remapped to emerging) with zero visitor-facing change — proven by an identical anon-key published-body count before (2) and after (2); 3 stale v2.0-era drafts were superseded via reject_block_version first so the canonical bodies actually land.**

## Performance

- **Duration:** ~40 min (includes the stale-draft investigation + operator escalation)
- **Completed:** 2026-06-08T17:38Z
- **Tasks:** 2 (both `checkpoint:human-verify`, orchestrator/operator-driven)
- **Files created:** 1 (16-LOAD-EVIDENCE.md)

## Accomplishments
- 8 in-scope canonical bodies present as `status='draft'`, each exactly once; substrate trio (`identity-trust`/`memory-context`/`payments-settlement`) carry `proposed_maturity='emerging'`.
- **SC#1 proven**: anon-key published-body count is 2 before AND after the load — zero new published rows, `#/map` unchanged for visitors.
- Caught a plan-vs-reality gap (3 stale foreign drafts that would have been silently skipped) **before** any live write; escalated; resolved per operator approval.
- LOAD-03 posture recorded: corrections via canonical-body-rewrite / reject-then-rewrite; no raw UPDATE on any append-only column; no duplicate open draft.
- Idempotent re-run confirmed (`inserted=0 skipped=8`).

## Task Commits

Both tasks are `checkpoint:human-verify` (live-DB actions, operator-approved). No source code commits; the record is `16-LOAD-EVIDENCE.md` + this SUMMARY.

1. **Task 1: BEFORE snapshot + live loader run** — captured anon BEFORE (published=2, blocks=9); superseded 3 stale drafts (reject_block_version, HTTP 204 ×3); ran loader (`inserted=8 skipped=0`, exit 0).
2. **Task 2: AFTER snapshot + zero-change proof + LOAD-03 posture + idempotency** — anon AFTER (published=2, blocks=9) == BEFORE; +2 structural blocks delta explained; re-run skips all 8; LOAD-03 disposition recorded.

## Files Created/Modified
- `.planning/phases/16-content-load-unpublished/16-LOAD-EVIDENCE.md` — BEFORE/AFTER anon evidence, loaded-draft inventory, LOAD-03 posture, the stale-draft deviation, idempotency check, chronological run log.

## Decisions Made
- **Reject-then-load** for the 3 stale drafts (operator-approved) — see Deviations.
- Anon snapshots + service-role reads via direct PostgREST + `Accept-Profile`/`Content-Profile` (no `.in_()`), per the standing constraint.

## Deviations from Plan

### Operator-approved correction — pre-existing stale drafts

**1. [Plan-vs-reality gap — silent-skip prevented] 3 in-scope slugs held stale 2026-06-04 drafts**
- **Found during:** Task 1 dry-run pre-flight (before any live write).
- **Issue:** `memory-context`, `autonomy-control`, `psychology-disposition` already had open drafts from 2026-06-04 (v2.0-era), with bodies differing from the current canonical docs and wrong maturity for two (`nascent` vs canon `emerging`/`contested`). The loader's `skip-if-open-draft` idempotency (designed for its own partial-run recovery) would have silently skipped these 3 — failing LOAD-01 ("frontmatter is truth") and the substrate-trio `emerging` criterion.
- **Fix:** Surfaced the finding with evidence; operator chose "Reject stale, then load." Called `economy_map.reject_block_version()` on the 3 stale draft version IDs (`draft → superseded`; status-only, trigger-legal, via the purpose-built RPC — NOT a raw body UPDATE, NOT a DELETE), then ran the loader so the canonical bodies land as fresh drafts.
- **Verification:** Post-load: all 8 in-scope slugs have exactly one open draft; substrate trio = emerging; idempotent re-run skips all 8; anon published count unchanged (2→2).
- **Committed in:** evidence recorded in 16-LOAD-EVIDENCE.md (live-DB action; no code change).

---

**Total deviations:** 1 (operator-approved live-DB correction)
**Impact on plan:** Necessary for LOAD-01/LOAD-03 correctness — without it, 3 canonical bodies would not have landed. No scope creep; no loader code change (the targeted reject-then-load is a one-time correction for v2.0-era artifacts; the loader's idempotency is correct for future re-runs).

## Issues Encountered
- The append-only trigger forbids DELETE and pins body columns, so the stale drafts could not be deleted or body-updated. Resolved via the `reject_block_version` RPC (status-only supersede), which is the schema's intended retire-a-draft mechanism.

## User Setup Required
None.

## Next Phase Readiness
- **Phase 17 (cross-link wiring & preview):** the hub + 7 block bodies exist as drafts and can be previewed on a non-published route; `renderHub` body fetch + cross-block link resolution can build on this content.
- **Phase 18 (gated batch publish):** the 8 drafts (incl. the canonical-body-rewrites over identity-trust/governance-accountability) are the publish set for the single operator-approved batch via `publish_block_version`.
- No blockers. `regulation-legal` remains deferred/body-less (P15-D-02) by design.

---
*Phase: 16-content-load-unpublished*
*Completed: 2026-06-08*
