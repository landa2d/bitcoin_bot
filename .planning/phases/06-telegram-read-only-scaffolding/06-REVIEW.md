---
phase: 06-telegram-read-only-scaffolding
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - docker/gato_brain/gato_brain.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-30T00:00:00Z
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Reviewed the Phase 6 additions to `docker/gato_brain/gato_brain.py` (commits `ced9e15`, `5ca7076`, `55aa549`, `07c97a6`) — a read-only `economy_map` PostgREST GET wrapper (`_economy_map_get`, `_economy_map_count`, `get_blocks`, `get_draft_versions`, `get_unsorted_entries`, `get_unsorted_count`, `get_unabsorbed_count`), the `maturity_pill` renderer, `handle_map_status`, `handle_map_pending`, the `handle_map_command` dispatcher, and the `/map-` routing branch in `/chat`. The diff is purely additive (339 lines); no pre-existing code was modified.

**Read-only-by-construction holds.** A line-level scan of the new code (1525–1860) confirms zero write verbs: only `httpx.get` is used, no `httpx.post/put/patch/delete`, no `supabase.table(...)`, no `.insert/.update/.delete/.upsert`, and no `Content-Profile` (schema-WRITE) header. The only `economy_map` access is `httpx.get` with `Accept-Profile: economy_map`. The service_role key is confined to these gated `/map-*` reads, which is justified (anon RLS hides `block_slug='unsorted'` and non-published drafts per 033:373-376).

**Correctness verified against the schema.** `MATURITY_STAGE` exactly mirrors the migration-033 enum order (nascent→emerging→contested→consolidating→mature, 033:47-51). The fail-loud contract is honored everywhere: every wrapper raises `RuntimeError` on non-2xx, the count helper distinguishes a real `*/0` zero-count (status 200) from a read failure (raise), and the dispatcher's single top-level try/except returns `"Command failed: <e>"` rather than rendering a misleading empty/zero state. No query value is f-string-interpolated into the request path; all filter values pass through `params=` (httpx URL-encodes).

**Security:** No injection surface found. No hardcoded secrets. No write path. The two warnings below are robustness/correctness concerns, not security holes. The known truncation item is signaled (not silent), so it is downgraded to Info.

## Warnings

### WR-01: Empty `/map-` message can raise IndexError inside the dispatcher, masking the real intent

**File:** `docker/gato_brain/gato_brain.py:1838-1841` (`handle_map_command`)
**Issue:** The dispatcher does `parts = msg.split(None, 1)` then immediately `cmd = parts[0].lower()` **outside** the try/except. The `/chat` routing branch (`if _msg_lower.startswith("/map-")`) guarantees a non-empty `/map-…` token today, so `parts[0]` is currently always present. However, the handler is a public `def -> str` that the SUMMARY documents as "mirrors `handle_x_command`" and is a forward-contract entry point for Phases 9/10. If it is ever called with an empty or whitespace-only string (e.g. a future caller, or a refactor of the routing guard), `msg.split(None, 1)` returns `[]` and `parts[0]` raises `IndexError` **before** the try block — the fail-loud "Command failed" wrapper does not catch it, and the exception propagates into the FastAPI handler as a 500 rather than a friendly string. This contradicts the stated "one top-level try/except returning a human-readable failure string" contract.
**Fix:** Move the parse inside the try, or guard the empty case:
```python
def handle_map_command(message: str) -> str:
    try:
        parts = message.strip().split(None, 1)
        if not parts:
            return "Usage: /map-status, /map-pending"
        cmd = parts[0].lower()
        if cmd == "/map-status":
            return handle_map_status()
        elif cmd == "/map-pending":
            return handle_map_pending()
        else:
            return f"Unknown map command: {cmd}\nAvailable: /map-status, /map-pending"
    except Exception as e:
        logger.error(f"Map command failed: {message!r} — {e}")
        return f"Command failed: {e}"
```

### WR-02: `/map-status` issues a per-block unabsorbed COUNT inside a render loop while raising on any single failure — one slow/failed block aborts the entire status view

**File:** `docker/gato_brain/gato_brain.py:1730-1735` (`handle_map_status` → `get_unabsorbed_count` per block)
**Issue:** `handle_map_status` calls `get_unabsorbed_count(slug, ...)` once per block inside the tier loop (7 separate PostgREST GETs, each `timeout=10`). Each call raises `RuntimeError` on any non-2xx. Because the loop has no per-block isolation, a transient failure on the *last* block discards the *already-fetched* maturity/draft data for all seven and surfaces only `"Command failed: …"`. For a fail-loud surface this is defensible (better a loud error than a wrong number), but it makes `/map-status` brittle: the operator's primary situational-awareness command has 10 independent failure points (1 blocks read + 1 drafts read + 1 unsorted count + 7 unabsorbed counts), any one of which blanks the whole view, and a single hung block can stall the response up to ~10s. This is a robustness defect, not a correctness one. (Performance is out of v1 scope; the finding is the all-or-nothing failure coupling, not the N+1 itself.)
**Fix:** Either (a) wrap each per-block unabsorbed count so a single failure renders `·? new` for that block while the rest of the table still shows, e.g.:
```python
try:
    unabsorbed = get_unabsorbed_count(slug, b.get("last_synthesized_at"))
    new_seg = f"·{unabsorbed} new"
except RuntimeError:
    logger.error(f"unabsorbed count failed for {slug}", exc_info=True)
    new_seg = "·? new"
```
or (b) accept the fail-loud coupling but document it explicitly as the intended behavior and shorten the per-call `timeout` so a hung block degrades gracefully. If (a) is chosen, ensure a `?` placeholder is visually distinct from a real `0` so a degraded count is never mistaken for "nothing pending."

## Info

### IN-01: `get_unsorted_entries` orders by `created_at.desc`, but the schema's canonical newest-first ordering is `event_date DESC`

**File:** `docker/gato_brain/gato_brain.py:1648` (`order=created_at.desc`)
**Issue:** The migration's newest-first index and the documented convention (`idx_timeline_entries_block_slug_event_date ... event_date DESC`, 033:160-161, REQ-TIMELINE-NEWEST / RNDR-07) treat `event_date` as the canonical sort key. `/map-pending` instead orders the unsorted queue by ingestion time (`created_at`). For backlog triage this is a reasonable, internally-consistent choice (it matches the D-05 "absorption is ingestion-time" decision), but it diverges from how the web renderer and timeline present "newest" entries, so the operator may see a different top entry in `/map-pending` than on the map page. Flag for intentionality, not a defect.
**Fix:** Confirm the divergence is intended. If the operator should see the same "newest" ordering as the timeline, switch to `order=event_date.desc` (tie-break `created_at.desc`). Otherwise add a one-line comment noting the deliberate created_at ordering so a future maintainer doesn't "fix" it to match RNDR-07.

### IN-02: Unabsorbed count compares `created_at` against `last_synthesized_at` (a wall-clock `NOW()`), not the entry-window watermark `synthesized_from_through`

**File:** `docker/gato_brain/gato_brain.py:1668-1685` (`get_unabsorbed_count`)
**Issue:** `publish_block_version` sets `blocks.last_synthesized_at = NOW()` (033:304) — the wall-clock moment of publish — while `block_body_versions.synthesized_from_through` (033:101) is documented as "the upper bound of the entry window actually consumed." Counting `created_at > last_synthesized_at` therefore approximates "entries ingested after the last publish," which can drift from "entries not yet absorbed by synthesis": an entry whose `event_date` fell inside the consumed window but which was ingested (`created_at`) shortly after the publish ran would be (correctly) counted as new, whereas a backfilled entry with an old `event_date` ingested before publish would be (correctly) excluded — but if Phase 7 ever windows on `event_date`/`synthesized_from_through` rather than wall-clock, this count and the synthesis trigger will disagree. The plan (06-01-PLAN.md:75, SUMMARY:93) explicitly accepted `created_at`-vs-`last_synthesized_at` as the D-05 default "consistent with Phase 7 SYNT-01," so this is a documented decision, not a bug — recorded here so the reconciliation with Phase 7 SYNT-01/03 windowing is not lost.
**Fix:** No change required now. When Phase 7 SYNT-01 lands, verify its windowing column matches this one; if SYNT-01 windows on `synthesized_from_through`/`event_date`, update `get_unabsorbed_count` to match so the "·N new" count and the synthesis trigger never diverge.

### IN-03: `/map-pending` unsorted list is char-budget truncated; truncation is signaled but the truncation marker itself is not budget-accounted

**File:** `docker/gato_brain/gato_brain.py:1808-1822` (`handle_map_pending`, `CHAR_BUDGET = 3600`)
**Issue:** This is the executor-flagged item. Assessment: the truncation is **not silent** — when `omitted > 0` the handler appends `"…and {omitted} more (truncated)"`, so the operator is explicitly told entries were withheld and the count is exact. That, plus full-UUID/stateless listing (no ephemeral index to go stale) and the downstream Gato 4000-char split, makes this acceptable; it does not rise to a data-hiding Warning. Two minor residual notes: (1) the `"…and N more"` line is appended *after* the budget loop and is not itself counted against `CHAR_BUDGET`, so the final message can exceed 3600 chars by that line's length (harmless — well under Telegram's 4096, and the Node layer splits anyway); (2) the budget recomputes `sum(len(x)+1 for x in lines)` on every iteration, but since `lines` stops growing once truncation begins, the per-iteration check correctly counts *all* remaining entries into `omitted`.
**Fix:** No change required. Optionally, reserve a small fixed allowance for the truncation marker in the budget check (e.g. compare against `CHAR_BUDGET - 40`) so the final message is guaranteed under budget including the marker.

### IN-04: `tag_confidence` rendered verbatim; PostgREST returns `NUMERIC(3,2)` as a JSON string, so `conf:` may show e.g. `conf:0.70` with full precision and no None-vs-zero distinction issue

**File:** `docker/gato_brain/gato_brain.py:1812-1813` (`conf_str = f"conf:{conf}"`)
**Issue:** `tag_confidence` is `NUMERIC(3,2)` (033:156); PostgREST serializes numerics as JSON strings (e.g. `"0.70"`), so `f"conf:{conf}"` renders the raw string. The `conf is not None` guard correctly distinguishes an unset confidence (`conf:—`) from a real `0.00` (`conf:0.00`), which is good — no false-empty rendering. The only note is cosmetic: a real `0.00` confidence is shown as `conf:0.00`, which is correct but easy to mistake for "no signal" at a glance.
**Fix:** Cosmetic only. If desired, render `conf:{float(conf):.2f}` for consistent two-decimal display and to normalize string-vs-numeric serialization, keeping the existing `None → conf:—` guard.

---

_Reviewed: 2026-05-30T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
