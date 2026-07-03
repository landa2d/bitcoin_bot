# Phase 26: Continuity & Exemplar Context - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 3 code surfaces (2 modified, 1 new test) + 1 non-code MCP mutation
**Analogs found:** 6 / 6 (every change has an in-repo analog; the loader has an exact behavioral twin)

## Orientation

This is a **purely-additive integration phase** in the newsletter service. The continuity machinery is already built and wired into consumers — it is **starved of data, not missing**. The single new function `load_edition_context(supabase, limit=3, exemplar_paras=8)` is a refined, in-service re-creation of a builder that **already exists in the processor** (`agentpulse_processor.py:5577-5631`). Most of this map is "copy the established shape, then apply the D-07/D-09/D-10/D-02 fail-loud refinements on top."

Line numbers below were re-verified against current source on 2026-06-22 (CONTEXT's cites had drifted slightly; corrected values are used here).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docker/newsletter/newsletter_poller.py` → new `load_edition_context()` | utility / loader | CRUD-read + transform | `docker/processor/agentpulse_processor.py:5577-5631` (existing `narrative_context` builder) | **exact** (behavioral twin) |
| `docker/newsletter/newsletter_poller.py` → `process_task` injection (~:2034) | controller / dispatch glue | request-response | budget injection `:2031-2034` + processor `input_data['narrative_context']=…` `:5615` | exact |
| `docker/newsletter/newsletter_poller.py` → `exemplars=` at both `generate_from_blocks` calls (`:2078`, `:2269`) | controller / call-site | request-response | the two call sites themselves (mirror the existing `model_voice=` kwarg) | exact |
| `docker/newsletter/newsletter_poller.py` → avoided-themes feed (new query + `input_data['avoided_themes']`) | utility / loader | CRUD-read | `newsletter_prepass_tracking` insert `:921-928` (same table) + loader select pattern | role-match |
| `docker/newsletter/block_pipeline.py` → Phase E "not scored" (`:410-411`, `:674`) | service | transform / LLM-eval | the function's own existing return dicts | exact (in-place edit) |
| `tests/test_26_*.py` (NEW) | test | — | `tests/test_19_smartquote.py` + `tests/conftest.py` | exact (most-recent newsletter unit test) |
| Backfill `data_snapshot.lead_theme` (D-12/D-13) | migration-ish data mutation | batch UPDATE | `apply_migration`/MCP `UPDATE` — **no code file** | n/a (orchestrator/operator-owned) |

---

## Pattern Assignments

### `load_edition_context(supabase, limit=3, exemplar_paras=8)` — NEW in `newsletter_poller.py` (utility, CRUD-read + transform)

**Primary analog:** `docker/processor/agentpulse_processor.py:5577-5631` — this is the **exact behavioral twin**. It already queries published editions with the loader's mandated query and builds `previous_editions` with the same key shape. The new loader is this code, moved into the newsletter service, with the D-07/D-09/D-10 fail-loud refinements applied and an `exemplars` block added. **Copy this query + dict-build verbatim, then apply the deltas listed under it.**

**The query + previous_editions build to copy** (`agentpulse_processor.py:5578-5598`):
```python
try:
    recent_editions = supabase.table('newsletters')\
        .select('edition_number, title, title_impact, primary_theme, content_markdown_impact, content_markdown')\
        .eq('status', 'published')\
        .order('edition_number', desc=True)\
        .limit(8)\
        .execute()
    previous_editions = []
    for i, ed in enumerate(recent_editions.data or []):
        title = ed.get('title_impact') or ed.get('title') or ''
        content = ed.get('content_markdown_impact') or ed.get('content_markdown') or ''
        previous_editions.append({
            'edition_number': ed.get('edition_number'),
            'title': title,
            'primary_theme': ed.get('primary_theme') or '',   # ← D-07 delta: read data_snapshot.lead_theme, not primary_theme
            'opening_excerpt': content[:300],                  # ← D-10 delta: strip leading `## Read This, Skip the Rest` first
            'weeks_ago': i + 1,                                # ← D-09 delta: real round((now-published_at)/7d); OMIT on null published_at
        })
    previous_editions.reverse()  # oldest first
except Exception as e:
    logger.warning(f"Narrative context assembly failed (non-critical): {e}")  # ← fail-loud-but-not-fatal pattern
```

**Deltas the loader must apply on top of the copied shape (from CONTEXT decisions):**
- **D-07/code_context line 98:** `primary_theme` ← `data_snapshot.lead_theme` when present, else `null` (never the title-derived fallback the *single-pass* writer uses at `:1563-1567`). Add `data_snapshot` to the `.select(...)` column list. `data_snapshot.primary_theme` is **always null** in the live DB — do not read it.
- **D-09:** `weeks_ago` ← `round((now − published_at) / 7 days)`. On null `published_at`, **omit the key entirely** for that edition (do NOT use the analog's `i + 1` edition-number-gap heuristic — that reintroduces cadence error). Add `published_at` to `.select(...)`.
- **D-10:** `opening_excerpt` = first ~300 chars of `content_markdown` **after stripping the leading `## Read This, Skip the Rest` header** (published bodies have no H1; the section label is not prose).
- **D-11:** `limit = 3` (not the analog's `8`). `previous_editions` is sourced from **all** published editions.
- **CTX-03 / spec §1 / D-16:** zero published editions → `logger.warning("continuity context empty")` and return the **explicit** `{'previous_editions': [], 'exemplars': [], 'empty': True}` — never a bare `{}`.

**Within-service Supabase select analog** (so the loader matches newsletter-service convention, not just the processor) — `docker/newsletter/block_selection.py:62-69`:
```python
result = sb.table('problems')\
    .select('id, description, category, source, max_source_tier, keywords, metadata, first_seen, source_post_ids')\
    .eq('metadata->>anchorable', 'true')\
    .gte('first_seen', window_start)\
    .order('first_seen', desc=True)\
    .limit(600)\
    .execute()
all_anchorable = result.data or []
```
Same backslash-continuation chain style, `.eq().order().limit().execute()`, `result.data or []` guard, wrapped in try/except with `logger.error`.

**ANTI-PATTERN — do NOT copy** `newsletter_poller.py:1790-1796` (`generate_scorecard`). It uses `.in_("status", [...])` — the **known silent-failure bug** (CONTEXT D-14, MEMORY economy_map note). The loader and the avoided-themes feed must use plain `.eq('status','published')` only.

**Exemplar paragraph extraction (`exemplars`)** — D-05/D-06. No dedicated paragraph-splitter exists in the service; build one reusing established idioms rather than reinventing:
- **Word-count idiom** (the service's universal pattern) — `newsletter_poller.py:640` `word_count = len(content_md.split())` and `verification.py:181` `len(candidate.split()) > 3`. Use `len(para.split()) >= 40` for the ≥40-word filter.
- **Header / list exclusion** — reuse the header-detection regexes from `verification.py:96-97`:
  ```python
  _SECTION_HEADER = re.compile(r'^#+\s+.*$', re.MULTILINE)      # ## / ### headers
  _BOLD_HEADER    = re.compile(r'^\*\*[^*]+\*\*\s*$', re.MULTILINE)  # bold-on-own-line headers
  ```
  A paragraph is a header if it matches these; a list item starts with `-`, `*`, `+`, or `\d.`. Exclude both. (`re` is already imported at `newsletter_poller.py:12`.)
- **Splitting heuristic (Claude's Discretion, D-05 note):** blank-line split (`re.split(r'\n\s*\n', md)`) is the simplest fit and matches how the service assembles markdown (`block_pipeline.py:648-661` joins sections with `"\n\n"`). Select qualifying paragraphs in **document order, front-loaded** (D-05), cap at `exemplar_paras=8` (D-06), drawn from the **2 most-recent operator-written editions, expanding to a 3rd only to reach the cap**.
- **D-01/D-02/D-03 provenance:** exemplar pool is restricted to editions where `data_snapshot.operator_written == 'true'` (string in live DB — see code_context line 97). Edition 29 (`pipeline_version='block_v1'`) is excluded. Empty operator pool → return an **explicit, distinguishable "not scored" marker** (Claude's Discretion: boolean flag / sentinel / status enum), NOT a bare `exemplars:[]` and NOT a silent fallback to any-published. This is distinct from CTX-03's whole-corpus-empty (`empty:True`).

---

### `process_task` injection point — `newsletter_poller.py` (~:2034, controller, request-response)

**Analog (immediately-preceding established injection):** `newsletter_poller.py:2031-2034`:
```python
# Inject budget constraints
budget = get_budget_config(AGENT_NAME, task_type)
input_data["budget"] = budget
logger.info(f"Budget for {task_type}: {budget}")
```

**Analog (the assignment shape, cross-service):** `agentpulse_processor.py:2031-2034` sets it directly, but per CONTEXT D-injection the loader must use `setdefault` so an upstream-provided context wins (CTX-04):
```python
# Inject narrative context (continuity + exemplars) — covers both writer paths and the prepass
ctx = load_edition_context(supabase)
input_data.setdefault('narrative_context', ctx)
```
**Placement:** after budget injection (`:2034`) and **before** the block/single-pass branch at `:2046` (`if _use_block_pipeline:`). Both writer paths read `input_data.get('narrative_context')` (single-pass `:1149`, A/B prepass via `:2253`), so this single `setdefault` covers all consumers. `supabase` is a module-level global (used throughout, e.g. `:873`, `:921`).

**Avoided-themes feed (D-14, same injection region):** before the branch, query the last 3 `newsletter_prepass_tracking.chosen_angle` rows and `input_data.setdefault('avoided_themes', [...])`. Table/column analog is the existing insert at `newsletter_poller.py:921-928`:
```python
supabase.table('newsletter_prepass_tracking').insert({
    'edition_number': edition,
    'chosen_angle': angle,
    ...
}).execute()
```
Read side mirrors the loader's select: `.select('chosen_angle').order('created_at', desc=True).limit(3).execute()` (plain `.eq()`/ordered — **no `.in_()`**, D-14). Both prepass consumers already accept it unfed: `editorial_prepass` reads `input_data.get('avoided_themes', [])` at `newsletter_poller.py:970`; `editorial_prepass_from_blocks` accepts `avoided_themes` at `block_pipeline.py:473` and is called with `avoided_themes=input_data.get('avoided_themes', [])` at `:2064` and `:2254`.

---

### `exemplars=` pass-through at BOTH `generate_from_blocks` call sites — `newsletter_poller.py` (controller, request-response)

`generate_from_blocks` already declares `exemplars: list[str] | None = None` (`block_pipeline.py:567`) but **no caller passes it** — that is the entire CTX-05 fix.

**Call site 1 (primary block path, `:2078-2085`)** — runs only when `block_pipeline.enabled=true`:
```python
bp_result = generate_from_blocks(
    blocks_data,
    angle=block_angle,
    llm_client=prose_client,
    model_structure=_bp_config.get('model_structure', 'deepseek-chat'),
    model_prose=prose_model,
    model_voice=_bp_config.get('model_voice', 'deepseek-chat'),
)
```

**Call site 2 (A/B comparison path, `:2269-2276`)** — runs when `enabled=false AND ab_comparison=true` (**the live config** — confirmed `config/agentpulse-config.json:128-133`: `enabled:false`, `ab_comparison:true`, `model_voice:"deepseek-chat"`). Identical shape. **This is the site that makes the D-17 live Phase E verification work without flipping `enabled`.**

**Add to BOTH** (mirroring the existing kwarg style — pull from the injected context):
```python
    exemplars=(input_data.get('narrative_context') or {}).get('exemplars'),
```
Pass it through whatever the loader's "not scored" marker is (D-02/D-04) so Phase E can distinguish the three states.

---

### Phase E "not scored" resurrection — `block_pipeline.py` (service, transform)

**Two sites return a silent `score:0` today; both must become a "not scored" verdict (D-04, closes CTX-05 silent-zero gap):**

`phase_e_voice_check` empty-exemplar guard (`block_pipeline.py:410-411`):
```python
if not exemplars:
    return {"score": 0, "observations": ["No exemplars provided — voice check skipped"]}
```

`generate_from_blocks` default before the `if exemplars:` gate (`block_pipeline.py:674-678`):
```python
voice_result = {"score": 0, "observations": ["Skipped — no exemplars"]}
if exemplars:
    voice_result = phase_e_voice_check(md_tech, exemplars, llm_client, model=model_voice)
    logger.info(f"[BLOCK PIPELINE] Phase E: voice score = {voice_result.get('score', 0)}")
```

**Edit:** replace `{"score": 0, ...}` with an unambiguous "not scored" result (e.g. `{"score": None, "status": "not_scored", "observations": [...]}` — exact marker is Claude's Discretion, must differ from a real `score:0`). Leave the `except` branch at `:432` (`Voice check failed: {e}`) as-is — that is a genuine error, distinct from "no exemplars". With 7 operator editions present today, the `if exemplars:` branch fires and returns a **real** DeepSeek score (Phase E `model_voice` defaults to `deepseek-chat`, `:570` / config `:133` — independent of the Phase-29 Sonnet judge). The score lands in the A/B row's `data_snapshot.voice_score` already wired at `newsletter_poller.py:2329`.

---

### `tests/test_26_*.py` — NEW (test)

**Analog:** `tests/test_19_smartquote.py` (Jun 10, most-recent newsletter unit test) + `tests/conftest.py`.

**Module-load pattern to copy** (`test_19_smartquote.py:32-39`) — imports the REAL production function via the conftest-preloaded module (never reimplement the transform — "a copy could pass while production regresses", per the test's own docstring):
```python
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))
import newsletter_poller as nl  # the REAL module (conftest preloads it w/ correct schemas)
loader = nl.load_edition_context
```
`conftest.py:32-65` (`_preload_poller`) already registers `newsletter_poller` in `sys.modules` with the right `schemas` — no extra wiring needed.

**Supabase fixture:** the loader takes `supabase` as a parameter (not the module global), so tests pass a stub exposing the chain `.table().select().eq().order().limit().execute()` returning an object with a `.data` list. This is why the loader signature accepts `supabase` explicitly — it makes the degrade paths (D-16) testable with fixtures without a live DB.

**D-16 required cases (all fixture-driven):** (1) correct return shape; (2) `operator_written` filtering excludes edition 29 / pipeline rows; (3) ≥40-word + non-header/non-list paragraph filtering; (4) **CTX-03 whole-corpus-empty** → `{previous_editions:[], exemplars:[], empty:True}` + WARNING + generation still completes; (5) **empty-operator-pool "not scored"** path (D-02/D-03) distinct from corpus-empty. Use `pytest.mark.parametrize` (test_19 style) and `caplog` to assert the WARNING line.

---

### Data-hygiene backfill (D-12/D-13) — NOT a code file

Backfill `data_snapshot.lead_theme` on editions **25, 26, 27, 28** (30–32 already have it) and verify `published_at` non-null on all 7 operator-written editions. `lead_theme` is **operator-authored editorial copy** → derive a candidate from each edition's opening thesis, present for **operator confirmation**, then apply via Supabase MCP `UPDATE`.

**This is a live-data mutation → worktree-unsafe, orchestrator/operator-owned on the main tree** (MEMORY: "Scoped rebuild → worktree-unsafe"; "Executor edits STATE directly"). It is a small data mutation, **not a migration** — do not add a file under `supabase/migrations/`. No analog file; the planner should route this through the orchestrator's MCP step, not an executor edit.

---

## Shared Patterns

### Fail-loud-but-not-fatal (the milestone spine, applied everywhere here)
**Source:** `agentpulse_processor.py:5630-5631`, `newsletter_poller.py:930-931`
```python
except Exception as e:
    logger.warning(f"... failed (non-critical): {e}")
```
**Apply to:** the loader (degraded corpus warns + returns explicit empty marker, never aborts generation), the avoided-themes feed, and the Phase E branch. **Contrast with the "not scored" marker (D-02/D-04):** missing-input must surface a *distinguishable* state, never a silent `score:0` or silent substitution. ("NULL ≠ intent / no silent zero" — CONTEXT specifics, MEMORY fail-loud governance.)

### Supabase select convention
**Source:** `block_selection.py:62-69` (in-service), `agentpulse_processor.py:5579-5584` (exact query)
**Apply to:** loader + avoided-themes feed.
- Backslash-continuation `.table().select().eq().order().limit().execute()` chain
- `.eq('status','published')` only — **never `.in_()`** (silent-failure bug; anti-pattern at `newsletter_poller.py:1792`)
- `result.data or []` guard
- module-level global `supabase` (loader takes it as a param for testability)

### Logging
**Source:** logger name `"agentpulse"` (processor) / module logger `logging.getLogger('block_pipeline')` (`block_pipeline.py:23`). newsletter_poller uses a module-level `logger`.
**Apply to:** loader uses `logger.info` on success (echo the processor's `f"Narrative context: {len(previous_editions)} edition(s)…"` at `:5629`) and `logger.warning("continuity context empty")` on the degrade path (spec §1 verbatim string for the D-17/acceptance-criterion-4 grep).

### narrative_context dict contract (consumers read these exact keys — Claude's Discretion is bounded by them)
**Source:** consumed at `newsletter_poller.py:1151-1159` (single-pass writer), `:1353-1365` (editor pass), `:944-956` (`editorial_prepass`), `block_pipeline.py:508-516` (block prepass).
Required keys the loader MUST emit: `previous_editions[]` each with `{edition_number, title, primary_theme, opening_excerpt, weeks_ago}`, plus top-level `exemplars` and `empty`. Optional `recent_spotlights` is read at `:1152` — loader may omit (defaults to `[]` via `.get`).

---

## No Analog Found

None. Every change has an in-repo analog; the loader's behavioral twin already exists in the processor.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All surfaces covered. |

## Metadata

**Analog search scope:** `docker/newsletter/` (all 4 .py), `docker/processor/agentpulse_processor.py` (narrative_context builder, selects), `tests/` (newsletter unit tests + conftest), `config/agentpulse-config.json` (block_pipeline flags).
**Files scanned:** 9
**Line numbers re-verified:** 2026-06-22 (loader twin `processor:5577-5631`; single-pass continuity `:1148-1182`; injection `:2031-2046`; call sites `:2078`, `:2269`; prepass `block_pipeline.py:470-524`; Phase E `:404-432`, `:674-678`; `generate_from_blocks` sig `:563-571`).
**Pattern extraction date:** 2026-06-22
