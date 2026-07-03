---
phase: 31-surfacing-escalation
verified: 2026-07-03T07:15:39Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
---

# Phase 31: Surfacing & Escalation Verification Report

**Phase Goal:** Operator-facing eval surfacing and escalation — hold/escalation alerts via a hardened `send_telegram` (never a silent no-op), a compact per-draft eval summary in the Friday newsletter notify (plain select, no Processor LLM), and a live `/newsletter_eval` (+ `trend`) Gato command wired into the `isGatoBrainCommand` allowlist so it is not a dead command.
**Verified:** 2026-07-03T07:15:39Z
**Status:** passed
**Re-verification:** No — initial verification

## Method Note

This verification goes beyond static grep/read checks: the actual live `processor` and `gato_brain` containers were exercised directly (via `docker compose exec ... python -c ...`) against the real Supabase project, including inserting/deleting synthetic `edition_evals` rows to force the D-06/D-07/D-08/D-10 rendering branches and confirm real output — not just unit-test doubles. The live `gato` container's compiled `dist` bundle was also inspected to confirm `isNewsletterEval` is present in the running artifact, not just source.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `send_telegram` returns bool, never raises, hardened in place (D-01/D-02) | VERIFIED | `docker/processor/agentpulse_processor.py:9631` `def send_telegram(message: str) -> bool`. Live-exercised in the running processor container with `TELEGRAM_BOT_TOKEN=None`: returned `False`, never raised. |
| 2 | Env-unset path ERROR-logs a fixed grep-able label, never a silent bare return (SURF-01) | VERIFIED | Live run in the processor container: `[TELEGRAM-SEND] cannot send — TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_ID unset; len=1529 head=...` — bounded to len+80-char head (WR-06 fix confirmed live, not just in source). |
| 3 | Boot-time `[TELEGRAM-CONFIG]` ERROR fires when env unset; service still runs (D-04) | VERIFIED | `_check_telegram_config()` at `:9615`, called from `init_clients()` at `:435`. Live processor logs show NO `[TELEGRAM-CONFIG]` line (env is set) and the container is healthy/running. |
| 4 | Auto-publish notification is a critical caller — checks `send_telegram`'s bool return, CRITICAL-logs `[EVAL-ALERT]` on failure (D-03) | VERIFIED | `scheduled_auto_publish_newsletter` at `:10942` — `if not send_telegram(...): logger.critical("[EVAL-ALERT] CRITICAL — auto-publish notification delivery FAILED ...")`. Only this site + the Friday notify check the return; the other 23 call sites remain fire-and-forget (grep count = 25 total call sites, matches SUMMARY claim). |
| 5 | Friday notify (`scheduled_notify_newsletter`) appends a compact per-draft eval section covering both `pipeline_version`s (D-05), read via a plain `.eq()`-only select, no LLM | VERIFIED | `_read_edition_evals` (`:10691`) is `.eq("edition_number", ...)`-only, no `.in_(`. Live-exercised against real Supabase with synthetic rows inserted then deleted — `_format_notify_eval_section` rendered `— Primary (single_pass) —` before `— Telemetry (block_v1) —` (D-05 order confirmed live). No `routed_llm_call`/proxy reference in the function region. |
| 6 | Mechanical flag count ALWAYS shown, even on a passed verdict (D-06 / P29 D-12) | VERIFIED | Live render showed `flags: fabrication=0 unverified=0 mechanical=1` on a deterministic-layer `passed` row while the judge layer held — the mechanical count was present. |
| 7 | A pipeline_version with no eval rows renders explicit `⚠ no eval recorded for this draft` (D-07) | VERIFIED | Live render (synthetic single_pass-only insert) showed `— Telemetry (block_v1) —` / `⚠ no eval recorded for this draft` for the version with zero rows. |
| 8 | `held_*` verdict with `enforce=False` renders `⚠ WOULD HAVE HELD (report-only)` at top of block (D-08) | VERIFIED | Live render with a synthetic `held_voice` judge row and `enforce=False` produced `⚠ WOULD HAVE HELD (report-only)` immediately above `verdict: held_voice`. |
| 9 | Friday notify is a critical caller — checks `send_telegram`'s return, CRITICAL-logs `[EVAL-ALERT]` on delivery failure (D-03) | VERIFIED | `scheduled_notify_newsletter` `:10888` — `if send_telegram(message): ... else: logger.critical("[EVAL-ALERT] CRITICAL — Friday notify delivery FAILED for edition #%s", ...)`. Post-review WR-05 fix confirmed live in source: the "sent" INFO fires only on `True`; the no-supabase path ERROR-logs `[EVAL-NOTIFY] supabase unavailable — Friday notify SKIPPED` rather than a bare return. |
| 10 | `/newsletter_eval` (no-args) renders the latest edition WITH eval rows, or an explicit "no eval yet" message if none exist anywhere (D-09) | VERIFIED | Live call inside the running gato_brain container against the real (currently-empty) `edition_evals` table returned `'No eval has run for any edition yet.'`. With synthetic rows inserted for a fake edition + a direct `<edition#>` call, `_format_eval_detail` rendered the full detail view (see #11). |
| 11 | Detail view: per-dim score lines for ALL 5 dims; bounded evidence + before/after exemplars ONLY for failing dims; mechanical flags listed even on `passed` (D-10 / P29 D-12) | VERIFIED | Live render (synthetic `held_voice` judge row, one failing dim `hedging_filler`): all 5 dims printed (`continuity`, `hedging_filler`, `clickbait`, `repeated_subtopics`, `specificity`); only `hedging_filler` printed `⚠ evidence` / `✎ before` / `✎ after`; `mechanical flags (1): - link_check: test flag` printed despite the deterministic layer being `passed`. |
| 12 | `/newsletter_eval trend` renders recent editions' verdicts, `.eq()`-only (D-11) | VERIFIED | Live call: `_eval_read_trend(supabase, pv, limit=8)` uses `.eq("pipeline_version", ...)`, no `.in_(`. Empty-table live call returned `'No eval trend yet — no edition has been evaluated.'` correctly (no crash). |
| 13 | The whole `/newsletter_eval` handler is owner-gated — refuses BEFORE any read, no draft prose leak (D-12) | VERIFIED | Live call with `access_tier='free'` against both the empty table AND a table containing synthetic unpublished draft prose (judge evidence/exemplars) returned only the fixed refusal string `"🔒 /newsletter_eval is owner-only — ..."` — zero leakage confirmed by direct inspection of the returned string. |
| 14 | `/newsletter_eval` is NOT a dead command — matches a dedicated `isNewsletterEval` regex OR'd into `isGatoBrainCommand` in `inject-gato-brain.mjs`, live in the rebuilt gato container | VERIFIED | Source: `inject-gato-brain.mjs:115-116` (`isNewsletterEval` regex + OR-chain). Running container: `docker compose exec gato` — the injected `/app/src/telegram/bot.ts` contains `isNewsletterEval` at lines 491-492, AND the **compiled** `/app/dist/*.js` bundle (`reply-Kz1AONaH.js` etc.) contains `isNewsletterEval` — confirming the live process is actually running this code, not stale. |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/processor/agentpulse_processor.py` | `send_telegram` bool-return hardening + `_check_telegram_config` + critical-caller checks + `_read_edition_evals`/`_format_notify_eval_section` | VERIFIED | All functions present, syntax-clean (`ast.parse` OK), live in the running container (`hasattr` checks all True). |
| `docker/gato_brain/gato_brain.py` | `/newsletter_eval` dispatch + `handle_newsletter_eval` + `.eq()`-only readers + detail/trend formatters | VERIFIED | All functions present, dispatched before intent router (`:3077` vs `intent_router.route` at `:3168`), live in the running container. |
| `docker/gato/inject-gato-brain.mjs` | `isNewsletterEval` regex + OR-chain into `isGatoBrainCommand` | VERIFIED | 2 occurrences confirmed (`grep -c` = 2); `node --check` clean; present in the running gato container's compiled dist bundle. |
| `tests/test_31_send_telegram.py` | Unit coverage of the fail-loud contract | VERIFIED | 305 lines, 10 tests, all pass. |
| `tests/test_31_notify_eval.py` | Reader/formatter/seam coverage D-05..D-08 | VERIFIED | 565 lines, 27 tests (20 base + 7 fix-pass), all pass. |
| `tests/test_31_newsletter_eval_handler.py` | Handler coverage D-09..D-12 | VERIFIED | 460 lines, 11 tests, all pass. |
| `.planning/phases/31-surfacing-escalation/31-04-SUMMARY.md` | Deploy + live-verification evidence | VERIFIED | Contains SURF-01/02/03 evidence, deploy log, live round-trip transcripts, notify-path result. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `scheduled_auto_publish_newsletter` | `send_telegram` | `if not send_telegram(...): logger.critical(...)` | WIRED | Confirmed at `:10942`; grep + read. |
| `scheduled_notify_newsletter` | `edition_evals` | `_read_edition_evals(supabase, edition_number)` `.eq()`-only | WIRED | Confirmed at `:10874`; live-exercised against real Supabase. |
| `scheduled_notify_newsletter` | `send_telegram` | `if send_telegram(message): ... else: logger.critical(...)` | WIRED | Confirmed at `:10888`. |
| `gato_brain /chat` dispatch | `/newsletter_eval` handler | `_msg_lower.startswith("/newsletter_eval")` before intent router | WIRED | Confirmed at `:3077`, precedes `intent_router.route` at `:3168`. |
| `inject-gato-brain.mjs isGatoBrainCommand` | `gato_brain /chat` | `isNewsletterEval` OR-chain forwarding | WIRED | Confirmed in source AND in the running gato container's compiled dist bundle. |
| `handle_newsletter_eval` | `edition_evals` | `_eval_read_by_edition`/`_eval_read_latest_with_rows`/`_eval_read_trend` `.eq()`-only | WIRED | Confirmed via grep (no `.in_(` in any of the three functions) and live execution against real Supabase. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `_format_notify_eval_section` | `eval_rows` | `_read_edition_evals(supabase, edition_number)` — live `edition_evals` table | Confirmed FLOWING — inserted synthetic rows and observed the formatter render live verdict/scores/flags, then rendered `⚠ no eval recorded` for the version with none | FLOWING |
| `_format_eval_detail` / `_format_eval_trend` | `eval_rows` / `rows` | `_eval_read_by_edition` / `_eval_read_latest_with_rows` / `_eval_read_trend` — live `edition_evals` table | Confirmed FLOWING — same synthetic-insert method; genuine empty-table answers on the real (currently empty) table match the D-09 "no eval yet" contract | FLOWING |
| `handle_newsletter_eval` owner-gate | `access_tier` | `user.get("access_tier")` at `:2946`, threaded into the handler at `:3078` | Confirmed FLOWING — non-owner call against a table WITH synthetic unpublished prose returned only the refusal string, zero leakage | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `send_telegram` env-unset never raises, returns False, bounded log | live `docker compose exec processor python -c ...` with `TELEGRAM_BOT_TOKEN=None` | `False`, `[TELEGRAM-SEND] ... len=1529 head='draft prose...'[:80]` | PASS |
| Processor boot has no `[TELEGRAM-CONFIG]` ERROR with env set | `docker compose logs processor \| grep TELEGRAM-CONFIG` | no output (env configured) | PASS |
| `/newsletter_eval` (no-args) against live empty `edition_evals` | live `handle_newsletter_eval('/newsletter_eval', 'owner')` in running gato_brain container | `'No eval has run for any edition yet.'` | PASS |
| `/newsletter_eval` non-owner refusal | live `handle_newsletter_eval('/newsletter_eval', 'free')` | owner-only refusal string, no eval read attempted | PASS |
| `/newsletter_eval trend` against live empty table | live call | `'No eval trend yet — no edition has been evaluated.'` | PASS |
| Notify eval-section render with synthetic held_voice row | live `_format_notify_eval_section` call with inserted/deleted synthetic rows | Full D-05/D-06/D-07/D-08 render confirmed (see Truths #5-#8) | PASS |
| Detail-view render with synthetic held_voice row | live `handle_newsletter_eval('/newsletter_eval 99998', 'owner')` | Full D-10 render confirmed (see Truth #11) | PASS |
| gato compiled dist bundle carries the allowlist change | `docker compose exec gato grep -l isNewsletterEval /app/dist/*.js` | multiple matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SURF-01 | 31-01-PLAN.md | Hold/escalation notifications reuse `send_telegram`, hardened (never silent no-op) | SATISFIED | Truths #1-#4 |
| SURF-02 | 31-02-PLAN.md | Friday notify includes compact per-draft eval summary via plain select, no Processor LLM | SATISFIED | Truths #5-#9 |
| SURF-03 | 31-03-PLAN.md, 31-04-PLAN.md | `/newsletter_eval` (+ `trend`) live Gato command, owner-gated, allowlisted, not dead | SATISFIED | Truths #10-#14 |

No orphaned requirements: REQUIREMENTS.md maps exactly SURF-01, SURF-02, SURF-03 to Phase 31 (traceability table line 219: "31 — Surfacing & Escalation | SURF-01..03 | 3"), and all three IDs appear in plan frontmatter (`requirements:` field) across 31-01/02/03/04. REQUIREMENTS.md checkboxes for SURF-01..03 are still unchecked `[ ]` and the traceability table still shows "Pending" (lines 70-72, 201-203) — this is pending post-verification housekeeping (consistent with how WIRE-01..06 were marked `[x]`/"Complete" only after Phase 30's verification), not an implementation gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in the phase diff (`32c3662..HEAD`) across the three modified source files or three new test files | — | N/A — clean |
| `docker/gato_brain/gato_brain.py:2427-2436` | `_EVAL_FAIL_BELOW` | Hardcoded judge thresholds (WR-07, open advisory) — gato_brain has no `../config` mount, so a live operator threshold tune (already a Phase 29 capability) will silently desync the failing-dim detection from the judge's actual verdict | WARNING (deferred, documented in 31-REVIEW.md) | Does not block the phase goal — the detail view still renders correctly today; a future threshold tune could make evidence-rendering inconsistent with the true verdict |
| `docker/processor/agentpulse_processor.py:9674` + `:10741` | Markdown `parse_mode` vs underscore-heavy eval labels | Even-parity underscore counts pair across tokens as italic entities, silently stripping underscores from labels like `single_pass`/`held_voice` in the delivered notify (WR-04, open advisory) | WARNING (deferred) | Cosmetic corruption risk to the calibration signal's legibility; does not prevent delivery (message still sends) |
| `docker/processor/agentpulse_processor.py:10696`, `docker/gato_brain/gato_brain.py:2440` | Edition-keyed reads mix rows from multiple generations of a reprocessed edition (WR-01, open advisory) | Reprocessing an edition_number with a new `newsletter_id` can render a stale/mixed verdict | WARNING (deferred) | Edge case (reprocessing flow); not exercised by the current empty-table calibration window |
| `docker/gato_brain/gato_brain.py:2477-2494` | Trend `limit=8` is a ROW limit not an edition-group limit (WR-02, open advisory) | Trend view under-covers ~8 editions and can truncate a boundary edition's group into a wrong verdict at higher data volumes | WARNING (deferred) | Not observable at the current (empty) data volume; will matter once ~10+ editions accumulate |

All four open Warnings (WR-01, WR-02, WR-04, WR-07) plus five Info findings are recorded in `31-REVIEW.md` as deliberately deferred this pass (only WR-03/WR-05/WR-06 were fixed pre-verification). None of them contradict a roadmap Success Criterion — SC1 (hardened `send_telegram`), SC2 (compact eval summary present + plain-select), and SC3 (`/newsletter_eval` + `trend` live and not dead) are all independently, live-verified true regardless of these edge-case correctness issues. They are correctly classified as advisory technical debt, not phase gaps.

### Human Verification Required

None. The phase's `checkpoint:human-verify`/`checkpoint:human-action` gates (31-04 Tasks 1-3: scoped rebuild, live `/newsletter_eval` Telegram round-trip, manual Friday-notify invocation) were already completed by the operator during execution, with recorded resume signals ("deployed", "eval-live", "notify-verified") in 31-04-SUMMARY.md. This verification independently reproduced the underlying live-DB round trips (container-internal function calls against the real Supabase project) to confirm the wiring the operator confirmed over Telegram, rather than trusting the SUMMARY narrative alone.

### Gaps Summary

No gaps. All three roadmap Success Criteria are independently verified true against the live codebase and live running containers, not just unit-test doubles:

1. `send_telegram` is bool-returning, never-raises, ERROR-logs on both env-unset and delivery failure (labels `[TELEGRAM-SEND]`/`[TELEGRAM-CONFIG]`), and the auto-publish + Friday-notify critical callers CRITICAL-log `[EVAL-ALERT]` on a False return.
2. The Friday notify's eval section is a genuine `.eq()`-only read + pure formatter with no LLM in the Processor, live-verified to render D-05 (pipeline order), D-06 (mechanical always shown), D-07 (missing-eval line), and D-08 (WOULD HAVE HELD tag) correctly against real inserted rows.
3. `/newsletter_eval` (+ `trend`) is owner-gated, `.eq()`-only, renders D-09/D-10/D-11 correctly against real data, and is confirmed present in the compiled/running gato container — not a dead command.

Four advisory Warnings (WR-01, WR-02, WR-04, WR-07) remain intentionally open per the code review's fix-pass triage and are noted above; they are edge-case correctness issues that do not block goal achievement and were explicitly scoped as deferred by the phase's own review process.

---

_Verified: 2026-07-03T07:15:39Z_
_Verifier: Claude (gsd-verifier)_
