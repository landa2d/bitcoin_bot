# Phase 7: Synthesis Loop Core - Pattern Map

**Mapped:** 2026-05-31
**Files analyzed:** 4 (1 modified, 2 created, 1 test created)
**Analogs found:** 4 / 4 (every primitive exists in-repo as a Phase-5 artifact)

> **Spine-critical correction (from 07-RESEARCH.md, supersedes CONTEXT.md D-01/D-10):** The single
> Sonnet call MUST be a raw `httpx.post` to `{LLM_PROXY_URL}/anthropic/v1/messages` with an Anthropic
> Messages body. Do **NOT** use `routed_llm_call()` (it calls the OpenAI/DeepSeek SDK directly, has no
> Anthropic branch — `agentpulse_processor.py:506-533`) and do **NOT** use `/v1/chat/completions` (its
> Sonnet base_url is `https://api.anthropic.com`, which has no `/chat/completions` route). The transport
> analog is `classify_intake_event` (`:2996-3013`) but pointed at the Anthropic route with the Anthropic body.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docker/processor/agentpulse_processor.py` (add synthesis poller + helpers) | service/poller | event-driven (scheduled) + LLM request-response + CRUD | Phase-5 intake poller in the **same file** (`classify_intake_*` :2974-3298) | exact |
| `config/economy_map/synth_identity.md` (new) | config (operator-controlled voice) | file-I/O (mtime hot-reload) | `config/persona.md` / `config/guardrails.md` (mounted config); load pattern = `analyst_poller.py:82-110` | role-match |
| `config/agentpulse-config.json` (add `synthesis` block) | config | transform (threshold lookup) | `intake_classifier` block (`config/agentpulse-config.json:101-103`) | exact |
| `tests/test_07_synthesis.py` (new) | test | request-response (httpx stub) | `tests/test_05a_intake_classifier.py` (full harness) | exact |

## Pattern Assignments

### `docker/processor/agentpulse_processor.py` — synthesis poller + helpers (service, scheduled/LLM/CRUD)

New top-level functions land near their analogs in this single ~10k-line module (snake_case, no classes,
broad `except Exception:` + `logger.error(..., exc_info=True)`, module-level prompt string constants).

---

**(a) Single Sonnet call — transport analog `classify_intake_event` (:2974-3013), retargeted to `/anthropic/v1/messages`**

The intake classifier shows the exact in-processor proxy-call shape to mirror; only the URL, headers, and
body shape change to the Anthropic Messages contract:

```python
# ANALOG agentpulse_processor.py:2996-3013 (intake classifier — DeepSeek via /v1/chat/completions):
resp = httpx.post(
    f"{LLM_PROXY_URL}/v1/chat/completions",
    headers={"Authorization": f"Bearer {_get_agent_api_key()}"},
    json={"model": get_model("extraction"), "messages": messages,
          "temperature": 0.2, "max_tokens": 400},
    timeout=30,
)
if resp.status_code not in (200, 201):
    raise RuntimeError(f"intake classifier proxy call failed ({resp.status_code}): {resp.text}")
content = resp.json()["choices"][0]["message"]["content"]
return json.loads(_clean_json_response(content))
```

**Phase-7 adaptation (Anthropic route + body — from RESEARCH D-01 Resolution):**
```python
resp = httpx.post(
    f"{LLM_PROXY_URL}/anthropic/v1/messages",
    headers={
        "Authorization": f"Bearer {_get_agent_api_key()}",   # send BOTH (Open Question 1)
        "x-api-key": _get_agent_api_key(),
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    },
    json={
        "model": cfg.get("synthesis_model", "claude-sonnet-4-20250514"),
        "system": synth_identity_text,          # the hot-reloaded synth_identity.md
        "max_tokens": cfg.get("output_max_tokens", 8000),
        "temperature": cfg.get("temperature", 0.4),
        "messages": [{"role": "user", "content": assembled_prompt}],
    },
    timeout=120,    # match proxy TIMEOUT_CHAT
)
if resp.status_code not in (200, 201):
    raise RuntimeError(f"synthesis Sonnet call failed ({resp.status_code}): {resp.text}")
text = resp.json()["content"][0]["text"]      # Anthropic shape, NOT choices[0].message.content
```
Reuse `_get_agent_api_key()` (`:6467-6479`, cached). Reuse `_clean_json_response` (`:2965-2971`) on `text`.

---

**(b) JSON fence-stripper + output parse — analog `_clean_json_response` (:2965-2971)**

```python
# ANALOG agentpulse_processor.py:2965-2971:
def _clean_json_response(text: str) -> str:
    """Strip markdown code fences from LLM JSON output."""
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
    return text.strip()
```
Phase-7 parser wraps `json.loads(_clean_json_response(text))` and validates `proposed_maturity` against
`{"nascent","emerging","contested","consolidating","mature"}` — fail-loud (raise → caller logs + skips THIS
block's INSERT, never defaults). See RESEARCH "Parse + validate output (D-12)" example.

---

**(c) economy_map PostgREST READ with `Accept-Profile` — analog `_fetch_economy_map_block_slugs` (:3043-3070), `economy_map_edition_already_emitted` (:600-626)**

```python
# ANALOG agentpulse_processor.py:3050-3070 (blocks read — reuse for watermark/maturity/tension/current_body_version_id):
resp = httpx.get(
    f"{SUPABASE_URL}/rest/v1/blocks",
    params={"select": "slug"},
    headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
             "Accept-Profile": "economy_map"},
    timeout=10,
)
if resp.status_code == 200:
    ...
```
Phase-7 reads (mirror this with profile headers, raise on non-2xx):
- `/blocks?select=slug,maturity,live_tension,last_synthesized_at,current_body_version_id`
- **draft-existence guard (D-03):** `/block_body_versions?block_slug=eq.<slug>&status=eq.draft&select=id&limit=1` → non-empty list ⇒ block NOT eligible. The `idx_block_body_versions_status` partial index (`033:109-110`) makes this cheap.
- **entry window (D-04/D-07):** `/timeline_entries?block_slug=eq.<slug>&created_at=gt.<watermark>&select=event_date,what_shifted,why_it_mattered,source_url,created_at` (NULL watermark ⇒ omit the `created_at` filter — cold-start = all). Order by `event_date` desc in Python after fetch.
- **prior published body:** if `current_body_version_id` set, `/block_body_versions?id=eq.<id>&select=body_md`.

The existence-check analog raises on non-2xx so "read failure" is never mistaken for "no draft":
```python
# ANALOG agentpulse_processor.py:621-626:
if resp.status_code != 200:
    raise RuntimeError(f"economy_map ... existence check failed ({resp.status_code}): {resp.text}")
rows = resp.json()
return bool(isinstance(rows, list) and rows)
```

---

**(d) economy_map PostgREST INSERT with `Content-Profile` (D-13) — analog `economy_map_insert_timeline_entry` (:573-597)**

Add a **second purpose-scoped** helper `economy_map_insert_block_body_version(row)` — do NOT generalize into a
schema-agnostic writer (the `:566-571` rationale keeps the service_role write surface tight, threat T-05-02).

```python
# ANALOG agentpulse_processor.py:580-597 (clone, swap table + payload):
resp = httpx.post(
    f"{SUPABASE_URL}/rest/v1/timeline_entries",      # → /block_body_versions
    headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
        "Content-Profile": "economy_map",
    },
    json=entry,                                       # → {block_slug, body_md, proposed_maturity, synthesized_from_through}
    timeout=10,
)
if resp.status_code not in (200, 201):
    raise RuntimeError(f"economy_map timeline_entries insert failed ({resp.status_code}): {resp.text}")
rows = resp.json()
return rows[0] if isinstance(rows, list) and rows else rows
```
Payload: `{block_slug, body_md, proposed_maturity, synthesized_from_through}` — **omit `status`** (DB default
`'draft'`, `033:98-99`); `synthesized_from_through = datetime.now(timezone.utc).isoformat()` (the **run** timestamp,
not the newest entry's date — Pitfall 5). NEVER write `published`/`blocks.maturity`/`blocks.current_body_version_id`
(autonomy boundary; append-only trigger `033:177-211` backstops pinned columns anyway).

---

**(e) Orchestrator poller — analog `classify_intake_poller` (:3234-3298)**

```python
# ANALOG agentpulse_processor.py:3242-3264 (guard + config + fail-loud key check + run logging):
if not supabase:
    return {'error': 'Supabase not configured'}
cfg = get_full_config().get('intake_classifier', {})   # → .get('synthesis', {})
if not cfg.get('enabled', True):
    logger.info("[INTAKE] classifier disabled via config — skipping")
    return {'disabled': True}
floor = cfg.get('confidence_floor', 0.6)                # → N = cfg.get('N', 5); T_days = cfg.get('T_days', 30)
run_id = log_pipeline_start('classify_intake')          # → 'synthesize_blocks'
...
if not _get_agent_api_key():                            # fail-loud: no key → abort run, not a silent no-op
    logger.error("[INTAKE] processor agent API key unavailable — aborting run ...")
    log_pipeline_end(run_id, 'failed', {'error': 'missing agent api key'})
    return {'error': 'missing agent api key'}
```
Phase-7 poller structure: guard (supabase set? `synthesis.enabled`? identity present via `load_synth_identity()`
not None — else `log_pipeline_end('failed')` and return, D-11) → `_fetch_economy_map_block_slugs()` (or full blocks
read) → per-block try/except loop (eligibility → assemble → ONE Sonnet call → parse/validate → INSERT) →
`log_pipeline_end(run_id, 'completed', totals)`. Per-block try/except so one bad block never aborts the cycle
(mirror `:3278-3291`). Iterate all 7 blocks (low volume).

Eligibility predicate (D-05/D-06) and the recency-by-`created_at` rule: see RESEARCH "Eligibility predicate" example.
**Pitfall 2:** count "new" by `created_at > last_synthesized_at`, order the prompt by `event_date` desc.

---

**(f) Thin scheduled wrapper + registration — analog `scheduled_classify_intake` (:9834-9845) + `main()` (:10261-10263)**

```python
# ANALOG agentpulse_processor.py:9834-9845:
def scheduled_classify_intake():
    """Thin try/except wrapper around classify_intake_poller()."""
    try:
        result = classify_intake_poller()
        logger.info(f"Intake classification: {result}")
    except Exception as e:
        logger.error(f"Intake classification failed: {e}")

# ANALOG registration agentpulse_processor.py:10261-10263:
schedule.every(30).minutes.do(scheduled_classify_intake)
```
Add `scheduled_synthesize_blocks()` (clone) and register near `:10263`. Cadence is Claude's discretion —
RESEARCH recommends daily or every 6h, avoiding the Friday 08:30/11:00/12:00 newsletter slots (`:10255-10258`).

---

### `config/economy_map/synth_identity.md` (config, file-I/O hot-reload)

**Analog (load pattern):** `docker/analyst/analyst_poller.py:82-110` — module-global cache + mtime guard.

```python
# ANALOG analyst_poller.py:82-95:
_identity_cache: str | None = None
_identity_mtime: float = 0

def load_identity(agent_dir: Path) -> str:
    global _identity_cache, _identity_mtime
    identity_path = agent_dir / "IDENTITY.md"
    current_mtime = identity_path.stat().st_mtime if identity_path.exists() else 0
    if _identity_cache and current_mtime == _identity_mtime:
        return _identity_cache
    ...
```

**Phase-7 adaptation (fail-loud — return None on missing/empty so caller skips the cycle, D-11):** see RESEARCH
"Pattern 4" `load_synth_identity()` snippet. Path = `/home/openclaw/.openclaw/config/economy_map/synth_identity.md`.
**Mount already exists** (`docker-compose.yml:268` mounts `../config:/home/openclaw/.openclaw/config:ro`) — committing
`config/economy_map/synth_identity.md` to the repo auto-mounts it, **no docker-compose change**. `:ro` is fine (Phase 7
only reads). The file's default voice should follow the newsletter prose voice + the six-part block skeleton (RNDR-02).
**Analyst caveat:** the analyst uses `if _identity_cache` (truthy) — Phase 7 should use `if _synth_identity_cache is not None`
(the `load_skill` variant at `analyst_poller.py:120` already does this) so an intentionally non-empty-then-edited file re-checks correctly.

---

### `config/agentpulse-config.json` — add `synthesis` block (config, transform)

**Analog:** `intake_classifier` block (`:101-103`), read via `get_full_config().get('intake_classifier', {})` (`:3245`).

```json
// ANALOG config/agentpulse-config.json:101-103:
"intake_classifier": {
    "enabled": true,
    "confidence_floor": 0.6
}
```
**Add (RESEARCH D-09 recommended defaults):**
```json
"synthesis": {
    "enabled": true,
    "N": 5,
    "T_days": 30,
    "synthesis_model": "claude-sonnet-4-20250514",
    "max_input_entries": 22,
    "max_input_tokens": 12000,
    "output_max_tokens": 8000,
    "temperature": 0.4
}
```
Read in the poller via `get_full_config().get('synthesis', {})` (config caching already handled by `get_full_config` `:542` — Don't Hand-Roll).

---

### `tests/test_07_synthesis.py` (test) — analog `tests/test_05a_intake_classifier.py`

**Harness to mirror (verified `test_05a_intake_classifier.py:28-101`):**
- Stub `schedule`/`tweepy`/`resend`/`markdown` before `import agentpulse_processor` (`:28-38`).
- `os.environ.setdefault("OPENCLAW_DATA_DIR", ...)`; `sys.path.insert(0, .../docker/processor)` (`:40-43`).
- Prime `proc._model_config_cache` from repo `config/agentpulse-config.json` (`:48-49`).
- `_FakeResponse` class (`:65-75`) — Phase-7 version: `json()` returns the Anthropic shape
  `{"content": [{"type": "text", "text": "<json or tagged body>"}]}`.
- `_install_proxy_stub` (`:78-96`) — monkeypatch `proc._get_agent_api_key` + `proc.httpx.post`, capture
  `url`/`headers`/`body`; restore after (`:99-101`). Add a `proc.httpx.get` stub for the economy_map reads/INSERT path.

**Phase-7 assertions (from RESEARCH Test Map):**
- SYNT-04: captured `url` endswith `/anthropic/v1/messages`; `headers` carry the agent key; `body["model"] == "claude-sonnet-4-20250514"`; non-2xx ⇒ raises.
- SYNT-01/05: eligibility predicate (N/T, cold-start NULL watermark, no-draft guard).
- SYNT-03/D-09: assembly orders by `event_date` desc, caps at `max_input_entries`, logs + in-prompt note on omission.
- SYNT-05/D-11: `load_synth_identity()` returns None on missing/empty (tmp file).
- SYNT-06/D-12: maturity-enum validation raises on invalid/missing.
- D-13: INSERT hits `/block_body_versions` with `Content-Profile: economy_map`, `status` omitted, no `published`/`blocks.*` write.

Run: standalone `python3 tests/test_07_synthesis.py`; suite `python3 -m pytest tests/ -q`.

## Shared Patterns

### Proxy-routed LLM call (RivalScope constraint)
**Source:** `agentpulse_processor.py:2996-3013` (transport), `proxy.py:992-1227` (`/anthropic/v1/messages` route)
**Apply to:** the single synthesis Sonnet call. ALWAYS via `{LLM_PROXY_URL}/...`, never a direct provider SDK,
never `routed_llm_call` for Sonnet.

### economy_map access via PostgREST + profile headers
**Source:** reads `:600-660` / `:3043-3070`; write `:573-597`
**Apply to:** every economy_map read (blocks, draft-existence, entries, prior body) and the draft INSERT. Use
`Accept-Profile: economy_map` (reads) / `Content-Profile: economy_map` (writes); raise on non-2xx. NEVER supabase-py
`.schema()`/`.in_()` (silent failure — CLAUDE.md/PROJECT.md constraint).

### Fail-loud governance (MEMORY: fail_loud_governance)
**Source:** `classify_intake_poller:3255-3264` (missing key → abort run, not silent no-op)
**Apply to:** missing/empty identity (D-11 → skip cycle), invalid `proposed_maturity` (D-12 → skip block), over-cap
entries (D-09 → include cap + `logger.warning` + in-prompt note). Never silent default, never silent drop.

### Pipeline run logging
**Source:** `log_pipeline_start('classify_intake')` / `log_pipeline_end(run_id, 'completed'|'failed', totals)` (`:3252`, `:3293-3296`)
**Apply to:** the synthesis poller (`'synthesize_blocks'`).

### Structural immutability over app checks (MEMORY: structural_over_application)
**Source:** append-only trigger `033:177-211`
**Apply to:** rely on the trigger for pinned-column immutability; Phase 7's INSERT-only draft write avoids UPDATEs entirely.

## No Analog Found

None. Every primitive exists in-repo (Phase-5 intake artifacts + analyst mtime loader + test_05a harness).
The only deviation is a **correction**, not a gap: Sonnet routing uses `/anthropic/v1/messages` (the intake
transport retargeted), because `routed_llm_call`/`/v1/chat/completions` cannot reach Anthropic.

## Metadata

**Analog search scope:** `docker/processor/agentpulse_processor.py`, `docker/analyst/analyst_poller.py`,
`docker/newsletter/newsletter_poller.py` (voice ref), `docker/llm-proxy/proxy.py` (route ref), `tests/test_05a_intake_classifier.py`,
`config/agentpulse-config.json`, `supabase/migrations/033_economy_map_schema.sql`
**Files scanned:** 7 (all line refs verified against current source this session)
**Pattern extraction date:** 2026-05-31
