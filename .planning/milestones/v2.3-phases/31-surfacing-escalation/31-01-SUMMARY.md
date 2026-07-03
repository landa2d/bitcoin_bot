---
phase: 31-surfacing-escalation
plan: 01
subsystem: infra
tags: [telegram, alerting, fail-loud, processor, pytest, observability]

# Dependency graph
requires:
  - phase: 30-sequencer-wiring-hold-action-activation-gate
    provides: "eval armed report-only (enabled=true/enforce=false); hold/escalation alerts route through send_telegram"
  - phase: 29-layer-2-judge-feedback-rewrite-loop
    provides: "_alert_operator fail-loud contract (the shape SURF-01 mirrors)"
provides:
  - "send_telegram is a bool-returning, fail-loud function (True on success / False on any failure, never raises)"
  - "boot-time [TELEGRAM-CONFIG] ERROR when TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_ID unset (visible at container boot)"
  - "auto-publish notification is a critical caller that CRITICAL-logs [EVAL-ALERT] on delivery failure (D-03)"
  - "tests/test_31_send_telegram.py: unit coverage of every branch of the fail-loud contract"
affects: [SURF-02 Friday-notify eval summary, SURF-03 /newsletter_eval command, 31-04 deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-loud operator alert: ERROR-log a fixed grep-able label + bounded single-line message on env-unset AND send failure; never raise, never bare return"
    - "Critical callers check the bool return and CRITICAL-log a labeled failure; fire-and-forget callers get the ERROR log for free"

key-files:
  created:
    - tests/test_31_send_telegram.py
  modified:
    - docker/processor/agentpulse_processor.py

key-decisions:
  - "D-01: hardened send_telegram in place — no shared/copied helper, no cross-service routing; newsletter _alert_operator untouched (calibration-window protection)"
  - "D-02: loud = bool return + ERROR log, never raise (25 existing call sites assume it never raises)"
  - "D-03: only the auto-publish notification (a hold/eval-critical caller) checks the return this plan; digest/watchdog/briefing stay fire-and-forget"
  - "D-04: boot-time [TELEGRAM-CONFIG] ERROR + per-send [TELEGRAM-SEND] ERROR; service still runs on an alerting gap"
  - "Return semantics: terminal non-200 (Markdown then plain-text both fail) -> return False fail-fast; explicit return True after the send loop; httpx exception -> ERROR + return False"

patterns-established:
  - "Boot-time config check (_check_telegram_config) called from init_clients — never raises, surfaces gaps at container start not first-alert-time"
  - "Log hygiene (T-30-LOG): bounded single-line message [:1000], labels only, never the bot token or raw draft prose"

requirements-completed: [SURF-01]

# Metrics
duration: 18min
completed: 2026-07-02
---

# Phase 31 Plan 01: send_telegram Fail-Loud Hardening Summary

**Hardened the processor's `send_telegram` into a bool-returning, never-raising fail-loud alert (ERROR-labeled on env-unset and delivery failure), added a boot-time `[TELEGRAM-CONFIG]` config ERROR, and made the auto-publish notification a critical caller that CRITICAL-logs `[EVAL-ALERT]` when the notice fails to land.**

## Performance

- **Duration:** ~18 min
- **Completed:** 2026-07-02
- **Tasks:** 2
- **Files modified:** 1 modified (processor), 1 created (test)

## Accomplishments
- `send_telegram(message: str) -> bool`: True on success, False on any failure, never raises — the env-unset bare `return` is now an ERROR-log (`[TELEGRAM-SEND]` + `TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_ID unset`) + `return False`; terminal delivery failure and the httpx-exception path both ERROR-log and `return False`.
- 4000-char newline-boundary splitter preserved verbatim; multi-chunk all-200 still returns True.
- `_check_telegram_config()` boot-time ERROR (`[TELEGRAM-CONFIG]`) wired into `init_clients()` — surfaces an alerting gap at container boot, never raises.
- `scheduled_auto_publish_newsletter` now checks `send_telegram`'s bool return and `logger.critical("[EVAL-ALERT] CRITICAL — auto-publish notification delivery FAILED ...")` with the edition number only (T-30-LOG); publish logic + `do_not_publish` hold guard unchanged.
- `tests/test_31_send_telegram.py`: 10 tests covering env-unset, happy path, multi-chunk, delivery failure, exception path, bool signature, boot-config check (both states), and the auto-publish critical-caller (fail + ok).

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): failing tests for send_telegram fail-loud contract** - `216cfa2` (test)
2. **Task 1 (GREEN): harden send_telegram + boot-time config ERROR** - `ac1d6f8` (feat)
3. **Task 2: auto-publish critical-caller return check + tests** - `f21a100` (feat)

## Files Created/Modified
- `docker/processor/agentpulse_processor.py` - `send_telegram` bool-return fail-loud hardening; new `_check_telegram_config()` called from `init_clients()`; `scheduled_auto_publish_newsletter` critical-caller CRITICAL-log on delivery failure.
- `tests/test_31_send_telegram.py` - unit coverage of the SURF-01 contract using the test_09 harness bootstrap (real processor module, fake httpx.Client, in-memory supabase stub, `caplog` label assertions).

## Decisions Made
- Terminal delivery failure returns False fail-fast inside the send loop, with an explicit `return True` after the loop (satisfies "any terminal non-200 yields return False" and "a return True at successful completion"); the Markdown-parse retry note stays a `warning` because it retries.
- Boot check placed in `init_clients()` (the container-boot path called from `main()`) rather than module scope, so it does not fire on every test import while still running at boot; unit-tested directly via `_check_telegram_config()`.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None. RED confirmed 8 failing tests before implementation; GREEN passed all; regression suite (`test_27_edition_eval`, `test_30_orchestration`) stayed green (24 passed).

## Known Stubs
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `send_telegram` now returns a bool that SURF-02 (Friday-notify eval summary) and SURF-03 (`/newsletter_eval`) critical callers will check — the contract those plans depend on is in place.
- Deploy of this change is DEFERRED to plan 31-04 (worktree-unsafe scoped `processor` rebuild, orchestrator-owned on the main tree). No `docker compose` build was run in this worktree.

## Self-Check: PASSED

- FOUND: `docker/processor/agentpulse_processor.py`
- FOUND: `tests/test_31_send_telegram.py`
- FOUND commit `216cfa2` (Task 1 RED), `ac1d6f8` (Task 1 GREEN), `f21a100` (Task 2)
- Acceptance greps verified: `def send_telegram(message: str) -> bool` ×1; `[TELEGRAM-SEND]` ×4 (≥2); `[TELEGRAM-CONFIG]` ×1; 0 `raise` statements in `send_telegram` (AST); exactly 1 guarded `if not send_telegram(` caller.
- Suite: 10/10 `test_31` pass; 24/24 regression (`test_27`, `test_30`) pass; `ast.parse` syntax check OK.

---
*Phase: 31-surfacing-escalation*
*Completed: 2026-07-02*
