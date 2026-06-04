# Phase 10: Operator Write Commands - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 3 source files modified + 2–3 new migrations
**Analogs found:** 9 / 9 (every new piece has an exact in-tree precedent — this phase is almost entirely "copy Phase 9 / Phase 7, parameterized")

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docker/gato_brain/gato_brain.py` — generalize `_economy_map_rpc` | utility (write helper) | request-response (PostgREST POST) | current `_economy_map_rpc` (gato_brain:1615) | exact (same fn, widen params) |
| `docker/gato_brain/gato_brain.py` — `handle_map_assign` | command handler | request-response → RPC | `handle_map_approve` (gato_brain:2023) | exact |
| `docker/gato_brain/gato_brain.py` — `handle_map_entry` | command handler | request-response → RPC | `handle_map_approve` (gato_brain:2023) | exact |
| `docker/gato_brain/gato_brain.py` — `handle_map_synth` | command handler | request-response → RPC (enqueue) | `handle_map_approve` + open-draft read | exact |
| `docker/gato_brain/gato_brain.py` — `handle_map_tension` | command handler | request-response → RPC | `handle_map_approve` (gato_brain:2023) | exact |
| `docker/gato_brain/gato_brain.py` — `handle_map_command` dispatch + "Available:" | router | dispatch | current dispatch (gato_brain:2127) | exact |
| `docker/gato_brain/gato_brain.py` — `get_unsorted_entries`/`get_unsorted_count` filter add | utility (read) | CRUD read | current readers (gato_brain:1770/1793) | exact (add one filter) |
| `docker/processor/agentpulse_processor.py` — synth-request drain poller | service (poller) | event-driven / batch drain | `synthesize_blocks_poller` (processor:3666) | exact (role + fail-loud structure) |
| `docker/processor/agentpulse_processor.py` — `scheduled_synth_request_drain` wrapper + `schedule.every(...)` | config (scheduler) | event-driven | `scheduled_synthesize_blocks` (processor:10594) + schedule block (processor:10999+) | exact |
| `docker/processor/agentpulse_processor.py` — 23505 benign-skip in `synthesize_block` | service | CRUD insert | `economy_map_insert_block_body_version` (processor:3174) INSERT site | role-match |
| Migration 040 — synth-request table + enqueue RPC + reassign columns/trigger/RPC + `/map-entry` RPC + `set_block_live_tension` RPC | migration | schema + RPC | migration 033 §7/§8/§9 + 038 | exact |
| Migration 041 — WR-01 UNIQUE partial draft index | migration | schema | migration 033:109-110 (non-unique partial index) | exact (UNIQUE upgrade) |

> **Migration grouping is planner's discretion (D-09 / Folded Todos).** D-07 *requires* the WR-01 unique index ships as its OWN operator-approved migration (separate track). The other schema changes may be one migration (040) or split. Numbers start at **040** — verified on disk: latest present is `039_publish_block_version_watermark_null_guard.sql`.

---

## Pattern Assignments

### `_economy_map_rpc` — generalize to arbitrary params (D-09)

**File:** `docker/gato_brain/gato_brain.py`
**Analog:** itself, current form at lines 1612–1646 (the only change: widen the hardcoded `{"p_version_id": ...}` to a caller-supplied dict; keep the allowlist + fail-loud).

**Current source (the exact thing to change):**
```python
_ECONOMY_MAP_RPC_ALLOWLIST = frozenset({"publish_block_version", "reject_block_version"})

def _economy_map_rpc(fn: str, version_id: str) -> httpx.Response:
    if fn not in _ECONOMY_MAP_RPC_ALLOWLIST:
        raise ValueError(f"economy_map rpc {fn!r} is not in the allowlist")
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Content-Profile": "economy_map",
        },
        json={"p_version_id": version_id},      # ← hardcoded; generalize to a params dict
        timeout=10,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"economy_map rpc {fn} failed ({resp.status_code}): {resp.text}"
        )
    return resp
```

**Target shape (planner confirms exact signature — D-09 / Discretion):**
- Add the four new RPC names to the allowlist:
  `_ECONOMY_MAP_RPC_ALLOWLIST = frozenset({"publish_block_version", "reject_block_version", "reassign_timeline_entry", <entry-insert-rpc>, "set_block_live_tension", <synth-enqueue-rpc>})`
- Signature becomes `_economy_map_rpc(fn: str, params: dict) -> httpx.Response` with `json=params`.
- **Existing call sites** (`handle_map_approve`:2051, `handle_map_reject`:2095) must be updated to `_economy_map_rpc("publish_block_version", {"p_version_id": version_id})`.
- **Critical constraints to preserve:** allowlist check BEFORE the URL is built (`fn` is interpolated into the path — threat WR-01); status not in `(200, 204)` RAISES `RuntimeError` carrying `resp.text` (fail-loud, preserves the DB's typed RAISE for the case-(c) match); `Content-Profile: economy_map` (NOT Accept-Profile); never supabase-py `.rpc()`.
- Note: enqueue RPCs that `RETURNS` a value (e.g. the synth-request row id, or reassign returning new entry id) may return `200` with a JSON body — the `(200, 204)` check already covers that; read `resp.json()` in the caller if a return is needed.

**Sibling write helper to mirror if you prefer a `return=representation` POST instead of an RPC** (e.g. the synth-request enqueue, if done as a direct table INSERT rather than an RPC — D-01 leaves this open): the processor's `economy_map_insert_timeline_entry` (processor:573) and `economy_map_insert_block_body_version` (processor:3174) show the `Prefer: return=representation` + `Content-Profile: economy_map` direct-INSERT idiom. **But D-09 says all gato_brain writes go through a `SECURITY DEFINER` RPC** — prefer the RPC enqueue.

---

### `handle_map_assign` / `handle_map_entry` / `handle_map_synth` / `handle_map_tension` (controller, request-response)

**Analog:** `handle_map_approve` (gato_brain:2023–2072) and `handle_map_reject` (gato_brain:2075–2109). All four new handlers follow this exact template: **owner-gate FIRST → strict arg-validate → read precondition (if any) → RPC call wrapped in try/except mapping the typed RAISE to a distinct message → rich confirmation.**

**The owner-gate-first template (lines 2031–2038):**
```python
def handle_map_approve(parts: list[str], access_tier: str) -> str:
    if access_tier != "owner":
        return (
            "/map-approve is owner-only. Only the verified operator can publish a draft "
            "to the live economy map."
        )
    version_id, err = _validate_version_id(parts, "/map-approve")
    if err:
        return err
    ...
```

**The RPC-call + typed-error-map template (lines 2050–2058):**
```python
    try:
        _economy_map_rpc("publish_block_version", version_id)   # → ("publish_block_version", {"p_version_id": version_id}) after generalize
    except Exception as e:
        if _RPC_ALREADY_ACTIONED in str(e):        # _RPC_ALREADY_ACTIONED = "not found or not in draft status" (gato_brain:1997)
            return (
                "That draft was already published/rejected or doesn't exist — nothing "
                "to publish. Run /map-pending to see what's still awaiting approval."
            )
        raise   # any other failure → top-level fail-loud "Command failed: <e>"
```

**Arg validation template — `_validate_version_id` (lines 2000–2020):** strict parse, return `(value, None)` or `(None, usage_hint)` BEFORE building any RPC body.
```python
def _validate_version_id(parts: list[str], verb: str) -> tuple[str | None, str | None]:
    if len(parts) < 2 or not parts[1].strip():
        return None, (f"Usage: {verb} <version-id>\n...")
    arg = parts[1].strip()
    try:
        version_id = str(uuid.UUID(arg))
    except (ValueError, AttributeError, TypeError):
        return None, (f"'{arg}' is not a valid version id.\n...")
    return version_id, None
```

**IMPORTANT — multi-arg parsing gotcha (D-06/D-10):** `handle_map_command` splits the message with `parts = msg.split(None, 1)` (gato_brain:2124), so `parts[1]` is the **entire remainder** as one string, NOT tokenized. The current write commands take a single UUID so this is invisible. The new commands take multiple args:
- `/map-assign <entry_id> <block_slug>` → re-split `parts[1].split()` into two tokens.
- `/map-entry <slug> <what_shifted> | <why_it_mattered>` → first token is the slug, then split the rest on the ` | ` delimiter (D-06). Both halves required; missing delimiter/second-half → usage hint.
- `/map-synth <block_slug>` → single token (slug).
- `/map-tension <block_slug> <text>` → first token slug, rest is the free-text tension.
Write per-command validators modeled on `_validate_version_id` (return `(parsed, None)` or `(None, hint)`); validate the slug against the **seven-block allowlist** (see below). Reject `unsorted`/unknown with a typed error (D-05/D-10).

**The seven-block slug allowlist (from migration 033 seed, lines 402–410):**
```
identity-trust, memory-context, payments-settlement,
autonomy-control, governance-accountability, psychology-disposition,
regulation-legal
```
Define this as a module-level `frozenset` in gato_brain (mirrors `_ECONOMY_MAP_RPC_ALLOWLIST`). Reject `unsorted` and anything not in the set. (You may alternatively GET `economy_map.blocks` via `get_blocks()` at :1724 and validate against live slugs — but a static frozenset is cheaper and the slug set is fixed.)

**`handle_map_synth` extra precondition (D-02):** before enqueuing, GET the target block's open-draft state and refuse (do NOT enqueue) if one exists. Reuse the read idiom from `block_has_open_draft` (processor:3124) — in gato_brain use `_economy_map_get("block_body_versions", {"block_slug": f"eq.{slug}", "status": "eq.draft", "select": "id", "limit": 1})`. Return a pointer: "this block already has a pending draft — approve or reject it first via `/map-pending`". Then enqueue and ack ("Queued — draft appears within ~Ns; check `/map-pending`").

**Confirmation/error UX (D-10):** five distinct cases per command — not-owner refusal / missing-or-malformed-arg usage hint / unknown-or-`unsorted` slug / already-actioned-or-precondition-failed / generic `Command failed: <e>`. Wording/emoji is Discretion; match the `✅`/`🚫` style already used at :2068/:2106.

---

### `handle_map_command` dispatch + "Available:" fallthrough (router)

**File:** `docker/gato_brain/gato_brain.py`
**Analog:** itself, lines 2112–2143.

```python
    try:
        if cmd == "/map-status":
            return handle_map_status()
        elif cmd == "/map-pending":
            return handle_map_pending()
        elif cmd == "/map-approve":
            return handle_map_approve(parts, access_tier)
        elif cmd == "/map-reject":
            return handle_map_reject(parts, access_tier)
        # ← add: /map-assign, /map-entry, /map-synth, /map-tension (each (parts, access_tier))
        else:
            return (
                f"Unknown map command: {cmd}\n"
                f"Available: /map-status, /map-pending, /map-approve, /map-reject"
                # ← extend Available: with the four new verbs
            )
    except Exception as e:
        logger.error(f"Map command failed: {cmd} — {e}")
        return f"Command failed: {e}"
```
`access_tier` is already threaded from `/chat` dispatch at gato_brain:2487–2488 (`handle_map_command(req.message, access_tier)`) — **no change needed there**, and forwarding is a wildcard `isMapCommand = /^\/map-/i` in `inject-gato-brain.mjs` (DO NOT touch — canonical_refs).

---

### `get_unsorted_entries` / `get_unsorted_count` — add `reassigned_to_entry_id IS NULL` (D-04, SC1)

**File:** `docker/gato_brain/gato_brain.py` (lines 1770–1798)
**Analog:** themselves. PostgREST `IS NULL` filter syntax is `"reassigned_to_entry_id": "is.null"`.

Current:
```python
def get_unsorted_entries() -> list[dict]:
    resp = _economy_map_get(
        "timeline_entries",
        {
            "select": "id,what_shifted,tag_confidence,created_at,event_date",
            "block_slug": "eq.unsorted",
            "order": "created_at.desc",
        },
    )
    ...

def get_unsorted_count() -> int:
    return _economy_map_count(
        "timeline_entries",
        {"block_slug": "eq.unsorted"},
    )
```
Add `"reassigned_to_entry_id": "is.null"` to **both** param dicts so a reassigned original leaves the `/map-pending` backlog immediately. (No supabase-py — these already use direct PostgREST via `_economy_map_get`/`_economy_map_count`, which is correct per the project rule.)

---

### Synth-request drain poller (service, event-driven) — Phase 10's only new processor function

**File:** `docker/processor/agentpulse_processor.py`
**Analog:** `synthesize_blocks_poller` (processor:3666–3759) — copy its **fail-loud autonomous-cycle structure** exactly. The drain poller differs only in: (a) it reads PENDING request rows instead of all seven blocks, (b) it calls `synthesize_block` **bypassing `is_block_eligible`** (D-01), and (c) it writes the request row's `done`/`failed` status (D-03).

**Structure to mirror (the fail-loud skeleton, processor:3685–3759):**
```python
def synthesize_blocks_poller() -> dict:
    if not supabase:
        return {'error': 'Supabase not configured'}
    cfg = get_full_config().get('synthesis', {})
    if not cfg.get('enabled', True):
        logger.info("[SYNTH] synthesis disabled via config — skipping")
        return {'disabled': True}
    run_id = log_pipeline_start('synthesize_blocks')        # durable queryable run row FIRST
    identity_text = load_synth_identity()                   # fail-loud if None (never voiceless)
    if identity_text is None:
        log_pipeline_end(run_id, 'failed', {'error': 'synth_identity unavailable'})
        return {'error': 'synth_identity unavailable'}
    if not _get_agent_api_key():                            # fail-loud if missing
        log_pipeline_end(run_id, 'failed', {'error': 'missing agent api key'})
        return {'error': 'missing agent api key'}
    totals = {...}
    try:
        blocks = fetch_economy_map_blocks()
        for block in blocks:
            try:
                result = synthesize_block(block, cfg, identity_text)
                ...
            except Exception as e:
                totals['failed'] += 1
                logger.error(f"[SYNTH] block {slug} failed: {e}", exc_info=True)
        log_pipeline_end(run_id, 'completed', totals)
    except Exception as e:
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}
    return totals
```

**Drain-poller adaptations (D-01/D-02/D-03):**
1. Same `if not supabase` / config-enable / `log_pipeline_start` / `load_synth_identity` (None → fail-loud) / `_get_agent_api_key()` (missing → fail-loud) preamble. A failed forced-synth must be queryable, never a silent drop (D-03).
2. Read pending requests via `_economy_map_get("<synth_request_table>", {"status": "eq.pending", "select": "...", "order": "created_at.asc"})` (processor:3088 read helper).
3. For each request: mark `processing`, fetch the target block (`fetch_economy_map_blocks()` filtered to the slug, or a single-slug GET), then call `synthesize_block(block, cfg, identity_text)` **but bypass eligibility** — D-01 says ignore N/T. Two clean options for the planner:
   - call `synthesize_block` with a `force=True` flag added to its signature that skips the `is_block_eligible` short-circuit (processor:3619) while STILL honoring `block_has_open_draft`/the 23505 guard (D-02 — never bypass the open-draft invariant); OR
   - inline the eligible branch of `synthesize_block` (processor:3631–3663) in the drain path.
   The open-draft guard (`block_has_open_draft`, processor:3124) and the 23505 backstop stay intact regardless (D-02).
4. On success: mark the request `done` with the resulting `version_id`. On per-request failure: mark `failed` with the error (queryable — D-03), `logger.error(..., exc_info=True)`, continue the loop (per-request isolation, same as the per-block isolation at processor:3737).

**The 23505 site + benign-skip (D-07):** `economy_map_insert_block_body_version` (processor:3174) is the INSERT that the new `uq_block_body_versions_one_open_draft` UNIQUE index will reject on a lost race. The benign-skip handling per D-07 ("logged benign skip, NEVER a fail-loud abort") goes around the INSERT call inside `synthesize_block` (processor:3646) — catch the `23505` unique-violation (PostgREST returns it in `resp.text` / status 409; `economy_map_insert_block_body_version` currently RAISES on non-(200,201)). The planner should detect the `"23505"` / `"duplicate key"` marker on the raised `RuntimeError` and convert it to a logged skip result (`{'status': 'skipped', 'reason': 'race-lost-open-draft'}`), keeping `block_has_open_draft` (processor:3613) as the cheap fast-path.

---

### Scheduler registration (config) — `scheduled_synth_request_drain` wrapper + `schedule.every(...)`

**File:** `docker/processor/agentpulse_processor.py`
**Analog (thin wrapper):** `scheduled_synthesize_blocks` (processor:10594) / `scheduled_classify_intake` (processor:10580):
```python
def scheduled_synthesize_blocks():
    try:
        result = synthesize_blocks_poller()
        logger.info(f"Block synthesis: {result}")
    except Exception as e:
        logger.error(...)
```
**Analog (registration):** the `schedule.every(...)` block at processor:10999–11064. Existing short-interval examples to slot beside:
```python
    schedule.every(30).minutes.do(scheduled_classify_intake)        # processor:11024
    schedule.every(5).minutes.do(scheduled_post_approved_x)         # processor:11055
    schedule.every(10).minutes.do(scheduled_check_negotiation_timeouts)  # processor:11048
    schedule.every().day.at("07:00").do(scheduled_synthesize_blocks)     # processor:11030
```
Add `schedule.every(<30–60>).seconds.do(scheduled_synth_request_drain)` here (cadence is Discretion per D-01 — `schedule` supports `.seconds`). D-01 also permits reusing an existing tick if natural; a dedicated short job is the cleanest match to the "drains pending requests" intent.

---

## Migration Patterns

### Mutable lifecycle-column exemption on `timeline_entries` (D-04)

**Analog:** the `block_body_versions` lifecycle exemption — migration 033 §8, function `block_body_versions_append_only()` (033:177–206) exempts `status`/`published_at` by simply NOT listing them in the "DISTINCT FROM → RAISE" guards. The `timeline_entries_append_only()` trigger (033:213–248) currently guards **every** column (033:223 comment: "every column on this table is pinned"). D-04 adds two **mutable** columns and exempts ONLY them.

**Pattern to follow:**
1. `ALTER TABLE economy_map.timeline_entries ADD COLUMN IF NOT EXISTS reassigned_to_entry_id UUID;` (on original) and `... reassigned_from_entry_id UUID;` (on copy). Both nullable, mutable.
2. `CREATE OR REPLACE FUNCTION economy_map.timeline_entries_append_only()` — re-emit the full body (033:213–248) UNCHANGED (it still guards every CONTENT column: block_slug, event_date, what_shifted, why_it_mattered, source_url, source_edition_id, tag_confidence) and simply does NOT add guards for the two new `reassigned_*` columns — so they remain UPDATE-able. The DELETE block stays. This is the exact `block_body_versions` precedent (content pinned, lifecycle free).

### `reassign_timeline_entry` RPC + the `/map-entry` insert RPC + `set_block_live_tension` RPC (D-04/D-06/D-08)

**Analog:** `publish_block_version` (033:267–310) and `reject_block_version` (033:319–342) — the SECURITY DEFINER template. Critical boilerplate to copy verbatim on EACH new RPC:
```sql
CREATE OR REPLACE FUNCTION economy_map.<fn>(<typed params>)
RETURNS <void | uuid>
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public        -- T-02 search-path pin (mandatory, 033:271)
AS $$
DECLARE ...
BEGIN ...
END;
$$;

REVOKE ALL ON FUNCTION economy_map.<fn>(<sig>) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.<fn>(<sig>) TO service_role;
```
- **`reassign_timeline_entry(p_entry_id uuid, p_block_slug text)`** (D-04/D-05): atomically (a) INSERT a new `timeline_entries` row under `p_block_slug` copying the original's `event_date`, `what_shifted`, `why_it_mattered`, `source_url`, `source_edition_id` verbatim (NOT today's date — provenance, D-05) with `reassigned_from_entry_id = p_entry_id` and `tag_confidence` per Discretion (NULL or 1.0), and (b) `UPDATE ... SET reassigned_to_entry_id = <new id>` on the original. Use the single-winner `RETURNING ... INTO v_*` + `IF v_* IS NULL THEN RAISE EXCEPTION` typed-error pattern (033:285–291) to reject when the entry isn't currently `unsorted`/already reassigned. The append-only trigger permits the `reassigned_to_entry_id` UPDATE per the new exemption above.
- **`/map-entry` insert RPC** (D-06): INSERT one `timeline_entries` row; `what_shifted`/`why_it_mattered` from the delimiter-split args (both NOT NULL), `event_date = CURRENT_DATE` (today), `source_url`/`source_edition_id` NULL, `tag_confidence` NULL, `block_slug = p_slug`. (Alternatively the existing `economy_map_insert_timeline_entry` direct-INSERT helper at processor:573 if done processor-side — but per D-09 gato_brain writes go through an RPC.) Validate slug ≠ `unsorted`/unknown.
- **`set_block_live_tension(p_slug text, p_text text)`** (D-08): `UPDATE economy_map.blocks SET live_tension = p_text WHERE slug = p_slug;` — `blocks` has NO append-only trigger (033:73 annotates `live_tension` "mutated via /map-tension"), so this is a plain mutable UPDATE. Use `IF NOT FOUND THEN RAISE EXCEPTION 'block % not found', p_slug;` for the typed unknown-slug error. (D-08: RPC is the default; a direct PostgREST PATCH would also work but the RPC keeps every economy_map write behind a SECURITY DEFINER fn + the allowlist — RPC preferred.)
- **synth-request enqueue** (D-01/D-03): if done as an RPC (preferred per D-09), `INSERT INTO economy_map.<synth_request_table> (block_slug, status) VALUES (p_slug, 'pending') RETURNING id` and return the id. Otherwise a direct `Prefer: return=representation` POST via a new processor-style writer.

### Synth-request table (D-01/D-03) — new `economy_map` table

**Analog:** `economy_map.block_body_versions` (033:94–105) for the lifecycle-status + `created_at` shape, and the `pipeline_runs` fail-loud status lifecycle (referenced D-03). Required by D-03: a `status` column (`pending` → `processing` → `done`/`failed`), the resulting `version_id` on done, and an `error` text on failed (queryable — never a silent drop). Column set is Discretion within those constraints. Add the partial index on `WHERE status='pending'` (mirror 033:109-110) so the drain poll is cheap.

### WR-01 UNIQUE partial draft index — its OWN migration (D-07)

**Analog:** the existing NON-unique partial index, migration 033:109-110:
```sql
CREATE INDEX IF NOT EXISTS idx_block_body_versions_status
    ON economy_map.block_body_versions(status) WHERE status = 'draft';
```
D-07 SQL (ships SEPARATELY per the scoped-approved-deploys discipline):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_block_body_versions_one_open_draft
    ON economy_map.block_body_versions (block_slug) WHERE status = 'draft';
```
This is the structural backstop for the `/map-synth` + scheduled-poller check-then-act race (D-02/D-07). Pair it with the processor 23505 benign-skip (above).

---

## Shared Patterns

### economy_map write surface (applies to ALL four new commands)
**Source:** `_economy_map_rpc` (gato_brain:1615), `economy_map_insert_*` (processor:573/3174)
**Apply to:** every Phase 10 write.
- Direct PostgREST `POST /rest/v1/rpc/<fn>` with `Content-Profile: economy_map` (writes) / `GET` with `Accept-Profile: economy_map` (reads). Service_role headers `apikey` + `Authorization: Bearer {SUPABASE_KEY}`.
- Allowlist-guard `fn` BEFORE building the URL (WR-01 hardening).
- Parameterized JSON body — NEVER f-string-interpolate values into the URL/body (threat T-09-07).
- Non-2xx → `raise RuntimeError(... resp.text)` (fail-loud; preserves the DB's typed RAISE).
- **NEVER** supabase-py `.rpc()`/`.schema()`/`.in_()` on economy_map (silent-failure rule, CLAUDE.md).

### Owner gate (applies to ALL four new commands — D-09)
**Source:** `handle_map_approve` (gato_brain:2031), `ensure_user`/`access_tier` (gato_brain:185/285)
**Apply to:** every write command, checked FIRST before any read/write.
```python
if access_tier != "owner":
    return "/map-<verb> is owner-only. Only the verified operator can ..."
```
`access_tier` is threaded from `/chat` (gato_brain:2487). The DB cannot know the Telegram caller — the gate lives in gato_brain.

### Fail-loud governance (applies to the drain poller + all RPC calls — D-03)
**Source:** `synthesize_blocks_poller` (processor:3666), `log_pipeline_start/end` (processor:7136/7149)
**Apply to:** the synth-request drain.
- `log_pipeline_start` BEFORE the fail-loud gates so every governance halt leaves a durable, queryable `failed` run row.
- `load_synth_identity()` None → fail-loud (never synthesize voiceless). `_get_agent_api_key()` missing → fail-loud.
- A failed forced-synth marks the request row `failed` with an error — queryable, never a silent drop ("the wallet bug" lesson).

### SECURITY DEFINER RPC boilerplate (applies to all new RPCs — D-04/D-06/D-08)
**Source:** `publish_block_version`/`reject_block_version` (033:267–342), re-emit precedent 038
**Apply to:** `reassign_timeline_entry`, `/map-entry` insert, `set_block_live_tension`, synth-enqueue.
- `SECURITY DEFINER` + `SET search_path = economy_map, public` (mandatory T-02 pin).
- `RETURNING ... INTO v_*` + `IF v_* IS NULL THEN RAISE EXCEPTION '<typed message>'` single-winner / typed-error pattern.
- `REVOKE ALL ... FROM PUBLIC; GRANT EXECUTE ... TO service_role;` after each function.
- `CREATE OR REPLACE FUNCTION` full-body re-emit (idempotent; NOT an `ALTER FUNCTION ... SET` shim — 038 comment lines 26–28).

### Append-only content + mutable lifecycle (applies to the timeline_entries amendment — D-04)
**Source:** `block_body_versions_append_only()` (033:177–206), §8 loud comment (033:164–175)
**Apply to:** `timeline_entries_append_only()` re-emit.
- Content columns stay guarded (`IS DISTINCT FROM` → `RAISE`); only the two new `reassigned_*` lifecycle columns are exempted (omitted from guards).
- Enforced by BEFORE UPDATE/DELETE **trigger, NOT RLS** — service_role bypasses RLS by design (033:166–171). A future dev "WILL try to simplify this to RLS. Do not."

---

## No Analog Found

None. Every Phase 10 piece has a direct in-tree precedent (Phase 9 write commands, Phase 7 synthesis poller, migration 033 §8/§9/§10, migration 038). The only genuinely new artifact is the **synth-request table**, and even its shape is constrained by D-03 to the `block_body_versions` lifecycle-status + `pipeline_runs` queryable-status precedents.

---

## Metadata

**Analog search scope:** `docker/gato_brain/gato_brain.py`, `docker/processor/agentpulse_processor.py`, `supabase/migrations/033_economy_map_schema.sql`, `supabase/migrations/038_publish_block_version_watermark.sql`
**Files scanned:** 4 source files + migration directory listing
**Latest migration on disk:** `039_publish_block_version_watermark_null_guard.sql` → Phase 10 starts at **040**
**Seven block slugs (validation allowlist):** identity-trust, memory-context, payments-settlement, autonomy-control, governance-accountability, psychology-disposition, regulation-legal
**Pattern extraction date:** 2026-06-03
