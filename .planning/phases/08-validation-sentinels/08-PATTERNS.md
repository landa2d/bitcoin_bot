# Phase 8: Validation Sentinels - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 3 (2 modified source, 1 modified test)
**Analogs found:** 3 / 3 (all analogs are in-file Phase 7 siblings — exact role + data-flow matches)

This phase MODIFIES existing Phase 7 code; it creates no new files. Every analog is a
sibling function in the same module, so "copy the pattern from X lines N-M" is literal:
match the surrounding code's style, headers, and fail-loud conventions exactly.

## File Classification

| Modified File / Symbol | Role | Data Flow | Closest Analog | Match Quality |
|------------------------|------|-----------|----------------|---------------|
| `run_sentinels(...)` (NEW helper in processor) | utility / pure-compute primitive | transform (body+block→dict) | `assemble_synthesis_input` / `parse_synthesis_output` (processor) | exact (sibling primitive) |
| `synthesize_block` (processor) | service / orchestration step | request-response (Sonnet→parse→sentinels→INSERT) | itself (Phase 7); insert call already present | exact |
| `parse_synthesis_output` (processor) | utility / parser | transform | itself (remove WR-02 raise only) | exact |
| `economy_map_insert_block_body_version` (processor) | service / DB writer | CRUD (INSERT, PostgREST) | itself; payload extension only | exact |
| `fetch_current_block_body` (processor) | service / DB reader | CRUD (GET) | itself; reuse as-is for length floor | exact (reuse, no change) |
| `handle_map_pending` (gato_brain) | controller / renderer | request-response (read-only render) | `handle_map_status` (gato_brain) | exact (sibling renderer) |
| `get_draft_versions` (gato_brain) | service / DB reader | CRUD (GET) | itself; extend `select` to add `validator_report` | exact |
| `test_parse_output_raises_on_missing_skeleton` → VLDT-04 test (tests) | test | n/a | sibling parse tests + `_install_post_stub` poller tests | exact |

## Pattern Assignments

### `run_sentinels(...)` — NEW pure-compute helper (utility, transform)

**Analog:** `parse_synthesis_output` (processor lines 3329-3354) and
`assemble_synthesis_input` (processor lines 3254+). Both are Phase 7 "primitives":
top-level `def`, snake_case, a docstring that cites the decision IDs it implements,
no class, return a plain `dict`. The new helper MUST match this primitive style
(per D-09 / CONTEXT: "one composable helper is the natural fit, mirroring the
Phase 7 primitives style").

**Primitive shape to copy** (note the decision-ID-citing docstring convention,
processor lines 3329-3338):
```python
def parse_synthesis_output(text: str) -> dict:
    """Parse the Sonnet output into {body_md, proposed_maturity}; fail-loud on invalid (D-12).
    ...docstring cites the D-IDs and the WHY...
    """
    parsed = json.loads(_clean_json_response(text))
    body_md = (parsed.get("body_md") or "").strip()
    ...
    return {"body_md": body_md, "proposed_maturity": maturity}
```

**Recommended signature** (from CONTEXT D-09):
`run_sentinels(body_md, prior_body_md, block, proposed_maturity) -> dict`
returning the `validator_report` dict.

**Inputs already available in the codebase (reuse, do not recompute):**
- `SYNTH_SKELETON_HEADINGS` (processor lines 3041-3048) — the 6-heading list. Structure
  sentinel (VLDT-04): `structure_missing = [h for h in SYNTH_SKELETON_HEADINGS if h.lower() not in body_md.lower()]`. This is the EXACT idiom currently at processor line 3351 (the `missing` computation) — lift it into the sentinel.
- `SYNTH_MATURITY_ENUM` (processor line 3038) — **CAUTION: it is a `set`, not an ordered
  list.** VLDT-03 needs ORDINAL distance. The comment at line 3037 documents the canonical
  order `nascent→emerging→contested→consolidating→mature`. The planner must define an
  ordered sequence (e.g. a module-level `SYNTH_MATURITY_ORDER` list or reuse the order in
  the comment) — do NOT call `.index()` on the set. Then
  `maturity_jump = abs(order.index(proposed_maturity) - order.index(block["maturity"]))`.
- live-tension extraction (VLDT-01, D-05): scan `body_md` for the `## The live tension`
  heading (it is `SYNTH_SKELETON_HEADINGS[2]`), take the section body up to the next `##`.
  Per "Claude's Discretion" in CONTEXT, a simple `## <heading>` line scanner is expected.

**Length floor (VLDT-02, D-06):** `len(new_body) / len(prior_body) < 0.60`. Cold-start
guard mirrors `fetch_current_block_body` returning `None` (processor lines 3152-3166):
when `prior_body_md is None`, the length sentinel is N/A — emit no flag (do NOT divide).

**Placeholder / verbatim-echo detection (VLDT-01, D-05):** the seed placeholder is
`'TBD — set via /map-tension'` (migration 033, line ~395 / line 73 comment) — NOT
`(no live_tension set yet)` as the CONTEXT prose loosely wrote. Detect both the placeholder
string AND a verbatim echo of `block["live_tension"]` (`fetch_economy_map_blocks` already
selects `live_tension`, processor line 3115; the block dict passed into `synthesize_block`
carries it).

**Fail-loud-but-never-block (VLDT-05, CONTEXT code_context "Fail-loud"):** the helper must
NOT raise on a per-sentinel computation error — that would block the draft, violating
VLDT-05. Wrap each sentinel (or the whole helper body) in try/except, log loudly with
`exc_info=True` (the project logging convention, see processor `load_synth_identity`
lines 3078-3080), and record the failure as a key in the report (e.g. `sentinel_errors`)
so the draft still lands with visible evidence. This is the inverse of
`parse_synthesis_output`'s fail-loud-and-skip — here it is fail-loud-and-still-draft.

**`requires_attention` rollup (D-04):**
```python
requires_attention = (
    (not tension_preserved)
    or length_below_floor
    or (maturity_jump > 1)
    or bool(structure_missing)
)
```

---

### `parse_synthesis_output` (processor lines 3329-3354) — REMOVE the WR-02 raise (D-01)

**Change:** delete lines 3348-3353 (the skeleton-missing raise block) AND the
clause "OR on a body_md missing any of the six required RNDR-02 skeleton sections"
from the docstring (lines 3334-3337). Keep the empty-body raise (3342-3343), the
invalid-maturity raise (3344-3347), and the missing-maturity path. The `missing`
computation logic is not deleted but RELOCATED into `run_sentinels` (VLDT-04).

**Exact block to remove** (processor lines 3348-3353):
```python
    # The six-part skeleton is a hard output contract (synth_identity.md + RNDR-02); a body that
    # drops or renames headings must be skipped, not drafted malformed for the operator to catch.
    _body_lower = body_md.lower()
    missing = [h for h in SYNTH_SKELETON_HEADINGS if h.lower() not in _body_lower]
    if missing:
        raise ValueError(f"body_md missing required skeleton sections: {missing}")
```

---

### `economy_map_insert_block_body_version` (processor lines 3169-3196) — payload extension

**Analog:** itself. The writer is intentionally tight (comment lines 3170-3177:
"A SECOND purpose-scoped writer... Payload keys are exactly..."). The function body
does not enumerate keys — it forwards `row` as `json=row` (line 3188). So NO change to
the function body is needed; the new key flows through. BUT:

1. Update the docstring (lines 3173-3174): it currently states "Payload keys are exactly
   block_slug, body_md, proposed_maturity, synthesized_from_through" — add `validator_report`.
2. The CALLER (`synthesize_block`, lines 3477-3482) is where `validator_report` is added to
   the payload dict.

**Caller call-site to extend** (processor lines 3477-3482):
```python
        inserted = economy_map_insert_block_body_version({
            "block_slug": slug,
            "body_md": parsed["body_md"],
            "proposed_maturity": parsed["proposed_maturity"],
            "synthesized_from_through": run_through,
            # NEW: validator_report computed by run_sentinels (D-02 — written atomically
            # at INSERT because the append-only trigger RAISES on any post-insert change).
        })
```

**PostgREST conventions already correct (do not touch):** headers carry
`Content-Profile: economy_map` (line 3186), `status` is omitted so the DB default
`'draft'` applies, non-2xx raises (lines 3191-3194). `validator_report` is a `jsonb`
column (`NOT NULL DEFAULT '{}'`, migration 033 line 102) — pass it as a plain Python dict
under `json=`; httpx serializes it to a JSON object PostgREST accepts.

---

### `synthesize_block` (processor lines 3425-3493) — wire sentinels between parse and INSERT (D-02)

**Analog:** itself. Insert the sentinel call inside the existing post-eligibility
`try` block (lines 3469-3484), AFTER `parse_synthesis_output` (line 3473) and BEFORE the
INSERT (line 3477). Both `prior_body_md` (line 3470, already fetched for the Sonnet input)
and `block` are already in scope — reuse `prior_body_md` directly for the length floor
(no second `fetch_current_block_body` call).

**Insertion point** (between current lines 3473 and 3475):
```python
        parsed = parse_synthesis_output(raw)

        # NEW (Phase 8): sentinels compute the validator_report BEFORE the INSERT —
        # the append-only trigger forbids annotating after the row lands (D-02).
        validator_report = run_sentinels(
            parsed["body_md"], prior_body_md, block, parsed["proposed_maturity"]
        )

        run_through = datetime.now(timezone.utc).isoformat()
        inserted = economy_map_insert_block_body_version({
            ...
            "validator_report": validator_report,
        })
```

**GATE-01 invariant (CONTEXT code_context):** this stays draft-only. The sentinel
addition writes ONLY into the new draft's payload — it must not touch `blocks.maturity`,
`blocks.current_body_version_id`, or any published row. No new PostgREST verb is added.

---

### `handle_map_pending` (gato_brain lines 1773-1830) — flag rendering (D-08, VLDT-06)

**Analog:** `handle_map_status` (gato_brain lines 1730-1770) — the sibling renderer.
Both are sync `def -> str`, build a `lines: list[str]`, and `return "\n".join(lines)`.
`handle_map_status` shows the maturity-pill + per-block-segment building pattern and the
`maturity_pill()` helper (lines 1570-1579) for the maturity direction display in D-08.

**Current per-draft rendering to extend** (gato_brain lines 1799-1803):
```python
        for slug in sorted(by_slug):
            lines.append(f" · {slug}")
            for v in by_slug[slug]:
                vid = v.get("id") or "?"
                lines.append(f"   version: {vid}  →  /map-approve {vid}")
```

**D-08 extension (render-only — no new write verb, read-only-by-construction stays intact):**
For each draft `v`, read `v.get("validator_report") or {}`:
- If `requires_attention` is true → emit a `⚠ REQUIRES ATTENTION` headline marker, then an
  INDENTED per-flag detail list, SERIOUS FLAGS FIRST, with concrete detail:
  - maturity: `nascent→contested (+2)` (use the ordered enum for direction; `maturity_pill`
    available if a pill is wanted)
  - length: `length 48% of prior (floor 60%)`
  - tension: `tension trivialized`
  - structure: `missing headings: <list>`
- If clean → a quiet `✓ clean` line.
- The pinned mockup is in CONTEXT `<specifics>` — match its wording exactly.

**REQUIRED upstream data change — `get_draft_versions` (gato_brain lines 1655-1674):**
the renderer cannot read `validator_report` unless the fetch selects it. Currently
`select` is `"id,block_slug"` (line 1665). Extend to `"id,block_slug,validator_report"`.
This is the only change to the reader; its fail-loud non-2xx guard (lines 1669-1672) and
`Accept-Profile: economy_map` (via `_economy_map_get`, line 1595) stay as-is.

---

### `tests/test_07_synthesis.py` — swap the WR-02 test (D-01a, VLDT-04)

**Analog (parse-test family):** sibling parse tests at lines 309-359. They use the
`raised` boolean + try/except idiom and `_FULL_SKELETON_BODY` fixture (line 63).

**Analog (poller/insert family):** `_install_post_stub` / `_restore_post` (lines 87-109)
and `_FakeResponse` (lines 66-78) for stubbing `httpx.post`; `_GetResponse` (lines 418+)
for stubbing reads. `test_insert_block_body_version_shape` (lines 365-389) shows how to
capture and assert the INSERT body keys — directly relevant for asserting
`validator_report` now appears in the payload.

**Test to DELETE** (lines 323-332): `test_parse_output_raises_on_missing_skeleton` — it
asserts the OPPOSITE of the new behavior.

**Replacement (VLDT-04 sentinel test, per D-01a):** assert that a missing-heading body now
(a) does NOT raise from `parse_synthesis_output` and (b) produces a `validator_report`
with `structure_missing` populated and `requires_attention == true` via `run_sentinels`.
Keep `test_parse_output_raises_on_empty_body` (335), `..._invalid_maturity` (344),
`..._missing_maturity` (353) AS-IS — only the skeleton test changes (D-01a explicit).

**Pattern for the new test (mirror lines 309-313 + 326-332):**
```python
def test_parse_output_keeps_partial_skeleton():
    # D-01: parse no longer raises on missing headings; the body lands.
    out = proc.parse_synthesis_output(json.dumps(
        {"body_md": "## What it is\nonly one section", "proposed_maturity": "emerging"}))
    assert out["body_md"].startswith("## What it is")

def test_sentinel_flags_missing_structure():
    report = proc.run_sentinels(
        "## What it is\nonly one section", None,
        {"maturity": "emerging", "live_tension": "..."}, "emerging")
    assert report["structure_missing"]            # populated
    assert report["requires_attention"] is True   # rollup fires (D-04)
```
(Exact key names / signature are the planner's to finalize per D-03/D-09.)

## Shared Patterns

### Decision-ID-citing docstrings
**Source:** every Phase 7 primitive, e.g. `parse_synthesis_output` (processor lines 3329-3338),
`fetch_current_block_body` (lines 3152-3157).
**Apply to:** `run_sentinels` and all edited functions. Docstring opens with one-line
summary + the (D-NN / VLDT-NN) IDs it implements, then the WHY.

### Fail-loud (project convention) — two flavors
**Source:** `load_synth_identity` (processor lines 3078-3080) for the log-loud idiom;
`_economy_map_get` (processor lines 3099-3102) for raise-on-non-2xx reads.
**Apply to:**
- DB reads/writes → raise on non-2xx (never mistake a read failure for "no data").
- Sentinel compute errors (VLDT-05) → log loudly (`logger.error(..., exc_info=True)`) and
  record in `validator_report`, but DO NOT raise — the draft must still land.

### economy_map access via direct PostgREST + profile headers
**Source:** processor `_economy_map_get` (lines 3083-3104, `Accept-Profile: economy_map`) and
`economy_map_insert_block_body_version` (lines 3179-3190, `Content-Profile: economy_map`);
gato_brain `_economy_map_get` (lines 1582-1604).
**Apply to:** the `get_draft_versions` select extension. NEVER supabase-py `.in_()`/`.schema()`
(project constraint). No new verbs needed in this phase — reads extend an existing select,
the write extends an existing INSERT payload.

### GATE-01 draft-only / autonomy boundary
**Source:** `synthesize_block` docstring (processor lines 3441-3443),
`economy_map_insert_block_body_version` docstring (lines 3175-3177).
**Apply to:** `run_sentinels` + the `synthesize_block` wiring + `handle_map_pending` —
sentinels only populate the draft's `validator_report`; rendering is read-only. Nothing
touches `blocks.maturity`, `blocks.current_body_version_id`, or a published row.

### Append-only write-at-insert constraint
**Source:** migration 033 trigger `block_body_versions_append_only()` (lines 177-211);
`validator_report IS DISTINCT FROM OLD.validator_report → RAISE` (lines 197-198).
**Apply to:** forces D-02 — `run_sentinels` MUST run before the INSERT inside
`synthesize_block`; there is no post-insert annotation path.

### Sync renderer building a line list
**Source:** `handle_map_status` (gato_brain lines 1753-1770) and current `handle_map_pending`.
**Apply to:** the D-08 flag rendering — append `⚠`/`✓`/indented detail lines to `lines`,
`return "\n".join(lines)`. `maturity_pill` (lines 1570-1579) available for maturity display.

## No Analog Found

None. Every modified symbol has an exact in-module sibling or is the symbol itself. The only
genuinely NEW code is `run_sentinels`, and it has a strong sibling-primitive analog in
`parse_synthesis_output` / `assemble_synthesis_input`.

## Watch-outs for the planner (gotchas surfaced during mapping)

- **`SYNTH_MATURITY_ENUM` is a `set`** (processor line 3038), not ordered — VLDT-03 ordinal
  distance needs a NEW ordered sequence (the canonical order is in the comment at line 3037).
- **Placeholder string is `'TBD — set via /map-tension'`** (migration 033), not the
  `(no live_tension set yet)` phrasing in CONTEXT prose. Use the real placeholder + a
  verbatim-echo check of `block["live_tension"]`.
- **`get_draft_versions` must add `validator_report` to its `select`** (gato_brain line 1665)
  or `handle_map_pending` will render no flags — easy to miss, it is an upstream data change
  separate from the renderer edit.
- **Reuse `prior_body_md` already in scope** in `synthesize_block` (line 3470) for the length
  floor — do not add a second `fetch_current_block_body` read.
- **Length floor cold-start** (`prior_body_md is None`) → N/A, emit no flag (do not divide).

## Metadata

**Analog search scope:** `docker/processor/agentpulse_processor.py` (Phase 7 synthesis
primitives + loop, lines 3030-3494), `docker/gato_brain/gato_brain.py` (/map-* renderers,
lines 1570-1830), `supabase/migrations/033_economy_map_schema.sql` (schema + append-only
trigger), `tests/test_07_synthesis.py` (parse + poller test families).
**Files scanned:** 4
**Pattern extraction date:** 2026-06-02
