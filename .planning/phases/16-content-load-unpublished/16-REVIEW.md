---
phase: 16-content-load-unpublished
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - supabase/migrations/043_economy_map_hub_and_negotiation_blocks.sql
  - scripts/load_economy_map_content.py
  - tests/test_16_content_load.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-06-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 16 one-shot content load: migration 043 (structure only), the
standalone PostgREST body loader, and its negative-path test. I verified against the
phase constraints (direct PostgREST + Content-Profile/Accept-Profile; fail-loud, no
partial load; loader never writes a `blocks` row or sets `status`/`published_at`/
`maturity`/`current_body_version_id`; narrow single-purpose write surface).

**The core constraints are met.** The loader replicates the three processor functions
faithfully (verified line-by-line against `agentpulse_processor.py:3088/3124/3174`), uses
the correct headers (`Accept-Profile` for reads, `Content-Profile` for writes), omits
`status` so the DB default `'draft'` applies, builds a payload restricted to exactly
`block_slug`/`body_md`/`proposed_maturity`, and never touches `blocks`. The migration's
title/subtitle for both new rows match the `.md` frontmatter verbatim (confirmed by
parse), the sort_order reshuffle is correctly highest-first to avoid the UNIQUE collision,
and all four tests pass. The `validate_all` gate is genuinely fail-loud and validate-ALL
(not fail-on-first), and the negative-path test correctly proves zero POSTs land when the
gate fires.

**No BLOCKERs found.** The findings are robustness gaps and one unverified atomicity claim.
Several would-be data-corruption paths fail *safe* because `validate_all` (missing `order`,
empty `body_md`, out-of-enum maturity) and `block_has_open_draft` (idempotent skip) act as
backstops. The WARNINGs identify where those backstops are the only thing standing between a
malformed input and a bad load, and where a claim in a docstring is not actually guaranteed
by the code.

## Warnings

### WR-01: Migration claims "ONE atomic transaction" but file has no transaction wrapper

**File:** `supabase/migrations/043_economy_map_hub_and_negotiation_blocks.sql:4, 35-54`
**Issue:** The header comment states the migration "owns ALL blocks-row STRUCTURE ... in ONE
atomic transaction." The file contains no explicit `BEGIN;`/`COMMIT;` (and the `BEGIN`
tokens in sibling migration 033 are PL/pgSQL `DO $$ BEGIN`, not transaction control). The
three `UPDATE`s + `INSERT` are atomic *only* if the apply mechanism wraps the whole file in
one transaction. Supabase CLI does; the MCP `apply_migration` path / a manual `psql -c`
per-statement run does not. If a failure occurs after a partial reshuffle (e.g. regulation
moved 7→8 but psychology not yet moved), the table is left in a non-contiguous,
constraint-violating state — and because the three `UPDATE`s run *unconditionally* on every
run (not guarded by the slug's current value), a recovery re-run can then collide the
`sort_order` UNIQUE constraint (e.g. psychology still at 6 while governance's 5→6 fires).
The atomicity the comment promises is the only thing preventing this, and the file does not
enforce it.
**Fix:** Make the atomicity explicit so it holds regardless of apply mechanism:
```sql
BEGIN;

ALTER TABLE economy_map.blocks DROP CONSTRAINT IF EXISTS blocks_tier_check;
-- ... all UPDATEs + INSERT ...

COMMIT;
```

### WR-02: `parse_doc` splits frontmatter on the `---` *substring*, not a line-anchored fence

**File:** `scripts/load_economy_map_content.py:167-171`
**Issue:** `text.split("---", 2)` splits on the first occurrence of the three-character
substring `---` anywhere in the file, not on a line consisting solely of `---`. If any
frontmatter VALUE contains `---` (e.g. a title/subtitle with an em-dash typed as `---`, or
`subtitle: between A --- B`), the split fires mid-value: the YAML is truncated, later keys
(`order`, `maturity`) fall into the "body", and `yaml.safe_load` silently parses a partial
frontmatter. Reproduced: `subtitle: has --- dash` yields `{subtitle: 'has'}` with `order`
and `maturity` missing and dumped into `body_md`. Current docs do not trigger this, and
`validate_all` would then halt loud on the missing `order`/`maturity` — so it fails *safe*
today — but the parser is fragile and the failure mode is "frontmatter silently truncated"
rather than "fence not found." A future doc with a legitimately dashed value would mis-load
or spuriously halt the whole batch.
**Fix:** Anchor the split to the fence line instead of the substring:
```python
import re
m = re.match(r"^---\n(.*?)\n---\n(.*)\Z", text, re.DOTALL)
if m:
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
```

### WR-03: No duplicate-slug or roster-completeness check in `validate_all`

**File:** `scripts/load_economy_map_content.py:205-262, 268-282`
**Issue:** `validate_all` checks each present slug is *in* `LOCKED_ROSTER`, but never checks
(a) that a slug appears only once in the batch, nor (b) that all 8 roster members are
present. Completeness is enforced only by `discover_docs`'s `len(paths) != EXPECTED_COUNT`
guard, which is *gated on the DEFAULT dir only* (line 276) — an `ECONOMY_MAP_DOCS_DIR`
override (the supported fixture/operator path) bypasses it entirely. So a batch of two
files both declaring `slug: identity-trust`, or a 3-file partial batch, passes
`validate_all` clean. The duplicate-slug case is mitigated at runtime only by
`block_has_open_draft` between iterations (the 2nd iteration's GET sees the 1st insert's
draft and skips) — but that mitigation depends on read-after-write timing and a real DB
round-trip, and is silently absent under `--dry-run` (no POST → the GET never sees a draft →
both "would insert"). For a one-shot service-role loader where an over-broad load is the
named risk, this should be caught at the gate, not left to a runtime skip.
**Fix:** Add a duplicate-slug check (and, for the default-dir run, a completeness check)
inside `validate_all`:
```python
seen = {}
for record in records:
    s = record.get("slug")
    if s:
        if s in seen:
            failures.append(f"{record.get('path')}: duplicate slug '{s}'")
        seen[s] = True
# optional: if running the canonical roster, require LOCKED_ROSTER == set(seen)
```

### WR-04: `type` field is never validated — a mislabeled `type: hub` silently bypasses tier/maturity gating

**File:** `scripts/load_economy_map_content.py:197, 235-242, 248-252`
**Issue:** The hub special-case (skip `tier`, skip `maturity`, force `proposed_maturity` =
`'nascent'`) is selected purely by `record.get("type") == "hub"`, but `validate_all` never
asserts that `type` is one of `{"hub","block"}` nor that exactly one record is the hub. A
block doc with a typo'd `type: hub` (or a copy-paste error) would skip the tier and maturity
checks entirely and be inserted with a hard-coded `proposed_maturity='nascent'`, silently
discarding its real maturity — exactly the kind of silent-wrong-value load the fail-loud
constraint exists to prevent. Conversely a block with `type` missing/None is treated as a
block (correct for today's docs, but only by luck of the frontmatter convention).
Reproduced: a fully-valid identity-trust record relabeled `type: hub` passes `validate_all`
and would insert a `nascent` draft.
**Fix:** Validate `type` explicitly and assert exactly one hub:
```python
if rtype not in ("hub", "block"):
    failures.append(f"{where}: invalid type '{rtype}' (expected 'hub' or 'block')")
# after the loop:
hubs = [r for r in records if r.get("type") == "hub"]
if len(hubs) != 1:
    failures.append(f"expected exactly 1 hub record, found {len(hubs)}")
```

## Info

### IN-01: `parse_doc` opens the file without a context manager

**File:** `scripts/load_economy_map_content.py:164`
**Issue:** `open(path, encoding="utf-8").read()` leaks the file handle until GC (CLAUDE.md
conventions list "missing `with` for file operations" as a Python smell). Negligible for an
8-file one-shot, but inconsistent with the fail-loud, defensive posture of the rest of the
file.
**Fix:** `with open(path, encoding="utf-8") as f: text = f.read()`

### IN-02: `--dry-run` still performs live DB reads (cannot run fully offline)

**File:** `scripts/load_economy_map_content.py:299-303, 322`
**Issue:** `--dry-run` skips POSTs but still calls `block_has_open_draft(slug)` (a live GET)
for every record, and still hard-exits if `SUPABASE_URL`/`SUPABASE_KEY` are unset. The
docstring (line 18) does say "validate + skip-check only (no POST)", so this is documented —
flagging only because "dry-run" commonly implies "no network," and an operator validating
frontmatter without DB credentials will hit the env-gate exit, not a clean validate pass.
**Fix:** Optionally short-circuit the skip-check under `--dry-run`, or document in `--help`
that dry-run still requires DB read access.

### IN-03: Test C mutates the process-global `httpx.post`

**File:** `tests/test_16_content_load.py:139-148`
**Issue:** `loader.httpx.post = lambda ...` replaces the attribute on the shared `httpx`
module object (not a loader-local reference), affecting any other test in the same process.
It is correctly restored in `finally`, so there is no leak today, but `monkeypatch.setattr`
(already imported as the fixture) would be safer and auto-restoring.
**Fix:** `monkeypatch.setattr(loader.httpx, "post", lambda url, **kw: captured["posts"].append(url))`
and drop the manual save/restore.

---

_Reviewed: 2026-06-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
