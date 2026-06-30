---
phase: 28
slug: layer-1-deterministic-gate
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-30
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `28-RESEARCH.md` § Validation Architecture (lines 456–528). Build-only phase (D-05):
> the gate emits a flags object only — no DB write, no LLM, no wiring. All network is MOCKED via the
> injected `http_client` param; there is **no live egress** in any Phase 28 test.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo standard; `tests/conftest.py` configured) |
| **Config file** | `tests/conftest.py` (sys.path + schemas-collision workaround) |
| **Quick run command** | `python3 -m pytest tests/test_28_deterministic_gate.py -x` |
| **Full suite command** | `cd /root/bitcoin_bot && python3 -m pytest tests/` |
| **Estimated runtime** | ~10 seconds (pure functions + mocked network — no I/O) |

**Import pattern for the new test** (mirror `tests/test_26_continuity_loader.py:33-37`):
```python
import sys
from pathlib import Path
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))
import deterministic_gate as gate          # the REAL module — never re-implement
```
`deterministic_gate` imports `verification` by bare `from verification import ...`, which resolves once
`NL_DIR` is on the path. `conftest.py` preloads `newsletter_poller` but not `verification`/`deterministic_gate`,
so the explicit `sys.path.insert` above (belt-and-suspenders, exactly as test_26 does) is required.

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_28_deterministic_gate.py -x`
- **After every plan wave:** Run `python3 -m pytest tests/test_28_deterministic_gate.py tests/test_27_edition_eval.py tests/test_26_continuity_loader.py`
- **Before `/gsd-verify-work`:** Full suite (`python3 -m pytest tests/`) must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 1 | GATE-01, GATE-08 | T-28-WRONGFB | Logs `meta.fact_base_path`; verifies block_v1 against `blocks`, single-pass against `input_data` (never a reconstructed fact base); emits flags only — no DB/LLM/verdict | unit | `python3 -m pytest tests/test_28_deterministic_gate.py -k "factbase or orchestrator or shape" -x` | ❌ W0 | ⬜ pending |
| 28-01-02 | 01 | 1 | GATE-04, GATE-05 | — | Reuses calibrated `verify_draft` tier-1 (no stop-list rebuild); arXiv ID + entity-merge are net-new membership checks on top | unit | `python3 -m pytest tests/test_28_deterministic_gate.py -k "arxiv or merge" -x` | ❌ W0 | ⬜ pending |
| 28-02-01 | 02 | 2 | GATE-02 | T-28-SSRF / T-28-TOKEN | `_is_safe_public_url` rejects loopback/private/link-local/internal-service hosts → `unverified(unsafe_host)`, **never fetched** (zero-calls assert); `GITHUB_TOKEN` env-only, sent only to `api.github.com` over HTTPS, never logged/in-flags (`meta.github_token_present` bool) | unit (mock client) | `python3 -m pytest tests/test_28_deterministic_gate.py -k "github or ssrf or dedup or retry" -x` | ❌ W0 | ⬜ pending |
| 28-02-02 | 02 | 2 | GATE-03 | T-28-SSRF | Untrusted draft URLs HEAD-checked behind the SSRF guard; 5s timeout bounds DoS; D-01 three outcomes (404/410→fabricated, timeout/5xx→unverified, 200→ok), retry-once-on-transient (never retry 404) | unit (mock client) | `python3 -m pytest tests/test_28_deterministic_gate.py -k "url or unverified or retry" -x` | ❌ W0 | ⬜ pending |
| 28-03-01 | 03 | 3 | GATE-06 | T-28-REDOS | Body-marker/H1/title-echo + tunable `READING_MODE_LABELS` blacklist; new regexes are simple character classes (no nested quantifiers) | unit | `python3 -m pytest tests/test_28_deterministic_gate.py -k "mechanical or h1 or label" -x` | ❌ W0 | ⬜ pending |
| 28-03-02 | 03 | 3 | GATE-07 | T-28-LOGINJ | Normalized-exact (no fuzzy) closer + duplicated-stat vs prior edition; logs counts/refs not raw prose | unit | `python3 -m pytest tests/test_28_deterministic_gate.py -k "recycled or stat" -x` | ❌ W0 | ⬜ pending |
| 28-03-03 | 03 | 3 | GATE-01..08 (integration) | T-28-SSRF | Combined golden-draft suite — all historical offenders, mocked network, no live egress; asserts full flags shape + **no `verdict` key** (emit-only, D-05) | integration | `python3 -m pytest tests/test_28_deterministic_gate.py -x && python3 -m pytest tests/` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Threat refs map to each plan's `<threat_model>` STRIDE register: T-28-SSRF (draft-URL SSRF), T-28-TOKEN (token leakage), T-28-WRONGFB (wrong fact base), T-28-REDOS (regex DoS), T-28-LOGINJ (log injection). T-28-SC (zero new packages) accepted.*

---

## Wave 0 Requirements

- [ ] `tests/test_28_deterministic_gate.py` — covers GATE-01..08 + D-01..D-03. Includes the golden fixtures from CONTEXT's Discretion: ed-36 invented "MCP authentication" study, ed-34 "GroupMemBench", a fake arXiv ID, a dead-URL/404 repo, a transient-5xx→unverified case, a recycled closer, a leaked reading-mode label.
- [ ] Fake injectable `httpx` client double (queue of `(status_code, json)` per URL; raises `httpx.TimeoutException`/`ConnectError` on demand) + a call-counter to assert dedup (D-03) and retry-once (D-02). Inject via the `http_client` param — no `monkeypatch` of the real network needed.
- [ ] No framework install needed — pytest + conftest already present.

*Golden-draft fixture design:* hand-author small markdown bodies (start with `## Read This, Skip the Rest`) embedding each offender, paired with a minimal `fact_base` dict (a few `premium_source_posts` for single-pass; a few `blocks` for block_v1) that does/does not contain the entity/arXiv/repo. Stub `prior_edition` with a body whose closer line + one stat match the current draft for the GATE-07 case.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All phase behaviors have automated verification.* (The two operator-confirmation items — A1 exact GATE-06 blacklist membership, A2 clean+unverified verdict mapping — are explicitly deferred to Phase 30 report-only calibration; neither is a Phase 28 verification target. Live GitHub/URL egress is intentionally never exercised this phase — tests mock the client.)

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (the new test file + fake httpx double)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-30
