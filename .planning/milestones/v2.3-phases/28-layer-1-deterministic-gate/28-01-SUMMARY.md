---
phase: 28-layer-1-deterministic-gate
plan: 01
subsystem: testing
tags: [newsletter, verification, fabrication-detection, deterministic-gate, arxiv, entity-merge, pytest, tdd]

# Dependency graph
requires:
  - phase: 27-eval-persistence-governed-agent
    provides: "migration 045 deterministic_flags JSONB shape ({fabrication, mechanical}); the edition_evals persistence target the flags object is shaped to fit"
  - phase: 26-continuity-exemplar-context
    provides: "test import-preamble + in-memory stub-double pattern (test_26/test_27) mirrored for the gate's golden-draft suite"
provides:
  - "docker/newsletter/deterministic_gate.py — run_deterministic_gate(draft, fact_base, prior_edition, *, http_client, github_token) orchestrator with the stable {fabrication, unverified, mechanical, meta} flags contract (the Phase 30 wiring surface)"
  - "Reuse of the calibrated verify_draft engine for tier-1 study/benchmark fabrication detection (D-04 — imported, never rebuilt)"
  - "Two net-new fabrication sub-checks: arXiv-ID membership (GATE-04) + entity-merge per-source verbatim (GATE-05)"
  - "GATE-08 fact-base-path trust + loud log (blocks vs input_data) + fail-loud non-dict guard"
  - "Interface-first http_client / github_token seams for Plan 02 network layer; empty unverified/mechanical lists for Plans 02/03"
  - "tests/test_28_deterministic_gate.py — 14 GATE-01/04/05/08 cases importing the REAL module"
affects: [28-02-network-checks, 28-03-mechanical-checks, 29-judge-loop, 30-sequencer-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reuse-then-refine: import the calibrated verify_draft engine; layer thin net-new checks ON TOP; never re-roll claim extraction / stop-list / tier classifier (FP-regression guard)"
    - "Interface-first orchestrator: full signature + flags-object contract locked in Plan 01 so Plans 02/03 wire results into a stable shape"
    - "Per-source provenance helper (_fact_base_source_texts) supplies the single-source verbatim evidence the engine's flat union lacks"

key-files:
  created:
    - docker/newsletter/deterministic_gate.py
    - tests/test_28_deterministic_gate.py
  modified: []

key-decisions:
  - "Emit-only (D-05): the gate returns flags, never writes DB / calls LLM / flips status / computes a verdict"
  - "unverified is a first-class top-level key (D-01), kept empty this plan and NEVER folded into fabrication/pass"
  - "Engine reused not rebuilt (D-04): verify_draft / _extract_claims_from_prose / _ARXIV_ID / _STATISTIC imported; _build_block_list and _STOP_WORDS untouched"
  - "Requirement closure deferred to phase end (fail-loud accuracy, matching the 27-01/27-02 posture): 28-01 realizes the GATE-04/05 detection cores + GATE-08 trust/log + GATE-01 both-version orchestration in code, but the gate is build-only/report-only and GATE-01's runs-on-every-edition short-circuit is Phase 30 wiring"

patterns-established:
  - "Reuse-then-refine fabrication checks: thin layers on the Edition-34-calibrated engine"
  - "Golden-draft suite imports the REAL production module (test_19_smartquote rule), no network (http_client=None)"

requirements-completed: []  # GATE-01/04/05/08 detection cores realized in code; formal closure deferred to phase end (see key-decisions) — consistent with the Phase 27 fail-loud-accuracy posture

# Metrics
duration: 12min
completed: 2026-06-30
---

# Phase 28 Plan 01: Layer 1 Deterministic Gate — Fabrication Core Summary

**A no-LLM `run_deterministic_gate` orchestrator that runs both body versions through the reused, Edition-34-calibrated `verify_draft` engine and adds two net-new fabrication sub-checks (arXiv-ID membership + entity-merge per-source verbatim), emitting a stable `{fabrication, unverified, mechanical, meta}` flags object shaped to migration 045 — build-only, emit-only, no wiring.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-30T11:01:00Z (approx)
- **Completed:** 2026-06-30T11:13:00Z
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files modified:** 2 (both created)

## Accomplishments
- Locked the Phase-30 wiring contract: `run_deterministic_gate(draft, fact_base, prior_edition, *, http_client=None, github_token=None)` returning exactly `{fabrication, unverified, mechanical, meta}` (migration 045 `deterministic_flags` JSONB shape + the first-class `unverified` D-01 key), with the `http_client`/`github_token` seams present now for Plan 02.
- Reused the calibrated `verify_draft` engine (D-04 — imported, never rebuilt) so tier-1 named-study/benchmark fabrications ("GroupMemBench", "MCP Authentication Security Study") surface with the inherited ~0-tier1-FP stop-list; recorded `meta.tier1_count` per version.
- Closed two documented engine gaps with thin net-new checks: arXiv-ID **membership** (GATE-04 — the engine extracts-then-discards arXiv IDs and never tests membership) and **entity-merge per-source verbatim** (GATE-05 — the engine's flat union + fuzzy substring match masks cross-source merges).
- GATE-08: the gate trusts the handed fact base, computes + loud-logs `meta.fact_base_path` (`blocks` vs `input_data`), and fails loud (`ValueError`) on a non-dict fact base ("an error is not evidence").
- 14 golden-draft tests (GATE-01/04/05/08) importing the REAL module, all green; regression suites `test_26`/`test_27` stay green (40/40 together).

## Task Commits

Each task was committed atomically (TDD test → feat):

1. **Task 1 (RED): GATE-01/08 scaffold tests** — `4c78865` (test)
2. **Task 1 (GREEN): module scaffold, flags contract, both-version orchestrator** — `ceade7b` (feat)
3. **Task 2 (RED): arXiv-membership + entity-merge tests** — `2f1271f` (test)
4. **Task 2 (GREEN): arXiv-ID membership (GATE-04) + entity-merge per-source verbatim (GATE-05)** — `5677249` (feat)

**Plan metadata:** (this SUMMARY + STATE + ROADMAP) — see final docs commit.

## Files Created/Modified
- `docker/newsletter/deterministic_gate.py` (created, 266 lines) — `run_deterministic_gate` orchestrator + `_fact_base_source_texts` (per-source provenance) + `_check_arxiv_membership` (GATE-04) + `_check_entity_merge` (GATE-05); imports `verify_draft`/`_extract_claims_from_prose`/`_ARXIV_ID`/`_STATISTIC` from `verification`; module constants `BODY_START_MARKER`, `READING_MODE_LABELS`, `_GITHUB_URL`, `_MD_LINK` seeded for Plans 02/03.
- `tests/test_28_deterministic_gate.py` (created, 267 lines) — fixture builders (`_make_draft`, `_single_pass_fact_base`, `_block_fact_base`, `_body`, `_body_with_study`) + 14 GATE-01/04/05/08 cases importing the REAL `deterministic_gate` module; no network (`http_client=None`).

## Decisions Made
- **Emit-only / build-only (D-05):** no DB write, no LLM call, no status flip, no verdict, no container rebuild — worktree-safe.
- **`unverified` first-class (D-01):** kept empty this plan; Plan 02's network three-outcome classifier populates it. Never folded into fabrication or pass.
- **Engine reuse (D-04):** `_build_block_list` / `_STOP_WORDS` / tier classifier left untouched to preserve the Edition-34 calibration; only thin per-source refinements added on top.
- **Requirement closure deferred to phase end** (fail-loud accuracy, matching 27-01/27-02): the GATE-04/05 detection cores + GATE-08 trust/log + GATE-01 both-version orchestration are realized in code here, but the gate is report-only/build-only and GATE-01's "runs on every edition + short-circuits to hold+escalate" is Phase 30 wiring — so `requirements mark-complete` was NOT run for GATE-01/04/05/08; they close at phase end after Plans 02/03 + verification.

## Deviations from Plan

None — plan executed exactly as written. Both tasks followed the specified TDD RED→GREEN flow; the two net-new sub-checks were built thin on top of the reused engine per TODO-1/TODO-2 and the PATTERNS "Net-New" rows.

## Issues Encountered
- The full `tests/` suite has **pre-existing** collection errors / failures unrelated to this plan (missing `uvicorn`/`anthropic` packages; `NoneType.rpc` / postgrest `APIError` from no live Supabase; pydantic schema drift). The new `deterministic_gate.py` is a standalone module imported only by `test_28` (no wiring this phase), so it cannot have caused them. The plan's regression gate (`test_26`, `test_27`) + `test_28` are green (40/40). Logged to `.planning/phases/28-layer-1-deterministic-gate/deferred-items.md`; recommend a separate environment-hardening pass.

## Threat surface
- T-28-01 (ReDoS): new regexes (`_GITHUB_URL`, `_MD_LINK`) use simple bounded character classes, no nested quantifiers — no catastrophic backtracking. Mitigated.
- T-28-02 (log injection): the gate logs only the `fact_base_path` label at INFO, never raw draft prose. Mitigated.
- T-28-03 (wrong fact base silently verifies): defensive `isinstance(fact_base, dict)` fail-loud + loud `meta.fact_base_path` log so a Phase-30 wrong-base wiring bug surfaces. Mitigated.
- No new threat surface beyond the plan's `<threat_model>` (zero new packages, no network egress this plan).

## Next Phase Readiness
- The flags-object contract + orchestrator + reused engine are stable. Plan 02 wires the GitHub/URL network three-outcome classifier into `unverified`/`fabrication` and `meta.github_checked`/`urls_checked` via the existing `http_client`/`github_token` seams. Plan 03 adds the GATE-06/07 mechanical checks into `mechanical` (consuming `BODY_START_MARKER`/`READING_MODE_LABELS`, and `prior_edition`).
- No blockers. Build-only / worktree-safe; nothing deployed.

## Self-Check: PASSED
- FOUND: `docker/newsletter/deterministic_gate.py`
- FOUND: `tests/test_28_deterministic_gate.py`
- FOUND commit: `4c78865` (test), `ceade7b` (feat), `2f1271f` (test), `5677249` (feat)
- 14/14 `test_28` cases green; `test_26`+`test_27` regression green; engine not rebuilt (no `_build_block_list`/`_STOP_WORDS` redefinition).

---
*Phase: 28-layer-1-deterministic-gate*
*Completed: 2026-06-30*
