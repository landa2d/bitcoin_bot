---
phase: 09-gated-publishing-approval-commands
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/gato_brain/gato_brain.py
  - supabase/migrations/038_publish_block_version_watermark.sql
  - tests/test_09_gated_publishing.py
findings:
  critical: 1
  warning: 2
  info: 2
  total: 5
status: resolved
resolution:
  resolved_in: 2c30a85
  resolved: 2026-06-03
  notes: >
    CR-01 fixed via migration 039 (COALESCE watermark guard), applied live + drift-clean.
    WR-01 fixed (RPC fn allowlist frozenset). IN-01/IN-02 fixed (reject missing-arg test;
    robust GATE-01 URL assertion). WR-02 accepted by design — the implemented D-05 case-(c)
    message already reads "...or doesn't exist". 15/15 phase-9 tests pass.
---

# Phase 9: Code Review Report

**Reviewed:** 2026-06-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** resolved (fixes in 2c30a85; CR-01 via live migration 039)

## Summary

Phase 9 adds owner-gated `/map-approve` and `/map-reject` Telegram commands to `gato_brain.py`,
a parameterized `_economy_map_rpc` PostgREST POST helper, and migration 038 which re-emits
`publish_block_version` to advance the watermark from `synthesized_from_through` instead of
`NOW()`.

The owner-gate (`access_tier == "owner"`) is correct and is enforced BEFORE any RPC call in
both write handlers. The UUID validation is strict (`uuid.UUID()` parse with catch on ValueError),
applied before any RPC call, and neither the UUID nor user input touches the URL path. The
`_economy_map_rpc` helper uses `json={"p_version_id": version_id}` (parameterized body) and
raises `RuntimeError` on any non-2xx. The `Content-Profile: economy_map` write header is set
correctly and no supabase-py `.rpc()`/`.schema()`/`.in_()` is used. The `access_tier` is
threaded from `ensure_user` (live DB read per request) through the `/chat` handler to
`handle_map_command` and into each write handler.

One blocker-level correctness defect exists in migration 038: the watermark can be silently
NULLed on approval of a draft whose `synthesized_from_through` column is NULL. Two warnings
address the latent `fn` path-injection risk in `_economy_map_rpc` and a TOCTOU false-already-
actioned message on non-existent UUIDs. Two info items flag missing test coverage and a
misleading GATE-01 assertion.

## Critical Issues

### CR-01: Migration 038 — NULL `synthesized_from_through` silently resets watermark to NULL

**File:** `supabase/migrations/038_publish_block_version_watermark.sql:68-72`

**Issue:** The entire motivation for migration 038 is to advance `blocks.last_synthesized_at`
to the draft's pinned `synthesized_from_through` instead of `NOW()`. Step 4 writes:

```sql
UPDATE economy_map.blocks
   SET ...
       last_synthesized_at = v_synthesized_from_through
 WHERE slug = v_slug;
```

`synthesized_from_through` is declared `TIMESTAMPTZ` with no `NOT NULL` constraint in
`033_economy_map_schema.sql` (line 101). If a draft row has a NULL `synthesized_from_through`
(manually inserted row, test harness, or a future code path that omits the field),
`v_synthesized_from_through` will be NULL and `last_synthesized_at` will be written as NULL.

A NULL `last_synthesized_at` is the cold-start sentinel in both the processor's
`fetch_block_new_entries` (`if watermark is not None: params["created_at"] = f"gt.{watermark}"`)
and in `is_block_eligible_for_synthesis` (the age clock falls back to the earliest entry).
Setting it to NULL silently **reverts a block to cold-start**, causing the next synthesis pass
to re-read all timeline entries — the exact double-count/skip problem migration 038 was meant
to fix. The block's prior watermark (which was non-NULL) is overwritten with no warning.

The processor always sets `synthesized_from_through` (line 3650 of `agentpulse_processor.py`),
so the common path is safe today. But the SQL function is the gating mechanism and must be
defensive regardless of caller behavior.

**Fix:** Use `COALESCE` to fall back to the prior watermark when `synthesized_from_through` is
NULL, rather than silently overwriting with NULL:

```sql
-- Step 4 (migration 038 replacement)
UPDATE economy_map.blocks
   SET current_body_version_id = p_version_id,
       maturity                = v_maturity,
       last_synthesized_at     = COALESCE(v_synthesized_from_through, last_synthesized_at)
 WHERE slug = v_slug;
```

This preserves the intent (use the draft's pinned window end when available) while refusing to
regress the watermark to NULL. A strict alternative is to add `NOT NULL` to
`block_body_versions.synthesized_from_through` and `RAISE` if null, but that requires a
schema-altering migration; `COALESCE` is the minimal safe fix inside the RPC body.

---

## Warnings

### WR-01: `_economy_map_rpc` — `fn` interpolated into URL path without validation

**File:** `docker/gato_brain/gato_brain.py:1622`

**Issue:** The RPC function name is interpolated directly into the PostgREST URL:

```python
f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
```

Both callers use hardcoded string literals (`"publish_block_version"`,
`"reject_block_version"`), so this is not currently exploitable. However, the function
accepts any `str fn` with no validation. A future caller passing user-controlled input
(e.g., refactoring that threads a command string through to `_economy_map_rpc`) would
create a URL path traversal vulnerability (e.g., `fn = "../../auth/v1/admin/users"` could
reach unexpected Supabase endpoints).

**Fix:** Add a strict allowlist at the top of `_economy_map_rpc`:

```python
_ALLOWED_RPC_FNS = frozenset({"publish_block_version", "reject_block_version"})

def _economy_map_rpc(fn: str, version_id: str) -> httpx.Response:
    if fn not in _ALLOWED_RPC_FNS:
        raise ValueError(f"_economy_map_rpc: '{fn}' is not an allowed RPC function")
    ...
```

This makes the surface self-defending and documents the intended callers.

### WR-02: TOCTOU — non-existent UUID shows misleading "already actioned" message

**File:** `docker/gato_brain/gato_brain.py:2032-2048`

**Issue:** `get_draft_version_by_id(version_id)` returns `None` when no row exists for the
given UUID. The code proceeds to call the RPC anyway. The RPC raises
`"not found or not in draft status"`, which is mapped to:

> "That draft was already published/rejected or doesn't exist — nothing to publish."

The phrase "already published/rejected" is accurate when the draft existed but was already
actioned. For a UUID that never existed (user typed a wrong ID), the same message is shown.
The "or doesn't exist" clause partially covers this, but the leading "already published/rejected"
framing is misleading and may confuse the operator into thinking they already approved something
they did not.

**Fix:** Differentiate the pre-flight check from the RPC response:

```python
draft = get_draft_version_by_id(version_id)
if draft is None:
    return (
        f"No draft found for version {version_id}. "
        "Check the UUID from /map-pending."
    )
# ... then call RPC; the "already actioned" path then means the race-condition case
```

This gives the operator an accurate signal without changing the fail-loud property.

---

## Info

### IN-01: Missing test — `/map-reject` with no argument

**File:** `tests/test_09_gated_publishing.py`

**Issue:** There is a test `test_approve_missing_arg_usage_hint_no_rpc` for `/map-approve`
with no UUID argument, but no corresponding test for `/map-reject` with a missing argument.
The validator `_validate_version_id` handles both commands identically, so coverage is
probably correct by symmetry, but the gap leaves the reject path unverified by name in the
test suite. If `_validate_version_id` is ever refactored asymmetrically, the missing-arg
reject path would silently regress.

**Fix:** Add `test_reject_missing_arg_usage_hint_no_rpc` mirroring `test_approve_missing_arg_*`:

```python
def test_reject_missing_arg_usage_hint_no_rpc():
    monkey = {}
    calls = _install_gb_stubs(monkey)
    try:
        out = gb.handle_map_command("/map-reject", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert "usage" in out.lower()
    assert calls["rpc"] == [], "missing arg must NOT call the RPC"
```

### IN-02: GATE-01 URL assertion is accidentally correct but fragile

**File:** `tests/test_09_gated_publishing.py:234`

**Issue:** The assertion that the write never targets the `blocks` table uses:

```python
assert "/blocks" not in captured["url"].rsplit("/", 1)[-1]
```

`captured["url"].rsplit("/", 1)[-1]` extracts only the last path segment (e.g.,
`"block_body_versions"`). Checking `"/blocks"` (with a leading slash) in a bare last segment
will always be False because a URL path segment never contains its own preceding slash. The
check is accidentally correct: `/block_body_versions` is the right last segment. But if the
URL were unexpectedly `/rest/v1/economy_map.blocks`, the last segment would be
`"economy_map.blocks"` and `"/blocks" not in "economy_map.blocks"` would still be True —
the assertion would pass while the URL was wrong.

**Fix:** Assert the full URL ends with the expected path, not just a substring absence:

```python
assert captured["url"].endswith("/rest/v1/block_body_versions"), \
    f"expected block_body_versions, got: {captured['url']}"
```

---

_Reviewed: 2026-06-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
