---
phase: 29-layer-2-judge-feedback-rewrite-loop
reviewed: 2026-07-01T11:59:14Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/newsletter/judge_loop.py
  - tests/test_29_judge_loop.py
  - config/agentpulse-config.json
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-07-01T11:59:14Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the pure, build-only Layer-2 module (`judge_loop.py`), its unit suite, and the
`edition_eval` config block. I traced the core correctness surfaces the domain context flagged
as highest priority: the both-bodies threshold engine (`_compute_failing_dims`), the N=2
loop termination and verdict mapping, best-attempt selection, the per-rewrite fabrication
re-check, and the fail-loud entry guards. Cross-checked every imported contract
(`_llm_call`, `run_deterministic_gate`, `_fact_base_source_texts`, `parse_llm_json`,
`write_eval_row`) against its real signature, and confirmed the URL/GitHub fabrication
taxonomy in `deterministic_gate.py` (404/410 → fabrication; 5xx/timeout → unverified).

**Assessment: the scoring, threshold, loop-termination, and verdict logic are correct.** The
worst-case `min` across bodies (D-08), the continuity n/a exclusion (D-05), the hedging filler
combination (D-04), the hard N=2 stop with no best-effort publish (LOOP-02), the D-11
best-attempt tie-break, and the held_fabrication/escalated/held_voice/passed verdict mapping all
behave as specified. The dedup-cache shim is correctness-safe for the hold decision (a 404 is
never cached-away; only unverified is affected by neutered 5xx retry, and unverified never
holds). Config is valid JSON and mirrors `DEFAULT_CONFIG`. All 28 tests pass.

**No BLOCKERs found.** Two WARNINGs concern loop *effectiveness* and a latent fabrication-safety
gap in a deliberately test-gated path; both fail *safe* (they can only produce `held_voice`, which
holds for human review, never an unsafe auto-publish). The remaining items are minor quality nits.

## Warnings

### WR-01: Filler-triggered `hedging_filler` failure emits contradictory, non-actionable revise feedback

**File:** `docker/newsletter/judge_loop.py:171-176` (detection) and `:411-426` (`_build_feedback`)

**Issue:** When `hedging_filler` fails *only* on the deterministic filler-hit combination
(`max_hits >= hedging_filler_hits_max`) while the judge's hedging **score is passing**, the
feedback builder pulls its evidence/exemplar from `_worst_body_entry`, which returns the judge's
*passing-score* entry. The result is feedback that (a) quotes an evidence sentence the judge
graded as **clean** while instructing "this dimension fell below the voice bar and must be
fixed", and (b) **never names the blacklisted filler phrases** that actually triggered the
failure. The deterministic pre-pass knows exactly which phrases matched (`_count_filler_hits`),
but that information is discarded before feedback is built.

Reproduced: a body with 3 blacklist phrases and a judge `hedging_filler` score of 5 on both
bodies fails the dimension, and the generated feedback contains **zero** blacklist phrases —
the revise is never told what to remove. Because the judge score stays passing and the phrases
persist, `_count_filler_hits` re-trips on the re-judged draft, so a pure-filler failure tends to
**burn both revise attempts without converging** and lands in `held_voice`. Fails safe (holds),
but the loop cannot do the one fix it detected.

**Fix:** Thread the detected filler phrases into feedback for a filler-triggered failure instead
of the mismatched judge exemplar. For example, capture the matched phrases in the filler
pre-pass and, in `_build_feedback`, emit an explicit note when `hedging_filler` failed on hits:

```python
# in run_layer2, alongside the hit counts:
filler_matches = {v: [p for p in cfg["filler_blacklist"]
                      if p.lower() in (current.get(f) or "").lower()]
                  for v, f in _BODIES}
# pass filler_matches into _build_feedback; when hedging_filler is failing and the score is
# NOT below hedging_fail_below, emit:
#   "- hedging_filler: remove these banned filler phrases: \"...\", \"...\"."
```

### WR-02: Per-rewrite fabrication re-check is silently skipped when `http_client` is None — a fabricated rewrite can be returned as `passed`

**File:** `docker/newsletter/judge_loop.py:670, 682-698, 745-749`

**Issue:** The per-rewrite Layer-1 re-check — the module's only defense against a rewrite that
invents a new entity/repo/URL under `specificity` pressure (T-29-FABRW) — runs **only when
`caching_client is not None`**, i.e. only when the caller injects `http_client`. When
`http_client` is None, `run_layer2` still performs the targeted revise (`_revise_draft`), judges
the un-re-checked rewrite, and can return it as `final_draft` under verdict `passed` (or as the
best draft under `held_voice`). The rewrite is untrusted LLM output; nothing verifies it did not
fabricate. This is a fail-loud/fabrication-safety gap: the safety check degrades to a **silent
no-op** on a missing input, which is exactly the failure class the project's "fail-loud
governance" rule warns against.

This is a *deliberate* test contract (the zero-egress suite, e.g. `test_mechanical_rides_feedback`,
revises without `http_client`), and production is documented to always inject a real
`httpx.Client`, so there is no *current* live exposure. The risk is latent on the Phase-30 wiring:
if a live caller ever revises without `http_client`, a fabricated rewrite publishes as `passed`
with no signal in the verdict (only `reverify_flags: None` on the attempt telemetry hints at it).

**Fix:** Do not silently skip the safety check when a revise actually occurs. Emit a loud warning
(and/or make `http_client` mandatory once a rewrite is about to run) so a mis-wired Phase-30
caller fails visibly rather than shipping an unverified rewrite. This does not break the
zero-egress test contract (a log line is egress-free):

```python
if attempt_no > 0 and caching_client is None:
    logger.warning(
        "run_layer2: revising attempt %d WITHOUT a per-rewrite fabrication re-check "
        "(no http_client injected) — the returned rewrite is UNVERIFIED for fabrication",
        attempt_no,
    )
```

## Info

### IN-01: Unused imports (`json`, `re`)

**File:** `docker/newsletter/judge_loop.py:27-28`

**Issue:** Neither `import json` nor `import re` is referenced anywhere in the module body (all
JSON parsing goes through the imported `parse_llm_json`). `re` is `# noqa: F401`'d as "used by
later plans"; `json` is a plain unused import. Both are currently dead.

**Fix:** Remove `import json`; drop `import re` (or keep it only if a Phase-30-in-this-file
change genuinely needs it — the module surface argument is weak for a leaf module).

### IN-02: Revise feedback uses stale attempt-0 mechanical flags, not the fresh per-rewrite flags

**File:** `docker/newsletter/judge_loop.py:754`

**Issue:** `_build_feedback(..., det_flags.get("mechanical"))` always passes the **attempt-0**
mechanical flags. The per-rewrite re-check produces fresh `reverify["mechanical"]` for each
rewrite, but those are never fed into subsequent feedback: an already-fixed attempt-0 mechanical
note keeps being re-issued, and a mechanical flag newly introduced by a rewrite is never surfaced
to the next revise. Impact is low — mechanical flags are advisory-only ("if trivial"), never hold,
and the fresh flags are still captured in each attempt's `reverify_flags` telemetry.

**Fix:** For rewrite attempts, prefer `(reverify.get("mechanical") or None)` over the attempt-0
`det_flags` mechanical list when building the next feedback.

### IN-03: `_select_best_attempt([])` raises a bare `IndexError` on a misconfigured `max_attempts < 0`

**File:** `docker/newsletter/judge_loop.py:532-541, 763`

**Issue:** `run_layer2` fails loud on bad `draft`/`fact_base`/`prior_context`/`det_flags`, but does
not validate `cfg["max_attempts"]`. A negative value makes `range(0, max_attempts + 1)` empty, so
the loop never runs, `attempts` is empty, and `_select_best_attempt([])` does
`sorted([])[0]` → bare `IndexError` (a non-integer value would raise `TypeError` at `range`).
Config-sourced and unlikely, but it surfaces as an opaque error rather than a clear contract
message.

**Fix:** Coerce/validate in `_merged_config` (e.g. `max(0, int(merged["max_attempts"]))`) or add an
explicit guard: `if not isinstance(max_attempts, int) or max_attempts < 0: raise ValueError(...)`.

### IN-04: `thresholds.warn_below` (and `enabled`/`enforce`) are never read in this module

**File:** `docker/newsletter/judge_loop.py:88`, `config/agentpulse-config.json:139-153`

**Issue:** `warn_below` is defined in `DEFAULT_CONFIG`/config but consumed nowhere in
`judge_loop.py` — there is no "warn" verdict and no warn-tier telemetry. `enabled`/`enforce` are
likewise run-control flags this build-only module never reads. Expected for a Phase-30 wiring
surface, but flagged so it is confirmed rather than assumed.

**Fix:** No change needed if Phase 30 consumes these; otherwise drop `warn_below` as dead config.

### IN-05: held_fabrication attempt row is marked `eval_status="ok"` with `judge_scores=None`

**File:** `docker/newsletter/judge_loop.py:704-707`

**Issue:** The rewrite attempt that trips the fabrication abort is recorded with
`eval_status="ok"` even though the judge never ran on it (`judge_scores=None`). It passes
`write_eval_row`'s verdict-iff-ok check (verdict `held_fabrication` is in `_VERDICTS`), so this is
not a hard defect, but an "ok" eval with no scores is a mild telemetry inconsistency versus the
escalated path (which uses `eval_status="error"`). A downstream consumer reading `eval_status=="ok"`
may expect `judge_scores` to be present.

**Fix:** Optional — leave as-is (contract-valid), or add a brief comment documenting that a
fabrication-aborted attempt is intentionally "ok" (no judge *error*) with null scores.

---

_Reviewed: 2026-07-01T11:59:14Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
