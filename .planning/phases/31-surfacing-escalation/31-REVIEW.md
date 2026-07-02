---
phase: 31-surfacing-escalation
reviewed: 2026-07-02T22:53:06Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - docker/processor/agentpulse_processor.py
  - docker/gato_brain/gato_brain.py
  - docker/gato/inject-gato-brain.mjs
  - tests/test_31_send_telegram.py
  - tests/test_31_notify_eval.py
  - tests/test_31_newsletter_eval_handler.py
findings:
  critical: 0
  warning: 7
  info: 5
  total: 12
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-07-02T22:53:06Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the phase-31 diff (`32c3662..HEAD`): `send_telegram` hardening + boot-time config check + auto-publish return-check (31-01), the Friday-notify eval summary (`_read_edition_evals`, `_format_notify_eval_section`, extended `scheduled_notify_newsletter`) (31-02), and the owner-gated `/newsletter_eval` deep view in gato_brain plus the `isNewsletterEval` allowlist entry (31-03). All 41 phase tests pass. Verified against the live schema (045), the Phase 30 writer semantics (`write_eval_row` / `_persistable_attempt`: every `ok` judge attempt row carries the single top-level verdict — the formatters' "first/max judge verdict" picks are consistent with that), the `/chat` dispatch order (nothing swallows `/newsletter_eval` before branch 2c-3), and the `access_tier` derivation (DB-backed `corpus_users`, gated behind `X-Gato-Secret` — the owner gate is sound and refuses before any read).

No security vulnerabilities or crash paths found. However, both new eval readers key on `edition_number` while the schema's identity is `newsletter_id` — reprocessing an edition (a supported flow via `edition_override`) mixes eval rows from multiple generations and can display a stale verdict in the operator's publish-gating notify. Several formatter paths also ignore `eval_status='error'` rows, the trend view's row-limit under-covers and can truncate a group into a wrong verdict, and the Friday notify's underscore-heavy eval section interacts badly with `parse_mode='Markdown'`. These matter because this phase's output is precisely the calibration signal the operator will use to flip `enforce=true`.

## Warnings

### WR-01: Edition-keyed eval reads mix rows from multiple generations of the same edition

**File:** `docker/processor/agentpulse_processor.py:10696` (`_read_edition_evals`), `docker/processor/agentpulse_processor.py:10741` (`_format_notify_eval_section`), `docker/gato_brain/gato_brain.py:2440` (`_eval_read_by_edition`), `docker/gato_brain/gato_brain.py:2551` (`_format_eval_detail`)
**Issue:** `edition_evals` identity is `UNIQUE (newsletter_id, layer, attempt)` (045), but every phase-31 read filters only on `edition_number`. Reprocessing an edition is a supported flow — `prepare_newsletter_data` has an explicit `edition_override` "for reprocessing" (agentpulse_processor.py:5427), and the fallback numbering is `count + 1` (line 5439), so two `newsletters` rows with the same `edition_number` and distinct `newsletter_id`s (each with its own Phase-30 eval rows) are realistic. When that happens:
- `_format_notify_eval_section` resolves `max(det_rows, key=attempt)` among multiple attempt-0 deterministic rows from different generations — `max()` returns the first tie, and the query orders only `(pipeline_version, attempt)`, so which generation's verdict/flags render is DB-arbitrary (a stale `passed` or a stale `WOULD HAVE HELD` in the Friday notify).
- `_format_eval_detail` does `mech.extend(...)` / `fab.extend(...)` across ALL deterministic rows for the edition, double-counting flags across generations, and `scored[-1]` (max attempt) ties arbitrarily across generations.

This corrupts exactly the calibration signal the operator uses during the report-only window.
**Fix:** Disambiguate by generation. In `scheduled_notify_newsletter` the current draft row is already in hand — pass `draft.data[0]['id']` and filter the primary pipeline's rows on `newsletter_id`; for `block_v1` (a different `newsletter_id` by design), keep rows only from the newest `newsletter_id` per `pipeline_version`, e.g.:

```python
# after fetching rows ordered by created_at desc:
latest_nl = {}
for r in rows:
    latest_nl.setdefault(r["pipeline_version"], r["newsletter_id"])
rows = [r for r in rows if r["newsletter_id"] == latest_nl[r["pipeline_version"]]]
```

Apply the same dedup in gato_brain's `_eval_read_by_edition` consumers (add `newsletter_id, created_at` awareness to the select/order).

### WR-02: `_eval_read_trend` limit is a ROW limit, not an edition limit — trend under-covers and can truncate a group into a wrong verdict

**File:** `docker/gato_brain/gato_brain.py:2477-2494` (`_eval_read_trend`), `docker/gato_brain/gato_brain.py:2634` (`_format_eval_trend`)
**Issue:** Each (edition, pipeline_version) produces 2-4 rows (1 deterministic + 1-3 judge attempts). `limit=8` therefore returns ~2-4 editions, not the "~8 recent editions" the docstring and `_EVAL_TREND_MAX_LINES` promise (the test masks this: 10 passed editions × 2 rows → 4 trend lines, which satisfies `0 < len <= 8`). Worse, the query orders ONLY `edition_number desc` — no secondary order — so the limit cuts the boundary edition's group at an arbitrary row: if its judge rows are cut and only the deterministic row (verdict `passed` for a held_voice edition — Layer-1 passed, judge held) survives, the trend line renders `passed` for an edition whose real verdict was `held_voice`, with `attempts=1` and zeroed counts.
**Fix:** Fetch enough rows to cover 8 full groups and drop the (possibly partial) boundary group, or do a first query for the 8 most-recent distinct `edition_number`s and then `.eq()` per edition. At minimum add `.order("attempt", desc=True)` as secondary order and raise the limit to `8 * 4`, then discard the oldest edition's group if it may be truncated.

### WR-03: `eval_status='error'` rows render indistinguishably from clean rows; the `error` reason is never surfaced

**File:** `docker/processor/agentpulse_processor.py:10787-10790` (`final_judge` selection), `docker/processor/agentpulse_processor.py:10796-10803` (flags render), `docker/gato_brain/gato_brain.py:2551` (`_format_eval_detail`)
**Issue:** The 045 schema and `write_eval_row` are built around a fail-loud `eval_status='error'` + `error` reason (verdict NULL, `deterministic_flags` defaulting to `{}`), but no phase-31 formatter reads `eval_status` or `error`:
- Notify: `final_judge = max(judge_rows, key=attempt)` can select an error row (empty `judge_scores`, verdict None) even when an earlier `ok` attempt carries real scores and the run verdict → renders `verdict: unknown` + `scores: continuity=? hedging_filler=? ...` while good data exists. (The detail view's `scored` filter avoids this; the notify does not — inconsistent.)
- A deterministic error row (eval outage path, `newsletter_poller.py:600`) renders `flags: fabrication=0 unverified=0 mechanical=0` — indistinguishable from "gate ran clean" when the gate never ran.
- Neither the notify nor `/newsletter_eval` ever shows the recorded `error` text, so the operator cannot see WHY an eval errored from Telegram — the exact "silent zero" failure mode the eval schema was designed to prevent.
**Fix:** In both formatters, prefer the highest-attempt row with `eval_status == "ok"` for verdict/scores, and render an explicit error line when any row has `eval_status == "error"`:

```python
error_rows = [r for r in rows if r.get("eval_status") == "error"]
if error_rows:
    lines.append(f"⚠ eval ERROR: {error_rows[-1].get('error', 'unknown')[:200]}")
```

### WR-04: Friday-notify eval section vs `parse_mode='Markdown'` — underscores silently mangle labels (parity-dependent)

**File:** `docker/processor/agentpulse_processor.py:9674` (Markdown send), `docker/processor/agentpulse_processor.py:10741` (formatter output)
**Issue:** The eval section is dense with underscore-bearing tokens (`single_pass`, `block_v1`, `held_voice`, `held_fabrication`, `hedging_filler`, `repeated_subtopics`), and `send_telegram` sends with legacy `parse_mode='Markdown'`, where `_` toggles italic. When the message's total `_` count is odd, the API returns 400 and the plain-text fallback saves it (at the cost of a spurious warning every Friday). When the count is even — which verdict values make nondeterministic — Telegram accepts the message and pairs underscores ACROSS tokens as italic entities, stripping them: e.g., `single_pass ... held_voice` renders as "single*pass* … held*voice*"-style corruption with the labels' underscores deleted and arbitrary spans italicized. The operator's calibration report renders differently week to week depending on underscore parity.
**Fix:** Send the eval-bearing notify as plain text (skip the Markdown first attempt for this message), or escape underscores in the formatter output (`text.replace("_", "\\_")`), or switch `send_telegram` to no `parse_mode` for messages containing unpaired-risky characters.

### WR-05: `scheduled_notify_newsletter` logs "notification sent" before/without sending; supabase-None path silently suppresses the notify

**File:** `docker/processor/agentpulse_processor.py:10824-10830`
**Issue:** `logger.info("[PIPELINE] Newsletter notification sent")` fires unconditionally at function ENTRY. It is now false in three paths the phase itself added or touched: (a) `if not supabase: return` exits without sending anything — and without any warning/error log — even though the pre-change function always sent the static notice and the docstring promises "the static line still sends"; (b) terminal delivery failure (the CRITICAL fires, yet the INFO above it claims "sent"); (c) the exception path. An operator grepping logs sees "Newsletter notification sent" alongside a CRITICAL delivery failure. The supabase-None skip is test-locked (`test_notify_no_supabase_guard_returns`) so it may be plan intent, but silent suppression contradicts the phase's own fail-loud posture (D-02/D-04).
**Fix:** Move the INFO log after a successful `send_telegram(...)` return, and ERROR-log the early return:

```python
if not supabase:
    logger.error("[EVAL-NOTIFY] supabase unavailable — Friday notify SKIPPED")
    return
...
if send_telegram(message):
    logger.info("[PIPELINE] Newsletter notification sent")
else:
    logger.critical(...)
```

### WR-06: `send_telegram` env-unset path logs up to 1000 chars of the message — callers pass draft/briefing prose, contradicting the T-30-LOG claim in its own docstring

**File:** `docker/processor/agentpulse_processor.py:9640-9646`
**Issue:** The new env-unset branch logs `" ".join(str(message).split())[:1000]`. The docstring asserts "never the bot token or raw draft prose (T-30-LOG)", but that guarantee doesn't hold for the function's inputs: `agentpulse_processor.py:5913` passes `content_telegram`/`content_markdown[:4000]` (newsletter body) and `:10347` passes `header + briefing_text` (full briefing prose). With Telegram env unset, up to 1000 chars of that prose lands in container logs — the exact boundary T-30-LOG draws.
**Fix:** Log a bounded label instead of content: message length plus the first ~80 chars, e.g. `logger.error("[TELEGRAM-SEND] cannot send — env unset; len=%d head=%r", len(message), safe[:80])`, or drop the message body from this log entirely (the boot-time `[TELEGRAM-CONFIG]` ERROR already flags the gap).

### WR-07: `_EVAL_FAIL_BELOW` hardcodes judge thresholds that are operator-tunable at runtime — failing-dim detection will drift from the actual verdict

**File:** `docker/gato_brain/gato_brain.py:2429-2436`
**Issue:** The judge's per-dimension thresholds are NOT fixed: `judge_loop._merged_config` merges `config/agentpulse-config.json → edition_eval.thresholds` over `DEFAULT_CONFIG` key-by-key (judge_loop.py:116-122), and the live config carries them (agentpulse-config.json:145). gato_brain mirrors today's values in a hardcoded dict and — unlike the processor — has no `../config` mount (docker-compose.yml gato_brain `volumes:` mounts only the workspace), so it cannot even read the tuned values. After any operator threshold tune (a stated Phase-29 capability), `/newsletter_eval`'s fail-below check (which gates whether evidence/exemplars render) diverges from the judge's actual decision: a dim the judge held on renders score-only, or a passing dim renders "⚠ evidence". The comment acknowledges the mirror but ships no guard.
**Fix:** Either (a) mount `../config` read-only into gato_brain and read `edition_eval.thresholds` per-call with the same defaults, or (b) stop re-deriving failure in gato_brain: render evidence for any dim whose worst-body entry carries non-empty `evidence`/`exemplar_before` (the judge only populates those for dims it flagged), which stays correct under any threshold config.

## Info

### IN-01: Non-numeric edition argument silently falls back to the latest view

**File:** `docker/gato_brain/gato_brain.py:2694-2711` (`handle_newsletter_eval`)
**Issue:** `/newsletter_eval 1O3` (typo) or any non-numeric arg silently renders the LATEST edition's detail — the operator can believe they are looking at the edition they asked for. The T-31-09 comment says "falls through rather than raising", but falling through to a different edition is worse than an error message.
**Fix:** For a non-empty arg that is neither `trend` nor numeric, return `f"Unrecognized argument {arg!r} — use /newsletter_eval [<edition#>|trend]."`.

### IN-02: Trend query fetches `judge_scores` (the heaviest JSONB, carrying quoted draft prose) but never uses it

**File:** `docker/gato_brain/gato_brain.py:2477-2494` (`_eval_read_trend`)
**Issue:** The select includes `judge_scores` and the docstring claims it feeds the fab/unv/mech counts — those actually come from `deterministic_flags`. `_format_eval_trend` never reads `judge_scores`, so every trend call pulls up to 8×2 rows of evidence + exemplar prose for nothing.
**Fix:** Drop `judge_scores` from the trend select (and correct the docstring).

### IN-03: Dispatch prefix mismatch between gato allowlist and gato_brain handler

**File:** `docker/gato_brain/gato_brain.py:3055`, `docker/gato/inject-gato-brain.mjs:115`
**Issue:** The mjs allowlist uses `/^\/newsletter_eval\b/i` while gato_brain matches `startswith("/newsletter_eval")` — e.g. `/newsletter_evaluate` is rejected by gato but would reach `handle_newsletter_eval` if posted directly to :8100. Harmless via Telegram; keeps the two surfaces from being an exact contract.
**Fix:** In gato_brain use `_msg_lower.split()[0] in ("/newsletter_eval",)` or a regex with a word boundary.

### IN-04: Detail view suppresses failing-dim evidence when one body's score is non-numeric

**File:** `docker/gato_brain/gato_brain.py:2590-2593` (`_format_eval_detail`)
**Issue:** `if not (_eval_is_number(tech) and _eval_is_number(impact)): continue` skips the fail check even when the OTHER body has a numeric failing score (e.g., partial judge output where technical scored 1 and impact is missing). Inconsistent with the notify path's `_notify_worst_dim_score`, which takes the min over available numeric scores.
**Fix:** Evaluate failure over whichever body scores are numeric: `nums = [v for v in (tech, impact) if _eval_is_number(v)]; if nums and min(nums) < _EVAL_FAIL_BELOW[dim]: ...`.

### IN-05: Oversized single lines defeat the chunk splitter — the whole send now fails loudly

**File:** `docker/processor/agentpulse_processor.py:9650-9664`
**Issue:** Pre-existing splitter behavior, newly surfaced by the bool contract: a single line >4000 chars becomes its own >4096 chunk; both the Markdown and plain-text POSTs 400, `send_telegram` returns False, and the new hold/eval-critical callers CRITICAL-log a delivery failure. Any caller emitting a long unbroken line (e.g., a long URL list) now trips `[EVAL-ALERT] CRITICAL` deterministically.
**Fix:** Hard-wrap lines longer than `MAX_LEN` before the newline-based split: `line = line[:MAX_LEN]` chunks in a loop.

---

_Reviewed: 2026-07-02T22:53:06Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
