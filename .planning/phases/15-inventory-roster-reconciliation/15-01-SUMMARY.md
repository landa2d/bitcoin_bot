---
phase: 15-inventory-roster-reconciliation
plan: 01
subsystem: database
tags: [economy_map, postgres, rls, append-only-triggers, security-definer-rpc, maturity-enum, roster-reconciliation, documentation]

# Dependency graph
requires:
  - phase: 02-economy-map-schema-seven-block-seed
    provides: migration 033 (economy_map schema, blocks/block_body_versions/timeline_entries, maturity enum, publish_block_version RPC, RLS, 7-block seed)
  - phase: 09-operator-approval-publish
    provides: migration 039 (publish RPC watermark NULL-guard — current authoritative RPC body)
  - phase: 10-operator-write-commands
    provides: migration 041 (UNIQUE one-open-draft-per-slug index)
provides:
  - "15-CONTRACT.md — the live economy_map storage + serve contract documented from in-tree migration SQL + app.js (every fact line-cited): block data contract, body storage, the 2 append-only triggers, the atomic 4-step publish RPC, the anon RLS read boundary, the current hub serve path, and the verified 5-member maturity enum"
  - "15-RECONCILIATION.md — the per-slug roster disposition for all 9 entries (hub + 8), the D-03 collision-free {1..8} sort_order reshuffle map, the pinned Option-A hub schema accommodation (B/C rejected), and the F-1/F-2/F-3 doc-vs-live flags"
  - "Operator-approval target gating Phase 16: no economy_map write happens until this reconciliation is approved (D-05)"
affects: [16-load-unpublished, 17-hub-render-presentation, 18-publish-batch]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Document-from-source contract: every stated fact carries an in-tree line citation (033:LINE / 039:LINE / 041:LINE / app.js:LINE) so a reader verifies without reading code"
    - "Reconcile-before-write: the per-slug disposition + hub accommodation are locked as a doc gate before any economy_map mutation (the spine — read before writing)"

key-files:
  created:
    - .planning/phases/15-inventory-roster-reconciliation/15-CONTRACT.md
    - .planning/phases/15-inventory-roster-reconciliation/15-RECONCILIATION.md
  modified: []

key-decisions:
  - "INV-02: live maturity enum is nascent/emerging/contested/consolidating/mature (033:46-52); docs' `building` is NOT a member; D-01 remaps building→emerging at load time (Phase 16), no ALTER TYPE, no app.js change"
  - "ROST-01: 9 block-level entries, 3 tiers; regulation-legal kept deferred (D-02); negotiation-coordination is a new behavior block (D-03)"
  - "D-03 sort_order reshuffle resolves to collision-free {1..8}; blocks has no append-only trigger so the reshuffle is a permitted plain UPDATE (033 §8 guards only the content tables)"
  - "D-04 hub accommodation PINNED = Option A (relax tier CHECK + 'hub' sentinel tier); Option B (nullable tier) and Option C (parallel table+RPC) rejected — Option A reuses publish_block_version + marked.parse unchanged and preserves tier NOT NULL fail-loud"

patterns-established:
  - "Line-cited contract doc: a reader-facing storage/serve contract where each fact is greppable against the authoritative migration SQL"
  - "Per-slug disposition table citing the locked D-NN decision per row"

requirements-completed: [INV-01, INV-02, ROST-01]

# Metrics
duration: 5min
completed: 2026-06-08
---

# Phase 15 Plan 01: Inventory & Roster Reconciliation Summary

**Documented the live economy_map storage + serve contract (line-cited to migrations 033/039/041 + app.js) and locked the per-slug roster disposition — 9 entries across 3 tiers, the collision-free {1..8} sort_order reshuffle, and the pinned Option-A hub-tier accommodation — as the operator-approval gate before any Phase-16 write.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-08T13:22:43Z
- **Completed:** 2026-06-08T13:27:34Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- **15-CONTRACT.md** — the live `economy_map` storage + serve contract, every fact line-cited to in-tree source: the `blocks` data contract (8 load-relevant columns, the tier CHECK at 033:68, the no-trigger-on-blocks fact), body storage in `block_body_versions` (pinned vs lifecycle columns, the 041 one-open-draft invariant), the exactly-2 append-only triggers and why-triggers-not-RLS (service_role bypass), the atomic 4-step `publish_block_version` RPC (current body = migration 039, service_role-only at 039:82), the anon RLS read boundary (published-only at 033:370), the current hardcoded-`HUB_STORYLINE` hub serve path, and the verified 5-member maturity enum with the `building∉enum` fact and the D-01 `building→emerging` resolution.
- **15-RECONCILIATION.md** — the per-slug disposition for all 9 roster entries (hub + 8), each citing its D-NN decision; the D-02 3-tier model decision with `regulation-legal` kept deferred; the D-03 collision-free {1..8} sort_order reshuffle map with the highest-first execution note; the D-04 hub accommodation pinned to Option A (relax tier CHECK + `'hub'` sentinel) with explicit B/C rejection rationale; and the F-1/F-2/F-3 doc-vs-live divergence flags.
- All `<automated>` and `<acceptance_criteria>` grep assertions pass against both the live source files and the written docs (evidence below).
- Phase boundary held: no migration applied, no `app.js` edit, no `economy_map` write.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write 15-CONTRACT.md (INV-01, INV-02)** — `91b6850` (docs)
2. **Task 2: Write 15-RECONCILIATION.md (ROST-01)** — `823d84b` (docs)

_Plan metadata commit follows this summary._

## Files Created/Modified
- `.planning/phases/15-inventory-roster-reconciliation/15-CONTRACT.md` (created, 128 lines) — live storage + serve contract + verified maturity enum, every fact line-cited.
- `.planning/phases/15-inventory-roster-reconciliation/15-RECONCILIATION.md` (created, 96 lines) — per-slug roster disposition + D-04 hub pin + D-03 collision-free reshuffle + F-1/F-2/F-3 flags.

## Verification Evidence

**Live-source assertions (prove the docs state facts true of the live SQL/app.js):**
- tier CHECK `CHECK (tier IN ('substrate','behavior','frame'))` → 033:68 ✅
- append-only triggers: `grep -c "CREATE TRIGGER"` (non-comment) = 2; no trigger `ON economy_map.blocks` (empty) ✅
- publish RPC grant `GRANT EXECUTE ON FUNCTION economy_map.publish_block_version` → 039:82; `SET search_path` → 039:37 ✅
- anon published-only RLS `USING (status = 'published')` → 033:370 ✅
- maturity enum `CREATE TYPE economy_map.maturity` → 033:46; members nascent/emerging/contested/consolidating/mature; `building` absent ✅
- seed: `regulation-legal` seeded frame@7 (033:414); `negotiation-coordination` count = 0 (NOT seeded); `ON CONFLICT (slug) DO NOTHING` → 033:415 ✅
- frontmatter source-of-truth: `05-negotiation-coordination.md` `order: 5`; `01-identity-trust.md` `maturity: building` ✅

**Written-doc assertions:**
- 15-CONTRACT.md: `<automated>` CONTRACT_OK; 7 `## ` headings; all 5 enum members named; `building` stated + `building→emerging` remap; `publish_block_version`, `RLS`, `anon` headings present ✅
- 15-RECONCILIATION.md: `<automated>` RECONCILIATION_OK; all 9 slugs; all 5 headings; D-01..D-04 cited; contiguous `{1,2,3,4,5,6,7,8}` + moves 7→8 / 6→7 / 5→6; Option A pinned with B/C rejection ✅

**Phase boundary:** `git status --porcelain supabase/ docker/web/site/app.js` → empty ✅

## Decisions Made
None of substance beyond the plan — all four reconciliation calls (D-01..D-04) were pre-locked in CONTEXT and pre-verified in RESEARCH; this plan assembled them into the two reader-facing docs as specified. The Option-A hub accommodation, the `building→emerging` remap, the deferred `regulation-legal` frame slot, and the collision-free {1..8} reshuffle are all recorded per the locked decisions.

## Deviations from Plan

None - plan executed exactly as written.

(Note: `git status` shows `M .planning/STATE.md` in the working tree — this is the **orchestrator's** pre-spawn write recording "Phase 15 execution started", not an executor edit. STATE.md was NOT staged in either task commit; the executor did not modify STATE.md or ROADMAP.md, per instruction.)

## Issues Encountered
- The two acceptance-criteria heading greps that use `\|` alternation (`"publish RPC\|publish_block_version"`, `"RLS\|anon"`) and the contiguous-set grep (`"1.?2.?3.?4.?5.?6.?7.?8"`) require `grep -E` semantics; under default `grep` the alternation reads literally. The substantive content was present in both cases. Re-ran with `grep -E` (all pass) and tightened the reconciliation doc's ordered-set wording to the compact `{1,2,3,4,5,6,7,8}` form so the `.?`-spaced pattern matches. No content change to the contract; cosmetic wording change to the reconciliation set line.

## Known Stubs
None — both deliverables are complete reader-facing documents. (`regulation-legal` remaining body-less is an intentional deferred-frame disposition per D-02, not a stub: it is documented, decision-cited, and scheduled for a future EU AI Act milestone.)

## Threat Flags
None — Phase 15 introduces no net-new security surface (no body loaded, no migration applied, no app.js edit). The threat register's `mitigate` disposition (T-15-03, the tier-less/NULL block surface) is satisfied by 15-RECONCILIATION.md pinning Option A (keeps `tier NOT NULL`, enumerates `'hub'`) over the rejected Option B (nullable tier); all other dispositions are `accept (existing control documented)` and are recorded in 15-CONTRACT.md / 15-RECONCILIATION.md.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 16 (load-unpublished) has its two locked inputs: the documented contract (15-CONTRACT.md) and the approved per-slug disposition (15-RECONCILIATION.md). It executes the load + the D-03 reshuffle (highest-first, or one txn with deferrable unique) and applies the Option-A hub-tier migration.
- **Operator gate (SC#4):** Phase 15's deliverable is the reconciliation plan presented for approval. Per D-05 / EXECUTION_BRIEF §0, the operator must read and approve 15-CONTRACT.md + 15-RECONCILIATION.md before any Phase-16 write.
- **Flag F-2 carry-forward:** Phase-17 verification text must read `emerging` (not `building`) for the three substrate pills, per the D-01 remap.

## TDD Gate Compliance
N/A — `type: execute` plan; not a `type: tdd` plan, and tasks are doc-authoring (no behavior-adding source). No RED/GREEN/REFACTOR gate applies.

## Self-Check: PASSED
- FOUND: `.planning/phases/15-inventory-roster-reconciliation/15-CONTRACT.md`
- FOUND: `.planning/phases/15-inventory-roster-reconciliation/15-RECONCILIATION.md`
- FOUND commit: `91b6850` (Task 1)
- FOUND commit: `823d84b` (Task 2)

---
*Phase: 15-inventory-roster-reconciliation*
*Completed: 2026-06-08*
