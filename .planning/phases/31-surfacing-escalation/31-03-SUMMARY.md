---
phase: 31-surfacing-escalation
plan: 03
subsystem: api
tags: [gato_brain, telegram-command, edition_evals, supabase, owner-gate, newsletter-eval]

# Dependency graph
requires:
  - phase: 27-eval-persistence-governed-agent
    provides: "edition_evals table (migration 045) + read_evals_by_newsletter/read_eval_trend .eq()-only read semantics"
  - phase: 29-layer-2-judge-feedback-rewrite-loop
    provides: "judge_scores both-bodies schema {technical/impact}{dim:{score,evidence,exemplar_before,exemplar_after}} + 5 dims + per-dim thresholds"
  - phase: 30-sequencer-wiring-hold-action-activation-gate
    provides: "the persisted edition_evals rows (deterministic + judge layers/attempts) the view reads"
provides:
  - "Owner-gated /newsletter_eval Gato command handler in gato_brain (no-args latest-with-rows / <edition#> / trend)"
  - "Local .eq()-only edition_evals readers in gato_brain (_eval_read_by_edition / _eval_read_latest_with_rows / _eval_read_trend)"
  - "Pure detail (D-10) + trend (D-11) formatters with bounded evidence/exemplars and mechanical-on-passed"
  - "isNewsletterEval allowlist entry in inject-gato-brain.mjs (forwards to gato_brain instead of falling through to OpenClaw)"
affects: [31-04-deploy-live-verify]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Owner-gated read handler (autonomy boundary applied to a read surface that quotes unpublished draft prose)"
    - "Local .eq()-only readers mirroring edition_eval.py semantics (self-contained service — no cross-container import)"
    - "Pure formatter functions testable with a .eq()-only StubSupabase double (no live DB)"

key-files:
  created:
    - "tests/test_31_newsletter_eval_handler.py"
  modified:
    - "docker/gato_brain/gato_brain.py"
    - "docker/gato/inject-gato-brain.mjs"

key-decisions:
  - "Handler extracted as module-level handle_newsletter_eval(message, access_tier, supabase_client=None) mirroring handle_map_command — testable without the FastAPI app; /chat branch just wraps it in ChatResponse"
  - "Owner gate returns BEFORE any eval read (refusal string, no .table() call) — proven by StubSupabase.captured == []"
  - "Trend reads BOTH pipeline_versions (single_pass + block_v1) via _eval_read_trend and groups by (edition, pipeline_version), capped at 8 lines"
  - "_eval_read_trend also selects deterministic_flags (read_eval_trend does not) so the trend line can render fab/unv/mech counts (D-11)"

patterns-established:
  - "Local .eq()-only edition_evals readers with supabase as the first positional param (never .in_() — EVAL-03)"
  - ".eq()-only StubSupabase double (applies eq/order/limit, defines NO in_ method) as the structural EVAL-03 test"

requirements-completed: [SURF-03]

# Metrics
duration: ~15min
completed: 2026-07-02
---

# Phase 31 Plan 03: /newsletter_eval Owner-Gated Eval Deep View Summary

**Owner-gated `/newsletter_eval` (+ `<edition#>` / `trend`) Gato command in gato_brain — per-dimension judge scores for all 5 dims, ~300-char-bounded evidence/exemplars for FAILING dims, mechanical Layer-1 flags even on `passed`, via local `.eq()`-only edition_evals readers; allowlisted in inject-gato-brain.mjs.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-02T21:56:00Z
- **Completed:** 2026-07-02T22:07:00Z
- **Tasks:** 2
- **Files modified:** 3 (2 modified, 1 created)

## Accomplishments
- Added the `/newsletter_eval` direct-dispatch branch in `/chat` BEFORE the intent router (near `/newsletter_preview`), threading `access_tier` exactly like the `/map-` branch and tagging `intent=NEWSLETTER_COMMAND`.
- Implemented `handle_newsletter_eval` owner-gated as a whole (D-12): a non-owner caller gets an owner-only refusal BEFORE any eval read (T-31-07) — structurally proven (no `.table()` call). No-args targets the latest edition that HAS eval rows (D-09), `<edition#>` targets a specific edition, `trend` renders recent verdicts (D-11).
- Added three local `.eq()`-only readers mirroring `edition_eval.py` (`_eval_read_by_edition`, `_eval_read_latest_with_rows`, `_eval_read_trend`) — the `/newsletter_preview` handler's `.in_()` anti-pattern is deliberately NOT copied (EVAL-03).
- Added two pure formatters: `_format_eval_detail` (D-10 — per-dim score lines for all 5 dims, bounded (≤300 char) evidence + before/after exemplars for FAILING dims, mechanical flags listed even on `passed` per P29 D-12) and `_format_eval_trend` (D-11 — one line per (edition, pipeline_version), capped ~8, `#<edition> <pv> <verdict> attempts=<n> fab=<n>/unv=<n>/mech=<n>`).
- Allowlisted the command in `inject-gato-brain.mjs` with a dedicated `isNewsletterEval` regex OR'd into `isGatoBrainCommand` so it forwards to gato_brain instead of falling through to OpenClaw (the Phase 9 `/map-*` dead-command lesson).
- New 11-case unit suite (`tests/test_31_newsletter_eval_handler.py`) — all green; the shared `test_09` gato_brain-import harness stays green (15/15).

## Task Commits

Each task was committed atomically:

1. **Task 1: /newsletter_eval owner-gated handler + .eq()-only readers + detail/trend formatters** - `faefbf0` (feat)
2. **Task 2: Allowlist /newsletter_eval in inject-gato-brain.mjs** - `37fb079` (feat)

## Files Created/Modified
- `docker/gato_brain/gato_brain.py` - New `/newsletter_eval` dispatch branch in `/chat`; `handle_newsletter_eval` (owner-gated); local `.eq()`-only readers `_eval_read_by_edition` / `_eval_read_latest_with_rows` / `_eval_read_trend`; pure formatters `_format_eval_detail` (D-10) / `_format_eval_trend` (D-11) + helpers (`_eval_excerpt`, `_eval_dim_scores`, `_eval_worst_entry`, `_eval_describe_mechanical`); module-level dimension/threshold constants mirrored from `judge_loop.DEFAULT_CONFIG`.
- `docker/gato/inject-gato-brain.mjs` - New `isNewsletterEval` regex (`/^\/newsletter_eval\b/i`) OR'd into `isGatoBrainCommand`; `/newsletter_eval` help-text line.
- `tests/test_31_newsletter_eval_handler.py` - 11 cases: owner-gate refusal + no-read, no-args latest-with-rows, no-eval-anywhere message, `<edition#>` `.eq("edition_number")` path, edition-not-found, held_voice bounded failing-dim evidence + all-5-dim scores, passed mechanical-on-passed + no failing evidence, trend shape + 8-line cap, trend-empty message, structural EVAL-03 (StubSupabase has no `.in_()`).

## Decisions Made
- Extracted the handler as a module-level `handle_newsletter_eval(message, access_tier, supabase_client=None)` (mirrors `handle_map_command`) so it is unit-testable without the FastAPI app; the `/chat` branch only wraps the returned string in `ChatResponse`.
- `trend` reads BOTH pipeline versions and the formatter groups by `(edition, pipeline_version)` — the trend line carries the pipeline_version token and both A/B verdicts surface; capped at 8 lines to honor the "<=8 lines" acceptance.
- `_eval_read_trend` additionally selects `deterministic_flags` (the upstream `read_eval_trend` does not) because the D-11 trend line needs fab/unv/mech counts.
- A non-`trend`, non-integer arg falls through to the no-args latest view rather than raising (T-31-09 DoS hardening — the top-level try/except returns a human-readable failure string, never crashes).

## Deviations from Plan

None - plan executed exactly as written. (The two documented discretion choices — trend reading both pipeline versions and `_eval_read_trend` selecting `deterministic_flags` — are within D-11's "flag counts" requirement and the plan's Claude's-Discretion latitude, not deviations.)

## Issues Encountered
- The first Edit targeted the shared-checkout path and was rejected (worktree isolation). Re-read and edited the worktree copy at `.claude/worktrees/agent-a23ef2e70cdf9cd0c/...`; no functional impact.

## User Setup Required
None - no external service configuration required. The gato rebuild that makes the allowlist change live over Telegram is plan 31-04 (worktree-unsafe, orchestrator-owned).

## Next Phase Readiness
- Code + tests + commits complete. `/newsletter_eval` will be live over Telegram once plan 31-04 runs the scoped `gato_brain` + `gato` rebuild on the main tree and performs the live round-trip (D-13). The explicit "No eval has run for any edition yet." answer is a valid live-verify signal (it proves allowlist + handler + select) before Friday's real rows arrive (2026-07-03).
- No blockers. `edition_evals` reads are `.eq()`-only; the owner gate keeps unpublished draft prose out of any non-owner chat.

## Self-Check

- `docker/gato_brain/gato_brain.py` — FOUND (modified, syntax-OK)
- `docker/gato/inject-gato-brain.mjs` — FOUND (modified, node --check OK, isNewsletterEval count = 2)
- `tests/test_31_newsletter_eval_handler.py` — FOUND (created, 11 tests pass)
- Commit `faefbf0` — FOUND
- Commit `37fb079` — FOUND

## Self-Check: PASSED

---
*Phase: 31-surfacing-escalation*
*Completed: 2026-07-02*
