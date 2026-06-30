---
phase: 28-layer-1-deterministic-gate
audited: 2026-06-30
asvs_level: 1
block_on: high
threats_total: 12
threats_closed: 12
threats_open: 0
status: SECURED
register_authored_at_plan_time: true
---

# Phase 28 — Layer 1 Deterministic Gate: Security Audit

**Verdict:** SECURED — every declared mitigation in the plan-time threat register is present
in the current `docker/newsletter/deterministic_gate.py` and backed by passing test evidence
(78/78 in `tests/test_28_deterministic_gate.py`). The two prior code-review BLOCKERs
(CR-01 SSRF resolve-then-validate, CR-02 broad `httpx` transport catch) are reflected in the
shipped code and exercised by named regression tests.

This phase is **report-only / emit-only (D-05)**: the gate returns a flags object and never
writes the DB, calls an LLM, flips status, or fetches the network unless an `http_client` is
injected. Mitigations are judged against the standalone module's behavior; live poller wiring,
hold action, and a real `httpx.Client(timeout=5)` are Phase 30 responsibilities.

## Threat Verification (mitigate)

| Threat ID | Category | Disposition | Evidence (file:line) | Test evidence |
|-----------|----------|-------------|----------------------|---------------|
| T-28-04 | InfoDisclosure/EoP (SSRF) | mitigate | `_is_safe_public_url` rejects non-http(s) scheme (`deterministic_gate.py:427`), internal denylist (`:86-90,:436`), `*.internal` (`:439`), bare single-label (`:450`), canonical blocked-IP (`:446-447` via `_is_blocked_ip :394-400`); CR-01 resolve-then-validate via `_resolve_host :462` + per-addr `_is_blocked_ip :467-473`, fail-closed on `OSError :463-464`; routed to `unverified(unsafe_host)` w/o fetch in `_classify_url :672-673` | `test_ssrf_guard_rejects_internal_and_private`, `..._rejects_noncanonical_ip_encodings`, `..._rejects_public_hostname_pointing_internal`, `..._rejects_if_any_resolved_addr_is_internal`, `..._fail_closed_on_resolution_failure`, `..._url_layer_rejects_noncanonical_loopback_no_fetch` (asserts `client.calls == []`), `test_url_unsafe_internal_host_no_fetch`, `test_url_unsafe_metadata_ip_no_fetch` — all PASS |
| T-28-05 | InfoDisclosure (token leak) | mitigate | Token read from param/env only (`:213`), sent only in `Authorization: token` to `api.github.com` over HTTPS (`:492-494`), never logged (sole `logger.info :146` emits `fact_base_path` label), `meta.github_token_present` is `bool(...)` (`:239`) | `test_github_token_present_flag_and_never_leaked` asserts `secret not in json.dumps(flags)` and `secret not in caplog.text` — PASS |
| T-28-06 | DoS (link-heavy draft) | mitigate | 5s per-request timeout (`:497` GitHub GET, `:676` URL HEAD), D-03 per-run dedup cache shared across layers (`:605-608`, `:724-727`), sequential bounded iteration, httpx default redirect cap | `test_github_dedup_same_repo_one_call`, `test_url_dedup_single_head_call` (one call for N refs) — PASS |
| T-28-07 | Tampering (transient → false hold / silent miss) | mitigate | D-01 three-outcome: only 404/410 → fabricated (`:519-520` GH, `:698-699` URL); 403/429 quota, 5xx, timeout, conn-refused, redirects, broad transport → first-class `unverified`, never collapsed. CR-02: `httpx.TooManyRedirects` + base `httpx.HTTPError` caught → `unverified` not crash (`:506-517`, `:685-696`) | `test_github_403_unverified_not_fabrication`, `test_github_5xx_unverified_after_retry_once`, `test_url_403_unverified_not_fabrication`, parametrized `test_{url,github}_transport_error_unverified_full_dict[exc0..5]`, `test_transport_error_preserves_other_flags` — all PASS |
| T-28-08 | InfoDisclosure (response body in flags) | mitigate | Only the status code drives the URL outcome; response body never read (`_classify_url` reads `resp.status_code` only `:697`). GitHub layer reads only the integer `stargazers_count` for drift, never stores the body | `test_url_response_body_never_in_flags` asserts an injected body string never appears in `json.dumps(flags)` — PASS |
| T-28-03 | Spoofing/Tampering (wrong fact_base) | mitigate | `isinstance(fact_base, dict)` fail-loud `ValueError` (`:137-141`); symmetric `draft` guard (`:132-136`, WR-04 fix); loud `meta.fact_base_path` log (`:146`) | `test_gate08_non_dict_factbase_fails_loud`, `test_gate_non_dict_draft_fails_loud`, `test_gate08_factbase_path_{blocks,input_data}` — PASS |
| T-28-01 | DoS (ReDoS on GitHub/URL regexes) | mitigate | `_GITHUB_URL`/`_MD_LINK`/`_BARE_URL`/`_STAR_ASSERTION` (`:67-74`) use bounded char classes / negated classes only, no nested quantifiers; engine regexes imported (linear) not rebuilt | Whole suite runs in 0.08s (no backtracking blowup); golden offender drafts processed without hang |
| T-28-09 | DoS (ReDoS on closer/normalize) | mitigate | `_normalize` is a simple linear `re.sub(r'\s+', ' ', ...)` (`:784`); `_closer_line` uses linear `re.split(r'\n\s*\n', ...)` (`:789`); `_stat_tokens` reuses the linear engine `_STATISTIC` (`:796`) — no new nested-quantifier pattern | GATE-07 tests (`recycled`, `duplicated_stat`, `no_fuzzy_threshold`) — PASS |
| T-28-02 | Tampering (log injection at INFO) | mitigate | Sole `logger.info` emits the `fact_base_path` label only (`:146`); no raw draft prose logged (grep: one logger call total) | Covered implicitly; `test_github_token_present...` also asserts nothing sensitive in `caplog.text` |
| T-28-10 | Tampering (log injection, mechanical) | mitigate | Mechanical checks (`_check_h1_and_title_echo`, `_check_reading_mode_leak`, `_check_cross_edition`) emit no logging; grep confirms zero `logger.*` calls in the mechanical layer | GATE-06/07 suite — PASS |
| T-28-11 | Tampering (prior_edition None/malformed crash) | mitigate | None-safe guards: `prior_number :166`, `(prior_edition or {}).get :167-170`, `_check_cross_edition` returns `[]` on empty/None `prior_body :809-810` (GATE-06 still runs) | `test_mechanical_gate07_prior_none_skips_cleanly` — PASS |

## Accepted Risks Log

| Threat ID | Category | Disposition | Rationale | Verification |
|-----------|----------|-------------|-----------|--------------|
| T-28-SC | Tampering (pip installs) | accept | Zero new packages this phase. Module imports stdlib only (`os, re, socket, ipaddress, logging, typing, urllib.parse`) plus `httpx` (already in the newsletter service `requirements.txt`). No install task exists in any of the three plans. | Confirmed via module import list (`deterministic_gate.py:31-41`); SUMMARYs 01/02/03 all record `tech-stack.added: []`. **Accepted — no code mitigation required.** |

## Unregistered Flags

None. No SUMMARY contains a `## Threat Flags` section; all three SUMMARYs explicitly record
"No new threat surface beyond the plan's `<threat_model>`" and `tech-stack.added: []`. No new
attack surface (schema/endpoint/auth/package) appeared during implementation that is unmapped
to a register threat.

## Code-Review Blocker Reconciliation

Both prior 28-REVIEW.md BLOCKERs are resolved in the current code (not just documented):

- **CR-01** (SSRF bypass via non-canonical IP encodings / DNS rebinding): the string-only
  guard was replaced by resolve-then-validate. `_resolve_host` (`:403-408`) + `_is_blocked_ip`
  applied to every resolved address (`:467-473`), bare single-label rejected (`:450`),
  fail-closed on resolution error (`:463-464`). Regression tests for `127.1`, `0x7f.0.0.1`,
  `0177.0.0.1`, `10.1`, hex metadata, public-name→internal-A-record, and multi-homed all PASS.
- **CR-02** (unhandled `httpx` transport errors crash the gate, discarding all flags): both
  classifiers now catch `httpx.TooManyRedirects` and the base `httpx.HTTPError`
  (`_classify_github :506-517`, `_classify_url :685-696`), mapping to `unverified` and never
  propagating. `test_transport_error_preserves_other_flags` proves the already-computed
  fabrication + mechanical flags survive a transport error.

(The review's WR-01/WR-03/WR-04 robustness findings were also folded into the shipped code —
GATE-05 cross-source-merge tightening, anchored arXiv-ID set membership, and the symmetric
`draft` guard — though those are correctness/FP concerns rather than register threats.)

## Notes for Phase 30 (carry-forward, not blockers)

- The SSRF guard validates at resolution time; a real `httpx.Client` should where practical
  pin/connect to the validated IP to fully close the TOCTOU/DNS-rebinding window (review WR-02
  noted resolve-then-validate closes the exploitable literal-encoding gap but a rebind window
  remains). Acceptable at ASVS L1 / report-only; revisit when egress goes live.
- `meta.github_token_present` reflects env-token presence even when `http_client is None`
  (review IN-01) — reporting nuance, not a leak.
- `meta.urls_checked` counts SSRF-rejected hosts that were never fetched (review IN-03) —
  reporting nuance, no egress implication.
