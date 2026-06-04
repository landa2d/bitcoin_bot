# Phase 6: Telegram Read-Only Scaffolding - Pattern Map

**Mapped:** 2026-05-30
**Files analyzed:** 1 modified (`docker/gato_brain/gato_brain.py`)
**Analogs found:** 4 / 4 (all symbols have strong in-repo analogs)

This phase modifies a **single existing file** — `docker/gato_brain/gato_brain.py` — adding
read-only `/map-status` and `/map-pending` commands. No new files, no migrations, no web changes.
The four new symbols the planner will create all live inside that file (or a small sibling module,
planner's discretion per D-10):

| New Symbol | Role | Data Flow | Closest Analog | Match Quality |
|------------|------|-----------|----------------|---------------|
| `handle_map_command(message) -> str` | dispatcher | request-response | `handle_x_command()` @ `gato_brain.py:1488` | exact |
| `/map-*` routing branch in request handler | route | request-response | `/x-` branch @ `gato_brain.py:1855-1863` | exact |
| `handle_map_status() -> str` | handler/renderer | CRUD-read + transform | `_handle_x_plan()` @ `gato_brain.py:1205` | role-match |
| `handle_map_pending() -> str` | handler/renderer | CRUD-read + transform | `_handle_x_plan()` @ `gato_brain.py:1205` | role-match |
| read-only `economy_map` client wrapper | client/utility | request-response (GET-only) | processor `economy_map_*` GET helpers @ `agentpulse_processor.py:600-660`, `3043` | role-match (port shape) |
| maturity pill → text renderer | utility | transform | `renderMaturityPill()` + `MATURITY_STAGE` @ `app.js:38,357` | role-match (port to Python) |

---

## Pattern Assignments

### `handle_map_command()` — dispatcher (request-response)

**Analog:** `handle_x_command()` @ `docker/gato_brain/gato_brain.py:1488-1525`

This is the contract to clone exactly. Note: **synchronous** (`def`, not `async def`), splits
`message` into `cmd`/`args`, wraps the whole dispatch in one `try/except Exception` that logs and
returns a string, and **every branch returns a string** (the caller wraps it in `ChatResponse`).

```python
def handle_x_command(message: str) -> str:
    """Dispatch /x-* commands to their handlers."""
    msg = message.strip()
    parts = msg.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    try:
        if cmd == "/x-approve":
            return _handle_x_approve(args)
        elif cmd == "/x-plan":
            return _handle_x_plan()
        ...
        else:
            return f"Unknown X command: {cmd}\nAvailable: /x-plan, /x-approve, ..."
    except Exception as e:
        logger.error(f"X command failed: {cmd} — {e}")
        return f"Command failed: {e}"
```

**Conventions to replicate:**
- Sync `def ... -> str`. Mirror it (CONTEXT D-10 / Claude's-Discretion: "handle_x_command is sync; mirror it").
- One top-level `try/except Exception` → `logger.error(...)` + return human string. (Matches project
  "broad except Exception, log, continue" convention from CLAUDE.md.)
- Unknown-command branch returns an `Available: ...` help string — replicate for `/map-*`.
- `logger` is the module-level `"gato-brain"` logger already in scope.

### `/map-*` routing branch — route (request-response)

**Analog:** the `/x-` branch in the request handler @ `docker/gato_brain/gato_brain.py:1855-1863`

Add the `/map-` branch **here**, alongside `/x-`, `/code*`, `/cto` — **before** the intent router
(`intent_router.route` @ :1924), exactly as CONTEXT D-10 / ROADMAP criterion 3 require ("same place
`/x-*` and `/code*` are handled"). `_msg_lower` is already computed above this block.

```python
    # 2c. X Distribution commands — handle directly, skip intent router
    if _msg_lower.startswith("/x-"):
        x_response = handle_x_command(req.message)
        return ChatResponse(
            response=x_response,
            session_id="",
            intent="X_COMMAND",
            metadata={},
        )
```

**Conventions to replicate:**
- `if _msg_lower.startswith("/map-"):` → call dispatcher with **`req.message`** (raw, not lowered).
- Return `ChatResponse(response=..., session_id="", intent="MAP_COMMAND", metadata={})`.
- Place it inside the same prefix-dispatch ladder (2c/2d/2e), before session/intent logic — no
  parallel infrastructure (D-10).

### `handle_map_status()` / `handle_map_pending()` — handler + text renderer (read + transform)

**Analog:** `_handle_x_plan()` @ `docker/gato_brain/gato_brain.py:1205-1300+`

Closest in-file analog for "read rows, build a multi-section text block, return one string." Shows
the read → sort → format-into-lines → `return "\n".join(...)` shape, the empty-state early return,
and inline `_format_*` closures.

```python
def _handle_x_plan() -> str:
    """Show today's content candidates + any unactioned engagement replies."""
    today_resp = (
        supabase.table("x_content_candidates")
        .select("daily_index, content_type, status, ...")
        .gte("created_at", today_start.isoformat())
        .order("daily_index")
        .execute()
    )
    ...
    if not merged:
        return "No X content candidates."
    ...
    lines = ["X Content Plan\n"]
    def _format_candidate(c):
        ...
    return "\n".join(lines)
```

**Conventions to replicate:**
- Sync function returning a single string; explicit empty-state strings (D-08a: "Nothing awaiting
  approval. Nothing awaiting assignment." — fail-loud, not silent).
- Build `lines = [...]` then `"\n".join(...)`. Wrap the aligned status table in a Markdown code fence
  (triple backtick) so monospace columns align (D-01). The Markdown→plain-text fallback is handled
  downstream (Gato/Node layer); the handler just returns the string.
- **DO NOT** copy `_handle_x_plan`'s `supabase.table(...)` access for `economy_map` — that path is
  the public schema only. economy_map reads MUST go through the new GET wrapper below (PROJECT.md:
  supabase-py `.schema()`/`.in_()` silently fail against economy_map).
- **DO NOT** introduce a `daily_index`-style ephemeral index. D-07 locks **full raw UUIDs** for
  `version:`/`entry:` (the `/x-*` `daily_index` pattern is the explicit anti-example — stale-mismatch
  risk). Render `block_body_versions.id` and `timeline_entries.id` verbatim.

### read-only `economy_map` client wrapper — client/utility (GET-only)

**Analog (shape to PORT):** processor economy_map GET helpers @
`docker/processor/agentpulse_processor.py:600-660` and `3043-3070`

These are the proven Accept-Profile read shape. Port their structure into gato_brain, but **expose
only GET methods** (D-09: structural code-level read-only boundary). gato_brain already has
`SUPABASE_URL` (:37), `SUPABASE_KEY = SUPABASE_SERVICE_KEY or SUPABASE_KEY` (:38), and `import httpx`
(:19) in scope — same globals the helpers need.

```python
def economy_map_edition_already_emitted(source_edition_id: str) -> bool:
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/timeline_entries",
        params={"source_edition_id": f"eq.{source_edition_id}", "select": "id", "limit": 1},
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept-Profile": "economy_map",      # ← schema-READ header (GET only)
        },
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"economy_map timeline_entries existence check failed ({resp.status_code}): {resp.text}"
        )
    rows = resp.json()
    return bool(isinstance(rows, list) and rows)
```

And the blocks read (`agentpulse_processor.py:3043-3070`) — same headers, different table:

```python
resp = httpx.get(
    f"{SUPABASE_URL}/rest/v1/blocks",
    params={"select": "slug"},
    headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
             "Accept-Profile": "economy_map"},
    timeout=10,
)
```

**ANTI-EXAMPLE — the wrapper must NOT expose this:**
`economy_map_insert_timeline_entry()` @ `agentpulse_processor.py:573-597` uses
`"Content-Profile": "economy_map"` (the **write** header) + `httpx.post`. The new wrapper must have
**zero `httpx.post/patch/delete` and zero `Content-Profile` header** — only `httpx.get` +
`Accept-Profile`. This is the criterion-4 / D-09 read-only-by-construction boundary the code-review
gate checks.

**Conventions to replicate:**
- Sync `httpx.get` (mirror `handle_x_command` sync style — Claude's Discretion in CONTEXT).
- `Accept-Profile: economy_map` header on every call; `apikey` + `Authorization: Bearer` both set to
  `SUPABASE_KEY`; `timeout=10`.
- **Raise on non-2xx** (fail-loud read — never let a read failure read as "nothing pending", which
  would silently hide drafts/unsorted; matches the processor helpers' raise-on-non-2xx rationale and
  memory `feedback-fail-loud-governance`).
- Encapsulate the GET methods on a single object/module namespace exposing only:
  `get_blocks()`, `get_draft_versions()`, `get_timeline_entries(...)` — no insert/update/delete
  surface (D-09).

### maturity pill → Python text renderer — utility (transform)

**Analog (to MIRROR in Python):** `renderMaturityPill()` + `MATURITY_STAGE` @
`docker/web/site/app.js:38, 357-362`, and `renderStatus()`/`tierSection()` @ `app.js:635-671`

The DB `blocks.maturity` column is the **one source of truth** (RNDR-04 — no recomputation). The web
maps enum→stage 1..5 then renders 5 segments; mirror that as filled/empty glyphs in Python text.

```javascript
const MATURITY_STAGE = { nascent: 1, emerging: 2, contested: 3, consolidating: 4, mature: 5 };
const TIER_LABELS = { substrate: 'SUBSTRATE', behavior: 'BEHAVIOR', frame: 'FRAME' };

function renderMaturityPill(b) {
    var stage = MATURITY_STAGE[b.maturity] || 1;   // 5-segment fill, || 1 guards bad enum
    return '...<span class="seg"></span>×5...';
}
```

Tier grouping to mirror (`renderStatus` @ `app.js:635-671`): filter blocks into
substrate/behavior/frame, render each tier under its uppercase `TIER_LABELS` header, query already
ordered by `sort_order` ascending.

**Conventions to replicate (Python text form):**
- `MATURITY_STAGE = {"nascent":1, "emerging":2, "contested":3, "consolidating":4, "mature":5}` —
  identical to the migration 033 enum order (`033:46-52`) and the web map. `|| 1` → `.get(m, 1)`.
- Pill = `stage` filled glyphs + `(5-stage)` empty + space + word label, e.g. `◉◉○○○ emerging`
  (D-02). Glyph substitution allowed if `◉`/`○` don't render in Telegram monospace — the
  **5-segment + word-label** contract is locked, not the exact glyphs.
- Tier headers `SUBSTRATE` / `BEHAVIOR` / `FRAME` (uppercase, hardcoded — `app.js:41`), blocks under
  each ordered by `sort_order` (D-01).

---

## Shared Patterns

### economy_map read access (cross-cutting — applies to both handlers + the wrapper)
**Source:** `agentpulse_processor.py:564-660, 3043-3070` (read helpers) + `PROJECT.md` Constraints
**Apply to:** every economy_map touch in this phase
- Direct PostgREST + `Accept-Profile: economy_map` GET. **Never** supabase-py `.schema()`/`.in_()`
  (silent failure — PROJECT.md / Phase 2/5 lock). The existing `gato_brain.supabase` client is for
  the **public schema only** (corpus_users, conversation_messages, etc. — see `:186`, `:1210`).

### Telegram handler return + split contract
**Source:** `handle_x_command()` + `_handle_x_plan()` (`gato_brain.py:1488`, `1205`)
**Apply to:** both `/map-*` handlers
- Handler returns ONE string → request handler wraps in `ChatResponse`. The 4000-char split +
  Markdown-first/plain-text-fallback happens **downstream in the Gato/Node layer**, not in
  gato_brain (gato_brain itself returns the raw string; no `parse_mode` call exists here). Both
  /map messages are expected to fit one message (7 blocks), but keep lines compact. The `_handle_x_plan`
  `CHAR_BUDGET = 3600` truncation pattern (`:1242`) is available as a safety net if needed.

### Fail-loud reads + error wrapping
**Source:** processor helpers (raise on non-2xx) + `handle_x_command` except block
**Apply to:** the GET wrapper (raise on non-2xx) and the dispatcher (catch → `logger.error` + return
`f"Command failed: {e}"`). A read failure must never silently render as an empty/zero state — that is
the silent-data-loss class the operator designs against (memory: fail-loud governance, fix-review-blockers).

---

## Schema Reference (read targets — `supabase/migrations/033_economy_map_schema.sql`)

| Need (CONTEXT decision) | Table / column | Migration anchor |
|---|---|---|
| Block list, tier, order, maturity, synth watermark | `blocks(slug, tier, sort_order, maturity, last_synthesized_at)` | `033:65-77` |
| Pending-draft count per block (D-04) | `block_body_versions(block_slug, status='draft')` — **partial index built for /map-pending** | `033:98-99`, index `033:109-110` |
| Draft version id surfaced as `version:` (D-07) | `block_body_versions.id` | `033:95` |
| "Unabsorbed" entries newer than synth (D-05) | `timeline_entries(block_slug, created_at, event_date)` vs `blocks.last_synthesized_at` | `033:148-157` |
| Unsorted footer + `/map-pending` list (D-06/D-07) | `timeline_entries WHERE block_slug='unsorted'` (+ `tag_confidence`, `id` as `entry:`) | `033:149-157` |
| Maturity canonical order (pill stage fill) | `economy_map.maturity` ENUM nascent→emerging→contested→consolidating→mature | `033:46-52` |

**Why the service_role read path (not anon) — D-09 evidence:** the anon RLS policy
`timeline_entries_anon_read` @ `033:373-376` is `USING (block_slug <> 'unsorted')` — anon **cannot
see `unsorted`**, but `/map-pending` must. So the wrapper reuses `service_role` + Accept-Profile
(gato_brain's `SUPABASE_KEY` is the service key, `:38`), kept read-only by construction (GET-only).
DB-level read-only role / RLS hardening is deferred to Phase 9.

---

## No Analog Found

None. Every new symbol maps to a concrete in-repo analog (gato_brain dispatch, processor PostgREST
read helpers, web maturity/tier renderer). RESEARCH.md fallback patterns are not required for this phase.

---

## Metadata

**Analog search scope:** `docker/gato_brain/gato_brain.py`, `docker/processor/agentpulse_processor.py`,
`docker/web/site/app.js`, `supabase/migrations/033_economy_map_schema.sql`
**Files scanned:** 4
**Pattern extraction date:** 2026-05-30
