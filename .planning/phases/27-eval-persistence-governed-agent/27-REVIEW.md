---
phase: 27-eval-persistence-governed-agent
reviewed: 2026-06-25T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/newsletter/edition_eval.py
  - supabase/migrations/045_edition_evals.sql
  - tests/test_27_edition_eval.py
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-06-25
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 27 adds a fail-loud persistence helper (`edition_eval.py`), the `edition_evals`
migration (045), and a deterministic fixture suite. The stated contract is largely honored:
the module imports only stdlib, never imports `newsletter_poller`, uses `.eq()` only (no
`.in_()` footgun), validates the verdict-iff-ok NULLNESS invariant before insert, and
re-raises loudly on insert failure. The logger name (`newsletter-agent`) correctly matches
`newsletter_poller.py:75`, and every migration column/CHECK reference resolves against
023/034. The committed bcrypt hash is confirmed as an intentional audit record (per phase
context + 029 precedent) and is NOT flagged as a secret leak.

The headline defect is in the migration, not the helper: the `agent_wallets_v2` `ON CONFLICT`
clause **resets the governed eval wallet's balance on re-apply**, deviating from the very 029
precedent it claims to follow. The migration is explicitly advertised as "re-apply-safe in one
shot," so its own documented re-run path corrupts governed wallet accounting. Secondary
findings concern an under-mirrored Python validation (the milestone's feared numeric-zero
slips past it), a silent `None` return on empty insert results, and ambiguous trend-reader
semantics for the Phase 31 consumer.

This module sits on the milestone's governance/fail-loud spine, so wallet-state and
"no-silent-zero" defects are weighted accordingly.

## Critical Issues

### CR-01: Migration 045 resets the governed eval wallet balance on re-apply (governance/ledger corruption)

**File:** `supabase/migrations/045_edition_evals.sql:90-111`

**Issue:** The `agent_wallets_v2` upsert's `ON CONFLICT (agent_name) DO UPDATE` sets
`balance_sats = EXCLUDED.balance_sats` (25000) and `total_deposited_sats = EXCLUDED.total_deposited_sats`
(25000). The file's own header (lines 4-5, 28-30) advertises the migration as idempotent and
"`CREATE TABLE IF NOT EXISTS` makes the whole statement ... re-apply-safe in one shot," and the
SECTION 2 comment (lines 62-64) claims it follows "the 029 on-conflict-do-update idempotency
pattern."

It does not. Migration 029 — the cited precedent — deliberately updates **only**
`spending_cap_sats` and `spending_cap_window` on conflict (029:28-30) and **never** touches
`balance_sats` / `total_deposited_sats`, precisely so a re-apply does not reset a live wallet.
Because 045 *does* reset them, re-running this "re-apply-safe" migration after the eval agent
has spent will:
- refill `balance_sats` back to 25000 regardless of prior draw-down,
- reset `total_deposited_sats` to 25000,
- leave `total_spent_sats` untouched (it is not in the update list),

producing a wallet where `balance ≠ deposited − spent` — silent ledger corruption on a governed
wallet. This is the "wallet bug all over again" failure class the project's governance notes
explicitly warn against, triggered by the artifact's own documented re-run path. (The weekly
`spending_cap_sats=5000` window cap still bounds *actual* spend, which is why this is
ledger-integrity corruption rather than an uncapped-spend escape — but on a governance table
that is still incorrect behavior that must be fixed before this can be safely re-applied.)

**Fix:** Match the 029 precedent — exclude the balance/deposit ledger fields from the conflict
update, re-asserting only the governance fields (which is the actual idempotency intent):
```sql
ON CONFLICT (agent_name) DO UPDATE SET
    allow_negative = EXCLUDED.allow_negative,
    spending_cap_sats = EXCLUDED.spending_cap_sats,
    spending_cap_window = EXCLUDED.spending_cap_window,
    uncapped = EXCLUDED.uncapped,
    on_cap_behavior = EXCLUDED.on_cap_behavior,
    downgrade_map = EXCLUDED.downgrade_map;
    -- balance_sats / total_deposited_sats intentionally NOT reset on re-apply (029 precedent)
```

## Warnings

### WR-01: Python validation under-mirrors the DB CHECKs — the feared numeric/empty verdict slips through

**File:** `docker/newsletter/edition_eval.py:94-108`

**Issue:** The module docstring (lines 13-16, 54-56) and `write_eval_row` claim the Python guard
exists "because the in-memory test stub does not enforce DB CHECKs." But only two of the table's
CHECKs are mirrored: `eval_status IN ('ok','error')` and the verdict-iff-ok **nullness**
invariant. The value-domain CHECKs are NOT mirrored:
- `verdict IN ('passed','held_fabrication','held_voice','escalated')`
- `pipeline_version IN ('single_pass','block_v1')`
- `layer IN ('deterministic','judge')`

Consequence: a caller passing `eval_status='ok', verdict=0` (an integer `0`) passes the Python
check because `0 is not None` — i.e. the exact "numeric zero masquerading as a verdict/score"
this milestone is built to prevent slips past the in-Python guard and is caught only at the DB.
Likewise `verdict=""` or `error=""` (empty strings) satisfy the `is not None` checks, yielding a
degenerate "error with no reason" row that bypasses the intended "carries a reason" contract.
Because the test stub omits DB CHECKs, suites exercising these values would pass while production
would reject them — false confidence for the Phase 28/29 callers this helper is meant to protect.

**Fix:** Mirror the value-domain CHECKs too (and treat empty strings as invalid):
```python
_VERDICTS = ("passed", "held_fabrication", "held_voice", "escalated")
_PIPELINES = ("single_pass", "block_v1")
_LAYERS = ("deterministic", "judge")
if pipeline_version not in _PIPELINES:
    raise ValueError(f"pipeline_version must be one of {_PIPELINES}, got {pipeline_version!r}")
if layer not in _LAYERS:
    raise ValueError(f"layer must be one of {_LAYERS}, got {layer!r}")
ok_shape = eval_status == "ok" and verdict in _VERDICTS and error is None
err_shape = eval_status == "error" and verdict is None and bool(error)
```

### WR-02: `write_eval_row` returns `None` on a successful-but-empty insert — a silent no-op the fail-loud contract forbids

**File:** `docker/newsletter/edition_eval.py:142`

**Issue:** `return result.data[0]["id"] if result.data else None`. The function only re-raises on
an *exception*. If the insert executes without raising but `result.data` is empty (e.g. PostgREST
configured with `return=minimal`, or an RLS/representation quirk), the helper silently returns
`None`. To the Phase 28/29 caller that `None` is indistinguishable from "no row was written" — yet
no error was logged or raised. For a module whose entire purpose is "never a silent zero / a
caller cannot silently continue as if the row landed" (lines 17-19), a silent `None` after a
non-exception insert is exactly the ambiguity the contract is meant to eliminate.

**Fix:** Treat an empty result on a non-exception insert as a loud anomaly:
```python
if not result.data:
    logger.error(
        "edition_evals insert returned no row for newsletter_id=%s layer=%s attempt=%s",
        newsletter_id, layer, attempt,
    )
    raise RuntimeError("edition_evals insert returned no data — row may not have landed")
return result.data[0]["id"]
```

### WR-03: `read_eval_trend` has no `layer` filter and `limit` counts rows, not editions — ambiguous trend for the Phase 31 consumer

**File:** `docker/newsletter/edition_eval.py:157-176`

**Issue:** The reader filters only on `pipeline_version` and orders by `edition_number DESC` with
`limit=8`. Per the UNIQUE(newsletter_id, layer, attempt) shape, a single edition can produce
multiple rows: two layers (`deterministic`, `judge`) × up to three attempts (0/1/2). So `limit=8`
returns the 8 most recent *rows*, which may be only ~2-4 distinct editions of interleaved
layer/attempt rows — not "the recent 8 editions" a trend render (SURF-03) would expect. There is
also no secondary sort key, so rows sharing an `edition_number` come back in undefined order. The
consumer cannot reliably reconstruct one verdict-per-edition from this.

**Fix:** Filter to the trend-relevant layer/attempt and add a deterministic tiebreaker, e.g.:
```python
.eq("pipeline_version", pipeline_version)
.eq("layer", "judge")          # or accept a layer arg
.eq("attempt", 0)               # the headline eval, not rewrite re-evals
.order("edition_number", desc=True)
.order("created_at", desc=True) # deterministic tiebreak within an edition
.limit(limit)
```

## Info

### IN-01: Redundant import-time `LLM_PROXY_EVAL_KEY` constant vs the fresh-read getter

**File:** `docker/newsletter/edition_eval.py:40` (vs `43-51`)

**Issue:** Module-level `LLM_PROXY_EVAL_KEY = os.getenv("LLM_PROXY_EVAL_KEY")` is captured once at
import, while `_get_eval_api_key()` is documented (lines 44-49) to read fresh "so a late-bound
`.env` value is picked up." A Phase 28 caller that imports the constant directly would get the
possibly-stale import-time value, defeating the late-bind intent and creating two sources of
truth. Prefer exposing only the getter (or have the getter be the single accessor) to avoid the
footgun before the Phase 28 judge wires it in.

**Fix:** Drop the module-level constant and have callers use `_get_eval_api_key()` (renaming it
public, e.g. `get_eval_api_key()`), or define the constant as a thin alias the getter recomputes.

### IN-02: Committed bcrypt hash in SECTION 2 — confirmed intentional audit record (not a leak)

**File:** `supabase/migrations/045_edition_evals.sql:73`

**Issue:** The `$2b$12$...` `api_key_hash` is committed. Per the phase context and the 029
precedent (029:11), this is the intentional audit record of an internal proxy key whose plaintext
lives only in gitignored `config/.env`. Recorded here for traceability; deliberately NOT raised as
a secret-exposure finding. No action required.

### IN-03: Test suite does not assert reader query args or the empty-insert path

**File:** `tests/test_27_edition_eval.py:65-85, 228-242`

**Issue:** The stub's `select/eq/order/limit` ignore all arguments and return queued data
unconditionally, so a regression that dropped `.eq("pipeline_version", ...)` from
`read_eval_trend` (or mis-ordered the trend) would not be caught — the `.eq()`-only guarantee is
verified structurally (no `in_` method) but the *correctness* of the filter/order is not. There is
also no test for the WR-02 path (non-exception insert returning empty `data`). These are coverage
gaps, not production bugs.

**Fix:** Have the stub capture `eq`/`order`/`limit` call args so reads can assert the filter
columns/values and ordering; add a stub whose insert `.execute()` returns `data=[]` to lock the
empty-result behavior once WR-02 is resolved.

---

_Reviewed: 2026-06-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
