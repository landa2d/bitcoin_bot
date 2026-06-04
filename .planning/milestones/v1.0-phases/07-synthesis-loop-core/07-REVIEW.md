---
phase: 07-synthesis-loop-core
reviewed: 2026-06-01T19:35:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - config/agentpulse-config.json
  - config/economy_map/synth_identity.md
  - docker/processor/agentpulse_processor.py
  - tests/test_07_synthesis.py
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-06-01T19:35:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 07 synthesis-loop core: the new primitives (`load_synth_identity`,
the economy_map read/insert helpers, `is_block_eligible`, `assemble_synthesis_input`,
`parse_synthesis_output`, `synthesis_sonnet_call`), the orchestrators (`synthesize_block`,
`synthesize_blocks_poller`), the scheduled wrapper, and the schedule registration in
`setup_scheduler()`. Scope was the ~557-line additive diff against
`b452d2aabe33a3d03e3b9e02a187c23b3902d9de`.

**Phase invariants verified and holding:**
- **GATE-01 (draft-only):** The single write is `economy_map_insert_block_body_version`,
  which POSTs to `/block_body_versions` with `Content-Profile: economy_map`, omits
  `status` (DB default `draft`), and carries no `published_at` / `current_body_version_id`
  / `maturity` keys. No code path touches `blocks.*` or a published row. Confirmed by
  reading the writer and the DB append-only trigger in migration 033.
- **Fail-loud:** `load_synth_identity()` returns `None` on missing/empty file and the
  poller aborts; the missing-agent-key branch aborts with a `failed` run row. Neither
  degrades to a silent no-op.
- **LLM routing:** `synthesis_sonnet_call` uses `httpx.post` to
  `{LLM_PROXY_URL}/anthropic/v1/messages` with the agent key in both `Authorization`
  and `x-api-key`. No `api.anthropic.com`, no `routed_llm_call`, no `/chat/completions`
  in live code (grep-confirmed; only docstring mentions).
- **economy_map access:** All reads/writes use direct PostgREST with `Accept-Profile` /
  `Content-Profile: economy_map`. No supabase-py `.in_()` / `.schema()`.
- **Eligibility (N/T):** `n >= N` OR (`n >= 1` AND age `>= T_days`); cold-start age clock
  uses earliest new-entry `created_at`; recency filtered by `created_at` watermark.
- **Per-block isolation:** Each block runs in its own `try/except`; one failure increments
  `failed` and continues.

The 18-test harness passes. No BLOCKER-class defects found. The findings below are
robustness, observability, and latent-correctness concerns appropriate for a draft-only
(operator-gated) writer.

## Warnings

### WR-01: No DB-level guard against duplicate open drafts — `block_has_open_draft` is a TOCTOU check

**File:** `docker/processor/agentpulse_processor.py:3098-3110` (`block_has_open_draft`),
`3265-3290` (`synthesize_block`); schema `supabase/migrations/033_economy_map_schema.sql:107-110`
**Issue:** The "one open draft per block" invariant (D-03) is enforced *only* by an
application-layer read (`block_has_open_draft`) executed at the top of `synthesize_block`,
with no transaction or lock around the later INSERT. The schema has a *non-unique* partial
index `idx_block_body_versions_status ... WHERE status = 'draft'` — there is no unique
constraint on `(block_slug)` for `status='draft'`. If a manual `/map-*` invocation, a
re-entrant scheduled run, or any future concurrent caller overlaps the check-then-insert
window, two `draft` rows for the same block are written with nothing to stop them. The
daily single-threaded `schedule` loop makes this unlikely *today*, but the invariant is
asserted by docstrings and tests as if it were guaranteed, and it is not.
**Fix:** Add a partial UNIQUE index so the DB enforces the invariant the app assumes:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_block_body_versions_one_open_draft
    ON economy_map.block_body_versions (block_slug)
    WHERE status = 'draft';
```
Then treat the resulting unique-violation on INSERT as a benign skip (race lost), keeping
`block_has_open_draft` as the cheap fast-path. This matches the project's recorded
preference for structural over application-layer enforcement.

### WR-02: `proposed_maturity` enum validated, but the six-section skeleton is not — malformed bodies become drafts

**File:** `docker/processor/agentpulse_processor.py:3225-3243` (`parse_synthesis_output`)
**Issue:** `synth_identity.md` (lines 56-73, 102) and the constant `SYNTH_SKELETON_HEADINGS`
both make the six-part RNDR-02 skeleton a hard output contract ("`body_md` must … contain
all six skeleton sections"). `parse_synthesis_output` validates only that `body_md` is
non-empty and that `proposed_maturity` is in the enum. A model response that drops or
renames headings (or returns prose with none of them) passes validation and is written as
a draft, deferring the defect to the Phase 8 sentinels / operator. Given the renderer
(RNDR-02) expects those exact headings, a structurally-wrong body can reach the publish
path if the operator approves without close reading.
**Fix:** Add a structural assertion before returning, e.g. require each heading to appear
(case-insensitive substring or a leading-`#` heading match) and raise `ValueError` on a
miss so the block is skipped rather than drafted malformed:
```python
missing = [h for h in SYNTH_SKELETON_HEADINGS if h.lower() not in body_md.lower()]
if missing:
    raise ValueError(f"body_md missing required skeleton sections: {missing}")
```

### WR-03: Unguarded indexing of the Anthropic response shape can crash on a 200 refusal/empty content

**File:** `docker/processor/agentpulse_processor.py:3360-3382` (`synthesis_sonnet_call`)
**Issue:** On a 2xx the function returns `resp.json()["content"][0]["text"]`. Anthropic
Messages can return a 200 whose `content` is empty (e.g. a `stop_reason` other than
`end_turn`, certain tool/refusal states) or a proxy-shaped body that lacks `content`. Any
of these raises `KeyError`/`IndexError`/`TypeError` rather than a descriptive failure. The
per-block `try/except` in the poller catches it, so it is isolated — but the block is
counted `failed` with an opaque traceback instead of a clear "empty model response" signal,
and a transient empty completion is indistinguishable from a real error.
**Fix:** Validate the shape and raise a descriptive `RuntimeError`:
```python
data = resp.json()
content = data.get("content") or []
if not content or not content[0].get("text"):
    raise RuntimeError(f"synthesis Sonnet returned no content: {data!r}")
return content[0]["text"]
```

### WR-04: `totals['eligible']` is a misnomer — it counts successful synthese, not eligible blocks

**File:** `docker/processor/agentpulse_processor.py:3520-3545` (`synthesize_blocks_poller`)
**Issue:** `eligible` is incremented only inside the `status == "synthesized"` branch, in
lockstep with `synthesized`. A block that *is* eligible but fails mid-synthesis (Sonnet
error, parse failure, INSERT non-2xx) is counted `failed` and never `eligible`; an
ineligible block is `skipped`. So `eligible == synthesized` always, and the run-logged /
logged "{eligible} eligible block(s)" line under-reports true eligibility whenever a block
fails. This corrupts the observability signal the run record exists to provide (e.g. "5
eligible, 2 failed" can never appear). The final log line "`{synthesized} draft(s) from
{eligible} eligible block(s)`" is therefore self-referential rather than informative.
**Fix:** Increment `eligible` based on the eligibility decision, independent of outcome —
e.g. have `synthesize_block` surface an `eligible: bool` in its result (or count it before
the `try`), then increment `synthesized` / `failed` separately.

### WR-05: Identity-gate abort logs no pipeline-run row, unlike the key-gate abort

**File:** `docker/processor/agentpulse_processor.py:3492-3517` (`synthesize_blocks_poller`)
**Issue:** The two fail-loud guards are asymmetric. The missing-key branch calls
`log_pipeline_start` then `log_pipeline_end(run_id, 'failed', ...)`, leaving a durable
`failed` run row. The missing/empty-identity branch returns `{'error': 'synth_identity
unavailable'}` *before* `log_pipeline_start`, so a persistently-missing identity file
produces a loud log line but **no run record** — every day, invisibly to anything querying
`pipeline_runs`. The recorded "fail-loud governance" preference favors durable, queryable
loudness for governance-relevant halts; a config drift that silences the whole synthesis
spine should be as visible in the run table as the key case. The inline comment even
acknowledges the asymmetry ("a loud no-run, not a 'failed' run row").
**Fix:** Log a `failed` run for the identity gate too (start a run, end it `failed` with
`{'error': 'synth_identity unavailable'}`) so both governance halts are queryable, or
document explicitly why the identity case is intentionally run-less.

## Info

### IN-01: Token-budget cap can strip timeline entries while a large prior body stays

**File:** `docker/processor/agentpulse_processor.py:3296-3320` (`assemble_synthesis_input`)
**Issue:** The token-budget loop `while len(included) > 1 and (len(prompt)//4) > max_tokens`
only drops timeline entries (oldest-first). The `PRIOR PUBLISHED BODY` section is never
trimmed, so a large prior body can force the prompt to shed real new evidence down to a
single entry while the bloat (the prior body) remains. For a draft writer this only
degrades quality, not correctness, and the omission is noted in-prompt.
**Fix:** Consider counting the prior body toward the budget and truncating it (with a
marker) before discarding new entries, or raise the floor below which entries are never
dropped.

### IN-02: `len(text)//4` token estimate is a coarse heuristic

**File:** `docker/processor/agentpulse_processor.py:3296` and `:3312`
**Issue:** Both cap decisions use `len(prompt)//4` as a token proxy. This under/over-counts
substantially for non-English text, URLs, and code, so the `max_input_tokens` guard is
approximate. Acceptable for a best-effort cap; flagged for awareness.
**Fix:** None required; if precision matters later, swap in a real tokenizer count.

### IN-03: `_economy_map_get` accepts only HTTP 200; PostgREST range responses use 206

**File:** `docker/processor/agentpulse_processor.py:3045-3066` (`_economy_map_get`)
**Issue:** The read helper raises on any status `!= 200`. PostgREST returns `206 Partial
Content` when a `Range`/`Prefer: count` style response is in play, and some Supabase
configs cap rows server-side. None of the current callers request ranges and the block set
is 7 rows, so this is latent only. Worth noting that the insert helper correctly accepts
`(200, 201)` while the read helper is 200-only.
**Fix:** If range/count reads are ever added, broaden to `if resp.status_code not in
(200, 206)`.

### IN-04: `synthesized_from_through` decoupled from the recency watermark (documented, noted for the consumer)

**File:** `docker/processor/agentpulse_processor.py:3281-3290` (`synthesize_block`)
**Issue:** `synthesized_from_through` is the run wall-clock (`datetime.now(timezone.utc)`),
while the next cycle's recency filter is `created_at > blocks.last_synthesized_at`. Phase 07
never sets `last_synthesized_at` (correct — that is the Phase 9 approval flow's job). This
is intentional (Pitfall 5) and correct for draft-only scope, but the downstream Phase 9
publish path MUST set `last_synthesized_at` from this `synthesized_from_through` value (not
the newest entry date) or entries created between synthesis and approval will be
double-counted or skipped. Flagging so the Phase 9 reviewer carries the contract.
**Fix:** None in Phase 07; ensure the Phase 9 publish RPC advances the watermark from the
draft's `synthesized_from_through`.

---

_Reviewed: 2026-06-01T19:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
