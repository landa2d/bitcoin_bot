---
phase: 28-layer-1-deterministic-gate
verified: 2026-06-30T00:00:00Z
status: passed
score: 20/20 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 28: Layer 1 Deterministic Gate — Verification Report

**Phase Goal:** A no-LLM deterministic gate (`docker/newsletter/deterministic_gate.py`) exposing `run_deterministic_gate(draft, fact_base, prior_edition, *, http_client=None, github_token=None)` that detects all fabrication and mechanical conditions against an in-memory fact base, is EMIT-ONLY (no LLM/DB/verdict), reuses the calibrated `verify_draft` engine, and is proven by a golden-draft integration suite with mocked network — BUILD-ONLY / REPORT-ONLY this phase.

**Verified:** 2026-06-30
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Scoping Boundary Applied

Per the phase design (confirmed in CONTEXT.md, all 3 PLANs, all 3 SUMMARYs, and the verification prompt):
- **Phase 28 delivers:** The standalone detection module + test suite. A requirement is satisfied when its DETECTION is implemented and tested.
- **Deferred to Phase 30 (WIRE-01..06):** The `newsletter_poller` wiring at the two save points, the `hold+escalate` action, the `enforce` flag, `edition_evals` persistence. These are the "runs on every edition before LLM judge" and "reads in-memory at the save points" portions of GATE-01/02/03/08.

REQUIREMENTS.md correctly reflects this: GATE-06/07 marked `[x] Complete` (fully self-contained detection, no poller wiring needed); GATE-01..05/08 marked `[ ] Pending` (detection cores realized, live-wiring deferred to Phase 30).

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `run_deterministic_gate(draft, fact_base, prior_edition, *, http_client=None, github_token=None)` runs BOTH body versions and returns a single flags object | VERIFIED | `deterministic_gate.py:93-242`; `versions` list at :154; 78 tests pass |
| 2 | Flags object has exactly `{fabrication, unverified, mechanical, meta}` — `unverified` is first-class, NEVER folded into fabrication or pass (D-01) | VERIFIED | Return dict at :227-242; `test_shape_has_four_top_level_keys` asserts set equality; `test_golden_flags_object_is_json_serializable` round-trips to JSONB |
| 3 | Named study/benchmark absent from fact base (ed-36 "MCP Authentication Security Study", ed-34 "GroupMemBench") produces a `fabrication` entry via reused `verify_draft` tier1 | VERIFIED | `verify_draft` imported at :41; called at :177; `test_study_mcp_auth_fabrication`, `test_study_groupmem_tier1_fabrication` pass |
| 4 | Fake arXiv ID absent from fact-base source text → `kind=="arxiv"` fabrication; real ID present in source → clean (GATE-04) | VERIFIED | `_check_arxiv_membership` at :291-318; WR-03 anchored set check at :304; `test_arxiv_fake_id_fabrication`, `test_arxiv_real_id_clean`, `test_arxiv_fake_id_substring_of_real_id_still_flagged` pass |
| 5 | Entity present only split-across two sources → `kind=="entity_merge"` fabrication; composite verbatim in one source → clean (GATE-05) | VERIFIED | `_check_entity_merge` at :321-384; WR-01 cross-source logic at :375-378; `test_entity_merge_split_across_sources_fabrication`, `test_entity_merge_single_source_verbatim_clean`, `test_entity_merge_live_repo_not_double_flagged` pass |
| 6 | Gate trusts handed `fact_base`, logs `meta.fact_base_path` (`blocks` vs `input_data`), fail-loud on non-dict (GATE-08) | VERIFIED | Path dispatch at :145-146; `test_gate08_factbase_path_blocks/input_data`, `test_gate08_non_dict_factbase_fails_loud`, `test_gate_non_dict_draft_fails_loud` pass |
| 7 | Gate emits flags only — no DB write, no LLM call, no status flip, no verdict computed (D-05) | VERIFIED | No `supabase`, `openai`, `anthropic`, or `httpx.Client()` construction in module; no `verdict` key in return dict; `"verdict" not in flags` asserted in golden suite |
| 8 | GitHub 404 → `kind=="github_repo"` fabrication; 404 NEVER retried (D-02) | VERIFIED | `_classify_github` at :477-534; 404 returns immediately at :520; `test_github_404_fabrication_and_no_retry` asserts exactly 1 call |
| 9 | Star-drift >20% from live `stargazers_count` → `kind=="github_stars"` fabrication; within band → clean (GATE-02) | VERIFIED | `_run_github_layer` at :619-625; `test_github_stars_drift_fabrication`, `test_github_stars_within_band_clean` pass |
| 10 | GitHub 403/429 → `unverified` (not fabrication, D-01); 5xx/timeout → `unverified` after exactly one retry (D-02) | VERIFIED | `_classify_github` returns `("unverified", None, "rate_limit_403")` at :522 without retry; returns `("unverified", None, "server_error_5xx")` after 2 attempts at :526; `test_github_403_unverified_not_fabrication`, `test_github_5xx_unverified_after_retry_once` assert call counts |
| 11 | URL 404/410 → `kind=="dead_url"` fabrication; timeout/conn-refused/5xx → `unverified`, retried once (D-01/D-02); unsafe host → unverified without fetch (SSRF) | VERIFIED | `_classify_url` at :660-707; SSRF guard first at :672-673; `test_url_dead_404_fabrication`, `test_url_410_dead_fabrication`, `test_url_timeout_unverified_after_retry_once`, `test_url_unsafe_internal_host_no_fetch` (asserts `client.calls == []`) pass |
| 12 | Every unique owner/repo ref and URL checked exactly once via per-run dedup cache; duplicates reuse cached result (D-03) | VERIFIED | Shared `cache` dict at :214; keyed `("gh",...)` / `("url",...)` at :605, :726; `test_github_dedup_same_repo_one_call`, `test_url_dedup_single_head_call` assert exactly 1 call |
| 13 | Draft URL whose host is loopback/private/link-local or internal service → `unverified` reason `"unsafe_host"`, NEVER fetched (SSRF guard) | VERIFIED | `_is_safe_public_url` at :411-474; `_resolve_host` at :403; `_is_blocked_ip` at :394; CR-01 resolve-then-validate for non-canonical IPs; `test_ssrf_guard_rejects_internal_and_private`, `test_ssrf_guard_rejects_noncanonical_ip_encodings`, `test_ssrf_guard_rejects_public_hostname_pointing_internal` (DNS rebinding), `test_ssrf_guard_rejects_if_any_resolved_addr_is_internal` pass |
| 14 | `GITHUB_TOKEN` read from env/param, sent only to `api.github.com` over HTTPS, never logged or in flags object; `meta.github_token_present` is a bool only (T-28-05) | VERIFIED | Token at :213; sent in `Authorization` header at :493 only to `api.github.com`; `meta["github_token_present"]` is `bool(...)` at :239; `test_github_token_present_flag_and_never_leaked` asserts `secret not in json.dumps(flags)` and `secret not in caplog.text` |
| 15 | Single-hash H1 line, or edition title echoed as header → `mechanical` entry (GATE-06) | VERIFIED | `_check_h1_and_title_echo` at :747-764; `_H1_LINE` / `_HEADER_LINE` regexes at :80-81; `test_mechanical_gate06_h1_in_body`, `test_mechanical_gate06_title_echo`, `test_mechanical_gate06_title_echo_impact_uses_title_impact` pass |
| 16 | Leaked reading-mode label from tunable `READING_MODE_LABELS` → mechanical; bare "impact"/"Technical" in prose → no flag (GATE-06) | VERIFIED | `_check_reading_mode_leak` at :767-777; `READING_MODE_LABELS` at :58-63 (module-level constant, "IMPACT"/"Technical" absent); `test_mechanical_gate06_reading_mode_label_leak`, `test_mechanical_gate06_bare_word_no_label_leak`, `test_mechanical_gate06_labels_are_tunable_module_constant` pass |
| 17 | Closer line matching previous edition's closer (normalized: lowercase + collapse whitespace + strip trailing punctuation) → `kind=="recycled_closer"` mechanical flag (GATE-07/D-06) | VERIFIED | `_normalize` at :780-784; `_closer_line` at :787-790; `_check_cross_edition` at :799-824; `test_mechanical_gate07_recycled_closer`, `test_mechanical_gate07_recycled_closer_normalized_match`, `test_mechanical_gate07_no_fuzzy_threshold` pass |
| 18 | Numeric stat token verbatim (normalized) in both editions → `kind=="duplicated_stat"` per token (GATE-07/D-06, reusing `_STATISTIC`) | VERIFIED | `_stat_tokens` at :793-796 reuses imported `_STATISTIC`; `test_mechanical_gate07_duplicated_stat`, `test_mechanical_gate07_duplicated_stat_current_only_no_flag` pass |
| 19 | Mechanical flags under `mechanical` key — distinct from fabrication; `prior_edition=None` → clean skip, no raise (T-28-11) | VERIFIED | `mechanical.extend(...)` in per-version loop at :193-199; `test_mechanical_gate06_flags_under_mechanical_not_fabrication`, `test_mechanical_gate07_prior_none_skips_cleanly` pass |
| 20 | Full golden-draft integration suite (ed-36 MCP-auth, ed-34 GroupMemBench, fake arXiv, 404 repo, dead URL, transient-5xx→unverified, recycled closer, leaked label) passes on REAL module with mocked network; `unverified` non-empty and distinct from fabrication (D-01 headline) | VERIFIED | `test_golden_offender_single_pass_input_data_end_to_end`, `test_golden_offender_block_v1_end_to_end`, `test_golden_flags_object_is_json_serializable` pass; `_assert_golden_flags` asserts all expected entries plus `flags["unverified"]` non-empty and transient 5xx never in `fabrication` |

**Score:** 20/20 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/newsletter/deterministic_gate.py` | `run_deterministic_gate` orchestrator + SSRF guard + all check sub-functions; imports `verify_draft` from `verification` | VERIFIED | 825 lines; all key functions present at documented line numbers; syntax-clean; engine imported at :41 |
| `tests/test_28_deterministic_gate.py` | Golden-draft fixtures + full GATE-01..08 + D-01..D-03 + SSRF + CR fix tests importing REAL module | VERIFIED | 1132 lines; 78 tests pass; imports real module at line 41 (`import deterministic_gate as gate`) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `deterministic_gate.py` | `verification.py` | `from verification import verify_draft, _extract_claims_from_prose, _ARXIV_ID, _STATISTIC` | VERIFIED | Line 41; no `_build_block_list` / `_STOP_WORDS` redefinition |
| `run_deterministic_gate` return | migration 045 `deterministic_flags` JSONB | `{fabrication, unverified, mechanical, meta}` shape | VERIFIED | Confirmed by JSON round-trip test; `unverified` first-class per D-01 |
| `_classify_url` | `_is_safe_public_url` | SSRF gate before any fetch | VERIFIED | Called at :672; zero-call assertion passes |
| GATE-07 stat check | `verification._STATISTIC` | reused stat-token regex via `_stat_tokens` | VERIFIED | `_stat_tokens` at :796; no new number regex defined in module |

---

### Data-Flow Trace (Level 4)

Not applicable — `deterministic_gate.py` is a detection module, not a rendering component. It consumes in-memory `draft` + `fact_base` dicts passed as arguments and returns a flags dict. There is no external data source to trace; the fact-base wiring at the two poller save points is Phase 30 (deferred by design).

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Gate runs both versions and returns 4-key dict | `python3 -m pytest tests/test_28_deterministic_gate.py -q` | 78 passed in 0.09s | PASS |
| Regression suite stable | `python3 -m pytest tests/test_28_deterministic_gate.py tests/test_26_continuity_loader.py tests/test_27_edition_eval.py -q` | 104 passed in 0.11s | PASS |
| Module syntax-clean | `python3 -c "import ast; ast.parse(open('docker/newsletter/deterministic_gate.py').read())"` | SYNTAX OK | PASS |

---

### Probe Execution

No probes declared or applicable — build-only phase with no runnable entry points modified.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| GATE-01 | 28-01 | Gate runs on BOTH versions; short-circuits on fabrication (detection core) | SATISFIED (detection); wiring deferred to Phase 30 | Both versions processed at :154-199; 78 tests prove detection |
| GATE-02 | 28-02 | GitHub 404 → fabricated; >20% star drift → flag | SATISFIED (detection) | `_classify_github`, `_run_github_layer`; 10 GitHub tests pass |
| GATE-03 | 28-02 | URL HEAD liveness; 404/410 → flag; transient → unverified | SATISFIED (detection, refined by D-01) | `_classify_url`, `_run_url_layer`; 12+ URL tests pass. Note: D-01 refines the literal GATE-03 wording — 403/429 → unverified (not fabrication) per operator decision in CONTEXT.md |
| GATE-04 | 28-01 | Named study/benchmark + arXiv ID vs fact base | SATISFIED | `verify_draft` tier1 + `_check_arxiv_membership` + WR-03 anchored check; 5 tests pass |
| GATE-05 | 28-01 | Entity-merge per-source verbatim | SATISFIED | `_check_entity_merge` with WR-01 cross-source logic; 4 tests pass |
| GATE-06 | 28-03 | H1/title echo + reading-mode label leak | SATISFIED (COMPLETE in REQUIREMENTS.md) | `_check_h1_and_title_echo` + `_check_reading_mode_leak`; 8 tests pass |
| GATE-07 | 28-03 | Recycled closer + duplicated stat vs prior edition | SATISFIED (COMPLETE in REQUIREMENTS.md) | `_check_cross_edition` + `_normalize`; 8 tests pass |
| GATE-08 | 28-01 | Correct fact base (blocks vs input_data) dispatched in-memory | SATISFIED (detection); live save-point wiring deferred to Phase 30 | `fact_base_path` dispatch at :145; fail-loud at :131-141; 5 tests pass |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `deterministic_gate.py` | 534, 707 | `return ("unverified", None, "unknown")` (unreachable paths) | INFO | Documented `# pragma: no cover`; loop logic always returns before these — defensive dead code, not a stub |
| `deterministic_gate.py` | (none) | No TBD/FIXME/XXX/TODO markers | — | Clean — no unresolved debt markers |

No blocker anti-patterns found. No unreferenced debt markers. Module is substantive (825 lines), not a stub.

---

### Human Verification Required

None. The gate is a standalone pure-Python detection module with:
- No UI or visual output
- No real-time behavior
- No external service integration (all network calls are injected via `http_client` seam; tests use a fake client)
- No live database
- No container rebuild

All behaviors are fully verifiable via the test suite, which imports the real module and exercises every code path. The Phase 30 calibration window (READING_MODE_LABELS tuning, enforce flag) is a future-phase operator activity, not a Phase 28 deliverable.

---

## Security Sub-checks

| Threat | Mitigation | Verified |
|--------|-----------|---------|
| T-28-04 SSRF | `_is_safe_public_url` rejects loopback/RFC-1918/link-local/internal-service/`*.internal`; resolve-then-validate via `_resolve_host` catches non-canonical IP forms (CR-01) and DNS rebinding | Zero-calls assertion in 6 SSRF tests; `test_ssrf_guard_rejects_noncanonical_ip_encodings` and `test_ssrf_guard_rejects_public_hostname_pointing_internal` pass |
| T-28-05 Token leak | Token sent only in `Authorization` header to `api.github.com`; `meta.github_token_present` is `bool()` only; never logged | `test_github_token_present_flag_and_never_leaked` asserts `secret not in json.dumps(flags)` and `secret not in caplog.text` |
| T-28-07 Transient as fabrication | D-01 three-outcome classifier: only definitive 404/410 → fabrication; 5xx/timeout/403 → first-class `unverified` | `test_github_403_unverified_not_fabrication`, `test_url_403_unverified_not_fabrication`, parametrized transport-error tests pass |
| CR-02 Broad httpx errors | `httpx.HTTPError` caught after specific `Timeout`/`ConnectError`/`TooManyRedirects` catches → `unverified`, never crash | `test_url_transport_error_unverified_full_dict` (6 parametrized cases), `test_transport_error_preserves_other_flags` pass |

---

## Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | "runs on every edition before any LLM judge/rewrite" + hold+escalate action (GATE-01 runtime behavior) | Phase 30 | WIRE-01: "eval is invoked from newsletter_poller sequencer"; WIRE-02: "fabrication flag → status='held' + do_not_publish=true" |
| 2 | Live GitHub API + URL egress at the two poller save points (GATE-02/03 live-wiring) | Phase 30 | WIRE-01/05: "eval invoked at the two generation save points"; Phase 30 injects real `httpx.Client(timeout=5)` |
| 3 | "read in-memory at the two generation save points" via existing dual-fact-base wiring (GATE-08 live dispatch) | Phase 30 | WIRE-01/05: newsletter service where the true fact base exists; poller branch selects correct base |
| 4 | `edition_evals` persistence of the `deterministic_flags` JSONB (the flags object produced here) | Phase 30 | WIRE-01: "eval failure writes error row + continue" |

---

## REQUIREMENTS.md Reconciliation

REQUIREMENTS.md marks:
- `[x] GATE-06` — Complete: correct, detection fully realized and self-contained (no poller wiring needed for this check)
- `[x] GATE-07` — Complete: correct, same reasoning
- `[ ] GATE-01..05, GATE-08` — Pending: correct, detection cores realized in code this phase; live-wiring / hold-action closure deferred to Phase 30

This split accurately reflects the build-only / report-only design. No reconciliation action needed.

---

## Gaps Summary

No gaps. All 20 must-have truths are VERIFIED against the actual codebase. The 5 code-review blockers/warnings (CR-01 SSRF resolve-then-validate, CR-02 broad httpx catch, WR-01 entity-merge cross-source, WR-03 arXiv anchored, WR-04 draft validation) were all fixed before this verification, confirmed by commits `0405d9a`, `0de9764`, `fca03f5`, `ac1702a`, `e1c47c7` in the git log and by the 22 additional tests that exercise those fixes (78 total vs 56 pre-CR).

---

_Verified: 2026-06-30_
_Verifier: Claude (gsd-verifier)_
