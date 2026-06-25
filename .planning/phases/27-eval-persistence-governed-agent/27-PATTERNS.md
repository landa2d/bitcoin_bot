# Phase 27: Eval Persistence & Governed Agent - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 3 new (1 migration, 1 module, 1 test)
**Analogs found:** 3 / 3 (every new file has a locked existing analog)

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `supabase/migrations/045_edition_evals.sql` | migration | batch (DDL + seed) | `034_governance_caps_and_oncap_behavior.sql` (SECTION 1) + `029_rivalscope_agent.sql` (SECTION 2) | exact |
| `docker/newsletter/edition_eval.py` | service / persistence-helper | CRUD (insert + `.eq()` select) | `docker/newsletter/newsletter_poller.py` | role-match (no standalone persistence module exists yet; the patterns live inline in the poller) |
| `tests/test_27_edition_eval.py` | test | fixture / transform | `tests/test_26_continuity_loader.py` | exact (same milestone, same harness) |

---

## Pattern Assignments

### `supabase/migrations/045_edition_evals.sql` (migration, batch)

Two independently-runnable sections (D-11). SECTION 1 copies the idempotent-DDL house style from **034**; SECTION 2 copies the agent-seed shape from **029**.

#### SECTION 1 — table + constraints + index

**Analog:** `supabase/migrations/034_governance_caps_and_oncap_behavior.sql`

**House idempotency style — sectioned header banners** (034 lines 29-31):
```sql
-- ═══════════════════════════════════════════════════════
-- SECTION 1 — Schema extension on agent_wallets_v2 (D-02 / D-04)
-- ═══════════════════════════════════════════════════════
```

**Guarded `ADD CONSTRAINT` via `DO $$ … EXCEPTION WHEN duplicate_object`** (034 lines 131-147) — the canonical re-apply-safe constraint pattern the operator's discretion note in D-11/CONTEXT line 52 points at. Mirror this for the `edition_evals_verdict_iff_ok` CHECK if the table is created with `CREATE TABLE IF NOT EXISTS` (so the CHECK can be added separately and re-run safely); if instead the planner uses a bare `CREATE TABLE`, wrap the whole `CREATE TABLE` in the same `IF NOT EXISTS (information_schema…) THEN … EXCEPTION WHEN duplicate_object` guard:
```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.table_constraints
         WHERE constraint_name = 'agent_wallets_v2_cap_or_uncapped'
           AND table_name      = 'agent_wallets_v2'
    ) THEN
        BEGIN
            ALTER TABLE agent_wallets_v2
                ADD CONSTRAINT agent_wallets_v2_cap_or_uncapped
                CHECK ((spending_cap_sats IS NOT NULL AND spending_cap_sats > 0) OR uncapped = TRUE);
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END;
    END IF;
END $$;
```

**Inline CHECK-constraint syntax** the verdict-iff-ok / enum CHECKs copy (034 lines 42-47):
```sql
ALTER TABLE agent_wallets_v2
    ADD COLUMN IF NOT EXISTS on_cap_behavior TEXT NOT NULL DEFAULT 'reject'
        CHECK (on_cap_behavior IN ('reject', 'downgrade'));
```

> The exact table DDL (columns, `edition_evals_verdict_iff_ok` CHECK, `UNIQUE(newsletter_id, layer, attempt)`, `idx_edition_evals_trend`) is **verbatim from REQUIREMENTS.md lines 103-126** — that block is authoritative (D-07). 034 supplies only the *idempotency wrapper + CHECK syntax*, not the column shape.

#### SECTION 2 — governed `edition_eval` agent seed

**Analog:** `supabase/migrations/029_rivalscope_agent.sql` (the whole file is the template)

**`agent_registry` INSERT + `ON CONFLICT (agent_name) DO UPDATE`** (029 lines 4-17):
```sql
INSERT INTO agent_registry (agent_name, agent_type, api_key_hash, access_tier, allowed_models, rate_limit_rpm, is_active)
VALUES (
    'rivalscope',
    'internal',
    '$2b$12$eyHGcM/tClhT2hGNJNPyjuUP6HFbq9DtKostcFQWttHdg1knV8aFC',  -- committed bcrypt hash (D-13 precedent)
    'internal',
    ARRAY['deepseek-chat', 'claude-sonnet-4-20250514'],
    30,
    TRUE
)
ON CONFLICT (agent_name) DO UPDATE SET
    api_key_hash = EXCLUDED.api_key_hash,
    allowed_models = EXCLUDED.allowed_models,
    is_active = TRUE;
```
Adapt for `edition_eval` (per REQUIREMENTS.md lines 129-131): `agent_name='edition_eval'`, committed real bcrypt hash (orchestrator-substituted, D-12/D-13), `allowed_models = ARRAY['deepseek-chat','claude-sonnet-4-6']` (NOT the EOL `…-4-20250514`), `rate_limit_rpm = 10`.

**`agent_wallets_v2` INSERT + `ON CONFLICT (agent_name) DO UPDATE`** (029 lines 19-30) — **note 029's column list is the PRE-034 short form** (no `uncapped`/`on_cap_behavior`/`downgrade_map`):
```sql
INSERT INTO agent_wallets_v2 (agent_name, balance_sats, total_deposited_sats, allow_negative, spending_cap_sats, spending_cap_window)
VALUES (
    'rivalscope',
    50000,
    50000,
    TRUE,        -- ← rivalscope is allow_negative=TRUE; edition_eval is FALSE (GOV-02)
    10000,
    'daily'
)
ON CONFLICT (agent_name) DO UPDATE SET
    spending_cap_sats = 10000,
    spending_cap_window = 'daily';
```

**Full column list `agent_wallets_v2` expects (derived from 034's schema additions, lines 39-47)** — the eval seed MUST use the EXTENDED list, not 029's short one, so the governance columns are populated explicitly (matches REQUIREMENTS.md lines 132-134):
```sql
INSERT INTO agent_wallets_v2 (agent_name, balance_sats, total_deposited_sats, allow_negative,
                              spending_cap_sats, spending_cap_window, uncapped, on_cap_behavior, downgrade_map)
VALUES ('edition_eval', 25000, 25000, FALSE, 5000, 'weekly', FALSE, 'reject', '{}'::jsonb)
ON CONFLICT (agent_name) DO UPDATE SET ... ;   -- 029 idempotency pattern
```
GOV-02 values (D-01): `allow_negative=FALSE`, `spending_cap_sats=5000`, `spending_cap_window='weekly'`, `uncapped=FALSE`, `on_cap_behavior='reject'`, `downgrade_map='{}'::jsonb`, `balance_sats=total_deposited_sats=25000`.

**Structural CHECK the seed must satisfy** (034 lines 140-142): `agent_wallets_v2_cap_or_uncapped` = `((spending_cap_sats IS NOT NULL AND spending_cap_sats > 0) OR uncapped = TRUE)`. Satisfied because `spending_cap_sats=5000 > 0` (D-14) — the row inserts cleanly even with `uncapped=FALSE`.

---

### `docker/newsletter/edition_eval.py` (service / persistence-helper, CRUD)

**Analog:** `docker/newsletter/newsletter_poller.py` (no standalone persistence module exists; the insert/select/`.eq()`/proxy patterns are extracted inline). This new module holds `write_eval_row()` + readers (D-08).

**Supabase insert pattern** (`newsletter_poller.py` lines 2032-2045 — `log_llm_call`, the closest "write one telemetry row" analog) — copy the `.table().insert({...}).execute()` shape, but **diverge on error handling** (see D-09 note below):
```python
supabase.table("llm_call_log").insert({
    "agent_name": agent_name,
    "task_type": task_type,
    "model": model,
    ...
}).execute()
```

**Supabase insert that captures the inserted id** (`newsletter_poller.py` lines 1719-1724):
```python
insert_result = supabase.table("newsletters").insert(row).execute()
row_id = insert_result.data[0]['id'] if insert_result.data else None
```

**`.eq()`-ONLY read pattern (NEVER `.in_()`)** (`newsletter_poller.py` lines 2220-2227) — this is the EVAL-03 contract source; the comment on line 2217 names the silent-failure bug the rule exists to kill. The `write_eval_row` reader + the `edition_number DESC` trend reader copy this exact chain:
```python
# One published-set read — plain .eq() ONLY, never the `.in_` filter
# (silent-failure bug; anti-pattern at :1792). 
recent = supabase.table('newsletters')\
    .select('edition_number, title, title_impact, content_markdown, '
            'content_markdown_impact, data_snapshot, published_at')\
    .eq('status', 'published')\
    .order('edition_number', desc=True)\
    .limit(8)\
    .execute()
rows = recent.data or []
```
For the trend reader (D-08, Phase 31's `SURF-03`): same chain but `.eq('pipeline_version', …)` + `.order('edition_number', desc=True)` — never `.in_()` on a list of edition numbers.

**DIVERGE — fail-loud write contract (D-09).** The analog inserts above use a fail-SOFT `except Exception → log.warning → swallow` (e.g. `log_llm_call` 2044-2045: `logger.warning(...)`; `newsletters` insert 1723-1724: `logger.error(...)` then continues). `write_eval_row` MUST NOT copy that: per D-09(c) the eval-row write failing **logs ERROR with `exc_info=True` and raises / returns an explicit error — never a bare `except`, never swallowed**. Use the structured-fail-loud style the project uses elsewhere:
```python
except Exception:
    logger.error("edition_evals write failed for newsletter_id=%s layer=%s attempt=%s",
                 newsletter_id, layer, attempt, exc_info=True)
    raise
```
And per D-09(a/b): an errored eval writes `eval_status='error'` + non-null `error` + NULL `verdict` (a proxy 402 / cap-hit is an error state, never a `0`) — which is exactly what the table's `edition_evals_verdict_iff_ok` CHECK enforces structurally.

#### Proxy / agent-identity pattern (for Phases 28/29 callers — NOT invoked in Phase 27)

> Phase 27 ships only `write_eval_row()` + reader (no LLM calls). These excerpts document what the Phase 28/29 judge will call and, critically, the identity-separation point (D-15) the planner must encode.

**Claude-via-proxy client init** (`newsletter_poller.py` lines 294-298) — the Sonnet-via-`/anthropic/v1/messages` shape:
```python
claude_client = anthropic.Anthropic(
    api_key=OPENAI_API_KEY,  # Proxy uses the agent's ap_ key
    base_url=f"{LLM_PROXY_URL}/anthropic",
)
```

**Claude call site** (`newsletter_poller.py` lines 856-871) — `messages.create(model=STRATEGIC_MODEL, …)` where `STRATEGIC_MODEL = "claude-sonnet-4-6"` (line 57):
```python
response = claude_client.messages.create(
    model=STRATEGIC_MODEL,
    max_tokens=1024,
    system=review_prompt,
    messages=[{"role": "user", "content": f"DRAFT:\n{content_md}"}],
)
usage = _Usage(response.usage.input_tokens, response.usage.output_tokens)
log_llm_call("newsletter", "qualitative_review", response.model, usage, ...)
```

**Agent-identity resolution to DIVERGE FROM (D-15)** (`newsletter_poller.py` lines 199, 206-218):
```python
_agent_api_key: str | None = os.getenv("AGENT_API_KEY") or None

def _get_agent_api_key() -> str:
    """Return cached API key, or look it up from Supabase on first call."""
    global _agent_api_key
    if _agent_api_key:
        return _agent_api_key
    try:
        result = supabase.table("agent_api_keys").select("api_key").eq("agent_name", AGENT_NAME).limit(1).execute()
        if result.data:
            _agent_api_key = result.data[0]["api_key"]
            return _agent_api_key
    except Exception:
        pass
    return ""
```
`AGENT_NAME = "newsletter"` (line 53). The eval module must **NOT** reuse this — GOV-02's governed budget is a *separate* wallet. Per D-15 the eval module reads `LLM_PROXY_EVAL_KEY` from env and passes it explicitly on its proxy calls (e.g. a dedicated `anthropic.Anthropic(api_key=os.getenv("LLM_PROXY_EVAL_KEY"), base_url=f"{LLM_PROXY_URL}/anthropic")`), so the proxy attributes spend to `edition_eval`, not `newsletter`.

---

### `tests/test_27_edition_eval.py` (test, fixture/transform)

**Analog:** `tests/test_26_continuity_loader.py` (sibling-milestone test, same harness — D-08 says mirror it)

**Real-module import (no re-implementation — the test_19_smartquote rule)** (`test_26_continuity_loader.py` lines 33-37). conftest preloads the module (`tests/conftest.py:95` pre-imports `newsletter_poller` with the right `schemas`); the test imports the REAL function:
```python
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import newsletter_poller as nl  # noqa: E402  — the REAL production module
```
For Phase 27: `import edition_eval as ee` (same `NL_DIR` belt-and-suspenders fallback). `edition_eval.py` lives in `docker/newsletter/`, so the same sys.path insert applies. **If `write_eval_row` is to be importable, the conftest preload list may need `edition_eval` added** (mirror conftest.py:95) — flag for the planner.

**In-memory Supabase stub (no live DB, no network — threat T-26-T1)** (`test_26_continuity_loader.py` lines 49-85) — exposes ONLY the fluent chain under test, FIFO-queued responses:
```python
class _StubResult:
    def __init__(self, data):
        self.data = data

class _StubQuery:
    def __init__(self, response_queue):
        self._q = response_queue
    def select(self, *a, **k): return self
    def eq(self, *a, **k):     return self
    def order(self, *a, **k):  return self
    def limit(self, *a, **k):  return self
    def execute(self):
        data = self._q.pop(0) if len(self._q) > 1 else (self._q[0] if self._q else [])
        return _StubResult(data)

class StubSupabase:
    def __init__(self, *responses):
        self._q = list(responses) if responses else [[]]
    def table(self, name):
        return _StubQuery(self._q)
```
For Phase 27 the stub must additionally support `.insert(payload)` returning a `_StubResult` with `data=[{'id': <uuid>}]` (so `write_eval_row` can read back the id, mirroring `newsletter_poller.py:1721`), and let a test capture the inserted payload to assert the column contract.

**Assertion style — one behavior per test, explicit contract messages** (`test_26_continuity_loader.py` lines 157-166, 270-281). Phase 27's tests (per D-08/D-09) should prove, in this style:
- the **ok-row** write: `eval_status='ok'`, `verdict` NOT NULL, `error` NULL;
- the **error-row** write: `eval_status='error'`, `verdict` NULL, non-null `error` reason — never a silent `0` / `sats_spent=0` masquerading as a score;
- the **loud-raise-on-write-failure**: a stub whose `.insert().execute()` raises makes `write_eval_row` re-raise (assert `pytest.raises`) after an ERROR log — never swallowed;
- **`.eq()`-only reads**: the reader/trend-reader never call `.in_()` (the stub can omit `.in_()` so any accidental use raises `AttributeError`).
The `caplog`-based WARNING/ERROR assertion (lines 270-281) is the template for proving the loud-log half of D-09:
```python
def test_empty_corpus_returns_empty_marker_and_warns(caplog):
    with caplog.at_level(logging.WARNING):
        ctx = nl.load_edition_context(StubSupabase([]))
    assert any("continuity context empty" in r.message for r in caplog.records)
```

---

## Shared Patterns

### `.eq()`-only DB access (EVAL-03)
**Source:** `docker/newsletter/newsletter_poller.py:2217-2227` (the named-and-commented canonical example)
**Apply to:** every read/write in `edition_eval.py` and every stub method in the test. **Never `.in_()`** — known silent-failure bug (CLAUDE.md "economy_map" rule + the inline comment at line 2217).

### Fail-loud over fail-soft (EVAL-02 / D-09)
**Source (divergence baseline):** `docker/newsletter/newsletter_poller.py:2044-2045` and `:1723-1724` (the fail-SOFT pattern to *avoid* for the eval-row write)
**Apply to:** `write_eval_row` — `logger.error(..., exc_info=True)` then `raise`; never a bare `except`, never a silent zero score. This is the milestone-wide "no-silent-zero" invariant (CONTEXT lines 14-15, D-09). Telegram-delivery of the alert is explicitly NOT this phase (D-10 — lands in Phase 30/31 where `send_telegram` lives in the Processor).

### Committed-bcrypt-hash agent seed (GOV-01/02 / D-13)
**Source:** `supabase/migrations/029_rivalscope_agent.sql:8` (literal hash committed; bcrypt is one-way, key is an internal proxy key)
**Apply to:** SECTION 2 of migration 045 — orchestrator mints the `ap_edition_eval_<…>` key, substitutes the real bcrypt hash into the file, then MCP-applies (D-12). The committed file is the audit record of the live key-hash.

### Sectioned idempotent migration (D-11)
**Source:** `supabase/migrations/034_governance_caps_and_oncap_behavior.sql` (banner sections + `DO $$ … EXCEPTION WHEN duplicate_object`)
**Apply to:** both sections of migration 045 — independently runnable, re-apply-safe.

---

## No Analog Found

| Concern | Why no analog | Planner guidance |
|---------|---------------|------------------|
| DeepSeek-via-**proxy** call (`/v1/chat/completions` through `llm-proxy:8200`) | The newsletter service's `deepseek_client` goes **DIRECT** to `https://api.deepseek.com` (`newsletter_poller.py:51,283`) and its OpenAI client base_url defaults empty (`:52,278-281`) — only the Claude client is proxy-pointed (`:294-297`). So `routed_llm_call()` / `deepseek_client` do **NOT** satisfy GOV-01 for DeepSeek. | Phase 27 makes no LLM calls, so this is informational. When Phases 28/29 add DeepSeek judge/classify calls, build a dedicated proxy-pointed client `OpenAI(api_key=os.getenv("LLM_PROXY_EVAL_KEY"), base_url=f"{LLM_PROXY_URL}/v1")` — do NOT reuse the direct `deepseek_client`. Use RESEARCH.md / spec-01's `synthesis_sonnet_call` proxy patterns as reference. |
| `edition_evals` table itself | Net-new; `grep -rln edition_evals docker/` is empty (CONTEXT line 98). | DDL is authoritative from REQUIREMENTS.md lines 103-135 — copy verbatim, wrap in 034 idempotency. |

---

## Metadata

**Analog search scope:** `supabase/migrations/` (029, 034), `docker/newsletter/` (newsletter_poller.py, block_pipeline.py, conftest preload), `tests/` (test_26_continuity_loader.py, conftest.py), `config/agentpulse-config.json`, `config/.env`
**Files scanned:** 7 (2 migrations, 2 newsletter modules, 1 test, 1 conftest, 1 config)
**Pattern extraction date:** 2026-06-25
</content>
</invoke>
