---
phase: 18-gated-batch-publish
reviewed: 2026-06-09T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/web/site/app.js
  - scripts/publish_economy_map_batch.py
  - scripts/verify_economy_map_publish.py
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-06-09
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the three Phase-18 "Gated Batch Publish" changes:

1. `docker/web/site/app.js` — additive flag-independent published-hub-body fetch in `loadHub` (lines 490-519).
2. `scripts/publish_economy_map_batch.py` — operator-gated, fail-loud batch publish over the 8 in-scope drafts.
3. `scripts/verify_economy_map_publish.py` — anon-key post-publish assertion harness.

Cross-checked every load-bearing docstring claim against the live source it cites: migration 039 (`publish_block_version` typed RAISE text), migration 041 (one-open-draft UNIQUE index), migration 033/043 (RLS policies, hub `agent-economy` tier, deferred `regulation-legal` exclusion), `gato_brain._economy_map_rpc` (idempotency-substring idiom), and the loader / crosslinks-harness READ idioms.

The app.js change is correct and faithfully mirrors the existing `loadBlock` published path (draft-first / published-fallback precedence, graceful-degrade to `HUB_STORYLINE`, `trimHubBody` applied to both body sources). Both Python scripts are syntactically valid, carry no hardcoded secrets, use the sanctioned direct-PostgREST + `Accept-Profile`/`Content-Profile` idioms, and never touch the supabase-py array-membership filter.

The headline defect is in `publish_economy_map_batch.py`: the documented "re-run completes a halted batch via the idempotent SKIP" recovery path is **unreachable** — the pre-flight gate fails first on any already-published slug, so an operator who hits a mid-batch failure cannot recover by re-running. Three lower-severity items (dead function, redundant assertion, unused select column) round out the findings.

## Critical Issues

### CR-01: Re-run after a mid-batch HALT can never complete — pre-flight gate makes the documented idempotent-SKIP recovery unreachable

**File:** `scripts/publish_economy_map_batch.py:319-369`
**Issue:**
The script documents (docstring lines 32-34, and inline at 354-356, 367) that a re-run "completes a halted batch" because an already-published version triggers the RPC's `not found or not in draft status` RAISE, which the loop treats as an idempotent SKIP. That recovery path is dead code on the real re-run flow.

Trace a mid-batch failure: blocks 1-3 publish, block 4 hits a transient error → the loop HALTs and `sys.exit(1)` (lines 358-369). The operator fixes the cause and re-runs. On re-run, `main()` first calls `resolve_all()` (line 314), which calls `resolve_open_draft()` for every slug. `resolve_open_draft` filters `status = eq.draft` (line 211). Blocks 1-3 are now `status='published'` (the publish RPC flipped them, migration 039 Step 1), so `resolve_open_draft` returns `None` for those three. They are therefore absent from `resolved`, and the pre-flight check:

```python
missing = [s for s in PUBLISH_ORDER if s not in resolved]
if missing:
    print(f"ERROR: pre-flight failed — no open draft resolved for: {missing}. ...")
    sys.exit(1)
```

fires and `sys.exit(1)` BEFORE the publish loop is ever reached. The idempotent-SKIP branch (lines 351-357) is only reachable if a slug is published by *another actor* between this run's pre-flight and its own loop — never on the documented re-run-to-complete path.

Operator impact: after the very first partial failure the batch is stuck. Every re-run dies at pre-flight reporting the already-published slugs as "no open draft resolved", which reads as corruption rather than progress, and the remaining unpublished blocks (e.g. blocks 5-8 + the hub) can never be published by this script. This violates the fail-loud-but-recoverable governance contract the docstring promises.

**Fix:** The pre-flight "every slug must resolve to an open draft" invariant is too strict for a resumable batch. Treat an already-published slug as a satisfied (skippable) member during pre-flight, not a miss. For example, resolve each slug to either its open draft OR its current published version, and only fail pre-flight when a slug has neither:

```python
def resolve_open_draft(slug: str) -> dict | None:
    rows = _economy_map_get(
        "block_body_versions",
        {
            "block_slug": f"eq.{slug}",
            "status": "in.(draft,published)",   # accept an already-published version
            "select": "id,proposed_maturity,status",
            "order": "created_at.desc",
            "limit": 1,
        },
    )
    if rows and rows[0].get("id"):
        return {
            "version_id": rows[0]["id"],
            "proposed_maturity": rows[0].get("proposed_maturity"),
            "status": rows[0].get("status"),
        }
    return None
```

then in the loop, pre-skip a slug already `published` (or let the existing RPC RAISE → idempotent SKIP handle it, which now actually fires because the version_id resolves). Update the docstring if the resumability semantics change. Whichever direction is chosen, the "re-run completes a halted batch" claim and the pre-flight gate must be made mutually consistent — today they directly contradict.

## Warnings

### WR-01: Dead function `count_published_blocks()` — defined, documented as the count source, never called

**File:** `scripts/verify_economy_map_publish.py:229-242`
**Issue:**
`count_published_blocks()` is fully implemented and its docstring states it "keeps the count consistent with the per-slug assertions" — implying it is the source of the count used in assertion (d). But assertion (d) actually uses `published_count = len(published_bodies)` (line 345); `count_published_blocks()` is never called anywhere in the module. It is dead code, and its docstring is misleading about how the count is computed. A maintainer reading the file would reasonably believe the count flows through this helper.

**Fix:** Either delete `count_published_blocks()` (lines 229-242) since `len(published_bodies)` already does the job, or call it and remove the duplicate inline count. Prefer deletion — the inline `len(published_bodies)` reuses the bodies already fetched for assertions (a)-(c) and avoids a second pass of per-slug reads.

### WR-02: `resolve_open_draft` "exactly one open draft" pre-flight contract is silently weaker than documented

**File:** `scripts/publish_economy_map_batch.py:199-222, 319-328`
**Issue:**
The docstrings repeatedly promise that pre-flight verifies each slug resolves to "exactly one open draft" (lines 28-29, 319-320). The implementation uses `.order(created_at.desc).limit(1)` and accepts the first row. Migration 041's UNIQUE partial index makes "at most one" true today, so this is latent rather than active — but if that invariant is ever relaxed (or a second draft slips in before the index is enforced), the script would silently publish the *newest* draft and never detect the "more than one" condition the docstring claims to guard. "Exactly one" is asserted but only "at most one (newest wins)" is implemented.

**Fix:** Either soften the docstrings to "the newest open draft (mig 041 guarantees at most one)" so the code and contract match, or actually enforce exactly-one by reading `limit=2` and failing pre-flight loud if two rows come back for any slug. The latter is the more defensible fail-loud posture given the governance memory ("halt loudly on ambiguous inputs").

### WR-03: Idempotent-SKIP marker also matches a genuinely-missing/wrong version_id, masking a real fault as success

**File:** `scripts/publish_economy_map_batch.py:126-128, 351-357`
**Issue:**
`_RPC_ALREADY_ACTIONED = "not found or not in draft status"` is matched as the idempotency signal. Migration 039 raises that exact text for THREE distinct conditions: (a) version already published — benign skip; (b) version was rejected/superseded — arguably benign; (c) the `p_version_id` does not exist at all — a genuine fault (stale resolution, wrong UUID, deleted row). The loop treats all three identically as "SKIP: already published (idempotent re-run)" and continues to a `DONE` success. Case (c) cannot occur on the happy path because `version_id` comes straight from a just-resolved open draft, but combined with CR-01's resumability gap and any future refactor that resolves version_ids from a cached manifest, a stale/wrong UUID would be silently swallowed as success rather than halted — contrary to the fail-loud intent.

**Fix:** Tighten the recovery to re-confirm state before declaring an idempotent skip: on catching the marker, re-read the version row by id and only treat it as a benign skip if it resolves to `status in (published, superseded)`; otherwise re-raise / HALT. This keeps the genuine-fault case loud while preserving the resume-after-publish skip.

## Info

### IN-01: `read_old_maturity` selects an unused `slug` column

**File:** `scripts/publish_economy_map_batch.py:235`
**Issue:** The select list is `"slug,maturity"` but only `maturity` is read (`rows[0].get("maturity")`, line 241). The `slug` column is never used — the row was already filtered by `slug=eq.{slug}`.
**Fix:** Drop `slug` from the select: `"select": "maturity"`. Minor; harmless but slightly misleading.

### IN-02: Assertion (b) hub check is redundant

**File:** `scripts/verify_economy_map_publish.py:314`
**Issue:** `if HUB_SLUG in missing_published or HUB_SLUG not in published_bodies:` — the two clauses are mutually equivalent by construction (a slug is in exactly one of `missing_published` / `published_bodies`), so the `or` can never differ between the two sub-conditions. Not a bug, but the doubled condition implies a distinction that does not exist and invites a future maintainer to "fix" the wrong half.
**Fix:** Collapse to a single clause: `if HUB_SLUG not in published_bodies:`.

### IN-03: Cross-link check re-fetches each target body via per-target reads

**File:** `scripts/verify_economy_map_publish.py:333`
**Issue:** Inside the cross-link loop, `fetch_published_body(target)` is re-invoked for every link target even when `target` is one of the in-scope slugs already resolved into `published_bodies`. Correct, but it issues redundant network reads (two PostgREST GETs per distinct target). Flagged as Info only (performance is out of v1 scope); noting because it also means a transient network blip mid-loop raises and aborts verification (handled, but worth awareness).
**Fix:** When `target in published_bodies`, reuse the cached body instead of re-fetching; only fall through to `fetch_published_body(target)` for out-of-scope targets.

---

_Reviewed: 2026-06-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
