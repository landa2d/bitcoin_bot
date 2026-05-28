# Phase 5: Intake Classifier + `unsorted` Handling - Pattern Map

**Mapped:** 2026-05-28
**Files analyzed:** 3 (1 primary code file modified, 1 config modified, 1 test created)
**Analogs found:** 6 strong / 7 needed (1 partial — no in-tree Python `economy_map` write)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docker/processor/agentpulse_processor.py` (new poller fn + new prompt const + new `economy_map` write helper + schedule registration) | service / scheduler | batch + request-response (LLM classify) + DB write | `surface_x_content_candidates()` @ 6969; `extract_problems_multisource()` @ 2838; `MULTISOURCE_EXTRACTION_PROMPT` @ 1536; `routed_llm_call()` @ 506 | exact (poller, LLM, prompt) / **partial** (no Python `economy_map` write analog) |
| `config/agentpulse-config.json` (add confidence floor) | config | n/a | `pipelines.opportunity_finder.cluster_similarity_threshold` @ config:72 | exact |
| `tests/test_05*.py` (append-only proof + below-floor routing) | test | n/a | `tests/test_phase2_integration.py`; `tests/test_migrations.py` | role-match |

---

## Pattern Assignments

### `docker/processor/agentpulse_processor.py` — new classifier poller (service, batch + LLM + DB-write)

This phase adds, all inside the existing monolith:
1. A module-level prompt constant (classifier).
2. A poller function (read finalized editions → per tier-1 event classify → route → INSERT).
3. A scheduled wrapper + a `schedule.every(...)` registration line.
4. A new `economy_map` PostgREST write helper (no existing Python analog — see "No Analog Found").

#### 4a. LLM dispatcher — use `routed_llm_call()` (lines 506-533)

This is THE in-tree LLM call pattern for the processor. Mirror it; do NOT add a direct DeepSeek SDK call.

```python
def routed_llm_call(model, messages, temperature=0.3, max_tokens=4000, **kwargs):
    """Route LLM call to correct provider with DeepSeek→OpenAI fallback."""
    provider = get_provider(model)
    actual_model = model
    # If DeepSeek requested but unavailable, fall back to OpenAI
    if provider == "deepseek" and (not deepseek_client or not _is_deepseek_available()):
        actual_model = "gpt-4o-mini"; provider = "openai"
        logger.info(f"Routing {model} → {actual_model} (circuit breaker or no client)")
    client = deepseek_client if provider == "deepseek" else openai_client
    try:
        return client.chat.completions.create(model=actual_model, messages=messages,
            temperature=temperature, max_tokens=max_tokens, **kwargs)
    except Exception as e:
        if provider == "deepseek":
            _record_deepseek_failure()
            return openai_client.chat.completions.create(model="gpt-4o-mini", messages=messages,
                temperature=temperature, max_tokens=max_tokens, **kwargs)
        raise
```

Pick the model with `get_model('extraction')` (resolves to `deepseek-chat`, line 462-465). Usage exactly as in `extract_problems_multisource` @ 2864 and `surface_x_content_candidates` @ 2076-2080.

> **Proxy-routing caveat for the planner (load-bearing):** The CONTEXT/ROADMAP say "route through `llm-proxy:8200` (no direct DeepSeek SDK call)". BUT `routed_llm_call()` calls the OpenAI/DeepSeek SDK clients **directly** (`init_clients()` @ 412-432; clients built with provider `base_url`, NOT the proxy). The proxy URL (`LLM_PROXY_URL`, line 65 = `http://llm-proxy:8200`) is used in the processor ONLY for wallet summary (line 6032-6036). So ROADMAP criterion 2 ("verified by an llm-proxy log line") is NOT satisfiable by the current `routed_llm_call`. **Decision for planner:** either (a) accept `routed_llm_call` as the project's dispatcher convention (the established in-tree pattern, satisfies CONTEXT's "follow `MULTISOURCE_EXTRACTION_PROMPT` pattern"), and reconcile the proxy criterion as already-handled by the dispatcher abstraction; or (b) build the classifier call against `LLM_PROXY_URL` with an `httpx`/OpenAI-base_url-to-proxy client to literally produce a proxy log line. Flag this to the operator — it is a genuine inconsistency between the established code and the ROADMAP wording.

#### 4b. DeepSeek circuit breaker — drives the "error → unsorted, NULL confidence" path (D-05)

Lines 477-503. Check `_is_deepseek_available()` is already done **inside** `routed_llm_call`; you do not call it yourself. What you DO mirror for D-05: wrap the classify call in try/except, and on ANY exception (or on a parsed result you can't trust), route the event to `'unsorted'` with `tag_confidence = NULL` instead of dropping it.

```python
_deepseek_failures: list = []
_circuit_open_until: float = 0.0

def _is_deepseek_available() -> bool:
    global _circuit_open_until
    now = time.time()
    if now < _circuit_open_until:
        return False
    cutoff = now - 600
    while _deepseek_failures and _deepseek_failures[0] < cutoff:
        _deepseek_failures.pop(0)
    return len(_deepseek_failures) < 5

def _record_deepseek_failure():
    global _circuit_open_until
    _deepseek_failures.append(time.time())
    # ... opens circuit at >=5 failures in 10-min window for 5 min
```

D-05 implementation shape (per event):
```python
try:
    resp = routed_llm_call(get_model('extraction'), messages, temperature=0.2, max_tokens=400)
    parsed = json.loads(_clean_json_response(resp.choices[0].message.content))
    slug = parsed.get('block_slug'); conf = float(parsed.get('tag_confidence'))
    target_slug = slug if conf >= floor and slug in ALLOWED_SLUGS else 'unsorted'
    confidence = conf  # recorded even when below floor (D-05 flagged-not-dropped)
except Exception as e:
    logger.error(f"[INTAKE] classify failed for event: {e}")
    target_slug = 'unsorted'; confidence = None  # NULL — never lost (D-05)
```

#### 4c. Module-level prompt constant + JSON-parse-with-fence-strip (mirror `MULTISOURCE_EXTRACTION_PROMPT`)

Prompt constant pattern: `MULTISOURCE_EXTRACTION_PROMPT` @ 1536-1625 — module-level triple-quoted string, `{posts}` placeholder filled via `.format()`, paired with a `*_SYSTEM_MSG` constant. The classifier prompt should be a sibling constant (e.g. `INTAKE_CLASSIFIER_PROMPT`) outputting **only** `block_slug` + `tag_confidence` per D-04 (no prose generation).

JSON parse helper `_clean_json_response()` @ 2829-2835:
```python
def _clean_json_response(text: str) -> str:
    """Strip markdown code fences from LLM JSON output."""
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
    return text.strip()
```
Used as `json.loads(_clean_json_response(response.choices[0].message.content))` @ 2879. A more aggressive regex-fence variant exists @ 7083-7087 (`re.sub(r'^```\w*\n?', ...)`) — use either; the simple one is the dominant convention.

The **allowed label set** (Claude's discretion item) is the seven seeded slugs (from migration 033 §13, lines 406-414):
`identity-trust`, `memory-context`, `payments-settlement`, `autonomy-control`, `governance-accountability`, `psychology-disposition`, `regulation-legal`. Fetch them live via the `economy_map.blocks` read (see No-Analog helper) OR hard-list with a fallback; live fetch is preferred per CONTEXT discretion note.

#### 4d. End-to-end poller shape — closest analog `surface_x_content_candidates()` (lines 6969-7133)

This is the best structural template: a function that (1) guards `if not supabase`, (2) reads source rows from a table, (3) builds an LLM prompt, (4) calls `routed_llm_call`, (5) parses JSON, (6) loops over results, (7) does an existence/validity gate, (8) `.insert()`s rows, (9) wraps each source-block in try/except and continues. Key excerpts:

Read source (lines 7000-7005):
```python
recent_posts = supabase.table('source_posts')\
    .select('title, source_url, source, body')\
    .gte('scraped_at', day_ago).order('scraped_at', desc=True).limit(20).execute()
```
Call + parse (lines 7076-7087): `routed_llm_call(model, [...], temperature=0.4, max_tokens=2000)` then fence-strip + `json.loads`.
Per-item validity gate + insert (lines 7092-7133): skip-if-invalid, build `insert_data` dict, `supabase.table('...').insert(insert_data).execute()`, `+= 1`.

`extract_problems_multisource()` (lines 2838-2946) is the secondary analog — it shows the `run_id = log_pipeline_start(...)` / `log_pipeline_end(run_id, 'completed', result)` wrapping and the `log_llm_call(...)` cost-logging line @ 2877 that the new poller should also emit.

#### 4e. Schedule registration (lines 9748-9811, inside `setup_scheduler()`)

```python
def setup_scheduler():
    ...
    schedule.every(6).hours.do(scheduled_scrape_rss)
    ...
    schedule.every().monday.at("11:00").do(scheduled_auto_publish_newsletter)  # finalizes editions
    ...
```
Add one line, e.g. `schedule.every(30).minutes.do(scheduled_classify_intake)` (interval is Claude's discretion, D-77). Scheduled-wrapper convention (the thin try/except wrapper that the `.do()` points at) — `scheduled_surface_x_candidates()` @ 9353-9362:
```python
def scheduled_surface_x_candidates():
    try:
        result = surface_x_content_candidates()
        logger.info(f"X candidate surfacing: {result}")
    except Exception as e:
        logger.error(f"X candidate surfacing failed: {e}")
```
Place the registration near the newsletter/publish lines (9774-9777) so it reads as part of the newsletter→intake flow.

#### 4f. Read side — finalized editions + tier-1 events (D-02, D-03, D-04)

**Finalized status (D-02 — CONFIRMED):** `public.newsletters.status == 'published'`. Set by `publish_newsletter()` @ 4370-4374 (`{'status': 'published', 'published_at': now}`). The lifecycle is `draft`/`pending`/`preview` → `published` (see the unpublished filter @ 4331: `.in_('status', ['draft','pending','preview'])`). `'held'` is a separate blocking status (A/B comparison rows @ 2182, and held editions) and must be excluded — `'published'` is the only finalized value. **Poller read filter:** `.eq('status', 'published')` (matches the existing convention @ 3344, 3367, 3392, 4045).

**Edition id for `source_edition_id` (INTK-04, D-08):** use the newsletter row's `id` (UUID, stringified into the TEXT column) — that is the join key in ROADMAP criterion 4. `edition_number` is also present but `id` is the stable PK.

**Tier-1 events + field mapping (D-03/D-04 — see "Open Items" below for the important nuance):** The published newsletter row stores `data_snapshot` (JSONB) = `{**input_data, **result.data_snapshot}` (save @ newsletter_poller.py:1475). `input_data` is built in `prepare_newsletter_data()` @ processor 3972-4011. The tier-1 events live in `data_snapshot['premium_source_posts']`, each shaped (built @ 3961-3969):
```python
{'source': src, 'source_display': display_name,
 'tier': p.get('source_tier'),          # tier-1 events = tier == 1  (D-03)
 'tier_label': tier_label,
 'title': p.get('title', ''),
 'summary': (p.get('body') or '')[:300],
 'url': p.get('source_url', '')}
```
**Field mapping for the four timeline prose fields (D-04):**
| timeline column | source field | note |
|---|---|---|
| `what_shifted` (NOT NULL) | `title` | the event headline |
| `why_it_mattered` (NOT NULL) | `summary` (`body[:300]`) | the extracted/verified summary |
| `source_url` (nullable) | `url` | already-resolved source URL |
| `event_date` (NOT NULL DATE) | **NOT on the event** → use the edition's `published_at`/`created_at` date | see Open Items D-04 |

> Tier-1 filter against `premium_source_posts` is `tier == 1`. Note `block_selection.py`'s `max_source_tier == 1` (line 106) applies to the **block pipeline** event objects, which are NOT persisted in the published row's `data_snapshot` (only `block_summary` metadata is, @ newsletter_poller.py:2183-2190). So the planner's reliable read surface is `premium_source_posts` (`tier`), not the block objects (`max_source_tier`). See Open Items.

#### 4g. Idempotency — pre-emit existence check on `source_edition_id` (D-08)

Mirror the dedup convention @ 884-886:
```python
existing = supabase.table('moltbook_posts').select('id').eq('moltbook_id', moltbook_id).execute()
if existing.data:
    # skip — already emitted
```
For Phase 5 this is a `SELECT id FROM economy_map.timeline_entries WHERE source_edition_id = <id> LIMIT 1` via the PostgREST helper (below) — skip the whole edition if any row already carries that `source_edition_id`.

---

### `config/agentpulse-config.json` — confidence floor (config, D-06)

**Analog:** the nested-section threshold pattern, e.g. `pipelines.opportunity_finder.cluster_similarity_threshold` (config:72) and `spotlight_selection.min_score_threshold` (config:95).
**Read pattern (in processor):** `get_full_config()` @ 542-560 returns the whole JSON cached; read a nested value like `get_full_config().get("intake_classifier", {}).get("confidence_floor", 0.6)`. (`get_provider` @ 470 demonstrates the `.get(...).get(...)` chained-default idiom against `get_full_config()`.)
**Add** a new top-level section, e.g.:
```json
"intake_classifier": { "enabled": true, "confidence_floor": 0.6 }
```
Default 0.6 matches ROADMAP criterion 3.

---

### `tests/test_05*.py` — append-only proof + below-floor routing (test)

**Analog:** `tests/test_phase2_integration.py` (lines 1-90) for the `sys.path.insert` + `import agentpulse_processor as proc` + `proc.init_clients()` live-Supabase harness; `tests/test_migrations.py` (lines 19-35) for migration-text assertions.

- **Criterion 5 (append-only):** INSERT a `timeline_entries` row via the service_role PostgREST helper, then attempt an UPDATE of `what_shifted` and a DELETE — both must raise (the migration-033 trigger @ 213-253 raises `'timeline_entries is append-only ...'`). Assert the PostgREST call returns a 4xx / the supabase client raises.
- **Criterion 3 (below-floor routing):** feed a deliberately-ambiguous event; assert the resulting row has `block_slug == 'unsorted'` and a recorded `tag_confidence`.
- **D-05 (error path):** simulate classify failure; assert `block_slug == 'unsorted'` and `tag_confidence IS NULL`.
- Test-class style: `class TestX:` with `def test_*` methods (per CLAUDE.md conventions) or flat `def test_*()`.

---

## Shared Patterns

### LLM classification call
**Source:** `routed_llm_call()` @ processor:506-533 + `get_model('extraction')` @ 462-465
**Apply to:** the classifier call. Wrap in try/except for D-05.

### JSON output parsing
**Source:** `_clean_json_response()` @ processor:2829-2835 (or regex variant @ 7083-7087)
**Apply to:** parsing the classifier's `{block_slug, tag_confidence}` JSON.

### Cost / pipeline logging
**Source:** `log_pipeline_start()`/`log_pipeline_end()` (@ 2843/2944) and `log_llm_call("processor", "<task>", resp.model, resp.usage, elapsed_ms)` @ 2877
**Apply to:** the new poller (wrap the run; log each classify call's cost).

### Error handling
**Source:** broad `try/except Exception as e: logger.error(...)` around each per-item loop body and around the whole poller — convention throughout (e.g. 7135-7136, 9359-9362). 223 such clauses in the processor (per CLAUDE.md).
**Apply to:** per-event loop (continue on failure → but for D-05 the "failure" still emits an `'unsorted'` NULL-confidence row, it does NOT silently skip).

### Logger
**Source:** module-level `logger` named `"agentpulse"`; `logger.info` for progress, `logger.error` (with `exc_info=True` where useful) for failures.

---

## No Analog Found

| File / Concern | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `economy_map.timeline_entries` INSERT/SELECT from Python | service | DB write/read across non-`public` schema | **No in-tree Python `economy_map` (or `eu_ai_act`) write/read exists.** `app.js` uses JS `sb.schema('economy_map')` (app.js:373-459, 592, 700) — JS only. `code_session.py` has a generic PostgREST helper (`supabase_headers()` @ 87-94, `db_insert()` @ 159-178) but it does NOT set the schema-profile header and targets `public`. supabase-py `.schema()` is used **nowhere** in Python. The `eu_ai_act` precedent named in PROJECT.md exists only as a comment in migration 033 — no code. |

**Planner must build (no copy source):** a small `economy_map` PostgREST helper in the processor using the in-tree `httpx` client (the processor imports `httpx` @ 27; uses `httpx.get(...)` @ 6032) and `SUPABASE_SERVICE_KEY` (env read @ processor:60). Required headers, per PROJECT.md constraints (lines 99, 57) and migration 033 §2 comment (lines 21-22):
- **Write (INSERT):** `POST {SUPABASE_URL}/rest/v1/timeline_entries` with headers `apikey`, `Authorization: Bearer <SERVICE_KEY>`, `Content-Type: application/json`, `Prefer: return=representation`, **`Content-Profile: economy_map`**.
- **Read (existence check / blocks fetch):** `GET {SUPABASE_URL}/rest/v1/timeline_entries?source_edition_id=eq.<id>&limit=1` (and `/blocks?select=slug`) with **`Accept-Profile: economy_map`**.
- Reason `Content-Profile`/`Accept-Profile` (not the `.schema()` method): supabase-py `.in_()` silently fails on the isolated schema (PROJECT.md:91, 99) — direct PostgREST is mandated. service_role bypasses RLS by design (migration 033 §11, lines 347-349), so the service key write reaches the table; the append-only trigger (not RLS) still binds it.

The closest *shape* to copy for the helper body is `code_session.py:supabase_headers()`/`db_insert()` (extend with the profile header) combined with the processor's `httpx.get(...)` call style @ 6032-6036.

---

## Open Items from CONTEXT.md — Resolved

### D-02 — finalized newsletter status (CONFIRMED)
`public.newsletters.status == 'published'` is the single finalized value (set by `publish_newsletter()` @ processor:4370-4374, with `published_at` timestamp). Drafts (`draft`/`pending`/`preview`) and `'held'` (A/B + held editions) are excluded. Poller filter: `.eq('status', 'published')`. Column name confirmed: `status` on `public.newsletters`.

### D-04 — event → timeline field mapping (CONFIRMED, with one caveat)
From `data_snapshot['premium_source_posts']` (shape @ processor:3961-3969):
- `what_shifted` ← `title`
- `why_it_mattered` ← `summary` (= source `body[:300]`)
- `source_url` ← `url`
- `event_date` ← **caveat:** `premium_source_posts` does **NOT** carry a date field (`scraped_at`/`first_seen` is dropped when the dict is built @ 3961-3969). `event_date` is `DATE NOT NULL` (migration 033:151). **Planner must derive `event_date`** from the edition itself — use the newsletter row's `published_at` (or `created_at`) date. This is sound: the timeline display contract is `<event_date> · <what_shifted> / <why_it_mattered> [source ↗]`, and the edition's publish date is the correct "when this entered the map" anchor.

### D-03 — tier-1 identification (CONFIRMED, with surface caveat)
Tier-1 = `tier == 1` on `premium_source_posts` (built from `source_posts.source_tier == 1`, fetched @ processor:3904-3906 `.in_('source_tier', [1, 2])`). The `max_source_tier == 1` reference in CONTEXT (`block_selection.py:106`) is for the **block-pipeline** event objects, which are NOT persisted in the published `data_snapshot` (only `block_summary` metadata is, @ newsletter_poller.py:2183-2190; the A/B row is also `status='held'`, not `'published'`). **The reliable Phase-5 read surface is `data_snapshot['premium_source_posts']` filtered on `tier == 1`** — not the block objects. Planner: confirm whether the operator wants events from `premium_source_posts` (tier-1 RSS/authority posts) as the classification unit; this is the only tier-1 event list that survives into a published newsletter row.

---

## Metadata

**Analog search scope:** `docker/processor/agentpulse_processor.py`, `docker/newsletter/newsletter_poller.py`, `docker/newsletter/block_selection.py`, `docker/newsletter/block_pipeline.py`, `docker/gato_brain/code_session.py`, `docker/web/site/app.js`, `supabase/migrations/033_economy_map_schema.sql`, `config/agentpulse-config.json`, `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `tests/`.
**Files scanned:** 11
**Pattern extraction date:** 2026-05-28
