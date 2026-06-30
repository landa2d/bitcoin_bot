---
phase: 28-layer-1-deterministic-gate
plan: 02
subsystem: testing
tags: [newsletter, verification, deterministic-gate, ssrf, github-api, url-liveness, network, pytest, tdd, security]

# Dependency graph
requires:
  - phase: 28-layer-1-deterministic-gate
    plan: 01
    provides: "run_deterministic_gate orchestrator + the stable {fabrication, unverified, mechanical, meta} flags contract + the http_client/github_token seams (interface-first) the network layer wires into"
  - phase: 27-eval-persistence-governed-agent
    provides: "migration 045 deterministic_flags JSONB shape the flags object remains compatible with; fail-loud 'an error is not evidence' posture carried into the three-outcome classifier"
provides:
  - "GATE-02 GitHub network layer: _classify_github (/repos/{owner}/{repo} existence + stargazers_count star-drift >20%), _iter_github_refs, _asserted_star_count_for_ref, _parse_star_count, _run_github_layer"
  - "GATE-03 URL HEAD network layer: _classify_url (HEAD, 5s, follow_redirects), _iter_urls/_normalize_url/_add_url (markdown-link + bare-URL extraction, github-ref-excluded), _run_url_layer"
  - "Locked D-01 three-outcome classifier (confirmed-fabricated / first-class unverified / verified-ok), D-02 retry-once-on-transient (404 never retried), D-03 per-run dedup cache shared across both network layers"
  - "_is_safe_public_url SSRF guard (scheme + loopback/RFC-1918/link-local/unique-local IP + internal-service denylist + *.internal) routing unsafe hosts to unverified WITHOUT any fetch"
  - "Token hygiene: GITHUB_TOKEN read from env/param, sent only to api.github.com over HTTPS, never logged/in flags; meta.github_token_present is a bool only"
  - "tests/test_28_deterministic_gate.py: injectable fake httpx client double (call-counter) + 23 net-new GATE-02/03 + D-01/D-02/D-03 + SSRF + token-hygiene cases (zero live egress)"
affects: [28-03-mechanical-checks, 30-sequencer-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Network three-outcome classifier: every HTTP result mapped into exactly one of {fabricated, unverified, verified} (D-01); transient/quota are first-class unverified, never folded into fabrication or pass"
    - "Retry-once-on-transient + per-run dedup cache (D-02/D-03): one shared cache dict keyed ('gh',owner,repo)/('url',url) across the GitHub and URL layers; sequential iteration; each ref/URL checked exactly once"
    - "SSRF allowlist gate before any outbound fetch (ASVS L1): _is_safe_public_url short-circuits internal/private hosts to unverified with zero egress"
    - "Injected http_client seam: network layer runs ONLY when a client is provided (no default client constructed) — preserves the Plan-01 http_client=None zero-egress contract and keeps the whole suite network-free"

key-files:
  created: []
  modified:
    - docker/newsletter/deterministic_gate.py
    - tests/test_28_deterministic_gate.py

key-decisions:
  - "D-01 three outcomes never collapsed: GitHub/URL 404(+410)->fabrication; 403/429 quota, >=500, timeout, conn-refused->first-class unverified; 200->verified; star-drift >20% on a verified repo->github_stars fabrication"
  - "D-02 retry-once on transient ONLY (>=500/timeout/conn-refused), NEVER on a definitive 404/410 — proven via the fake client's call-counter (404=1 call, 5xx/timeout=2 calls)"
  - "D-03 single per-run dedup cache shared across both network layers; a repo/URL referenced N times -> exactly 1 network call (call-counter asserted)"
  - "SSRF guard is mandatory and fail-closed: unsafe/internal/private hosts route to unverified(reason=unsafe_host) with ZERO requests issued (T-28-04); github.com/owner/repo URLs excluded from the HEAD layer (handled by the GitHub API layer)"
  - "Token never leaks: read from env/param, only in the api.github.com Authorization header over HTTPS, never logged, never in the flags object (T-28-05); meta.github_token_present is a bool"
  - "Network layer gated on http_client being injected (no default client) so http_client=None stays zero-egress (Plan-01 contract) and tests never touch the real network"
  - "GATE-02/GATE-03 formal requirement closure DEFERRED to phase end (build-only/report-only; the runs-on-every-edition + live GitHub/URL egress wiring is Phase 30) — consistent with the 27-01/27-02/28-01 fail-loud-accuracy posture"

requirements-completed: []  # GATE-02/03 detection cores realized + proven in code; formal closure deferred to phase end (build-only; live wiring is Phase 30) per the established fail-loud-accuracy posture

# Metrics
duration: 7min
completed: 2026-06-30
---

# Phase 28 Plan 02: Layer 1 Deterministic Gate — Network Liveness + SSRF Summary

**Added the GATE-02 GitHub (repo existence + star-drift) and GATE-03 URL HEAD network-liveness layers to `run_deterministic_gate`, implementing the locked D-01 three-outcome classifier (confirmed-fabricated / first-class unverified / verified-ok), D-02 retry-once-on-transient (404 never retried), D-03 per-run dedup cache, and a fail-closed `_is_safe_public_url` SSRF guard — all proven against an injected fake httpx client with call-count assertions, zero live egress, and provable token hygiene.**

## Performance

- **Duration:** ~7 min
- **Completed:** 2026-06-30
- **Tasks:** 2 (both TDD: RED -> GREEN)
- **Files modified:** 2 (both extended, not rewritten — the Plan-01 fabrication core preserved)

## Accomplishments
- **GATE-02 (GitHub):** `_classify_github` hits `https://api.github.com/repos/{owner}/{repo}` with the processor's verbatim header/token convention; maps 404 -> fabricated (`github_repo`), 403/429 -> unverified (`rate_limit_403`), >=500/timeout/conn-refused -> unverified after exactly one retry, 200 -> verified with `stargazers_count`. `_run_github_layer` dedups refs (D-03), strips a trailing sentence period + `.git` from the captured repo, and flags `github_stars` fabrication when an asserted star count adjacent to the ref drifts >20% from live.
- **GATE-03 (URL HEAD):** `_classify_url` runs the SSRF guard FIRST (unsafe host -> unverified `unsafe_host`, never fetched), then `client.head(url, timeout=5, follow_redirects=True)`; 404/410 -> `dead_url` fabrication, timeout/conn-refused/5xx -> unverified after retry-once, other 4xx -> unverified `http_<code>` ("an error is not evidence"), 2xx -> verified. `_iter_urls` extracts markdown-link + bare URLs, normalizes trailing punctuation, **excludes** `github.com/owner/repo` (handled by the GitHub layer), and reuses the same per-run cache.
- **D-01/D-02/D-03 honored exactly:** three outcomes never collapsed; `unverified` is a populated, first-class top-level key strictly distinct from `fabrication`; the fake client's `.calls` counter proves 404=1 call (no retry), transient=2 calls (retry-once), duplicate ref/URL=1 call (dedup).
- **SSRF guard (security-critical):** `_is_safe_public_url` rejects non-http(s) schemes, loopback, RFC-1918 private, link-local (incl. the `169.254.169.254` metadata IP), unique-local, reserved/multicast IPs (IPv4 + IPv6), the compose internal-service denylist (`llm-proxy`, `supabase`, `gato_brain`, ...), `*.internal`, and bare single-label hosts — verified by a zero-calls assertion.
- **Token hygiene:** `GITHUB_TOKEN` read from param/env only, sent solely in the `Authorization: token` header to api.github.com over HTTPS, never logged, never placed in flags; `meta.github_token_present` is a bool (grep-asserted; a literal secret never appears in `json.dumps(flags)` nor captured logs).
- **23 net-new tests** (10 SSRF/GitHub in Task 1, 12 URL in Task 2 + 1 body-hygiene), all importing the REAL module and injecting the fake client — `test_28` now 37/37 green; `test_26`+`test_27` regression green (63/63 together); **zero** live network in the suite.

## Task Commits

Each task committed atomically (TDD test -> feat):

1. **Task 1 (RED): SSRF + GitHub classifier tests** — `f522d76` (test)
2. **Task 1 (GREEN): SSRF guard + GitHub repo/star three-outcome classifier + dedup + retry-once** — `406a862` (feat)
3. **Task 2 (RED): URL HEAD + SSRF-routing tests** — `e83e341` (test)
4. **Task 2 (GREEN): URL HEAD liveness classifier + URL extraction + orchestrator wiring** — `9b61fcf` (feat)

**Plan metadata** (this SUMMARY + STATE + ROADMAP) — see final docs commit.

## Files Created/Modified
- `docker/newsletter/deterministic_gate.py` (modified, 266 -> 605 lines) — added `ipaddress`/`urlparse` imports, `_BARE_URL`/`_STAR_ASSERTION`/`_INTERNAL_SERVICE_HOSTS` constants; `_is_safe_public_url`, `_classify_github`, `_iter_github_refs`, `_parse_star_count`, `_asserted_star_count_for_ref`, `_run_github_layer`; `_normalize_url`, `_add_url`, `_iter_urls`, `_classify_url`, `_run_url_layer`; wired both layers into `run_deterministic_gate` (gated on an injected `http_client`) populating `unverified`, `meta.github_checked`, `meta.urls_checked`. The Plan-01 fabrication core (`verify_draft` reuse, arXiv-membership, entity-merge) is untouched.
- `tests/test_28_deterministic_gate.py` (modified, 267 -> 623 lines) — added `httpx`/`json` imports, the injectable `_FakeHTTPClient`/`_FakeResponse` double with a `.calls` call-counter, github/url fixture helpers, and 23 net-new GATE-02/03 + D-01/D-02/D-03 + SSRF + token-hygiene + response-body-hygiene cases.

## Decisions Made
- **D-01 three outcomes, never collapsed:** only a definitive 404/410 (and GitHub 404) is `fabrication`; every transient (5xx/timeout/conn-refused) and quota (403/429) result is `unverified`; `unverified` is never folded into fabrication and never silently treated as a pass.
- **D-02 retry-once on transient ONLY:** a 404/410 is never retried (definitive evidence); 5xx/timeout/conn-refused retried exactly once before settling unverified — call-counter asserted.
- **D-03 one shared per-run cache** keyed `('gh',owner,repo)` / `('url',url)` across both layers; sequential; each unique ref/URL checked exactly once.
- **SSRF fail-closed + body-blind:** the SSRF guard runs before any URL fetch and short-circuits to unverified with zero egress; only the HTTP status code drives the outcome — a response body is never read into flags (T-28-08).
- **No default client for `http_client=None`:** deliberately not constructed, so the Plan-01 zero-egress contract holds and the suite never touches the network. Phase 30 injects a real `httpx.Client(timeout=5)`.
- **GATE-02/03 closure deferred to phase end:** the detection cores are realized and proven in code, but the gate is build-only/report-only and the "runs on every edition + live GitHub/URL egress" wiring is Phase 30, so `requirements mark-complete` was NOT run (fail-loud accuracy, matching 27-01/27-02/28-01).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] GitHub ref over-captured a trailing sentence period**
- **Found during:** Task 1 (GREEN — the `test_github_dedup_same_repo_one_call` case)
- **Issue:** `_GITHUB_URL`'s repo character class includes `.`, so `github.com/acme/tool.` (period ending a sentence) captured the repo as `tool.`, producing a second spurious `(owner, repo)` tuple and an extra, unmocked GitHub call. A real GitHub repo name never ends with a dot.
- **Fix:** `_iter_github_refs` now strips a trailing `.` from the captured repo (then the existing `.git` strip), and skips an empty result.
- **Files modified:** `docker/newsletter/deterministic_gate.py`
- **Commit:** `406a862`

**2. [Rule 2 - Doc accuracy] Plan-01 "Unused this plan" docstrings corrected**
- **Found during:** Task 1 (GREEN)
- **Issue:** the `http_client` / `github_token` arg docstrings still read "Unused this plan" from the interface-first Plan-01 skeleton; that is now false.
- **Fix:** updated both arg docstrings to describe the live network-layer behavior and the no-default-client / token-hygiene guarantees.
- **Files modified:** `docker/newsletter/deterministic_gate.py`
- **Commit:** `406a862`

No architectural deviations (Rule 4); no checkpoints; no authentication gates.

## Issues Encountered
- The **pre-existing** full-`tests/` collection errors/failures noted in the Plan-01 SUMMARY (missing `uvicorn`/`anthropic`, no live Supabase, pydantic drift) persist and are unrelated to this module. The plan's regression gate (`test_26`, `test_27`) + `test_28` are green (63/63). No new fix-attempt churn (out-of-scope, per the executor scope boundary).

## Threat surface
- **T-28-04 (SSRF):** mitigated — `_is_safe_public_url` rejects non-http(s) + loopback/private/link-local/unique-local IPs + internal-service denylist + `*.internal`; unsafe URLs route to `unverified(unsafe_host)` and are NEVER fetched (zero-calls asserted).
- **T-28-05 (token leak):** mitigated — token read from env/param, sent only to api.github.com over HTTPS, never logged/in flags; `meta.github_token_present` is a bool (grep + `json.dumps` assertions).
- **T-28-06 (DoS via link-heavy draft):** mitigated — 5s per-request timeout, D-03 dedup (each unique ref/URL once), sequential bounded iteration, httpx default redirect cap.
- **T-28-07 (transient treated as fabrication / silent miss):** mitigated — D-01 three-outcome classifier; transient/quota -> first-class `unverified`, asserted in tests.
- **T-28-08 (untrusted response body in flags):** mitigated — only the HTTP status code drives the outcome; body never read (asserted: an injected body string never appears in flags).
- No new threat surface beyond the plan's `<threat_model>` (zero new packages; no live egress in the suite).

## Next Phase Readiness
- The `{fabrication, unverified, mechanical, meta}` contract is unchanged and now fully populates `unverified` + `meta.github_checked`/`urls_checked`. Plan 03 adds the GATE-06/07 mechanical checks into `mechanical` (consuming `BODY_START_MARKER`/`READING_MODE_LABELS` + `prior_edition`) and runs the phase-gate + golden-draft integration suite.
- Phase-30 hand-offs (unchanged): inject a real `httpx.Client(timeout=5)`; verify `GITHUB_TOKEN` passthrough to the newsletter container; supply `prior_edition` as a FULL prior body (GATE-07).
- No blockers. Build-only / worktree-safe; nothing deployed.

## Self-Check: PASSED
- FOUND: `docker/newsletter/deterministic_gate.py`
- FOUND: `tests/test_28_deterministic_gate.py`
- FOUND commit: `f522d76` (test), `406a862` (feat), `e83e341` (test), `9b61fcf` (feat)
- `test_28` 37/37 green; `test_26`+`test_27` regression green (63/63 together); no live egress (`grep "httpx.Client()\|httpx.get(\|httpx.head(" tests/...` empty); `def _is_safe_public_url` present; token never in flags/logs.

---
*Phase: 28-layer-1-deterministic-gate*
*Completed: 2026-06-30*
