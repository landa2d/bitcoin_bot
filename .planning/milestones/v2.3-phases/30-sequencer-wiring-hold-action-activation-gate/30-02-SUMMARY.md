---
phase: 30-sequencer-wiring-hold-action-activation-gate
plan: 02
subsystem: newsletter
tags: [eval-orchestrator, governed-identity, fail-open, anthropic-proxy, telemetry, tdd, pytest]

# Dependency graph
requires:
  - phase: 27-eval-persistence-governed-agent
    provides: "edition_eval.write_eval_row (fail-loud verdict-iff-ok persistence) + _get_eval_api_key (LLM_PROXY_EVAL_KEY governed identity)"
  - phase: 28-layer-1-deterministic-gate
    provides: "deterministic_gate.run_deterministic_gate (emit-only {fabrication,unverified,mechanical,meta}, injected http_client)"
  - phase: 29-layer-2-judge-feedback-rewrite-loop
    provides: "judge_loop.run_layer2 ({final_draft,verdict,selected_attempt,attempts}) + _persistable_attempt (1:1 eval-row mapping)"
provides:
  - "run_edition_eval(supabase, draft, fact_base, prior_context, prior_edition, *, pipeline_version, newsletter_id, edition, config, llm_client, http_client, github_token=None) -> {verdict, reason, details, ran} — the single testable eval-invocation unit"
  - "_build_eval_llm_client() — NEW governed edition_eval anthropic client (GOV-01) or None on unset key (D-07 outage)"
  - "_read_edition_eval_config() — reads the edition_eval config block (enabled/enforce, D-15)"
  - "_alert_operator(msg) — interim loud (non-silent) newsletter-side Telegram alert (D-07)"
  - "_fetch_prior_published_edition() — full latest published edition via .eq('status','published') (no in-list filter)"
  - "tests/test_30_orchestration.py — 9-case unit suite over the REAL orchestrator, zero egress/DB"
affects: [30-03-wiring-verdict-action, 30-04-activation-runbook, 31-surfacing-escalation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dumb-sequencer orchestrator: lazy-import the three eval modules inside the function so tests inject fakes at the lazy-import seam (monkeypatch deterministic_gate.run_deterministic_gate / judge_loop.run_layer2 / edition_eval.write_eval_row)"
    - "Governed-identity client builder: NEW anthropic.Anthropic on the edition_eval key, never the newsletter claude client; key logged as a boolean only"
    - "Fail-open-but-loud: single outer try/except returns a verdict + error row + one operator alert, guarded so a telemetry/alert failure still returns; NEVER re-raises"

key-files:
  created:
    - "tests/test_30_orchestration.py — unit suite for run_edition_eval (9 cases, injected fakes + in-memory Supabase stub)"
  modified:
    - "docker/newsletter/newsletter_poller.py — +run_edition_eval orchestrator + _build_eval_llm_client + _alert_operator + _read_edition_eval_config + _fetch_prior_published_edition + reason helpers"

key-decisions:
  - "run_edition_eval receives llm_client + http_client as params (caller in 30-03 builds them) — keeps the orchestrator testable with injected fakes; the SAME http_client reaches both eval modules (D-08)"
  - "held_voice reason carries per-dimension NAME + worst-body (min) SCORE + a single-line bounded judge_feedback excerpt sourced from the selected attempt (WIRE-03/D-10); details carries the full per-dim judge_scores"
  - "llm_client=None (unminted eval key) is treated as an outage identically to an eval exception: error row + one alert + escalated/ran=False, no gate/judge call, no raise (D-07)"
  - "WIRE-01/05/06 closure DEFERRED to phase-end verify (this plan only BUILDS the invocation unit; 30-03 wires it into the two save points) — the milestone's fail-loud-accuracy posture"

patterns-established:
  - "Lazy-import seam for test injection: `from deterministic_gate import run_deterministic_gate` inside the function resolves the (monkeypatched) module attribute at call time"
  - "Reason/alert text built ONLY from category-label counts + per-dim scores + judge-critique excerpts (single-lined + bounded), NEVER raw draft prose (T-30-LOG)"

requirements-completed: []  # WIRE-01/05/06 cores built+proven; closure deferred to phase-end verify (two-save-point wiring is 30-03)

# Metrics
duration: ~16min
completed: 2026-07-01
---

# Phase 30 Plan 02: run_edition_eval Orchestrator Summary

**The governed, fail-open-but-loud pre-publish eval orchestrator (`run_edition_eval`) that sequences the Layer-1 gate → fabrication short-circuit → Layer-2 judge → verdict, persists every layer/attempt, and never lets an eval error block generation — the "dumb sequencer" body Plan 30-03 wires into the two save points.**

## Performance

- **Duration:** ~16 min
- **Completed:** 2026-07-01
- **Tasks:** 2 (Task 2 TDD: RED test → GREEN feat)
- **Files modified:** 2 (1 modified, 1 created)

## Accomplishments
- `run_edition_eval` orchestrator: gate → non-empty-fabrication short-circuit (ZERO `run_layer2` call, D-09) → Layer-2 judge → verdict object `{verdict, reason, details, ran}`; the SAME injected `httpx.Client` reaches BOTH `run_deterministic_gate` and `run_layer2` (D-08 live re-check), and the injected governed `llm_client` reaches `run_layer2` verbatim (GOV-01).
- Four support helpers: `_build_eval_llm_client` (NEW governed `edition_eval` anthropic client via `_get_eval_api_key`; returns None on unset key = the D-07 outage; never reuses the newsletter client; key never logged — T-30-KEY), `_read_edition_eval_config` (enabled/enforce, D-15), `_alert_operator` (interim loud non-silent Telegram path; ERROR-logs on unset `TELEGRAM_*`; single-lines/bounds the message — T-30-LOG), `_fetch_prior_published_edition` (`.eq('status','published')`, no in-list filter).
- Fail-open-but-loud: `llm_client=None` outage AND any eval exception → `eval_status='error'` row + exactly one `_alert_operator` + `{verdict:'escalated', ran:False}`, guarded so an inner telemetry/alert failure still returns, and NEVER re-raises (D-06/D-07 — generation continues to the Monday human gate).
- Telemetry-complete: persists the clean/held deterministic row + EVERY judge attempt via `_persistable_attempt` (1:1 mapping `reverify_flags→deterministic_flags`, `feedback→judge_feedback`, etc.), respecting verdict-iff-ok (LOOP-03/D-14).
- `held_voice` reason carries each failing dimension's NAME + its worst-body numeric SCORE + a bounded one-line `judge_feedback` excerpt; `details` carries the full per-dimension `judge_scores` from the selected attempt (WIRE-03/D-10 — not labels-only).
- Co-located suite `tests/test_30_orchestration.py` (9 cases) over the REAL module with injected fakes + an in-memory Supabase stub delegating to the REAL `write_eval_row` (so verdict-iff-ok is enforced for real) — zero live egress, zero live DB.

## Task Commits

Each task was committed atomically:

1. **Task 1: Governed client + loud alert + config read + prior-edition fetch** — `bb8bb0c` (feat)
2. **Task 2 (TDD RED): failing unit suite for run_edition_eval** — `93877bc` (test)
3. **Task 2 (TDD GREEN): implement run_edition_eval orchestrator** — `5d87e93` (feat)

**Plan metadata:** (this SUMMARY + STATE + ROADMAP) — final docs commit.

## Files Created/Modified
- `docker/newsletter/newsletter_poller.py` — added `run_edition_eval` + `_build_eval_llm_client` + `_alert_operator` + `_read_edition_eval_config` + `_fetch_prior_published_edition` + reason helpers (`_summarize_flags`, `_dim_score`, `_one_line_excerpt`, `_find_attempt`).
- `tests/test_30_orchestration.py` — 9-case unit suite: fabrication short-circuit, judge passed/held_voice persistence, fail-open on run_layer2 exception + llm_client None outage, governed identity + http_client passthrough, source-level guards (governed key getter; no `.update(`/`do_not_publish`/`"status":"held"` in the orchestrator).

## Decisions Made
- **Orchestrator receives `llm_client`/`http_client` as params** (the 30-03 caller builds the governed client via `_build_eval_llm_client` and one live `httpx.Client`) — keeps the unit testable with injected fakes and satisfies the D-08 "same client to both modules" rule.
- **`held_voice` reason format:** `held_voice: <dim>=<score>, ... | judge_feedback: <one-line bounded excerpt>` sourced from the selected (D-11 best) attempt; `details.judge_scores` carries the full per-dimension dict (WIRE-03/D-10).
- **`llm_client=None` == outage** (identical treatment to an eval exception) — no gate/judge call, error row + one loud alert + escalated/ran=False, no raise.
- **Requirement closure deferred:** WIRE-01/05/06 cores are built + proven, but this plan only builds the invocation unit; the actual two-save-point wiring is 30-03 and `enabled`/`enforce` are not yet read at a save point — so closure is left to phase-end `/gsd-verify-work` (fail-loud-accuracy posture, consistent with 27/28/29/30-01).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reworded docstrings/comments to remove literal tokens that the acceptance greps flag**
- **Found during:** Task 1 (helper authoring)
- **Issue:** The acceptance criteria use literal greps ("`_build_eval_llm_client` does NOT reference `claude_client`", "`_fetch_prior_published_edition` does NOT use `.in_(`", "`run_edition_eval` contains no `do_not_publish`"). My initial docstrings/comments *mentioned* those exact tokens (e.g. "NEVER reuse `claude_client`", "NEVER the supabase-py `.in_()`", "NEVER flips `do_not_publish`"), which would trip a naive literal grep even though the behavior is correct.
- **Fix:** Reworded the prose to token-free equivalents ("the newsletter service's own module Claude client", "the supabase-py in-list filter", "do-not-publish state"). Behavior unchanged; AST-confirmed zero actual `claude_client` / `.in_(` references in the respective function bodies and zero `do_not_publish` / `.update(` / `"status":"held"` in `run_edition_eval`.
- **Files modified:** docker/newsletter/newsletter_poller.py
- **Verification:** AST-level function-body checks all pass; full gate green.
- **Committed in:** `bb8bb0c` (Task 1), `5d87e93` (Task 2)

**2. [Rule 1 - Bug] Tightened the RED test's "no status flip" assertion**
- **Found during:** Task 2 (GREEN)
- **Issue:** The RED test asserted `"do_not_publish" not in src` and a convoluted `status` check; the orchestrator docstring legitimately referenced `do_not_publish`, so the naive assertion was both fragile and would false-fail.
- **Fix:** Removed the token from the source (deviation 1) and re-expressed the invariant structurally — assert the orchestrator makes NO `.update(` call and carries no `do_not_publish` / `"status": "held"` write (it persists via `write_eval_row` on `edition_evals` only). This proves the real invariant (no status action here; that is 30-03).
- **Files modified:** tests/test_30_orchestration.py
- **Verification:** Test passes; asserts the genuine structural property.
- **Committed in:** `5d87e93`

---

**Total deviations:** 2 auto-fixed (1 blocking token/grep alignment, 1 test-assertion correctness)
**Impact on plan:** Cosmetic wording + a stronger test assertion. No behavior change, no scope creep — all acceptance criteria and the full verification gate pass.

## Issues Encountered
None beyond the deviations above. The lazy-import seam (`from deterministic_gate import run_deterministic_gate` inside the function) cleanly resolves the monkeypatched module attribute at call time, so tests inject fakes with zero live egress/DB and the REAL `write_eval_row` still enforces verdict-iff-ok against an in-memory stub.

## Known Stubs
None. `_read_edition_eval_config()` returning `{}` when the block is absent is a documented fail-safe (absent block reads as `enabled=False`, so the eval simply never runs — rollback-safe), not a placeholder. No hardcoded UI-facing empties, no TODO/placeholder text.

## Threat Flags
None. All security-relevant surface introduced this plan is already in the plan's `<threat_model>`: the governed key handling (T-30-KEY — key passed only to `anthropic.Anthropic(api_key=...)`, logged as a boolean), the label-only/bounded alert + reason text (T-30-LOG), the fail-open branch that flips NO publish state (T-30-FAILOPEN), and the GITHUB_TOKEN pass-through (T-30-GHT). The one net-new egress path — `_alert_operator`'s direct Telegram POST — is the plan's Analog I (interim loud path; Phase 31 hardens via `send_telegram`).

## Next Phase Readiness
- **30-03** (Wave 2, blocked on 30-02 — same poller file) wires `run_edition_eval` into the two generation save points, threads the primary `newsletter_id`, and adds the enforce-gated verdict→action (held + `do_not_publish` + escalation) + the `data_snapshot.do_not_publish` → column reconciliation. The orchestrator's contract (`{verdict, reason, details, ran}`) and the governed-client + injected-`httpx.Client` builders are ready to call.
- **Blocker for first LIVE invocation (not for 30-03 code):** the operator must mint `LLM_PROXY_EVAL_KEY` (Phase 27-03) and MCP-apply migrations 045+046 (30-04 runbook). Ships `enabled=false` — dormant and rollback-safe.

## Self-Check: PASSED
- `docker/newsletter/newsletter_poller.py` — FOUND
- `tests/test_30_orchestration.py` — FOUND
- Commits `bb8bb0c`, `93877bc`, `5d87e93` — all FOUND in git log
- Gate: `pytest tests/test_30_orchestration.py -q` → 9 passed; regression `pytest tests/test_29_judge_loop.py tests/test_28_deterministic_gate.py tests/test_27_edition_eval.py -q` → 124 passed; both AST parses exit 0.

---
*Phase: 30-sequencer-wiring-hold-action-activation-gate*
*Completed: 2026-07-01*
