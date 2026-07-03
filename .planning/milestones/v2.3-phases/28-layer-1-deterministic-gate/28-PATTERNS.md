# Phase 28: Layer 1 Deterministic Gate - Pattern Map

**Mapped:** 2026-06-30
**Files analyzed:** 2 new (1 module + 1 test) — build-only phase (D-05)
**Analogs found:** 2 / 2 (both files have strong analogs; net-new sub-checks documented with closest style references)

> Build-only phase. Two deliverables: `docker/newsletter/deterministic_gate.py` (NEW) and `tests/test_28_deterministic_gate.py` (NEW). No wiring, no DB write, no rebuild — those are Phase 30. RESEARCH.md already cites exact lines; this map confirms each citation against source and excerpts the load-bearing code the executor copies from.

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `docker/newsletter/deterministic_gate.py` | service / verification engine | transform (draft+fact_base → flags) + outbound request-response (GitHub API, URL HEAD) | `docker/newsletter/verification.py` (engine reuse) + `docker/processor/agentpulse_processor.py::scrape_github` (network layer) | role-match (reuse) + partial (network) |
| `tests/test_28_deterministic_gate.py` | test | batch (fixture-driven asserts) + mocked request-response | `tests/test_26_continuity_loader.py` + `tests/test_27_edition_eval.py` | exact |

The gate is single-tier (newsletter Python service): an in-process pure function plus outbound HTTP. No browser/DB tier this phase.

---

## Pattern Assignments

### `docker/newsletter/deterministic_gate.py` (service, transform + outbound HTTP)

This module is **composed of three layers**: (1) REUSE the calibrated engine, (2) thin net-new fabrication additions, (3) net-new regex-only mechanical checks + net-new network layer. Each maps to a different analog.

#### Layer 1 — Reuse the fabrication engine (D-04, GATE-04/05 base)

**Analog (and direct import dependency):** `docker/newsletter/verification.py`

**Import the engine, do NOT rebuild it.** The gate's first lines mirror RESEARCH.md's recommended preamble. The symbols are confirmed present at these exact lines:
- `verify_draft(prose, input_data)` — `verification.py:483`
- `_extract_claims_from_prose(prose)` — `verification.py:141`
- `_build_block_list(input_data)` — `verification.py:299`
- `_ARXIV_ID` — `verification.py:109`
- `_STATISTIC` — `verification.py:112`

`verify_draft` return shape the gate consumes (verification.py:699-719) — pull `tier1_fabrications` for GATE-04/05 base:
```python
return {
    'items_checked': total,
    'verified': verified,
    'tier1_fabrications': tier1,      # named-entity fabrications (GATE-04/05 base)
    'tier2_likely': tier2,
    'tier3_possible': tier3,
    'all_ungrounded': all_ungrounded,
    'tier4_link_coverage': tier4,
    'summary': { 'total': total, 'tier1_count': len(tier1), ... },
    'block_entities_available': len(blocks['entities']),
    'block_stats_available': len(blocks['statistics']),
}
```

**The fact-base dispatch the gate must trust (GATE-08), NOT re-decide** — `_build_block_list` branches on `.get('blocks')` (verification.py:315-316):
```python
# verification.py:314-316
# ── Block pipeline path: extract from blocks directly ──
blocks = input_data.get('blocks', [])
if blocks:
    ...                         # block_v1 path
else:
    ...                         # single-pass path (premium_source_posts, section_b_emerging, clusters)
```
The gate passes its `fact_base` param straight through; `meta.fact_base_path = "blocks" if fact_base.get("blocks") else "input_data"` is the loud log (per RESEARCH.md defensive-assert recommendation).

**arXiv-IDs are extracted-then-DISCARDED today (the GATE-04 gap to close)** — `verification.py:287-289`:
```python
# ── Filter out arXiv IDs from statistics ──
# Pattern: YYMM.NNNNN (e.g., "2605.12673 introduces BenchJack")
statistics = {s for s in statistics if not _ARXIV_ID.match(s.split()[0]) if s.split()}
```
This only *removes* arXiv IDs from the stat set — there is **no membership test**. GATE-04 adds a NEW step: `_ARXIV_ID.finditer(body)` → flag any ID not present verbatim in the concatenated fact-base source text. (ed-36 fake-arXiv fixture.)

**The fuzzy match that masks entity-merge (the GATE-05 gap)** — `verification.py:499-514`:
```python
# ── Match entities ──
block_entities_lower = {e.lower() for e in blocks['entities']}
for entity in claims['entities']:
    if entity.lower() in block_entities_lower:
        verified.append({'type': 'entity', 'value': entity, 'verdict': 'VERIFIED'})
    else:
        # Fuzzy: check if entity is a substring of any block entity or vice versa
        fuzzy_match = any(
            entity.lower() in be or be in entity.lower()
            for be in block_entities_lower
            if len(be) >= 4  # don't fuzzy-match short strings
        )
        if fuzzy_match:
            verified.append({'type': 'entity', 'value': entity, 'verdict': 'VERIFIED (fuzzy)'})
        else:
            ungrounded.append({'type': 'entity', 'value': entity, 'verdict': 'UNGROUNDED'})
```
`block_entities_lower` is a **flat union with zero per-source provenance** (built in `_build_block_list`, declared `entities: set[str]` at verification.py:309, accumulated across every source). The fuzzy `be in entity.lower()` is what lets `acme/widgets` pass when only "acme" exists in source A. GATE-05's net-new per-source verbatim refinement runs ON TOP — see "Net-New" below. Do NOT touch the `_STOP_WORDS` list (verification.py:16-93, Edition-34-calibrated) or the tier classifier.

#### Layer 2 — Network three-outcome classifier (GATE-02/03, D-01/D-02/D-03)

**Analog:** `docker/processor/agentpulse_processor.py::scrape_github` (processor:1125-1167) — the codebase's canonical GitHub-API idiom.

**GitHub header + token convention** (processor:1134-1136) — copy verbatim:
```python
headers = {'Accept': 'application/vnd.github.v3+json'}
if GITHUB_TOKEN:
    headers['Authorization'] = f'token {GITHUB_TOKEN}'
```
**Token-from-env** (processor:96): `GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')` — the gate reads `github_token or os.getenv('GITHUB_TOKEN')` per D-03.

**Sync `httpx.Client` + 403-rate-limit handling** (processor:1157-1167):
```python
with httpx.Client(timeout=15) as client:
    for query in queries:
        try:
            resp = client.get('https://api.github.com/search/repositories', params={...}, headers=headers)
            if resp.status_code == 403:
                logger.warning("GitHub rate limit hit")
                break
            resp.raise_for_status()
            ...
```
**Star-count field** (processor:1177): `stars = repo['stargazers_count']` — GATE-02 reads `r.json().get('stargazers_count')` for the >20% drift band. Note: the gate uses `/repos/{owner}/{repo}` (existence/count), NOT `/search/repositories`.

**URL HEAD 5s-timeout convention** — `docker/newsletter/newsletter_poller.py:235-239` (the in-service sync httpx idiom):
```python
resp = httpx.get(
    f"{LLM_PROXY_URL}/v1/proxy/wallet/{AGENT_NAME}/summary?period=7d",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=5,
)
```
GATE-03 mirrors this as `httpx.head(url, timeout=5, follow_redirects=True)`. The D-01 three-outcome mapping (404/410→fabricated; timeout/5xx/conn-refused→unverified after 1 retry; 200→verified) and the D-03 dedup cache are **net-new** — RESEARCH.md §"Pattern 2/3" supplies the skeleton (`_classify_github`, keyed dict cache).

#### Layer 3 — Mechanical regex checks (GATE-06/07, D-06)

**Net-new, regex-only.** Closest *style* reference is verification.py's own module-level regex constants (verification.py:96-138) and the normalized-exact helpers in RESEARCH.md §"GATE-07". Reuse `_STATISTIC` (verification.py:112) for stat tokens — do NOT write a new number regex.

**GATE-06 body-start marker — CONFIRMED VERBATIM** (`block_pipeline.py:660-661`):
```python
if 'read_this_skip_the_rest' in rendered:
    md_parts.append("## Read This, Skip the Rest\n\n" + rendered['read_this_skip_the_rest'])
```
So `BODY_START_MARKER = "## Read This, Skip the Rest"` (two-hash, comma after "This"). The H1/title-echo check: body must NOT contain a single-hash `# ` H1, and `draft['title']`/`draft['title_impact']` must NOT appear as a header line in its body.

**GATE-06 reading-mode-label leak — CONFIRMED source literals** (`block_pipeline.py:347-350`):
```python
if audience == 'impact':
    audience_prefix = "AUDIENCE: Business leaders and strategic decision-makers. ..."
else:
    audience_prefix = "AUDIENCE: Technical builders and infrastructure teams. ..."
```
`AUDIENCE:` is the realistic leak vector. Seed the curated `READING_MODE_LABELS` blacklist (module constant, operator-tunable) from RESEARCH.md §TODO-3 — do NOT blacklist bare `"IMPACT"`/`"Technical"` (legitimate prose). This exact membership is the one open operator decision (A1) — ship tunable.

#### Output contract (matches migration 045 `deterministic_flags` JSONB)

**Migration 045 column shape** (`supabase/migrations/045_edition_evals.sql:47`):
```sql
deterministic_flags JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {fabrication:[...], mechanical:[...]}
```
The gate returns `{fabrication:[...], unverified:[...], mechanical:[...], meta:{...}}` — `fabrication`/`mechanical` match the migration comment; `unverified` is the first-class D-01 key (Phase 30 maps it into the JSONB / verdict). Full flags skeleton: RESEARCH.md §"Recommended module signature". Verdict taxonomy (`passed/held_fabrication/held_voice/escalated`, 045:41) is computed in Phase 30 — the gate does NOT compute a verdict (D-05 emit-only).

---

### `tests/test_28_deterministic_gate.py` (test, batch + mocked request-response)

**Analog:** `tests/test_26_continuity_loader.py` (import preamble + in-memory stub double) and `tests/test_27_edition_eval.py` (payload-capturing stub + the "dep-as-param → plain sys.path insert" note).

**Import preamble — copy verbatim** (`test_26_continuity_loader.py:24-37`, `test_27_edition_eval.py:24-37`):
```python
import logging
import sys
from pathlib import Path
import pytest

NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import deterministic_gate as gate  # noqa: E402 — the REAL production module
```
Critical: import the REAL module (the `test_19_smartquote` rule — a re-implemented copy can pass while production regresses). `conftest.py` preloads `newsletter_poller` but NOT `verification`/`deterministic_gate`; the `sys.path.insert` above makes both importable, and the gate's bare `from verification import ...` resolves once `NL_DIR` is on the path (test_27:30-35 confirms this works for a stdlib+param module).

**In-memory stub double (no network) — the fake httpx client mirrors this shape** (`test_26_continuity_loader.py:49-85`): a fluent double with a FIFO response queue.
```python
class _StubResult:
    def __init__(self, data):
        self.data = data

class _StubQuery:
    def __init__(self, response_queue):
        self._q = response_queue
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    ...
    def execute(self):
        data = self._q.pop(0) if len(self._q) > 1 else (self._q[0] if self._q else [])
        return _StubResult(data)

class StubSupabase:
    def __init__(self, *responses):
        self._q = list(responses) if responses else [[]]
    def table(self, name):
        return _StubQuery(self._q)
```
For Phase 28, build a **fake `httpx.Client` double** in the same spirit: a dict/queue keyed by URL returning `(status_code, json)` tuples, raising `httpx.TimeoutException`/`httpx.ConnectError` on demand, with a call-counter to assert D-02 retry-once and D-03 dedup. Inject via the gate's `http_client` param — **no `monkeypatch` of the real network** (test_27:43-50 precedent: a stub that captures/asserts call behavior).

**Fixture builder + golden-draft pattern** (`test_26:88-100`, `:107-130`): small helper that builds a row/fact_base dict carrying every field the function reads; hand-authored markdown bodies starting with `## Read This, Skip the Rest`. Seed the offenders from CONTEXT Discretion: ed-36 invented "MCP authentication" study, ed-34 "GroupMemBench", a fake arXiv ID, a 404 repo, a transient-5xx→unverified case, a recycled closer, a leaked reading-mode label. One `fact_base={'blocks':[...]}` fixture + one single-pass `input_data` fixture to lock both GATE-08 paths.

**`__main__` runner footer** (test_26:322-323): `if __name__ == "__main__": sys.exit(pytest.main([__file__, "-v"]))`.

---

## Shared Patterns

### Reuse-then-refine (do NOT rebuild)
**Source:** `docker/newsletter/verification.py` (`verify_draft`:483, `_ARXIV_ID`:109, `_STATISTIC`:112, `_STOP_WORDS`:16-93)
**Apply to:** every fabrication check in the gate.
Import the calibrated engine; add thin layers only. Re-rolling claim extraction or the stop-list regresses the Edition-34 ~0-tier-1-FP calibration. Import, never copy.

### Sync httpx + GitHub convention
**Source:** `docker/processor/agentpulse_processor.py:1134-1167` (headers/token/403), `:96` (env token), `:1177` (stargazers); `docker/newsletter/newsletter_poller.py:235-239` (5s-timeout sync HEAD idiom)
**Apply to:** GATE-02 (GitHub API) and GATE-03 (URL HEAD). Sync `httpx.Client`/`httpx.head`, `timeout=5`, token via `os.getenv('GITHUB_TOKEN')`, 403/429→unverified (never fabricated).

### Test import preamble + real-module rule
**Source:** `tests/test_26_continuity_loader.py:24-37`, `tests/test_27_edition_eval.py:24-37`, `tests/conftest.py:32-78`
**Apply to:** the new test file. `sys.path.insert(0, docker/newsletter)` then `import deterministic_gate as gate`; never re-implement the module under test.

### In-memory stub double (no network, no DB)
**Source:** `tests/test_26_continuity_loader.py:49-85` (fluent + FIFO queue), `tests/test_27_edition_eval.py:43-70` (payload-capturing + call-behavior asserts)
**Apply to:** the fake httpx client. Inject via the gate's `http_client` param; assert dedup (D-03) and retry-once (D-02) via a call counter. No live egress in Phase 28.

---

## Net-New (no direct analog — use RESEARCH.md code examples)

These sub-functions have no existing code analog; the planner should reference RESEARCH.md §"Code Examples" / §"Pattern 2/3" rather than a codebase file. Closest *style* references noted.

| Net-new piece | GATE | Why no analog | Style reference |
|---------------|------|---------------|-----------------|
| Network three-outcome classifier (404/410→fabricated, timeout/5xx→unverified, 200→ok) | GATE-02/03, D-01 | No existing code maps HTTP results into a 3-state fabrication taxonomy; `scrape_github` only breaks on 403 | RESEARCH.md §"Pattern 2", processor:1157-1167 (client/headers/403 shape) |
| Retry-once-on-transient + per-run dedup cache | D-02/D-03 | No existing retry/cache for liveness checks (processor uses tenacity at the function level, not per-ref) | RESEARCH.md §"Pattern 3" |
| arXiv-ID **membership** check | GATE-04 | Engine extracts-then-discards arXiv IDs (verification.py:287-289); membership test is genuinely absent | reuse `_ARXIV_ID` regex (verification.py:109) |
| Per-source verbatim entity-merge refinement | GATE-05 | Engine's fact base is a flat union (verification.py:309) with no per-source provenance | RESEARCH.md §TODO-1 (keep `_build_block_list`'s field accessors per-item instead of unioning) |
| Cross-edition recycled-closer + duplicated-stat check (normalized-exact) | GATE-07 | `validate_stat_repetition` (poller:367) is intra-edition + One-Number-keyed → a no-op now; NOT reusable | RESEARCH.md §"GATE-07" `_normalize`/`_closer_line`/`_stat_tokens`; reuse `_STATISTIC` (verification.py:112) |
| SSRF guard `_is_safe_public_url` (reject loopback/private/`llm-proxy`/`supabase`/link-local → unverified) | GATE-03 (security) | No existing egress-allowlist helper | RESEARCH.md §"Security Domain" recommendation (~10 lines) |
| Curated reading-mode-label blacklist (module constant) | GATE-06 | No single canonical body literal exists; `AUDIENCE:` (block_pipeline.py:348,350) is the seed | RESEARCH.md §TODO-3 list (operator-tunable; open question A1) |

---

## Phase 30 hand-offs surfaced (do NOT implement here)

- `prior_edition` must be supplied as a **full** previous-published `content_markdown` (+ `_impact`), NOT `load_edition_context`'s truncated excerpt (poller:2242-2253 exposes only `opening_excerpt`). The gate takes it as a param; Phase 30 fetches it via `.eq('status','published').order('edition_number', desc=True).limit(1)`.
- Verify `GITHUB_TOKEN` passthrough to the newsletter container (compose `env_file`) — Phase 30.
- The fact-base **selection branch** (poller:1737-1749, the `tool_stats`→`trending_tools` rename) stays in the poller; the gate trusts the dict it is handed.

---

## Metadata

**Analog search scope:** `docker/newsletter/` (verification.py, newsletter_poller.py, block_pipeline.py), `docker/processor/agentpulse_processor.py`, `supabase/migrations/045`, `tests/` (test_26, test_27, conftest.py)
**Files scanned:** 7
**All RESEARCH.md line citations confirmed against source:** verify_draft:483, _build_block_list:299/315, fuzzy:499-514, _ARXIV_ID:109 + discard:287-289, _STATISTIC:112, GitHub convention:1134-1167/96/1177, adapter:1737-1749, httpx HEAD:235-239, marker:660-661, AUDIENCE: literal:347-350, deterministic_flags:047, test preamble:test_26:24-37 / test_27:24-37.
**Pattern extraction date:** 2026-06-30
