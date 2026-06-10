# Phase 18: Gated Batch Publish - Pattern Map

**Mapped:** 2026-06-09
**Files analyzed:** 3 (2 new scripts, 1 modified frontend file)
**Analogs found:** 3 / 3 (all exact / role-match — every work product has a named, located analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/publish_economy_map_batch.py` (NEW) | utility / one-shot script | batch (read-validate-then-RPC-loop) | `scripts/load_economy_map_content.py` (publish RPC shape from `gato_brain.py` `_economy_map_rpc` / `handle_map_approve`) | exact (script idiom) + exact (RPC shape) |
| `docker/web/site/app.js` — `loadHub`/`renderHub` (MODIFIED) | component (frontend render) | request-response (fetch published body, render) | `loadBlock` published-body path (same file, `:671-677`) | exact (same-file sibling path) |
| `scripts/verify_economy_map_publish.py` *or* extend `scripts/verify_economy_map_crosslinks.py` (NEW/MODIFIED) | test / verification harness | request-response (anon read, fail-loud assert) | `scripts/verify_economy_map_crosslinks.py` (fail-loud PostgREST harness) | exact (direct adaptation) |

Note on the verification file (D-05, planner's call per CONTEXT `<decisions>`): either extend the existing crosslinks harness to read the PUBLISHED set, or add a sibling `verify_economy_map_publish.py`. Both reuse the same PostgREST + Accept-Profile idiom below. The key difference vs the existing harness: D-05 reads with the **anon key** (no service_role, no preview flag) so it proves what a real visitor sees — the existing harness reads drafts with service_role.

---

## Pattern Assignments

### `scripts/publish_economy_map_batch.py` (NEW — utility, batch)

**Analogs:** `scripts/load_economy_map_content.py` (whole-script idiom) + `docker/gato_brain/gato_brain.py` `_economy_map_rpc` (`:1636-1669`) and `handle_map_approve` (`:2047-2096`) for the RPC call shape.

This script has two pattern sources because it does two things the loader did not combine: it READS the open drafts (loader idiom) and it WRITES via the publish RPC (gato_brain idiom). Copy the structure of the loader for env-load / discover / validate-all-then-act / idempotent-skip / fail-loud, and copy the RPC POST shape from `_economy_map_rpc`.

**Config + env block** — copy from `load_economy_map_content.py` `:36-81` and `verify_economy_map_crosslinks.py` `:46-99` (env self-load):
```python
SUPABASE_URL = os.getenv("SUPABASE_URL")
# service_role: drafts are RLS-invisible to anon AND publish_block_version is GRANTed
# to service_role only (mig 039:82). Prefer explicit SERVICE_KEY, fall back to KEY.
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

# The 8 in-scope slugs — hub LAST per D-07 (publish blocks first, hub last).
# regulation-legal is EXPLICITLY excluded (P15-D-02, D-06).
PUBLISH_ORDER = [
    "identity-trust",
    "memory-context",
    "payments-settlement",
    "autonomy-control",
    "negotiation-coordination",
    "governance-accountability",
    "psychology-disposition",
    "agent-economy",          # the hub — LAST (D-07)
]
```
(The loader's `LOCKED_ROSTER` / `SOURCE_SLUGS` are the same 8 slugs — reuse the membership, but order matters for D-07.) If running the script host-side from the repo root, copy the `_load_env_file()` self-loader from `verify_economy_map_crosslinks.py` `:61-99` so a bare `python3 scripts/...` works (the loader requires `source config/.env` first; the harness self-loads — match the harness for the plan `<automated>` gate).

**READ idiom — resolve the open drafts (D-06 step 1, D-08 pre-flight)** — copy `_economy_map_get` from `load_economy_map_content.py` `:87-109` (identical to `verify_economy_map_crosslinks.py` `:141-166` and `gato_brain.py` `:1583-1605`). The READ header is `Accept-Profile` (never `Content-Profile`):
```python
def _economy_map_get(table: str, params: dict) -> list:
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept-Profile": "economy_map",   # READ profile — NOT Content-Profile
        },
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"economy_map {table} read failed ({resp.status_code}): {resp.text}"
        )
    rows = resp.json()
    return rows if isinstance(rows, list) else []
```
To resolve each slug's open draft `id` + `proposed_maturity` for the manifest, mirror `verify_economy_map_crosslinks.py::fetch_draft_body` `:189-209` (per-slug `eq.` filter, `status=eq.draft`, `limit=1` — **never** `.in_()`, CLAUDE.md). Select `id,proposed_maturity` instead of `body_md`:
```python
rows = _economy_map_get(
    "block_body_versions",
    {"block_slug": f"eq.{slug}", "status": "eq.draft",
     "select": "id,proposed_maturity", "order": "created_at.desc", "limit": 1},
)
```
For the maturity-transition manifest column (old maturity), read `blocks.maturity` per slug exactly as `gato_brain.py::get_block_by_slug` `:1697-1716`.

**Pre-flight validate-ALL-then-act (D-08)** — copy the `validate_all` → raise-once → nonzero-exit shape from `load_economy_map_content.py` `:218-296` and `:332-349`. The Phase-18 version asserts all 8 expected open drafts EXIST and resolve before publishing anything; collect ALL misses, raise once, exit nonzero:
```python
# D-08 pre-flight: every expected slug must resolve to exactly one open draft.
missing = [s for s in PUBLISH_ORDER if s not in resolved]   # resolved: slug -> version_id
if missing:
    print(f"ERROR: pre-flight failed — no open draft for: {missing}. "
          f"Halting BEFORE publishing anything (no partial pass).")
    sys.exit(1)
```

**Single operator-approval gate + manifest** (D-06 step 2, Claude's Discretion on format) — print the manifest (`slug → version_id → proposed_maturity`, with old→new maturity) for the ONE approval. The orchestrator surfaces the gate in-chat (mirrors the Phase-16 loader / migration-apply pattern; see CONTEXT `<decisions>` D-06 closing note). A `--dry-run` flag that prints the manifest + skips all POSTs mirrors `load_economy_map_content.py` `:333,361-363`.

**WRITE idiom — loop the existing publish RPC (D-06 step 3, D-07 ordering)** — copy the POST shape from `gato_brain.py::_economy_map_rpc` `:1636-1669`. WRITE uses `Content-Profile` (NOT `Accept-Profile`), the `/rpc/<fn>` endpoint, and `json=params` (never URL-interpolated). The RPC returns void → check `(200, 204)`:
```python
def _economy_map_rpc(fn: str, params: dict) -> httpx.Response:
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Content-Profile": "economy_map",   # WRITE profile
        },
        json=params,
        timeout=10,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"economy_map rpc {fn} failed ({resp.status_code}): {resp.text}"
        )
    return resp
```
The call shape per version (from `handle_map_approve` `:2075`):
```python
_economy_map_rpc("publish_block_version", {"p_version_id": version_id})
```
Loop it over `PUBLISH_ORDER` (blocks first, hub last — D-07).

**Idempotency + fail-loud halt-and-report (D-08)** — copy the already-actioned-marker handling from `handle_map_approve` `:2076-2082` together with the loader's mid-batch fail-loud-on-error pattern (`load_economy_map_content.py` `:353-373`). The RPC RAISEs `version % not found or not in draft status` (mig 039:59) on a non-draft version; the marker constant is `_RPC_ALREADY_ACTIONED = "not found or not in draft status"` (`gato_brain.py` `:2021`). Treat that match as SKIP/success (idempotent re-run completes a halted batch); any OTHER RuntimeError → HALT immediately, report which slugs succeeded / which failed, `sys.exit(1)` (never continue silently — MEMORY: fail_loud_governance):
```python
published, skipped = [], []
for slug in PUBLISH_ORDER:                       # blocks first, hub LAST (D-07)
    version_id = resolved[slug]
    try:
        _economy_map_rpc("publish_block_version", {"p_version_id": version_id})
        published.append(slug)
        print(f"PUBLISHED {slug} ({version_id})")
    except RuntimeError as e:
        if "not found or not in draft status" in str(e):
            skipped.append(slug)                 # already published → idempotent skip
            print(f"SKIP {slug}: already published (idempotent re-run)")
            continue
        # any other failure: HALT — report succeeded/failed, never partial-pass silently
        print(f"HALT at {slug}: {e}\n  published so far: {published}\n  remaining: ...")
        sys.exit(1)
```

**RPC contract the script relies on (read, do not rebuild)** — `economy_map.publish_block_version(p_version_id uuid)`, mig `039_publish_block_version_watermark_null_guard.sql` `:33-79`: atomic draft→published flip (`:49-55`), typed RAISE on non-draft (`:58-60` — the idempotency signal), supersede prior published for the block (`:63-67`), point `blocks.current_body_version_id` + sync `maturity := proposed_maturity` + advance watermark (`:73-77`). `GRANT EXECUTE ... TO service_role` only (`:82`) — hence the service_role key requirement above.

---

### `docker/web/site/app.js` — `loadHub` / `renderHub` (MODIFIED — component, request-response)

**Analog:** the `loadBlock` published-body path in the SAME file, `:671-677`. The new prod hub path must MIRROR this fetch-by-`current_body_version_id` shape, independent of `PREVIEW_ENABLED`.

**The published-body fetch to mirror** (`loadBlock`, `:671-677`):
```javascript
// Published body (D-10 / D-17) — unchanged prod path. NO .eq('status','published');
// RLS exposes only published versions to anon.
if (!bodyMd && blockRes.data.current_body_version_id) {
    var bodyRes = await sb.schema('economy_map').from('block_body_versions')
        .select('body_md').eq('id', blockRes.data.current_body_version_id).single();
    if (!bodyRes.error && bodyRes.data) bodyMd = bodyRes.data.body_md;
}
```
Note: `sb.schema('economy_map')` sets `Accept-Profile` automatically (D-16); NO defensive `.eq('status','published')` (D-17 — RLS is the boundary); `.eq('id', current_body_version_id).single()`.

**Where to add the new prod hub fetch** — in `loadHub` (`:449-518`). The hub row's `current_body_version_id` is ALREADY in the `loadHub` select (`:461`). Today the only hub-body fetch is the Phase-17 PREVIEW-only draft fetch (`:478-488`), which stays flag-gated and UNCHANGED (D-01). Add a NEW, flag-INDEPENDENT path that, when `data[0].current_body_version_id` (the `agent-economy` row) is non-null, fetches its published body by id — mirroring `:671-677`. Pattern to add (the hub row is `data.find(b => b.slug === 'agent-economy')`):
```javascript
// D-01: prod published-hub-body fetch — mirrors loadBlock :674-677, NOT flag-gated.
// Null current_body_version_id (pre-publish) → leaves hubBodyMd null → HUB_STORYLINE
// fallback in renderHub (visual no-op until the Phase-18 publish batch runs → D-04).
var hubRow = data.find(function (b) { return b.slug === 'agent-economy'; });
if (!hubBodyMd && hubRow && hubRow.current_body_version_id) {
    var hubBodyRes = await sb.schema('economy_map').from('block_body_versions')
        .select('body_md').eq('id', hubRow.current_body_version_id).single();
    if (!hubBodyRes.error && hubBodyRes.data) hubBodyMd = hubBodyRes.data.body_md;
}
```
Order it so the existing PREVIEW draft fetch (`:478-488`) still takes precedence in preview (draft preview unchanged), and the published path fills `hubBodyMd` when no draft was taken — exactly the precedence `loadBlock` uses (draft first at `:655-669`, published fallback at `:671-677`). IMPORTANT: the `loadHub` select at `:461` queries `.from('blocks')` for all rows; confirm the `agent-economy` hub row is returned by that select. If the hub row is NOT in the `blocks` select result (e.g. filtered by tier/sort_order), the planner must add a small dedicated hub-row read — but the simplest correct shape is the `data.find` above against the existing result set.

**Trim + render the published hub article (D-02)** — reuse `trimHubBody()` (`:74-85`) and the existing render fork at `renderHub` `:594-597` VERBATIM. It already does exactly what D-02 needs (trim the duplicative Tier-1/Tier-2 prose pillar-list; fall back to `HUB_STORYLINE` when no body):
```javascript
var trimmedHubBody = trimHubBody(hubBodyMd);
var hubIntroHtml = trimmedHubBody
    ? '<div class="hub-storyline">' + marked.parse(trimmedHubBody) + '</div>'
    : '<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>';
```
No change needed here — once `hubBodyMd` is populated by the new prod fetch, this fork renders the trimmed published article; when null (pre-publish), it renders the `HUB_STORYLINE` constant (`:32`) — the graceful pre-publish fallback D-02 requires (NOT deleted).

**Deploy-first no-op proof (D-04)** — the change is a visual no-op until publish because `agent-economy.current_body_version_id` is NULL pre-publish (→ `hubBodyMd` stays null → `HUB_STORYLINE`), and anon RLS exposes only published versions. This is the same DOUBLE-SAFE reasoning the Phase-17 preview comment documents at `:48-60` / `:473-477`. Keep `PREVIEW_ENABLED` (`:57-60`) and the preview draft fetch (`:478-488`, `:498-515`) untouched.

---

### `scripts/verify_economy_map_publish.py` (NEW) — or extend `verify_economy_map_crosslinks.py` (test, request-response)

**Analog:** `scripts/verify_economy_map_crosslinks.py` (whole-script fail-loud harness). The D-05 check is a near-direct adaptation: read the PUBLISHED set with the **anon key** (no service_role, no preview flag — D-05), assert (a) all 8 in-scope bodies are `status='published'`, (b) the hub renders its published article (its `blocks.current_body_version_id` is non-null and its published body resolves), (c) every `#/map/<slug>` cross-link resolves against PUBLISHED content, (d) the published-block count is 2 → 8 (+ hub). Fail loud (nonzero exit) on any miss.

**Env self-load + anon key** — copy `_load_env_file` from `verify_economy_map_crosslinks.py` `:61-99` so a bare `python3 scripts/...` works for the plan `<automated>` gate. The KEY change from the existing harness: D-05 reads with the **anon** key, not service_role:
```python
# D-05: prove what a real visitor sees — anon key, no service_role, no preview.
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")   # NOT SUPABASE_SERVICE_KEY
```

**READ idiom (anon)** — copy `_economy_map_get` from `verify_economy_map_crosslinks.py` `:141-166` verbatim (it is header-agnostic to which key is passed; `Accept-Profile: economy_map`, raises on non-2xx). With the anon key, RLS returns ONLY `status='published'` body versions (033:367-370) — so a body that fails to publish simply won't come back, which the assertions below catch fail-loud.

**Published-set assertions (D-05)** — adapt `fetch_roster` `:169-186` (empty-result → fail loud, never vacuous-pass) and `fetch_draft_body` `:189-209` (per-slug `eq.` read — change `status=eq.draft` to read the PUBLISHED body, or just verify `blocks.current_body_version_id` resolves to a published body for each of the 8 slugs). Count check: assert anon-visible published-block count is 8 (hub + 7), up from 2 (`identity-trust`, `governance-accountability` were the only published blocks pre-phase per CONTEXT `<code_context>`). Collect ALL failures, print each, `sys.exit(1)` if any — exactly the `run_crosslink_check` accumulate-then-fail-loud shape at `:224-312` (`missing_bodies`, `misses`, final summary print).

**Cross-link-against-published (D-05c)** — the existing `run_crosslink_check` (`:224-312`) extracts `#/map/<slug>` targets (`extract_targets` `:215-221`, `CROSSLINK_RE` `:135`) and asserts membership in the live roster. For D-05, the roster read (`fetch_roster` `:177`) stays — but the body reads must hit the PUBLISHED bodies (anon), and the assertion is that every target resolves to a slug whose published body the anon key can actually load (not just an in-roster slug). Reuse the regex + the fail-loud accumulation verbatim.

**Reuse-vs-extend decision (Claude's Discretion, D-05)** — extending the existing harness risks coupling the draft-read service_role path with the new anon published path. A clean separate `verify_economy_map_publish.py` (anon, published-only) is the lower-risk default; the planner decides. Either way, the PostgREST + Accept-Profile + per-slug-`eq.` + accumulate-then-fail-loud patterns above are the copy source. Do NOT use `.in_()` (CLAUDE.md / P15-D-06: silent-fails against economy_map).

---

## Shared Patterns

### PostgREST READ idiom (direct httpx + Accept-Profile)
**Source:** `scripts/load_economy_map_content.py` `:87-109` ≡ `scripts/verify_economy_map_crosslinks.py` `:141-166` ≡ `docker/gato_brain/gato_brain.py::_economy_map_get` `:1583-1605` (all three identical)
**Apply to:** the batch script's draft-resolution reads + the verification harness's published-set reads
- `Accept-Profile: economy_map` header (READ). Per-key filters use PostgREST `eq.` (`{"block_slug": f"eq.{slug}"}`). NEVER `.in_()` / supabase-py array-membership (silent-fails — CLAUDE.md). Raise RuntimeError on any non-2xx so a read failure is never mistaken for "no rows".

### PostgREST WRITE / RPC idiom (direct httpx + Content-Profile + /rpc/)
**Source:** `docker/gato_brain/gato_brain.py::_economy_map_rpc` `:1636-1669`; call shape at `handle_map_approve` `:2075`
**Apply to:** the batch publish script's per-version publish loop
- `Content-Profile: economy_map` header (WRITE, NOT Accept-Profile), `/rest/v1/rpc/<fn>` endpoint, `json=params` (values never URL-interpolated). RPC returns void → check `(200, 204)`. Call: `_economy_map_rpc("publish_block_version", {"p_version_id": version_id})`.

### Fail-loud, validate-all-then-act, idempotent re-run
**Source:** `scripts/load_economy_map_content.py` `:218-296` (validate-all → raise once), `:353-373` (mid-batch fail-loud), `:356-358` (idempotent skip); `gato_brain.py` `:2021` + `:2076-2082` (already-actioned marker); migration `039:58-60` (typed RAISE)
**Apply to:** the batch publish script (D-08) and the verification harness (D-05)
- Pre-flight: collect ALL failures across the batch, raise once, exit nonzero BEFORE any write (no partial pass). The publish RPC's typed RAISE `"not found or not in draft status"` (matched as a substring) is the idempotency signal — already-published → SKIP/success on re-run; any OTHER error → HALT and report succeeded/failed. MEMORY: fail_loud_governance — never silently default to a no-op or partial pass.

### supabase-js schema-scoped read (frontend)
**Source:** `docker/web/site/app.js::loadBlock` `:674-677`, `loadHub` `:458-462`
**Apply to:** the new prod hub published-body fetch
- `sb.schema('economy_map')` sets `Accept-Profile` automatically (D-16). NO defensive `.eq('status','published')` — anon RLS is the boundary (D-17). Fetch by `.eq('id', current_body_version_id).single()`.

### Service_role-leak guard (web-deploy path)
**Source:** `scripts/verify_economy_map_crosslinks.py::run_svc_role_guard` `:367-474` + `WEB_DEPLOY_PATH_FILES` `:345-351`
**Apply to:** still relevant this phase — the `app.js` change ships through the scoped `agentpulse-web` rebuild. The guard asserts `docker/web/site/app.js` keeps `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders (entrypoint.sh sed-substitutes at container start — MEMORY: web_static_preview_substitution) and the service_role key ships in NONE of the web-deploy-path files. The planner may reuse `--guard-only` as a deploy safety gate before the scoped rebuild. DEF-17-01 pre-existing leak in `.claude/settings.local.json` stays out of scope (operator rotation decision).

---

## No Analog Found

None. All three Phase-18 work products have a located, exact analog in the existing codebase.

---

## Metadata

**Analog search scope:** `scripts/` (standalone economy_map scripts), `docker/gato_brain/gato_brain.py` (RPC call surface), `docker/web/site/app.js` (hub/block render), `supabase/migrations/039_*.sql` (publish RPC contract)
**Files scanned:** 4 read in full / targeted; 2 grep-located (gato_brain helper line ranges, app.js function offsets)
**Pattern extraction date:** 2026-06-09
**Constraints honored:** no `.in_()` against economy_map (CLAUDE.md); no agent-service changes (v2.1); scoped `agentpulse-web` rebuild as the only deploy path; READ=Accept-Profile / WRITE=Content-Profile; reuse the existing `publish_block_version` RPC (never raw UPDATE); fail-loud governance.
