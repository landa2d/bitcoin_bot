---
phase: 28-layer-1-deterministic-gate
plan: 03
subsystem: testing
tags: [newsletter, verification, deterministic-gate, mechanical-checks, recycled-closer, duplicated-stat, h1-echo, reading-mode-leak, golden-draft, pytest, tdd]

# Dependency graph
requires:
  - phase: 28-layer-1-deterministic-gate
    plan: 01
    provides: "run_deterministic_gate orchestrator + the {fabrication, unverified, mechanical, meta} flags contract + BODY_START_MARKER/READING_MODE_LABELS constants + the prior_edition param (interface-first)"
  - phase: 28-layer-1-deterministic-gate
    plan: 02
    provides: "the GATE-02/03 network-liveness layer + the injected fake httpx client double the golden suite reuses"
  - phase: 27-eval-persistence-governed-agent
    provides: "migration 045 deterministic_flags JSONB shape the aggregated flags object is asserted to fit; fail-loud 'an error is not evidence' posture carried into the D-01 distinctness assertion"
provides:
  - "GATE-06 mechanical checks: _check_h1_and_title_echo (single-hash H1 + version-appropriate title-echo) + _check_reading_mode_leak (tunable READING_MODE_LABELS blacklist, no bare-word FP)"
  - "GATE-07 cross-edition checks: _normalize/_closer_line/_stat_tokens (D-06 normalized-exact, reusing _STATISTIC) + _check_cross_edition (recycled-closer + per-token duplicated-stat vs the FULL prior edition; prior_edition=None clean skip)"
  - "run_deterministic_gate now fully populates the `mechanical` list (per-version loop); the {fabrication, unverified, mechanical, meta} contract is complete"
  - "tests/test_28_deterministic_gate.py: +19 cases (GATE-06/07 + the combined golden-draft integration suite proving GATE-01..08 + D-01 end-to-end with a mocked client + the full-flags-shape/JSONB lock)"
affects: [30-sequencer-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mechanical-editorial layer kept distinct from fabrication: GATE-06/07 emit into `mechanical` (editorial miss, may feed the Phase 29 rewrite loop), NEVER `fabrication` (a hard hold)"
    - "Normalized-exact (D-06) not fuzzy: _normalize = collapse-ws + strip + lower + strip-trailing-punct; closer/stat comparison is exact on the normalized form (no similarity threshold to tune this phase)"
    - "Reuse-then-refine continued: _stat_tokens reuses the imported engine _STATISTIC regex (no new number regex); the golden suite imports the REAL module + reuses the Plan-02 fake httpx client"
    - "Tunable-constant + report-only window: READING_MODE_LABELS is the single GATE-06 tuning point, confirmed/adjusted by the operator during Phase 30 report-only calibration (A1)"

key-files:
  created: []
  modified:
    - docker/newsletter/deterministic_gate.py
    - tests/test_28_deterministic_gate.py

key-decisions:
  - "GATE-06: H1 check matches single-hash `# ` only (the two-hash `## Read This, Skip the Rest` body-start marker is excluded by `^#[ \\t]`); title-echo compares the version-appropriate title (technical->title, impact->title_impact) against any markdown header line, whitespace-normalized + case-insensitive"
  - "GATE-06 reading-mode-leak: case-insensitive substring scan of the tunable READING_MODE_LABELS; bare 'IMPACT'/'Technical' DELIBERATELY absent (they appear in legitimate prose) — proven by a bare-word negative test"
  - "GATE-07 D-06 normalized-exact: recycled-closer iff the normalized last-paragraph equals the prior edition's; duplicated-stat per normalized token in BOTH bodies; reuses _STATISTIC (no new number regex); NO fuzzy threshold; prior_edition=None/empty is a clean skip (T-28-11), never raises"
  - "Mechanical flags are distinct from fabrication (never a hard hold) — asserted in tests; the prior_edition param wiring (technical->content_markdown, impact->content_markdown_impact) trusts the FULL prior body the Phase-30 caller supplies (A3)"
  - "Golden suite locks the aggregated object: top-level keys EXACTLY {fabrication, unverified, mechanical, meta} (fits 045 JSONB; JSON round-trip asserted), unverified NON-EMPTY + DISTINCT from fabrication (D-01), no verdict (emit-only D-05), both GATE-08 fact-base paths exercised, zero live egress"
  - "Requirement closure: GATE-06/07 marked complete (detection cores fully realized + proven). GATE-01..05/08 detection is proven by the golden suite but their runs-on-every-edition / live-egress / hold-action closure is Phase 30 wiring (report-only/build-only this phase, D-05) — deferred to phase-end verification, consistent with the 27/28-01/02 fail-loud-accuracy posture"

patterns-established:
  - "Mechanical (GATE-06/07) emits into `mechanical`, never `fabrication`"
  - "Combined golden-draft integration test: one offender draft per fact-base path embeds every historical worst offender at once and asserts the whole flags object in a single aggregated check"

requirements-completed: [GATE-06, GATE-07]  # GATE-01..05/08 detection proven but their live-wiring/hold-action closure is Phase 30 — reconciled at phase-end verification

# Metrics
duration: 15min
completed: 2026-06-30
---

# Phase 28 Plan 03: Layer 1 Deterministic Gate — Mechanical Checks + Golden-Draft Suite Summary

**Added the GATE-06 (single-hash H1 / version-appropriate title-echo + tunable reading-mode-label leak) and GATE-07 (D-06 normalized-exact recycled-closer + verbatim-duplicated-stat vs the FULL prior edition, reusing `_STATISTIC`) mechanical-editorial checks to `run_deterministic_gate`, then closed the phase with a combined golden-draft integration suite that proves the whole GATE-01..08 + D-01 surface end-to-end against the named historical worst offenders with a mocked network — flags land under `mechanical` (never `fabrication`), the aggregated object fits migration 045's `deterministic_flags` JSONB, and the gate emits flags only (no verdict, no DB/LLM, zero live egress).**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-06-30
- **Tasks:** 3 (Tasks 1+2 TDD: RED -> GREEN; Task 3 integration suite)
- **Files modified:** 2 (both extended, not rewritten — the Plan-01 fabrication core + Plan-02 network layer preserved)

## Accomplishments
- **GATE-06 (H1/title echo):** `_check_h1_and_title_echo` flags a single-hash `# ` H1 line (the two-hash `## Read This, Skip the Rest` body-start marker is excluded via `^#[ \t]`) and flags the version-appropriate edition title echoed as a markdown header line in its own body (technical->`draft['title']`, impact->`draft['title_impact']`; whitespace-normalized, case-insensitive). Net-new line-anchored regexes `_H1_LINE`/`_HEADER_LINE` (no nested quantifiers — T-28-09).
- **GATE-06 (reading-mode-label leak):** `_check_reading_mode_leak` case-insensitively scans the body for each member of the operator-tunable `READING_MODE_LABELS` blacklist; bare `"IMPACT"`/`"Technical"` are deliberately NOT blacklisted (they appear in legitimate prose) — proven by a bare-word negative test. The constant's comment documents the Phase 30 report-only tunability (open question A1).
- **GATE-07 (cross-edition, D-06):** `_normalize` (collapse ws + strip + lower + strip trailing punct), `_closer_line` (normalized last non-empty paragraph), `_stat_tokens` (reuses the imported engine `_STATISTIC` — no new number regex). `_check_cross_edition` flags `recycled_closer` iff the normalized closers are equal-and-non-empty, and `duplicated_stat` per normalized stat token present in BOTH bodies. Normalized-exact only (NO fuzzy threshold); `prior_edition=None`/empty returns `[]` without raising (T-28-11). Wired into the orchestrator per version (technical->`content_markdown`, impact->`content_markdown_impact`).
- **Mechanical distinct from fabrication:** both checks extend the `mechanical` list; `run_deterministic_gate` now returns `"mechanical": mechanical` (was an empty placeholder). The `{fabrication, unverified, mechanical, meta}` contract is complete.
- **Golden-draft integration suite (Task 3):** one offender draft per GATE-08 fact-base path (single-pass `input_data` + block_v1 `blocks`) embeds EVERY historical worst offender at once — ed-36 "MCP Authentication Security Study", ed-34 "GroupMemBench", a fake arXiv ID, a 404 github repo, a dead URL, a transient-5xx URL, a recycled closer, a duplicated stat, a leaked `AUDIENCE:` label — run end-to-end through the REAL module with the injected fake httpx client. ONE aggregated assertion per path proves: fabrication carries the study/benchmark/arXiv/404-repo/dead-url; `unverified` carries the 5xx and is NON-EMPTY + DISTINCT from fabrication (the D-01 "an error is not evidence" headline); `mechanical` carries the recycled-closer/duplicated-stat/reading-mode-leak; `meta` reports the correct path + github/url counts + a bool token flag; top-level keys are EXACTLY the four (JSON round-trip proves the 045 JSONB fit); NO verdict (emit-only D-05); zero live egress.
- **Phase gate:** `tests/test_28_deterministic_gate.py` 56/56 green (37 prior + 19 net-new); `test_26`+`test_27` regression green (26/26). The wider `tests/` suite's failures are pre-existing/environmental and unrelated (see Issues).

## Task Commits

Each task committed atomically (Tasks 1+2 TDD test -> feat; Task 3 integration test):

1. **Task 1 (RED): GATE-06 H1/title-echo + reading-mode-label tests** — `ee9db78` (test)
2. **Task 1 (GREEN): GATE-06 _check_h1_and_title_echo + _check_reading_mode_leak wired** — `7cd399d` (feat)
3. **Task 2 (RED): GATE-07 recycled-closer + duplicated-stat tests** — `c84fb27` (test)
4. **Task 2 (GREEN): GATE-07 normalized-exact helpers + _check_cross_edition wired** — `8735ec1` (feat)
5. **Task 3: golden-draft integration suite + full-flags-shape/JSONB lock** — `90177c1` (test)

**Plan metadata** (this SUMMARY + STATE + ROADMAP + REQUIREMENTS) — see final docs commit.

## Files Created/Modified
- `docker/newsletter/deterministic_gate.py` (modified, 605 -> ~700 lines) — added the GATE-06 regex constants `_H1_LINE`/`_HEADER_LINE`; the `mechanical` list + GATE-06/07 wiring in `run_deterministic_gate`'s per-version loop (plus the `prior_bodies`/`prior_number` cross-edition inputs); the helpers `_check_h1_and_title_echo`, `_check_reading_mode_leak`, `_normalize`, `_closer_line`, `_stat_tokens`, `_check_cross_edition`; enhanced the `READING_MODE_LABELS` comment (Phase 30 A1 tunability) and corrected the `prior_edition` arg docstring (now-live GATE-07 behavior). The Plan-01 fabrication core + Plan-02 network layer are untouched.
- `tests/test_28_deterministic_gate.py` (modified, 623 -> ~880 lines) — +8 GATE-06 cases, +8 GATE-07 cases (incl. normalized-match, no-fuzzy-threshold, prior_edition=None skip), +3 combined golden-draft integration cases (single-pass + block_v1 + JSON-serializable lock) with the shared `_golden_offender_body`/`_golden_prior`/`_golden_client`/`_assert_golden_flags` helpers.

## Decisions Made
- **GATE-06 H1 = single-hash only:** `^#[ \t]` matches `# ` but not the legitimate two-hash `## ` body marker; title-echo uses the version-appropriate title and whitespace-normalized/case-insensitive header matching.
- **GATE-06 label blacklist tunable + bare-word-safe:** `READING_MODE_LABELS` is the single tuning point (operator confirms membership in the Phase 30 report-only window, A1); bare `"IMPACT"`/`"Technical"` are excluded to avoid prose false positives.
- **GATE-07 normalized-exact (D-06), no fuzzy:** reuses `_STATISTIC` (no new number regex); `prior_edition=None`/empty is a clean skip (T-28-11), never raises; the gate trusts the FULL prior body the Phase-30 caller supplies (A3).
- **Mechanical != fabrication:** GATE-06/07 flags are editorial misses (may feed the Phase 29 rewrite loop), never a hard fabrication hold — asserted in tests.
- **Emit-only (D-05) preserved:** the golden suite asserts no `verdict` key and exactly the four top-level keys; no DB/LLM call; zero live egress (fake client).
- **Requirement closure:** GATE-06/07 marked complete (detection cores realized + proven). GATE-01..05/08 detection is proven by the golden suite but their runs-on-every-edition / live-egress / hold-action closure is Phase 30 wiring (report-only/build-only this phase) — deferred to phase-end verification (the 27/28-01/02 fail-loud-accuracy posture).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Doc accuracy] `prior_edition` arg docstring corrected**
- **Found during:** Task 2 (GREEN)
- **Issue:** the `prior_edition` arg docstring still read "Unused this plan (the recycled-closer / duplicated-stat checks are Plan 03)" from the Plan-01 interface-first skeleton; that is now false (GATE-07 consumes it).
- **Fix:** updated the docstring to describe the live GATE-07 behavior (technical->`content_markdown`, impact->`content_markdown_impact`; None = clean skip; Phase 30 supplies the FULL prior body — A3).
- **Files modified:** `docker/newsletter/deterministic_gate.py`
- **Commit:** `8735ec1`

**2. [Process - non-code] Accidental `git stash` during verification recovered**
- **Found during:** Task 3 (post-test verification)
- **Issue:** a `git stash` invocation buried in a diagnostic command stashed the uncommitted Task-3 golden tests (working tree on the MAIN tree, sequential mode — not a worktree).
- **Fix:** `git stash pop` restored the changes cleanly (working tree was clean; no conflict); re-ran test_28 (56/56 green) before committing Task 3. No work lost, no history damage.
- **Files modified:** none (recovery only)
- **Commit:** `90177c1` (the restored Task 3 commit)

No architectural deviations (Rule 4); no checkpoints; no authentication gates. No new packages (T-28-SC honored).

## Issues Encountered
- The **pre-existing** wider-`tests/` failures persist and are unrelated to this module: `test_llm_proxy.py` collection error (missing `uvicorn`), `test_05_intake`/`test_07_synthesis` (unset proxy env / model-id), `test_1a`/`test_3c`/`test_4b`/`test_1d` (`agentpulse_processor` attribute drift / no live Supabase `NoneType.rpc` / postgrest APIError), `test_newsletter_quality`/`test_schemas` (pydantic + quality drift). Confirmed not regressions: NONE of the failing files import `deterministic_gate`, and `verification.py` is unchanged vs the pre-phase baseline (`bd7452d`). The plan's regression gate (`test_26`+`test_27`) + `test_28` are green (82/82 together). Out-of-scope per the executor scope boundary; recommend a separate environment-hardening pass.

## Threat surface
- **T-28-09 (ReDoS):** mitigated — `_H1_LINE`/`_HEADER_LINE` are line-anchored with no nested quantifiers; `_normalize` uses a simple linear `\s+` collapse; `_stat_tokens` reuses the already-linear engine `_STATISTIC`. No new catastrophic-backtracking pattern.
- **T-28-10 (log injection):** mitigated — the mechanical checks add NO logging of raw closer/body prose; the only INFO log remains the `fact_base_path` label (Plan 01).
- **T-28-11 (prior_edition None/malformed crashes the gate):** mitigated — `_check_cross_edition` returns `[]` on empty/None `prior_body` without raising; GATE-06 still runs; proven by `test_mechanical_gate07_prior_none_skips_cleanly`.
- **T-28-SC (pip installs):** accepted/honored — zero new packages this phase.
- No new threat surface beyond the plan's `<threat_model>` (no live egress in the suite; no schema/endpoint/auth surface added).

## Next Phase Readiness
- The deterministic gate is code-complete: `deterministic_gate.py` exposes the full GATE-01..08 surface (fabrication core + network liveness + mechanical-editorial), emitting the `{fabrication, unverified, mechanical, meta}` object proven to fit migration 045's `deterministic_flags` JSONB. Phase 30 (WIRE) injects a real `httpx.Client(timeout=5)`, supplies the FULL `prior_edition` body (A3), selects the correct fact base at the two save points (GATE-08), invokes the gate on every edition, and maps the flags into a verdict + the hold/escalate action behind the report-only `enforce` flag.
- Phase-30 hand-offs (unchanged): verify `GITHUB_TOKEN` passthrough to the newsletter container (A4); `prior_edition` must be the FULL prior body, not `load_edition_context`'s excerpt; confirm/adjust the `READING_MODE_LABELS` membership during report-only calibration (A1).
- No blockers. Build-only / worktree-safe; nothing deployed. (Separately: Phase 27 Plan 03 — key mint + migration 045 MCP apply — remains orchestrator/operator-owned and pending.)

## Self-Check: PASSED
- FOUND: `docker/newsletter/deterministic_gate.py`
- FOUND: `tests/test_28_deterministic_gate.py`
- FOUND commit: `ee9db78` (test), `7cd399d` (feat), `c84fb27` (test), `8735ec1` (feat), `90177c1` (test)
- `test_28` 56/56 green; `test_26`+`test_27` regression green (82/82 together); `_STATISTIC` reused (grep-confirmed; no new number regex); `READING_MODE_LABELS` is a module-level constant; mechanical flags asserted distinct from fabrication; aggregated keys exactly `{fabrication, unverified, mechanical, meta}` with no `verdict` (emit-only).

---
*Phase: 28-layer-1-deterministic-gate*
*Completed: 2026-06-30*
