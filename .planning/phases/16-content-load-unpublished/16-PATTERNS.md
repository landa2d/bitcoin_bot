# Phase 16: content-load-unpublished - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 3 (1 new script, 1 new migration, 1 new test)
**Analogs found:** 3 / 3 (all exact or strong role-matches)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/load_economy_map_content.py` | utility (standalone one-shot loader) | batch / file-I/O → CRUD-insert | `scripts/backfill_impact.py` (script shape) + `docker/processor/agentpulse_processor.py:3174` (insert path) | exact (replicate, not import) |
| `supabase/migrations/043_*.sql` | migration | structural DDL + seed | `033_economy_map_schema.sql` §4/§13 + `027` (CHECK relax) + `041` (own-track style) | exact |
| `tests/test_16_*.py` (negative-path) | test | transform/validation-gate | `tests/test_07_synthesis.py` lines 438-516, 690-700 | exact |

---

## Pattern Assignments

### `scripts/load_economy_map_content.py` (utility, batch → CRUD-insert)

**Primary analogs:**
- **Script skeleton + env/exit conventions** → `scripts/backfill_impact.py` (whole file).
- **The ~15-line insert function to REPLICATE (D-01 — copy, do NOT import)** → `economy_map_insert_block_body_version()` at `docker/processor/agentpulse_processor.py:3174-3203`.
- **Schema-READ helper to replicate for the D-07 anon snapshot + idempotency check** → `_economy_map_get()` at `:3088-3109`.
- **Idempotent skip-if-open-draft logic** → `block_has_open_draft()` at `:3124-3135`.

**Run posture (HOST-SIDE, not docker-exec).** The loader is a self-contained one-shot that needs only `SUPABASE_URL`/`SUPABASE_KEY` (from `config/.env`) + outbound HTTPS — it is NOT copied into the processor container (`docker/processor/Dockerfile` copies only `agentpulse_processor.py`; docker-compose mounts only `../data/openclaw/workspace` + `../config`, so there is NO `/scripts/` path inside the container and a docker-exec would fail with "can't open file"). Run it from the host:
```
source /root/bitcoin_bot/config/.env && python3 /root/bitcoin_bot/scripts/load_economy_map_content.py
```

**Standalone-script header + env-gate + `sys.exit(1)` fail-loud pattern** (`scripts/backfill_impact.py:1-30, 73-83`):
```python
#!/usr/bin/env python3
"""One-shot economy_map body loader. Run HOST-SIDE (not inside the container):
    source /root/bitcoin_bot/config/.env && python3 /root/bitcoin_bot/scripts/load_economy_map_content.py
"""
import yaml, os, sys, glob, httpx
# ...
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

def main():
    dry_run = "--dry-run" in sys.argv
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_KEY not set")
        sys.exit(1)
```
Note: `backfill_impact.py` uses `supabase-py` `.table().update()` — the loader must NOT. Per CLAUDE.md + P15-D-06 use **direct PostgREST httpx** (so `import httpx`, drop `from supabase import create_client`). Replicate the processor's `httpx` insert/read instead.

**Input discovery — pin the glob to the 8 numbered bodies.** `.planning/docs/` holds 11 `.md` files but only 8 are canonical bodies (`00-hub.md`..`07-psychology-disposition.md`). The other three — `EXECUTION_BRIEF.md`, `REDESIGN_BRIEF.md`, `economy-map-build-spec-v2.md` — have NO YAML frontmatter. A bare `glob("*.md")` would pick them up and (correctly, per D-04 validate-all) halt every live run with a misleading "validate_all failed". Pin the glob:
```python
DOCS_DIR = os.getenv("ECONOMY_MAP_DOCS_DIR", ".planning/docs")
paths = sorted(glob.glob(os.path.join(DOCS_DIR, "[0-9][0-9]-*.md")))  # 00-*..07-*, excludes the 3 briefs
# count gate on the default docs dir (the fixture-dir override may legitimately differ):
if DOCS_DIR == ".planning/docs" and len(paths) != 8:
    print(f"ERROR: expected exactly 8 numbered bodies, found {len(paths)}")
    sys.exit(1)
```

**The INSERT function to copy verbatim into the script** (`agentpulse_processor.py:3186-3203`) — keep the exact header dict, the `status`-omitted payload contract, and raise-on-non-2xx:
```python
resp = httpx.post(
    f"{SUPABASE_URL}/rest/v1/block_body_versions",
    headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
        "Content-Profile": "economy_map",   # WRITE profile header (D-01)
    },
    json=row,
    timeout=10,
)
if resp.status_code not in (200, 201):
    raise RuntimeError(
        f"economy_map block_body_versions insert failed ({resp.status_code}): {resp.text}"
    )
```
Payload `row` keys are EXACTLY `block_slug, body_md, proposed_maturity, synthesized_from_through, validator_report` — `status` intentionally OMITTED so the DB default `'draft'` applies (033:98). Never put `published_at`, `current_body_version_id`, or `maturity` in the payload (those are `blocks`/published columns, off-limits to this writer — autonomy boundary).

**The READ helper to copy for D-07 anon snapshot + skip-if-open-draft** (`agentpulse_processor.py:3094-3109`):
```python
resp = httpx.get(
    f"{SUPABASE_URL}/rest/v1/{table}",
    params=params,
    headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept-Profile": "economy_map",   # READ profile header (note: Accept- not Content-)
    },
    timeout=10,
)
if resp.status_code != 200:
    raise RuntimeError(f"economy_map {table} read failed ({resp.status_code}): {resp.text}")
rows = resp.json()
return rows if isinstance(rows, list) else []
```

**Skip-if-open-draft query shape** (`block_has_open_draft`, `:3131-3135`) — reuse exactly for the idempotent re-run posture (Claude's Discretion in CONTEXT):
```python
rows = _economy_map_get(
    "block_body_versions",
    {"block_slug": f"eq.{slug}", "status": "eq.draft", "select": "id", "limit": 1},
)
return bool(rows)
```

**Frontmatter parse contract (metadata source of truth).** The 8 `.md` files carry YAML frontmatter delimited by `---`/`---`. Two shapes:
- **Hub** (`.planning/docs/00-hub.md:1-7`): `slug, type: hub, title, subtitle, order` — **NO `tier`, NO `maturity`** (special-case per D-05). Body begins after the second `---`.
- **Block** (`.planning/docs/01-identity-trust.md:1-9`, `05-negotiation-coordination.md:1-8`): `slug, type: block, tier, title, subtitle, order, maturity`.

**The maturity remap (P15-D-01 / D-05) — apply BEFORE insert:**
```python
# building → emerging at load time (no ALTER TYPE). Only 01/02/03 carry maturity: building.
MATURITY_REMAP = {"building": "emerging"}
LIVE_MATURITY = {"nascent", "emerging", "contested", "consolidating", "mature"}  # 033:46-52
proposed_maturity = MATURITY_REMAP.get(raw_maturity, raw_maturity)
# hub special-case: no frontmatter maturity → proposed_maturity = "nascent" (blocks default; D-05)
```

**Pre-flight validate-ALL-then-insert gate (D-04/D-05) — the fail-loud spine of this script:**
- Parse + validate all 8 files first; collect failures; if ANY fail, `print` each + `sys.exit(1)` BEFORE a single POST.
- Per-file gate: `slug` present & in the locked roster; `title`; `subtitle`; (block) `tier` / (hub) `type=hub`; `order`; (block) `maturity`; **`body_md` non-empty after `.strip()`** (the DB `NOT NULL` does NOT reject `''` — see "Shared: empty-string-is-not-NULL"); **post-remap `proposed_maturity ∈ LIVE_MATURITY`**.
- Mirror the processor's raise-style (`ValueError`/`RuntimeError` with a specific message), but at script top-level convert to `print(...) + sys.exit(1)` so the operator sees a loud nonzero exit.

---

### `supabase/migrations/043_*.sql` (migration, structural DDL + seed)

**Primary analog:** `supabase/migrations/033_economy_map_schema.sql` (§4 `blocks` definition, §13 idempotent seed). Secondary: `027_x_content_candidates_narrative_type.sql` (the exact CHECK-relax idiom), `041_block_body_versions_unique_open_draft.sql` (own-approved-track / loud-header style), `040` (the in-schema `INSERT INTO economy_map.blocks`-adjacent write style).

**(a) Tier-CHECK relax to admit `'hub'`** — copy the `027` DROP-then-ADD idiom (`027:4-6`), adapted to the `blocks` table and the 3-tier set + `'hub'`:
```sql
ALTER TABLE economy_map.blocks DROP CONSTRAINT IF EXISTS blocks_tier_check;
ALTER TABLE economy_map.blocks ADD CONSTRAINT blocks_tier_check
  CHECK (tier IN ('substrate','behavior','frame','hub'));
```
(The original inline CHECK is `tier IN ('substrate','behavior','frame')` at `033:68`; Postgres auto-names it `blocks_tier_check`.)

**(b) Column contract for the two new `blocks` rows** (from `033:65-78`): required NOT NULL columns are `slug` (UNIQUE), `tier` (CHECK), `title`, `subtitle`, `accent` (`CHECK accent IN ('teal','purple','coral','gray')`), `sort_order` (UNIQUE), `live_tension` (NOT NULL), `maturity` (DEFAULT `'nascent'`). `live_tension` placeholder is `'TBD — set via /map-tension'` (033:73 / D-05 recommended default). Hub `accent` recommended `'gray'`; negotiation `accent` planner-picks (behavior tier uses purple/coral in seed).

**(c) Seed INSERT idiom** — copy the `033:402-415` shape (explicit column list, `::economy_map.maturity` cast, `ON CONFLICT (slug) DO NOTHING` so re-run never clobbers operator copy):
```sql
INSERT INTO economy_map.blocks
    (slug, tier, title, subtitle, accent, sort_order, live_tension, maturity)
VALUES
    ('agent-economy', 'hub', 'The Agent Economy', '...', 'gray', 0,
     'TBD — set via /map-tension', 'nascent'::economy_map.maturity),
    ('negotiation-coordination', 'behavior', 'Negotiation & Coordination', '...', '<accent>', 5,
     'TBD — set via /map-tension', 'nascent'::economy_map.maturity)
ON CONFLICT (slug) DO NOTHING;
```

**(d) Collision-free `sort_order` reshuffle (D-02)** — `sort_order` is `UNIQUE` (033:72), so the UPDATEs MUST run highest-first and BEFORE the negotiation insert lands at 5, or the UNIQUE constraint transiently collides:
```sql
-- highest-first, vacate slot 5 before inserting negotiation there
UPDATE economy_map.blocks SET sort_order = 8 WHERE slug = 'regulation-legal';          -- 7→8
UPDATE economy_map.blocks SET sort_order = 7 WHERE slug = 'psychology-disposition';     -- 6→7
UPDATE economy_map.blocks SET sort_order = 6 WHERE slug = 'governance-accountability';  -- 5→6
-- THEN insert negotiation at the now-vacant 5 (in the seed INSERT above)
```
`blocks` has **NO append-only trigger** (033 §8 triggers are on `block_body_versions` + `timeline_entries` only) — so these plain UPDATEs/INSERTs are permitted writes. Body *corrections* (LOAD-03) must NEVER be a raw UPDATE — use the canonical-body-rewrite path (new draft) — but that is the loader's job, not the migration's.

**(e) Migration header style** — copy the loud multi-line `--` comment block from `041:1-18` / `033:1-16`: state the phase, the D-decisions it lands, the atomicity guarantee, and WHY the reshuffle is highest-first. Wrap structure-discovery (constraint existence) in `DO $$ ... EXCEPTION` only if needed (033:119-138 precedent); the plain `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT` from `027` is sufficient here.

---

### `tests/test_16_*.py` (test, validation-gate / negative-path)

**Primary analog:** `tests/test_07_synthesis.py`. This file already exercises the exact fail-loud surfaces this phase needs: parse raises on empty/invalid input (438-462), the insert raises on non-2xx (503-516), and the orchestrator aborts loud + lands NOTHING (690-700). The deliberately-broken-fixture negative test (D-06) is structurally identical.

**Test-harness header (bare-env import of a standalone script, no pytest required)** — copy `test_07_synthesis.py:23-52` shape; for the loader script the import target is the script under `scripts/`, not the processor, but the stub/`sys.path.insert` idiom is the model:
```python
import json, os, sys, types
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
# stub libs imported at module level so the target imports in a bare env
for _name in ("schedule", "tweepy", "resend"):
    try: __import__(_name)
    except Exception: sys.modules[_name] = types.ModuleType(_name)
sys.path.insert(0, str(_ROOT / "scripts"))
import load_economy_map_content as loader  # noqa: E402
```

**The "raises on broken input" assertion idiom** (`test_07_synthesis.py:438-462`) — flag/try/except/assert, the codebase's standard (no `pytest.raises`):
```python
def test_load_halts_on_empty_body():
    raised = False
    try:
        loader.validate_all(fixtures_with_one_empty_body)   # the pre-flight gate (D-04)
    except (ValueError, SystemExit, RuntimeError):
        raised = True
    assert raised, "must halt loud on an empty body_md"
```

**The "lands NOTHING because the VALIDATION gate fired" assertion idiom** (`test_07_synthesis.py:690-700`, `test_poller_aborts_loud_on_missing_key`) — stub `httpx.post`, run, assert zero POSTs captured. This is the D-06 "lands nothing" proof. CRITICAL fix vs. a naive version: set DUMMY env vars first so the env-gate (`sys.exit(1)` on missing `SUPABASE_*`) does NOT short-circuit — otherwise the empty-POST assertion passes for the wrong reason (env-gate, not validation-gate). With dummy env set, `validate_all` is actually reached against the broken fixture, proving the load landed nothing BECAUSE the validation gate halted it:
```python
def test_load_lands_nothing_when_gate_fires(monkeypatch):
    # dummy env so the env-gate PASSES and validate_all is the gate that fires:
    monkeypatch.setenv("SUPABASE_URL", "http://fake")
    monkeypatch.setenv("SUPABASE_KEY", "fake")
    captured = {"posts": []}
    monkey_post = loader.httpx.post
    loader.httpx.post = lambda url, **kw: captured["posts"].append(url)
    raised = False
    try:
        try: loader.main()  # DOCS_DIR pointed at a broken fixture dir (one 00-/01- .md w/ empty body)
        except (SystemExit, ValueError, RuntimeError): raised = True
    finally:
        loader.httpx.post = monkey_post
    assert raised, "the validation gate must fire on the broken fixture"
    assert captured["posts"] == [], "no INSERT POSTs when any input fails the gate (D-04/D-06)"
```

**Insert-shape / non-2xx-raises analogs** (`test_07_synthesis.py:468-516`) — if the test also asserts the loader's replicated insert is shaped correctly: assert the URL ends `/block_body_versions`, `Content-Profile == "economy_map"`, `status` absent from the body, and forbidden keys (`published_at`, `current_body_version_id`, `maturity`) absent.

---

## Shared Patterns

### Direct PostgREST schema isolation (NEVER supabase-py `.in_()`)
**Source:** `agentpulse_processor.py:3088-3109` (read), `:3174-3203` (write); CLAUDE.md constraint.
**Apply to:** the loader (all reads + the insert) and the D-07 snapshot.
- READ → header `Accept-Profile: economy_map`.
- WRITE → header `Content-Profile: economy_map`.
- Both raise `RuntimeError` on non-2xx (a read failure must never be mistaken for "no rows"). Never `supabase.table(...).in_(...)` against `economy_map` (silent failure).

### Fail-loud governance
**Source:** `scripts/backfill_impact.py:76-81` (`sys.exit(1)` on missing env), `agentpulse_processor.py:3091-3092, 3198-3201` (raise on non-2xx), MEMORY `feedback_fail_loud_governance`.
**Apply to:** the loader's env gate, the input-count gate (exactly 8 numbered bodies), the pre-flight validate-all gate (D-04), and every PostgREST call.
- Missing input / wrong body count / blank body / out-of-enum maturity → halt the whole batch BEFORE any insert; never silently default to a no-op or partial load.
- Negative-test note: prove the load is stopped by the VALIDATION gate (set dummy env so the env-gate passes), not by a missing-env short-circuit.

### Empty-string-is-not-NULL guard
**Source:** CONTEXT D-05; `block_body_versions.body_md TEXT NOT NULL` (033:97) accepts `''`.
**Apply to:** the loader's body gate.
- The DB `NOT NULL` does NOT reject `''`/whitespace — the loader MUST explicitly reject `body_md.strip() == ""`. Same logic the `parse_synthesis_output` empty-body test guards (`test_07_synthesis.py:438-444`).

### Append-only boundary (which writes are permitted where)
**Source:** `033 §8` (triggers on `block_body_versions` + `timeline_entries`, NONE on `blocks`); CONTEXT code_context.
**Apply to:** migration `043` (permitted plain UPDATE/INSERT on `blocks`) vs. the loader (only ever INSERTs new `block_body_versions` drafts; never UPDATEs a body — canonical-body-rewrite only).

### Idempotency / safe re-run
**Source:** `041` UNIQUE-open-draft index (raises 23505), `block_has_open_draft()` (`:3124`), `033:415` `ON CONFLICT (slug) DO NOTHING`.
**Apply to:** migration `043` (seed via `ON CONFLICT DO NOTHING`; structure via `IF NOT EXISTS` / `DROP ... IF EXISTS`) and the loader (skip-if-open-draft fast-path, with the `041` UNIQUE index as the structural backstop).

---

## No Analog Found

None. All three artifacts have strong in-repo analogs. The only adaptation gaps the planner must bridge (not missing analogs, just deltas):
- `scripts/backfill_impact.py` uses `supabase-py` writes — the loader must swap to direct PostgREST httpx (analog for that is the processor, not the script). The script provides the *skeleton*; the processor provides the *I/O*.
- No prior migration relaxes `blocks_tier_check` specifically — `027` provides the generic CHECK-relax idiom on a different table; the planner applies it to `economy_map.blocks`.

## Metadata

**Analog search scope:** `supabase/migrations/`, `tests/`, `scripts/`, `docker/processor/agentpulse_processor.py` (lines 3080-3300), `.planning/docs/*.md` (frontmatter).
**Files scanned:** ~12 (3 migrations read in full, 2 test files inspected, 1 script read in full, 3 doc frontmatters, 1 processor section).
**Pattern extraction date:** 2026-06-08
</content>
