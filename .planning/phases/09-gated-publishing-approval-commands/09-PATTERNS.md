# Phase 9: Gated Publishing + Approval Commands - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 2 (1 new migration, 1 modified service)
**Analogs found:** 2 / 2 (both exact — CONTEXT.md pre-named every analog with line numbers)

> NOTE: This phase has NO RESEARCH.md (research disabled). The file list and analog
> pointers were extracted from `09-CONTEXT.md`, which already names every analog file
> and line range. All analogs were read and the concrete excerpts below confirmed.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `supabase/migrations/038_*.sql` (NEW) | migration (RPC amendment) | transform (lifecycle update) | `supabase/migrations/033_economy_map_schema.sql` §9 `publish_block_version` (lines 267-307) | exact — re-emit the same function with one line changed |
| `docker/gato_brain/gato_brain.py` (MODIFY) | command handler + RPC-POST helper | request-response (write/RPC) | `_economy_map_get` (1582-1604) for the helper; `economy_map_insert_block_body_version` (processor 3174-3203) for the POST style; `handle_map_command` (1902-1923) for the dispatch | exact (all three named in CONTEXT) |

---

## Pattern Assignments

### `supabase/migrations/038_*.sql` (migration, transform — D-01 watermark amendment)

**Analog:** `supabase/migrations/033_economy_map_schema.sql` §9 (lines 267-307).

**What changes (D-01):** Step 4 currently sets `last_synthesized_at = NOW()`. Replace
it with the approved draft's `synthesized_from_through` (a pinned column on
`block_body_versions`, declared at 033:101). Capture it in Step 1's `RETURNING`.

**IMPORTANT — re-emit the WHOLE function, do NOT use the `ALTER FUNCTION ... SET` style
of 035/037.** Migrations 035/037 only fix a `search_path` GUC and are pure
`ALTER FUNCTION` statements (037:30-45). They are the WRONG analog for a body change.
This phase amends the function *body*, so the correct precedent is the
`CREATE OR REPLACE FUNCTION` block in 033 §9 itself — copy it verbatim and change only
Step 1's RETURNING + Step 4's assignment. Keep `SECURITY DEFINER`,
`SET search_path = economy_map, public`, and the REVOKE/GRANT lines (033:309-310).

**The current Step 1 + Step 4 to amend** (033 lines 277-305):
```sql
DECLARE
    v_slug      text;
    v_maturity  economy_map.maturity;
BEGIN
    -- Step 1: atomic draft → published flip. RETURNING is empty if the row is not
    -- found or not in draft status — single-winner property (T-02-05).
    UPDATE economy_map.block_body_versions
       SET status        = 'published',
           published_at  = NOW()
     WHERE id     = p_version_id
       AND status = 'draft'
    RETURNING block_slug, proposed_maturity
      INTO v_slug, v_maturity;
    -- ... Step 2 (typed RAISE if v_slug IS NULL), Step 3 (supersede prior) unchanged ...
    -- Step 4: point block at new version + sync maturity + bump timestamp.
    UPDATE economy_map.blocks
       SET current_body_version_id = p_version_id,
           maturity                = v_maturity,
           last_synthesized_at     = NOW()       -- ← D-01: this is the line to change
     WHERE slug = v_slug;
END;
```

**The amendment (planner/executor — D-01, precise SQL is open per Claude's Discretion):**
add `v_synthesized_from_through timestamptz;` to the DECLARE block; extend Step 1's
`RETURNING` to also return `synthesized_from_through INTO ... v_synthesized_from_through`;
in Step 4 set `last_synthesized_at = v_synthesized_from_through`.

**Append-only trigger is NOT implicated** (033:177-211 read): the trigger guards
`synthesized_from_through` on `block_body_versions` against UPDATE — D-01 only READS that
column and writes `blocks.last_synthesized_at`, a `blocks`-table lifecycle update. No
trigger conflict.

**Migration header comment style** (037:1-28): every migration opens with a ROOT
CAUSE / WHY-SAFE / idempotency comment block. Follow it — state the IN-04 double-count
contract, why touching only `blocks` is trigger-safe, and the D-01a scope fence (NO
WR-01 UNIQUE index folded in).

**Apply mechanism** (CLAUDE.md + CONTEXT D-01): Supabase MCP `apply_migration`, project
ref `zxzaaqfowtqvmsbitqpu`, then `scripts/drift-check.sh`, then scoped redeploy. Latest
migration is 037, so this is **038**.

---

### `docker/gato_brain/gato_brain.py` (command handler + RPC-POST helper, request-response)

This file gets THREE additions: (1) a new RPC-POST helper, (2) two write branches in
`handle_map_command`, (3) threading the owner tier into the dispatch.

#### (1) New RPC-POST helper — analog: `_economy_map_get` (1582-1604) + processor POST style

The GET helper to mirror, headers and fail-loud shape (gato_brain 1582-1604):
```python
def _economy_map_get(table: str, params: dict, *, count_exact: bool = False) -> httpx.Response:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept-Profile": "economy_map",          # ← READ profile
    }
    if count_exact:
        headers["Prefer"] = "count=exact"
    return httpx.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params, headers=headers, timeout=10,
    )
```

The POST style to copy for the RPC call — `Content-Profile` (WRITE profile) +
`return=representation` + fail-loud non-2xx (processor `economy_map_insert_block_body_version`
3186-3203):
```python
resp = httpx.post(
    f"{SUPABASE_URL}/rest/v1/block_body_versions",
    headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
        "Content-Profile": "economy_map",         # ← WRITE profile (NOT Accept-Profile)
    },
    json=row, timeout=10,
)
if resp.status_code not in (200, 201):
    raise RuntimeError(
        f"economy_map block_body_versions insert failed ({resp.status_code}): {resp.text}"
    )
```

**For the RPC POST helper specifically** (D-04): the URL is
`{SUPABASE_URL}/rest/v1/rpc/<fn>` (PostgREST RPC endpoint, not a table), the JSON body
is the named arg `{"p_version_id": "<uuid>"}`, keep `Content-Profile: economy_map` +
service_role headers. `publish_block_version`/`reject_block_version` `RETURNS void`, so a
success is `200/204` with empty/null body — do NOT require representation rows. NEVER use
supabase-py `.rpc()`/`.schema()` (CLAUDE.md economy_map rule). A typed RPC RAISE
(`version … not found or not in draft status`, 033:290/336) comes back in `resp.text` —
the helper must surface it so the caller can match D-05 case (c). Helper name/signature
is planner's call (CONTEXT Discretion).

#### (2) Two write branches — analog: `handle_map_command` dispatch (1902-1923)

Current dispatcher (note the top-level fail-loud try/except — D-05 layers typed cases
*in front of* this catch-all):
```python
def handle_map_command(message: str) -> str:
    msg = message.strip()
    parts = msg.split(None, 1)
    cmd = parts[0].lower()
    try:
        if cmd == "/map-status":
            return handle_map_status()
        elif cmd == "/map-pending":
            return handle_map_pending()
        else:
            return f"Unknown map command: {cmd}\nAvailable: /map-status, /map-pending"
    except Exception as e:
        logger.error(f"Map command failed: {cmd} — {e}")
        return f"Command failed: {e}"
```
Add `/map-approve` and `/map-reject` branches here. `parts[1]` is the full-UUID arg
(D-04a). Missing/malformed UUID → typed usage hint (D-05 case b), not a silent no-op.

**Confirmation lookup pattern** (D-05, block name + maturity + URL): resolve via a
`_economy_map_get("blocks", {...})` by `block_slug` — the same GET helper `get_blocks`
already uses (1635-1652). The RPCs return void, so for the approve message you need the
new maturity (`proposed_maturity` of the draft) and the block url; read the draft row and
the block row via the existing GET helper before/after the RPC call.

**`/map-pending` already emits the approve lines verbatim** (handle_map_pending,
1867): `f"   version: {vid}  →  /map-approve {vid}"`. The full UUID it prints is exactly
the `<version_id>` arg `/map-approve` consumes (D-04a) — no new card UI needed.

#### (3) Owner gate — analog: `access_tier` resolution in `/chat` (2124-2126)

The owner concept already exists and is resolved in the `/chat` body BEFORE the `/map-`
dispatch:
```python
# /chat, lines 2124-2126
user = ensure_user(req.user_id)
access_tier = user.get("access_tier") or "free"
```
`TIER_LIMITS` (53-57) defines `"owner"` with `None` limits; `check_rate_limit`/`check_web_search_limit`
treat `owner` as unlimited via the `limits["messages"] is None` guard (287/315). Reuse this
SAME `access_tier == "owner"` notion for D-02 — no new env var / config.

**Wiring gap the planner MUST resolve:** the dispatch at line 2264 calls
`handle_map_command(req.message)` with ONLY the message string — `access_tier` (computed
at 2126) is NOT currently passed in. To gate the two write commands, thread the tier into
the map dispatch (e.g. change the call site to `handle_map_command(req.message, access_tier)`
and add the param), OR gate at the call site before dispatch. Read commands
(`/map-status`, `/map-pending`) stay UNGATED (D-02a) — the gate applies only to the two
write branches.

**Dispatch call site to amend** (2263-2271):
```python
# 2c-map. Economy Map read-only commands — handle directly, skip intent router
if _msg_lower.startswith("/map-"):
    map_response = handle_map_command(req.message)   # ← thread access_tier in here
    return ChatResponse(response=map_response, session_id="", intent="MAP_COMMAND", metadata={})
```
Update the section comment too (no longer "read-only").

---

## Shared Patterns

### economy_map PostgREST access (READ vs WRITE profile)
**Source:** `_economy_map_get` (gato_brain 1582-1604, `Accept-Profile`) /
`economy_map_insert_*` (processor 580-597, 3186-3203, `Content-Profile`)
**Apply to:** the new RPC-POST helper.
Reads use `Accept-Profile: economy_map`; writes/RPCs use `Content-Profile: economy_map`.
Both use `apikey` + `Authorization: Bearer SUPABASE_KEY` (service_role). NEVER supabase-py
`.in_()`/`.schema()`/`.rpc()` (CLAUDE.md — silent failure). Filter/arg values go in
`params`/`json`, never f-string-interpolated into the path (threat T-06-04).

### Fail-loud non-2xx
**Source:** every economy_map helper (e.g. processor 592-595, gato_brain 1647-1650)
**Apply to:** the new RPC-POST helper.
`if resp.status_code not in (...): raise RuntimeError(f"... failed ({resp.status_code}): {resp.text}")`.
A read/write failure must never read as a benign empty/no-op (the recurring silent-failure
class). D-05 case (d) is the command-layer surfacing of this: `Command failed: <e>`.

### Single-winner concurrency (already in the RPC — do not reimplement)
**Source:** `publish_block_version` Step 1 (033:280-291), `reject_block_version` (033:328-337)
**Apply to:** D-05 case (c) handling.
`UPDATE ... WHERE status='draft' RETURNING ... INTO v_slug; IF v_slug IS NULL THEN RAISE
EXCEPTION 'version % not found or not in draft status'`. A concurrent double-approve loses
safely (RETURNING-empty → typed RAISE), surfacing as case (c) "already actioned", never a
double-publish. The command handler matches this RAISE text to produce case (c).

### SECURITY DEFINER RPC header (preserve on re-emit)
**Source:** 033:267-272, 309-310
**Apply to:** migration 038.
`SECURITY DEFINER` + `SET search_path = economy_map, public` (T-02 hardening) +
`REVOKE ALL ... FROM PUBLIC; GRANT EXECUTE ... TO service_role`. Carry all of these
through unchanged when re-emitting the function.

---

## No Analog Found

None. Every file in this phase maps to an exact in-tree analog (CONTEXT.md pre-identified
all of them with line numbers).

The only NEW *kind* of thing is the RPC-POST-to-`/rpc/<fn>` shape (vs the existing
table-INSERT POSTs and table-GET reads), but its construction is a direct compose of two
existing analogs: the `_economy_map_get` header/timeout/fail-loud shape and the processor
POST's `Content-Profile` write profile. No RESEARCH.md fallback needed.

---

## GATE-01 verification (no new code — verify only)

**Source to verify:** `synthesize_block` / `economy_map_insert_block_body_version`
(processor 3174-3203). The INSERT helper OMITS `status` so the DB default `'draft'`
applies (3181-3182 docstring) and NEVER touches the published row / blocks. That IS
GATE-01 (synthesis only ever writes `draft`). Verification approach is open (CONTEXT
Discretion): a test asserting the synthesis writer emits `status='draft'` only, and/or an
inspection note. No production code change for GATE-01.

---

## Metadata

**Analog search scope:** `docker/gato_brain/gato_brain.py`,
`docker/processor/agentpulse_processor.py`, `supabase/migrations/033`, `037`
**Files scanned:** 4 (all analogs named in CONTEXT.md; read directly, no broad search needed)
**Pattern extraction date:** 2026-06-02
