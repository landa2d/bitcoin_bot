# Phase 30: Sequencer Wiring, Hold Action & Activation Gate - Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 4 (2 modified with real work + 1 new migration + 1 config confirm-only)
**Analogs found:** 4 / 4 (all in-tree, mostly self-analogs — this is a wiring phase, so the closest pattern is the code already at the two save points)

> **Phase shape:** Wiring only. No new eval logic. The three eval modules
> (`deterministic_gate.py`, `judge_loop.py`, `edition_eval.py`) are ALREADY BUILT and
> MUST NOT be modified — Phase 30 only *sequences* them into the poller and acts on the
> returned verdict. Their call contracts are mapped below under "Module Call Contracts (do
> NOT modify)".

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docker/newsletter/newsletter_poller.py` (MODIFY) | service / sequencer | event-driven → transform (gate+judge over in-memory fact base) | **the existing Phase-D block inside `save_newsletter` itself** (`:1726-1793`) + block A/B insert (`:2643-2701`) | exact (self-analog) |
| `docker/processor/agentpulse_processor.py` (MODIFY) | service / publish-gate | request-response + CRUD (select draft → gate → UPDATE status) | the existing draft select in `publish_newsletter` (`:5865-5870`) + `scheduled_auto_publish_newsletter` (`:10636-10641`) | exact (self-analog) |
| `supabase/migrations/046_do_not_publish_columns.sql` (CREATE) | migration | schema / DDL (ADD COLUMN on `newsletters`) | `supabase/migrations/020_newsletter_verification.sql` (ADD COLUMN on `newsletters`) + `045` header house-style | exact |
| `config/agentpulse-config.json` → `edition_eval` (CONFIRM-only) | config | config-read | block read at `newsletter_poller.py:2396-2400` | exact — block already exists, ship as-is (`enabled=false`) |

---

## Pattern Assignments

### `docker/newsletter/newsletter_poller.py` — the sequencer (service, event-driven → transform)

The single most important fact: **the closest analog for the Layer-1 gate + judge invocation is the code already sitting where the gate goes.** The existing Phase-D verification block in `save_newsletter` (`:1726-1793`) already (a) selects the correct fact base by branch, (b) runs the check over BOTH body versions, and (c) writes results back to the row in a logs-and-continue try/except. Phase 30 inserts the gate/judge call in the same spot with the same fact-base branch, then adds the verdict→status action the Phase-D block deliberately does NOT do (flag-not-block).

**Analog A — fact-base selection + dual-version check** (`:1727-1757`, the pattern to copy for `run_deterministic_gate`'s `fact_base` arg and `run_layer2`'s draft/fact_base):
```python
try:
    from verification import verify_draft
    tech_prose = content_markdown
    impact_prose = content_markdown_impact or ""

    # Block pipeline path: pass blocks directly (Option B). Single-pass: input_data.
    if blocks_data and blocks_data.get('blocks'):
        verification_input = {
            'blocks': blocks_data['blocks'],
            'tracked_entity_signals': blocks_data.get('tracked_entity_signals', []),
            'trending_tools': blocks_data.get('tool_stats', []),
            'predictions': blocks_data.get('predictions', []),
        }
        fact_base_source = 'blocks'
    else:
        verification_input = input_data
        fact_base_source = 'input_data'

    tech_report = verify_draft(tech_prose, verification_input) if tech_prose else None
    impact_report = verify_draft(impact_prose, verification_input) if impact_prose else None
```
> **Copy this branch verbatim to build the `fact_base` dict handed to `run_deterministic_gate` /
> `run_layer2`.** Both modules TRUST the handed dict (GATE-08 / D-08) and re-derive the label
> internally (`deterministic_gate.py:145` — `"blocks" if fact_base.get("blocks") else "input_data"`).
> The draft dict is `{title, title_impact, content_markdown, content_markdown_impact, pipeline_version}`.

**Analog B — logs-and-continue write-back wrapper** (`:1727` + `:1792-1793`) — the shell the fail-open eval wrapper (D-06) copies:
```python
try:
    # ... verification ...
    if row_id:
        supabase.table("newsletters").update({
            "verification_warnings": verification
        }).eq("id", row_id).execute()
except Exception as e:
    logger.error(f"[VERIFICATION] Failed for edition #{edition}: {e}")
```
> **Landmine (D-06 vs D-07):** copy the try/except-continue SHAPE, but the current block is
> fail-SILENT (logger.error only). D-07 requires the eval *outage* also alert the operator
> (fail-open-but-LOUD). Enrich the except: write the `eval_status='error'` row via
> `write_eval_row(...)` AND emit an operator alert. Never a bare swallow.

**Analog C — where the primary `newsletter_id` is captured** (`:1720-1721`): `save_newsletter` already binds `row_id = insert_result.data[0]['id']`. This is the id the status flip / `do_not_publish` UPDATE targets (D-13 — only the primary/single-pass draft). `save_newsletter` currently returns it (`:1812`) but the caller at `:2595` discards the return — **capture it** (`primary_id = save_newsletter(...)`) to thread the verdict→status flip.

**Analog D — the status-flip UPDATE** (mirror the write-back at `:1778-1780`): for `held_fabrication` / `held_voice` the action is
```python
supabase.table("newsletters").update({
    "status": "held",
    "do_not_publish": True,
    "do_not_publish_reason": reason,   # net-new column, migration 046
}).eq("id", row_id).execute()
```
> Only fires when `enforce=true` (D-15). Under report-only (`enforce=false`) compute the verdict,
> write the `edition_evals` rows, surface the "would-have-held" line — but do NOT flip status.

**Analog E — CRITICAL: the governed-identity proxy client** (`:294-298`, the client-construction pattern — but see landmine):
```python
claude_client = anthropic.Anthropic(
    api_key=OPENAI_API_KEY,            # authenticates as the NEWSLETTER agent
    base_url=f"{LLM_PROXY_URL}/anthropic",
)
```
> **THE key non-obvious wiring detail.** `run_layer2` requires an `llm_client` authenticating as
> the governed `edition_eval` identity (GOV-01, `judge_loop.py:645-646`), **NOT** the newsletter
> identity. You must construct a NEW `anthropic.Anthropic` client with
> `api_key=edition_eval._get_eval_api_key()` (returns `LLM_PROXY_EVAL_KEY`, `edition_eval.py:43`),
> same `base_url=f"{LLM_PROXY_URL}/anthropic"`. **Do NOT reuse the module `claude_client`** — that
> would attribute eval spend to the newsletter wallet and defeat the whole governed-budget design.
> If `_get_eval_api_key()` returns None (key unminted), that is the fail-loud/outage case (D-07),
> not a fallback to `claude_client`.

**Analog F — httpx.Client injection for the live network re-check** (D-08). `run_deterministic_gate` and `run_layer2` both take `http_client=` and do zero network egress when it is None; the live caller MUST inject a real client so GATE-02/03 and the per-rewrite fabrication re-check are active. The construction pattern is the processor's `send_telegram` (`agentpulse_processor.py:9623`):
```python
with httpx.Client() as client:
    ...
```
> `httpx` is already imported at `newsletter_poller.py:17`. Build one `httpx.Client` (timeout set)
> and pass the SAME instance to both `run_deterministic_gate(..., http_client=hc)` and
> `run_layer2(..., http_client=hc)`. Phase-29 WR-02 emits a loud `logger.warning` if omitted — so
> omission is loud but the re-check silently won't run; injection is load-bearing.

**Analog G — config gating read** (`:2396-2400`, the exact pattern for reading the `edition_eval` block + the `enabled`/`enforce` flags, D-15):
```python
_bp_config_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
_bp_config = {}
if _bp_config_path.exists():
    _bp_config = _json.loads(_bp_config_path.read_text()).get('block_pipeline', {})
_use_block_pipeline = _bp_config.get('enabled', False) and task_type == 'write_newsletter'
```
> Copy this exact idiom, swapping `'block_pipeline'` → `'edition_eval'`. `enabled` gates
> INVOCATION (false = don't call the eval at all → rollback-safe); `enforce` gates the status flip
> (false = report-only). The full `edition_eval` block is passed to `run_layer2`'s `config` arg.

**Analog H — the block_v1 A/B insert (D-02 reconciliation target + D-14 telemetry-only eval)** (`:2674-2700`):
```python
bp_row = {
    "edition_number": edition,
    ...
    "status": "held",
    "data_snapshot": {
        "do_not_publish": True,      # ← D-02: the ONLY place do_not_publish lives today
        "ab_comparison": True,
        "pipeline_version": "block_v1",
        ...
    },
    "verification_warnings": ab_verification,
}
supabase.table("newsletters").insert(bp_row).execute()
```
> **D-02 landmine:** this JSONB `do_not_publish` flag must be reconciled to the new column so there
> is exactly ONE canonical home. Move it to `"do_not_publish": True` at the top level of `bp_row`
> (the block row is already always-held — its hold state does not change, only its *home* does).
> **D-14 landmine:** the block_v1 draft is STILL fully evaluated (Layer-1 + judge run on the
> `blocks_data` fact base for A/B trend completeness) but the eval is **telemetry-only** — it writes
> `edition_evals` rows and NEVER flips publish state. Only the PRIMARY (single-pass) draft's verdict
> drives a status change (D-13).

**Analog I — operator alert from the newsletter service (net-new; see "No In-Service Analog" below).**

---

### `docker/processor/agentpulse_processor.py` — the publish gate (service, request-response + CRUD)

The Processor stays a **dumb sequencer** (D-05): no LLM, no eval logic. The only Phase-30 change here is structural defense-in-depth (D-01) — the two publish selects already exclude `held` by status; add a `do_not_publish` column read so a mis-statused-but-held row still can't ship.

**Analog A — the manual publish draft select** (`:5865-5870`):
```python
draft = supabase.table('newsletters')\
    .select('*')\
    .in_('status', ['draft', 'pending', 'preview'])\
    .order('created_at', desc=True)\
    .limit(1)\
    .execute()
```

**Analog B — the auto-publish draft select** (`:10636-10641`):
```python
draft = supabase.table('newsletters')\
    .select('id, edition_number, created_at')\
    .in_('status', ['draft', 'pending'])\
    .order('created_at', desc=True)\
    .limit(1)\
    .execute()
```
> **D-01 action:** add an explicit `do_not_publish=false` guard so the publish gate reads the
> COLUMN directly, not just relies on the `held` status exclusion. `.in_('status', ...)` here is on
> the `public` `newsletters` table — the supabase-py `.in_()` silent-failure rule is **economy_map-schema
> ONLY**; `.in_()` on `newsletters` is the established working idiom (do not "fix" it). Add
> `.eq('do_not_publish', False)` (or filter in-Python on the fetched row) as the structural
> belt-and-suspenders. Auto-publish (`:10651`) also has the <1h freshness guard — leave it.

---

### `supabase/migrations/046_do_not_publish_columns.sql` (CREATE) — migration (schema / DDL)

**Analog A — ADD COLUMN on `newsletters`** (`020_newsletter_verification.sql`, verbatim house style):
```sql
-- Migration 020: Add verification_warnings column to newsletters
-- Stores unverified references flagged by verify_briefing_references()

ALTER TABLE newsletters
  ADD COLUMN IF NOT EXISTS verification_warnings jsonb DEFAULT NULL;

COMMENT ON COLUMN newsletters.verification_warnings IS
  'List of unverified entity references detected before publish';
```
> **Copy this shape.** Migration 046 adds two columns (D-01):
> `ADD COLUMN IF NOT EXISTS do_not_publish boolean NOT NULL DEFAULT false` and
> `ADD COLUMN IF NOT EXISTS do_not_publish_reason text`. Use `IF NOT EXISTS` (re-apply-safe house
> style — every recent ADD COLUMN migration uses it). Add `COMMENT ON COLUMN` for both.

**Analog B — the SQL-first / MCP-apply header block** (`045_edition_evals.sql:12-16`) — copy this operator-runbook header verbatim in spirit:
```sql
-- SQL-FIRST — the operator applies this via MCP after DDL review (project ref
-- zxzaaqfowtqvmsbitqpu). ...
-- Do NOT apply this from a worktree and do NOT run `supabase db push`.
```
> **Landmine (from CONTEXT + memory):** migrations are **operator-applied via MCP**, NOT
> `supabase db push`, NOT from a worktree. Migration 046 apply is an orchestrator/operator runbook
> step (D-04 step 2), NOT worktree execution. Highest applied on disk is 045; 046 is the next number.
> **Discretion (D + CONTEXT):** the planner decides whether to backfill historical A/B shadow rows
> from `data_snapshot.do_not_publish` to the new column, or leave them as historical (low-risk —
> `DEFAULT false` covers new rows).

---

### `config/agentpulse-config.json` → `edition_eval` (CONFIRM-only) — config

Block ALREADY EXISTS with the correct shape (verified live):
```json
"edition_eval": {
  "enabled": false, "enforce": false, "max_attempts": 2,
  "judge_model": "claude-sonnet-4-6", "judge_temperature": 0.2, "judge_max_tokens": 1500,
  "revise_model": "claude-sonnet-4-6", "revise_temperature": 0.3, "revise_max_tokens": 3000,
  "thresholds": { "continuity_fail_below": 4, "hedging_fail_below": 3, ... },
  "filler_blacklist": []
}
```
> Ship `enabled=false` (D-03, rollback-safe). No new config schema needed — the wiring just READS
> these flags. The whole block is passed to `run_layer2`'s `config` arg (it merges over
> `judge_loop._merged_config` DEFAULT_CONFIG). Live arming (flip `enabled`, later `enforce`) is the
> operator runbook (D-04), NOT a code change in this phase.

---

## Module Call Contracts (do NOT modify — sequence only)

### `run_deterministic_gate` — `deterministic_gate.py:93`
```python
run_deterministic_gate(draft, fact_base, prior_edition, *, http_client=None, github_token=None)
    -> {fabrication: [...], unverified: [...], mechanical: [...], meta: {...}}
```
- `draft`: `{title, title_impact, content_markdown, content_markdown_impact, pipeline_version}`.
- `fact_base`: the SAME dict Analog A builds (`{blocks,...}` for block_v1, `input_data` for single-pass). TRUSTED verbatim — raises `ValueError` if not a dict (`:137-141`).
- `prior_edition`: FULL previous-published edition `{content_markdown, content_markdown_impact, edition_number}` or None — **NOT** the truncated `load_edition_context` excerpt (contract note A3, `:117`).
- `http_client`: inject a real `httpx.Client` (D-08 / Analog F) or NO network check runs (zero egress).
- **Action rule (D-09):** a NON-EMPTY `fabrication` list → `held_fabrication`, short-circuit — do NOT enter Layer 2. `unverified` is telemetry-only, NEVER a hold ("an error is not evidence").

### `run_layer2` — `judge_loop.py:620`
```python
run_layer2(draft, fact_base, prior_context, det_flags, config, llm_client,
           *, http_client=None, github_token=None)
    -> {final_draft, verdict, selected_attempt, attempts:[...]}
    # verdict ∈ {passed, held_fabrication, held_voice, escalated}
```
- `prior_context`: `load_edition_context(supabase)` output (already assembled in `process_task` at `:2357`).
- `det_flags`: the Layer-1 result. **A non-empty `fabrication` raises `ValueError` (JUDGE-01, `:681-685`)** — Layer 1 MUST short-circuit first; only call `run_layer2` on a fabrication-clean draft.
- `llm_client`: the GOVERNED `edition_eval` client (Analog E) — REQUIRED, never reused from `claude_client`.
- `http_client`: same injected client (Analog F) so the per-rewrite fabrication re-check is live.
- **Verdict → action (D-09/10/11/12):** `held_fabrication`/`held_voice` → status flip + escalate;
  `passed` → NO auto-publish, unchanged Monday human gate; `escalated` → fail-open + operator alert.

### `write_eval_row` / `_get_eval_api_key` — `edition_eval.py:66` / `:43`
```python
write_eval_row(supabase, *, newsletter_id, edition_number, pipeline_version, attempt, layer,
               eval_status, verdict=None, error=None, deterministic_flags=None,
               judge_scores=None, judge_feedback=None, sats_spent=0, model_calls=None) -> str
```
- Fail-loud: `eval_status='ok'` REQUIRES a real `verdict` in `{passed,held_fabrication,held_voice,escalated}` + `error=None`; `eval_status='error'` REQUIRES `verdict=None` + a non-empty `error`. Any other combo raises `ValueError` BEFORE insert; a failed insert re-raises (never swallowed).
- `_get_eval_api_key()` returns `os.getenv("LLM_PROXY_EVAL_KEY")` — the governed identity for Analog E.

---

## Shared Patterns

### Fail-open-but-loud eval wrapper (D-06 + D-07)
**Source shape:** `newsletter_poller.py:1727 / :1792-1793` (try/except-continue).
**Apply to:** every eval invocation in `save_newsletter` / `process_task`.
```python
try:
    det = run_deterministic_gate(draft, fact_base, prior_edition, http_client=hc)
    # ... judge, verdict, write_eval_row ...
except Exception as e:
    write_eval_row(supabase, ..., eval_status='error', error=str(e))  # fail-loud row
    _alert_operator(f"eval did not run for edition #{edition}: {e}")  # D-07 loud outage
    logger.error(f"[EVAL] Failed for edition #{edition}: {e}")
    # DO NOT re-raise — generation continues, draft reaches the Monday human gate (D-06)
```
> The draft NEVER blocks on an eval error; but the outage pages the operator. Never a silent no-op.

### Governed-identity proxy client (GOV-01 — the phase's signature landmine)
**Source:** `newsletter_poller.py:294-298` (client-construction shape) + `edition_eval.py:43` (key getter).
**Apply to:** the `llm_client` handed to `run_layer2`.
> Build a NEW `anthropic.Anthropic(api_key=_get_eval_api_key(), base_url=f"{LLM_PROXY_URL}/anthropic")`.
> NEVER reuse `claude_client`. All eval LLM spend must land on the `edition_eval` wallet.

### Injected live httpx.Client (D-08)
**Source:** `agentpulse_processor.py:9623` (`with httpx.Client() as client:`).
**Apply to:** one client, passed to BOTH `run_deterministic_gate` and `run_layer2` per generation.

### Config-flag gating (D-15)
**Source:** `newsletter_poller.py:2396-2400`. **Apply to:** reading `edition_eval.enabled` / `.enforce`.

---

## No In-Service Analog

| Concern | Role | Data Flow | Reason / planner guidance |
|---------|------|-----------|---------------------------|
| Operator escalation alert **from the newsletter service** (D-07/D-09/D-10) | service | notify (out-of-band) | The newsletter service has **NO `send_telegram` helper** (`send_telegram` lives only in the processor, `agentpulse_processor.py:9599`, and reads processor-global `TELEGRAM_BOT_TOKEN`/`TELEGRAM_OWNER_ID`). Two viable analogs for the planner: **(a)** the newsletter service's existing cross-service task hop — `handle_negotiation_request` inserts an `agent_tasks` row for the processor (`newsletter_poller.py:1840` / `:1857`) — enqueue a processor-side telegram task; or **(b)** a direct `httpx` POST to `api.telegram.org` mirroring `send_telegram` (`:9623`), if the newsletter container has the token envs. Exact copy/format/dedup is **Claude's Discretion** (CONTEXT), and the *hardened* `send_telegram` is **Phase 31 (SURF)** — Phase 30 needs only a loud, non-silent alert path. |

---

## Metadata

**Analog search scope:** `docker/newsletter/` (poller + 3 eval modules), `docker/processor/agentpulse_processor.py` (publish gate + send_telegram), `supabase/migrations/` (020, 045), `config/agentpulse-config.json`.
**Files scanned:** 6 code files + 2 migrations + 1 config.
**Pattern extraction date:** 2026-07-01

### Worktree / rebuild landmines (from CONTEXT + memory — carry into every plan)
- Scoped `docker compose ... up -d --build newsletter` (and processor) rebuilds are **worktree-UNSAFE / main-tree-only** — a worktree executor builds stale code. Run no-worktree/sequential; the orchestrator owns the live rebuild.
- Migrations 045 (prereq, needs key/hash + apply) and 046 are **operator/orchestrator MCP-applied on the main tree**, NOT `supabase db push`, NOT worktree. This is the D-04 activation runbook, not phase-completion (D-03: "done" ships `enabled=false`, no live edition required).
