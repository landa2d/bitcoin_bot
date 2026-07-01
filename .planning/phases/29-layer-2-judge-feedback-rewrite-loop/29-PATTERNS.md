# Phase 29: Layer 2 Judge + Feedback-Rewrite Loop - Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 3 (2 new, 1 modified)
**Analogs found:** 3 / 3 (every file has a concrete in-repo analog; the module is a composite of 4 reused engines)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docker/newsletter/judge_loop.py` (**NEW**) | service (pure module, `run_layer2`) | request-response (Sonnet judge) + transform (revise) + event-driven loop | `docker/newsletter/deterministic_gate.py` (purity/guards/signature seam) **+** `block_pipeline.py::phase_e_voice_check` (the judge) | role-match (composite of 4 engines) |
| `tests/test_29_judge_loop.py` (**NEW**) | test | — (mocked I/O, zero egress) | `tests/test_28_deterministic_gate.py` | exact |
| `config/agentpulse-config.json` (**MODIFIED**) | config | — | sibling `block_pipeline` / `synthesis` top-level blocks in the same file | exact (sibling block) |

**Theme: reuse, not rebuild.** Four engines are imported verbatim (`run_deterministic_gate`, `_llm_call`, `parse_llm_json`, `_fact_base_source_texts`). The net-new surface is the judge prompt/schema, the revise prompt, `_compute_failing_dims`, `_select_best_attempt`, `_count_filler_hits`, and the N=2 loop orchestration. Every I/O boundary is an already-tested engine.

---

## Pattern Assignments

### `docker/newsletter/judge_loop.py` (pure service module, `run_layer2`)

This file has no single analog — it is assembled from several. Per-responsibility analogs below.

#### A. Module purity + fail-loud entry guard + keyword-only seam

**Analog:** `docker/newsletter/deterministic_gate.py::run_deterministic_gate` (`:93-141`)

The signature seam to mirror (positional core args + keyword-only `http_client`/`github_token`, both defaulting `None`, no default client constructed):

```python
# deterministic_gate.py:93-100
def run_deterministic_gate(
    draft: dict,
    fact_base: dict,
    prior_edition: dict | None,
    *,
    http_client: httpx.Client | None = None,
    github_token: str | None = None,
) -> dict:
```

The fail-loud type guard to copy (an entry guard on `det_flags['fabrication']` is the Phase-29 analog of this — "an error is not evidence", never a bare AttributeError deep in the body):

```python
# deterministic_gate.py:132-141
if not isinstance(draft, dict):
    raise ValueError(
        "run_deterministic_gate: draft must be a dict, got "
        f"{type(draft).__name__} — refusing to verify a wrong/missing draft"
    )
if not isinstance(fact_base, dict):
    raise ValueError(...)
```

Phase-29 entry guard (JUDGE-01, RESEARCH §Pattern 5) mirrors this shape:
```python
if det_flags.get("fabrication"):
    raise ValueError("run_layer2 called with a non-empty fabrication list — "
                     "Layer 1 must short-circuit before Layer 2 (mis-wired caller)")
```

**Also copy:** the INFO-log-the-label-not-the-prose discipline (`deterministic_gate.py:144-146` logs `fact_base_path`, never raw draft prose — T-28-02 log-injection mitigation; ASVS V7 in RESEARCH §Security).

#### B. The 5-dimension Sonnet judge (`_judge_draft` + `_validate_judge_response`)

**Analog:** `docker/newsletter/block_pipeline.py::phase_e_voice_check` (`:404-441`) + `PHASE_E_PROMPT` (`:378-401`)

The exemplar-anchored, JSON-out, distinguishable-fail template to generalize from 1 dimension to 5×2-bodies:

```python
# block_pipeline.py:404-441 (structure to generalize — NOT the JSON strip, see §Shared)
def phase_e_voice_check(draft, exemplars, llm_client, model='deepseek-chat') -> dict:
    if not exemplars:
        return {"score": None, "status": "not_scored",
                "observations": ["No operator exemplars available — voice not scored"]}
    exemplar_text = "\n\n---\n\n".join(exemplars[:10])
    prompt = PHASE_E_PROMPT.format(exemplars=exemplar_text, draft=draft[:4000])
    try:
        text = _llm_call(llm_client, model,
                         "You evaluate newsletter voice consistency. Respond only with valid JSON.",
                         prompt, temperature=0.2, max_tokens=500)
        # >>> ANTI-PATTERN (block_pipeline.py:428-432) — DO NOT COPY, see §Shared/JSON <<<
        if text.startswith('```'):
            text = text.split('```')[1]
            ...
        return json.loads(text.strip())
    except Exception as e:
        return {"score": None, "status": "not_scored", ...}   # distinguishable fail, never a fake 0
```

Key patterns to carry: temperature `0.2` (judge), `status: "not_scored"` distinguishable-fail (Phase 29's equivalent is `eval_status='error'` → `escalated`, JUDGE-05 — never a fabricated `0`).

**Prior-editions rendering for the continuity dimension** — reuse the exact shape `editorial_prepass_from_blocks` consumes (`block_pipeline.py:516-525`); the judge reads the same `prior_context.previous_editions[*]`:

```python
# block_pipeline.py:516-525 — the prior_context.previous_editions render shape
editions_text = "No previous editions available."       # <- D-05 empty case (continuity n/a)
if narrative_context and narrative_context.get('previous_editions'):
    lines = []
    for ed in narrative_context['previous_editions']:
        excerpt = (ed.get('opening_excerpt') or '')[:100]
        lines.append(
            f"#{ed.get('edition_number', '?')} ({ed.get('weeks_ago', '?')}w ago): "
            f"\"{ed.get('title', '?')}\" — {excerpt}"
        )
    editions_text = "\n".join(lines)
```

Judge output schema (Claude's discretion; RESEARCH §Pattern 2): both-bodies `{technical:{5 dims}, impact:{5 dims}}`, each dim `{score, evidence, exemplar_before, exemplar_after}`; continuity accepts the string `"n/a"` ONLY when `not continuity_applicable` (D-05). `_validate_judge_response` raises on any dim missing `evidence`/`exemplar_*` → JUDGE-05 schema-reject.

#### C. The targeted revise call (`_revise_draft`)

**Analogs:** `block_pipeline.py::_llm_call` (`:26`) + `deterministic_gate.py::_fact_base_source_texts` (`:245`) + `parse_llm_json`

The "only-these-facts" guardrail accessor to reuse verbatim (handles BOTH fact-base shapes — `blocks` for block_v1, `premium_source_posts`/`section_b_emerging`/`clusters` for single_pass — so ONE revise fn serves both writers, D-07):

```python
# deterministic_gate.py:245-288 — _fact_base_source_texts(fact_base) -> list[str]
blocks = fact_base.get("blocks") or []
if blocks:                                   # block_v1 path
    for block in blocks:
        ents = " ".join(str(e) for e in (block.get("named_entities") or []))
        texts.append(f"{block.get('description', '')} {ents}".strip())
    ...
else:                                        # single_pass path
    for post in fact_base.get("premium_source_posts", []) or []:
        texts.append(f"{post.get('title','')} {post.get('summary','')} {post.get('source_display','')}".strip())
    ...
return [t for t in texts if t]
```

Revise output parsed via `parse_llm_json(text, context="layer2_revise")` → `{content_markdown, content_markdown_impact}`; both bodies rewritten as a unit (D-08); `title`/`title_impact` stay unchanged.

#### D. Filler pre-pass (`_count_filler_hits`)

**Analog (data source, not code):** `data/openclaw/agents/newsletter/agent/IDENTITY.md:12-17` — seed `DEFAULT_FILLER_BLACKLIST` verbatim:

```
"navigating without a map", "wake-up call", "smart businesses are already",
"sifting through the narrative", "elevated urgency", "the landscape is shifting",
"builders should leverage", "as we move forward", "the evidence suggests",
"in today's rapidly evolving", "it remains to be seen", "only time will tell"
```

Combination (D-04): hedging dim fails iff `min(tech_hedging, impact_hedging) < hedging_fail_below` **OR** `max(tech_hits, impact_hits) >= hedging_filler_hits_max`.

#### E. Telemetry shape (`attempts[]` → `write_eval_row` params)

**Analog:** `docker/newsletter/edition_eval.py::write_eval_row` (`:66-82`) — the Phase-30 WRITE SURFACE the module does NOT call (D-09/D-10) but whose params each `attempt` object must map 1:1 onto:

```python
# edition_eval.py:66-82 — the param list the telemetry maps to
def write_eval_row(supabase, *, newsletter_id, edition_number, pipeline_version,
                   attempt, layer, eval_status, verdict=None, error=None,
                   deterministic_flags=None, judge_scores=None, judge_feedback=None,
                   sats_spent=0, model_calls=None) -> str:
```

The **verdict-iff-ok** invariant the telemetry must respect (an `error` attempt → `verdict=NULL`, non-empty `error`; an `ok` attempt → `verdict IN _VERDICTS`, `error=None`) — `edition_eval.py:121-134`:

```python
ok_shape  = eval_status == "ok"    and verdict in _VERDICTS and error is None
err_shape = eval_status == "error" and verdict is None and isinstance(error, str) and error.strip() != ""
if not (ok_shape or err_shape):
    raise ValueError("verdict-iff-ok violation: ...")
# _VERDICTS = ("passed", "held_fabrication", "held_voice", "escalated")   # edition_eval.py:61
```

Per-attempt telemetry object (RESEARCH §Pattern 9): `{attempt, eval_status, error, judge_scores, feedback, reverify_flags, sats, model_calls}` + internal-only `{failing, summed_score, draft}` (not persisted). Top-level: `{final_draft, verdict, selected_attempt, attempts:[...]}`.

---

### `tests/test_29_judge_loop.py` (unit suite)

**Analog:** `tests/test_28_deterministic_gate.py` (exact — mirror its structure)

**Import preamble to copy** (`test_28:34-41`) — sys.path insert to import the REAL module (test_19 rule: no re-implementation):

```python
# test_28_deterministic_gate.py:34-41
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))
import deterministic_gate as gate  # the REAL production module
```

For Phase 29: `import judge_loop as jl`. Note `judge_loop` imports `parse_llm_json` from `newsletter_poller`, which `conftest.py:95` preloads (`_preload_poller("newsletter_poller.py", ...)`) AND imports standalone — both verified; no new conftest fixture needed.

**Fixture builders to reuse** (`test_28:64-113`): `_make_draft(...)`, `_single_pass_fact_base(...)`, `_block_fact_base(...)`, `_body(...)`, `_clean_body()`, `_body_with_study(...)`. The draft shape (`content_markdown`/`content_markdown_impact`/`pipeline_version`) is identical to what `run_layer2` consumes.

**`_stub_dns` autouse fixture to carry** (`test_28:44-54`) — needed because `run_layer2` re-runs `run_deterministic_gate`, whose SSRF guard resolves hosts; without the stub the reverify tests do REAL DNS:

```python
# test_28:44-54
@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch):
    monkeypatch.setattr(gate, "_resolve_host", lambda host: ["93.184.216.34"])  # a public IP
```
(In test_29 this must patch the gate module the way judge_loop imports it — patch on the imported `deterministic_gate` symbol.)

**`_FakeHTTPClient` to reuse verbatim** (`test_28:135-159`) — the FIFO/last-sticky httpx double with `.calls` for the D-01 dedup-cache assert (`.calls` must NOT grow for an unchanged URL across attempts — RESEARCH §Pitfall 3) and the D-02 held_fabrication (queue a `(404, {})` for a rewrite-introduced repo):

```python
# test_28:135-159 (shape)
class _FakeHTTPClient:
    def __init__(self, responses=None):
        self._responses = {k: list(v) for k, v in (responses or {}).items()}
        self.calls = []
    def _next(self, url):
        self.calls.append(url)
        queue = self._responses.get(url)
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, Exception): raise outcome
        code, json_data = outcome; return _FakeResponse(code, json_data)
    def get(self, url, *, headers=None, timeout=None, **kwargs):  return self._next(url)
    def head(self, url, *, timeout=None, follow_redirects=None, **kwargs): return self._next(url)
```

**NET-NEW test double — `_FakeLLM` (OpenAI-shape, FIFO)** — no test_28 analog (test_28 makes no LLM calls). Add per RESEARCH §Code Examples 3; `anthropic` is NOT installed in the test env, so `_llm_call`'s `if anthropic and isinstance(...)` guard short-circuits to the OpenAI branch (`block_pipeline.py:33`), which reads `client.chat.completions.create(...).choices[0].message.content`. The fake queues canned judge/revise JSON strings and records `.calls` (assert exactly ≤2 revise calls for LOOP-02 N=2, RESEARCH §Pitfall 5):

```python
class _FakeLLM:
    def __init__(self, *responses): self._q=list(responses); self.calls=[]
    class _CC:
        def __init__(self, outer): self._o=outer
        def create(self, *, model, messages, temperature, max_tokens, **k):
            self._o.calls.append({"model":model,"messages":messages})
            return _Resp(self._o._q.pop(0) if len(self._o._q)>1 else self._o._q[0])
    @property
    def chat(self): return type("Chat",(),{"completions": _FakeLLM._CC(self)})()
```

**Test map** (RESEARCH §Validation Architecture, all Wave 0): JUDGE-01..05, LOOP-01..05, D-02/03/05/08/11 — 15 named test selectors.

---

### `config/agentpulse-config.json` (add top-level `edition_eval` block)

**Analog:** the sibling `block_pipeline` block (`config/agentpulse-config.json:127-134`) — the closest existing feature-flag + model-params block:

```json
"block_pipeline": {
  "enabled": false,
  "ab_comparison": true,
  "model_prepass": "claude-sonnet-4-6",
  "model_structure": "claude-sonnet-4-6",
  "model_prose": "claude-sonnet-4-6",
  "model_voice": "deepseek-chat"
}
```
(`synthesis` block `:` shows the `model` + `temperature` + `max_tokens` key convention to mirror for judge/revise params.)

**Placement:** top-level sibling. Current top-level keys: `version, models, budgets, pipelines, notifications, negotiation, spotlight_selection, intake_classifier, synthesis, analysis, pricing, block_pipeline, wallet_pricing`. `edition_eval` is **ABSENT** (verified). Append as a new top-level key (e.g., after `block_pipeline` at `:134`, or before `wallet_pricing` at `:135`). File is 143 lines; final block is `wallet_pricing` (per-model sat pricing).

**Block to add** (RESEARCH §Config Keys `:572-593`, thresholds VERBATIM from REQUIREMENTS.md, operator-confirmed `continuity_fail_below: 4` per D-04/A1):

```json
"edition_eval": {
  "enabled": false,
  "enforce": false,
  "max_attempts": 2,
  "judge_model": "claude-sonnet-4-6",
  "judge_temperature": 0.2,
  "judge_max_tokens": 1500,
  "revise_model": "claude-sonnet-4-6",
  "revise_temperature": 0.3,
  "revise_max_tokens": 3000,
  "thresholds": {
    "continuity_fail_below": 4,
    "hedging_fail_below": 3,
    "hedging_filler_hits_max": 3,
    "clickbait_fail_below": 3,
    "repeated_subtopics_fail_below": 3,
    "specificity_fail_below": 3,
    "warn_below": 4
  },
  "filler_blacklist": []
}
```
The module merges `config['edition_eval']` over `DEFAULT_*` constants so a partial/absent config still works (RESEARCH A4). `claude-sonnet-4-6` matches `MODEL`/`STRATEGIC_MODEL` (`newsletter_poller.py:56-57`) — spec 01's `claude-sonnet-4-20250514` is EOL (State of the Art).

---

## Shared Patterns

### Unified proxied LLM call (judge + revise)
**Source:** `docker/newsletter/block_pipeline.py::_llm_call` (`:26-53`)
**Apply to:** every LLM call in `judge_loop.py` (`_judge_draft`, `_revise_draft`). The anthropic-vs-OpenAI branch at `:33` is why the mocked test client works via the OpenAI path (`anthropic` is `None` in the test env → guard short-circuits):
```python
# block_pipeline.py:33-53
if anthropic and isinstance(client, anthropic.Anthropic):          # :33 — the branch
    response = client.messages.create(model=model, system=system,
        messages=[{"role":"user","content":user}], temperature=temperature, max_tokens=max_tokens)
    return response.content[0].text
# OpenAI-compatible (DeepSeek, OpenAI, proxied, AND the test mock)
response = client.chat.completions.create(model=model,
    messages=[{"role":"system","content":system},{"role":"user","content":user}],
    temperature=temperature, max_tokens=max_tokens)
return response.choices[0].message.content
```

### Robust JSON parse — the REQUIRED parser (and the anti-pattern to avoid)
**Source:** `docker/newsletter/newsletter_poller.py::parse_llm_json` (`:777-814`)
**Apply to:** every judge/revise parse (`context="layer2_judge"` / `"layer2_revise"`). Tries raw → fenced (`_JSON_FENCE_RE:732`) → first balanced object (`_first_balanced_object:748`), and FAILS LOUD (raises `json.JSONDecodeError`, never silent-empty):
```python
# newsletter_poller.py:786-814 (shape)
candidates = [stripped, fenced_group, balanced_object]
for cand in candidates:
    try: parsed = json.loads(cand)
    except (json.JSONDecodeError, ValueError): continue
    if isinstance(parsed, dict): return parsed
logger.error("[%s] No parseable JSON object ...", context, ...); raise json.JSONDecodeError(...)
```
**ANTI-PATTERN — DO NOT COPY:** `phase_e_voice_check`'s `if text.startswith('```')` inline strip (`block_pipeline.py:428-432`). That is the exact framing that produced the Phase-26 char-0 failure (State of the Art / MEMORY: commit bdb45ee). Any `startswith('```')` or `.split('```')` in `judge_loop.py` is a review-blocker.

### Governed proxy identity (documented, NOT constructed — D-09)
**Source:** `docker/newsletter/edition_eval.py::_get_eval_api_key` (`:43-51`) / `LLM_PROXY_EVAL_KEY` (`:40`)
**Apply to:** a docstring/comment in `judge_loop.py` stating the injected `llm_client` MUST authenticate as `edition_eval` (GOV-01). The pure module does NOT build the client (Phase 30 does: `anthropic.Anthropic(api_key=_get_eval_api_key(), base_url=f"{LLM_PROXY_URL}/anthropic")`). **Anti-pattern (RESEARCH §Pitfall 4):** any reference to `claude_client` or `OPENAI_API_KEY` in `judge_loop.py` bills the wrong wallet.

### Fail-loud / no-silent-zero
**Source:** `deterministic_gate.py:132-141` (type guards) + `edition_eval.py:121-134` (verdict-iff-ok) + `phase_e_voice_check` `not_scored` (`block_pipeline.py:414`)
**Apply to:** entry guard (`fabrication != []` → ValueError), schema-reject (`eval_status='error'` → `escalated`, never a fake `0`), `unverified` stays first-class (D-03, never folded into a hold). ASVS V5/V7 (RESEARCH §Security).

### Reused Layer-1 re-check on every rewrite (D-01)
**Source:** `deterministic_gate.py::run_deterministic_gate` (`:93`), injected shared `http_client`
**Apply to:** the loop body (`attempt_no > 0`) — re-run the SAME engine; a `fabrication` on the rewrite → `held_fabrication`, keep attempt-0 (D-02); `unverified`/`mechanical` → telemetry only (D-03). Cross-attempt dedup cache is the one net-new design decision (RESEARCH §Open Q1 — recommended: a thin caching `http_client` wrapper). SSRF is already handled inside the gate (`_is_safe_public_url`); the module adds NO raw egress.

---

## No Analog Found

None. Every file has a concrete in-repo analog. The genuinely net-new *logic* (no direct code analog, but pattern-guided) lives inside `judge_loop.py`:

| Helper | Role | Data Flow | Reason (no direct analog) |
|--------|------|-----------|---------------------------|
| `_compute_failing_dims` | pure transform | batch | Per-dimension threshold mapping (D-04) is net-new; thresholds come from config, not code |
| `_select_best_attempt` | pure transform | batch | D-11 tie-break (fewest fails → highest summed → latest) is net-new |
| `_validate_judge_response` | validator | request-response | JUDGE-05 schema gate (both-bodies × 5 dims, evidence+exemplar required) is net-new |
| cross-attempt dedup cache (`_CachingHTTPClient`) | utility | file-I/O (network memo) | RESEARCH §Open Q1 — the single net-new architectural decision; wraps the injected `http_client` |

These follow the fail-loud / pure-function patterns above but have no line-level copy source.

---

## Metadata

**Analog search scope:** `docker/newsletter/` (block_pipeline, deterministic_gate, newsletter_poller, edition_eval), `tests/` (test_28, conftest), `config/agentpulse-config.json`, `data/openclaw/agents/newsletter/agent/IDENTITY.md`
**Files scanned:** 8 (all read at source this session; ranges non-overlapping)
**Pattern extraction date:** 2026-07-01

### Line-reference index (for the planner)
| Symbol | File:line |
|--------|-----------|
| `_llm_call` (anthropic-vs-openai branch) | `docker/newsletter/block_pipeline.py:26` (branch `:33`) |
| `phase_e_voice_check` (judge template) | `docker/newsletter/block_pipeline.py:404` (`PHASE_E_PROMPT:378`) |
| JSON-strip ANTI-PATTERN | `docker/newsletter/block_pipeline.py:428-432` |
| prior_editions render shape | `docker/newsletter/block_pipeline.py:516-525` |
| `parse_llm_json` (REQUIRED parser) | `docker/newsletter/newsletter_poller.py:777` (`_JSON_FENCE_RE:732`, `_first_balanced_object:748`) |
| `MODEL`/`STRATEGIC_MODEL` = claude-sonnet-4-6 | `docker/newsletter/newsletter_poller.py:56-57` |
| `run_deterministic_gate` (signature + guards) | `docker/newsletter/deterministic_gate.py:93` (guards `:132-141`) |
| `_fact_base_source_texts` (revise guardrail) | `docker/newsletter/deterministic_gate.py:245` |
| `write_eval_row` (Phase-30 write surface) | `docker/newsletter/edition_eval.py:66` (verdict-iff-ok `:121-134`, `_VERDICTS:61`) |
| `_get_eval_api_key` / `LLM_PROXY_EVAL_KEY` | `docker/newsletter/edition_eval.py:43` / `:40` |
| test import preamble | `tests/test_28_deterministic_gate.py:34-41` |
| `_stub_dns` autouse | `tests/test_28_deterministic_gate.py:44-54` |
| fixture builders | `tests/test_28_deterministic_gate.py:64-113` |
| `_FakeHTTPClient` | `tests/test_28_deterministic_gate.py:135-159` |
| conftest newsletter_poller preload | `tests/conftest.py:95` |
| filler blacklist source | `data/openclaw/agents/newsletter/agent/IDENTITY.md:12-17` |
| sibling config block (`block_pipeline`) | `config/agentpulse-config.json:127-134` |
