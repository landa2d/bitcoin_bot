---
phase: 08-validation-sentinels
reviewed: 2026-06-02T18:26:16Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/processor/agentpulse_processor.py
  - docker/gato_brain/gato_brain.py
  - tests/test_07_synthesis.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-06-02T18:26:16Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 8 adds deterministic validation sentinels (`run_sentinels`) wired into `synthesize_block`
between parse and INSERT, the `SYNTH_MATURITY_ORDER` ordered sequence, removal of the WR-02
missing-headings raise from `parse_synthesis_output`, the `validator_report` payload key on the
append-only INSERT, and the read-only `_render_validator_flags` rendering in `/map-pending`.

The implementation is genuinely strong on the core contracts:

- **VLDT-05 fail-loud-but-never-block is correct.** Every sentinel block is individually
  try/wrapped, logs `exc_info=True`, appends to `sentinel_errors`, applies a *conservative*
  safe default (looks-missing / surface-don't-pass / jump > 1), and the rollup forces
  `requires_attention=True` on any sentinel error. `run_sentinels` cannot raise; the four error
  defaults all bias toward surfacing, never toward a silent pass.
- **No LLM call and no PostgREST verb** inside `run_sentinels` — pure compute (GATE-01 honored).
- **D-01 surgical removal verified:** only the missing-skeleton raise was deleted from
  `parse_synthesis_output`; the empty-body, invalid-maturity, and missing-maturity raises were
  KEPT (processor lines 3353–3358). The swapped test (`test_parse_output_keeps_partial_skeleton`)
  asserts the new land-as-draft behavior, and the three remaining raise-tests survive in `_run_all`.
- **Append-only INSERT contract:** `validator_report` is computed before the INSERT and written
  atomically in the `economy_map_insert_block_body_version` payload; `json=row` serializes the
  nested dict correctly. The insert-shape test asserts the key set is exactly the five expected keys.
- **Cross-plan data contract holds:** every key `run_sentinels` writes
  (`tension_preserved`, `length_below_floor`, `structure_missing`, `maturity_jump`,
  `requires_attention`, optional `sentinel_errors`) is exactly what `_render_validator_flags` reads.
  The `requires_attention` / `sentinel_errors` clean-line guard in the renderer is consistent with
  the writer always setting `requires_attention=True` whenever `sentinel_errors` is non-empty.
- **Read-only-by-construction preserved** in gato_brain: `get_draft_versions` only extends the
  `select` string; `_economy_map_get` is GET-only with `Accept-Profile: economy_map` and no
  Content-Profile / write verb. No new write surface introduced.
- **No ZeroDivisionError risk** in VLDT-02: the cold-start guard treats `None` and
  whitespace-only prior bodies as N/A before any division.
- `SYNTH_MATURITY_ORDER` (list) is correctly used for `.index()` ordinal math, distinct from the
  `SYNTH_MATURITY_ENUM` set used for membership; `proposed_maturity` is validated and lowercased by
  `parse_synthesis_output` before reaching the sentinel, so the proposed side of `.index()` cannot
  raise. The stored-maturity side is defensively wrapped.

All 29 tests in `tests/test_07_synthesis.py` pass; both source files pass `ast.parse`.

Two warnings concern the *fidelity of a sentinel signal* and the integrity of one test; the
remaining items are quality/maintainability notes.

## Warnings

### WR-01: VLDT-04 structure check and VLDT-01 tension check disagree on what "a heading" is

**File:** `docker/processor/agentpulse_processor.py:3392` (structure check) and `:3076` (`_extract_section_body`)
**Issue:** The VLDT-04 `structure_missing` computation uses naive substring containment —
`[h for h in SYNTH_SKELETON_HEADINGS if h.lower() not in body_lower]`. This treats a heading as
"present" if its text appears *anywhere* in the body, including inside prose. For example a body
that writes "the evolution of agent identity..." in running text satisfies the `"evolution"`
substring even with no `## Evolution` heading; likewise `"What it is"` / `"Maturity indicator"`
phrases can occur in prose. Meanwhile the VLDT-01 tension sentinel (`_extract_section_body`)
requires a *real* `## `-level heading whose text matches exactly. The two sentinels therefore
disagree about the same body: structure can report "intact" while the live-tension section does
not actually exist as a heading. This is the idiom inherited verbatim from the removed Phase 7
parse-gate, so it is not a Phase-8 regression — but Phase 8 *promoted* this string to a
load-bearing operator-facing signal (the `structure_missing` flag) and to a `requires_attention`
input, so the weakness now affects whether a malformed draft is flagged. A draft missing its
`## Evolution` heading but mentioning "evolution" in prose will render `✓ clean` for structure.
**Fix:** Make VLDT-04 use the same heading-aware detection as VLDT-01 so the two sentinels are
consistent and the flag reflects real section presence:
```python
structure_missing = [
    h for h in SYNTH_SKELETON_HEADINGS
    if _extract_section_body(body_md or "", h) is None
]
```
(`_extract_section_body` already returns `None` when the `## <heading>` line is absent.) Keep the
try/except wrapper and the `list(SYNTH_SKELETON_HEADINGS)` safe-default unchanged.

### WR-02: `test_sentinel_length_below_floor` builds a body it never exercises (misleading test)

**File:** `tests/test_07_synthesis.py:411-419`
**Issue:** The test constructs `body = _skeleton_with_tension(...)` and then calls
`proc.run_sentinels("short", prior, ...)` — the elaborately-built `body` is never passed to
`run_sentinels`; the assertion is driven by the literal `"short"` instead. The intervening
comment ("body is far shorter than 600 chars only if skeleton small; make prior dominate")
describes reasoning about the unused variable, which makes the test actively misleading: a future
reader will believe the realistic skeleton body is under test when it is not. The assertions
themselves are correct (`"short"` / `"x"*900` against `"x"*1000`), so this is test-quality, not a
false pass — but a dead setup line in a sentinel test invites drift.
**Fix:** Remove the unused `body` line and the stale comment, or actually pass the skeleton body:
```python
prior = "x" * 1000
report = proc.run_sentinels("short", prior,
                            {"maturity": "emerging", "live_tension": ""}, "emerging")
assert report["length_below_floor"] is True
assert report["requires_attention"] is True
report2 = proc.run_sentinels("x" * 900, prior,
                             {"maturity": "emerging", "live_tension": ""}, "emerging")
assert report2["length_below_floor"] is False
```

## Info

### IN-01: VLDT-01 tension extraction silently requires exactly two-hash (`## `) headings

**File:** `docker/processor/agentpulse_processor.py:3076-3100`
**Issue:** `_extract_section_body` matches only lines beginning with `## ` (level-2). If the
synthesizer emits the live-tension heading at a different level (`# The live tension`,
`### The live tension`) or without the trailing space, extraction returns `None` and
`tension_preserved` becomes `False`. This biases toward over-flagging (safe per VLDT-05), but it
silently couples the sentinel to one exact markdown level. If the synth prompt ever varies heading
depth, every block will flag tension-not-preserved. Acceptable for v1 given the fail-loud default;
worth a one-line acknowledgement in the docstring or a small tolerance for `#{1,6} ` prefixes.
**Fix:** Optionally relax the prefix test to any ATX heading level, e.g. match
`re.match(r"#{1,6}\s+(.*)", stripped)` and compare the captured text — keeps the next-heading
boundary logic intact.

### IN-02: VLDT-01 placeholder / verbatim-echo detection is exact-match only

**File:** `docker/processor/agentpulse_processor.py:3399-3406`
**Issue:** `tension_preserved` is set `False` only when the extracted section, after strip,
*exactly* equals the placeholder string or *exactly* equals `block.live_tension`. A body that
prepends or appends a few words to the placeholder/prior framing (e.g. placeholder + a trailing
sentence) escapes detection and reads as engaged. This is the documented deterministic v1 behavior
(the "shallow-but-present" LLM judge is the deferred v2 upgrade), so it is a known limitation, not
a defect. Flagging only for the deferral note.
**Fix:** None required for v1. v2 can substring/prefix-test the placeholder or compute a similarity
ratio against `block.live_tension`.

### IN-03: `_LENGTH_FLOOR_PCT` (gato_brain) and `0.60` (processor) are duplicated magic numbers

**File:** `docker/gato_brain/gato_brain.py:1736` and `docker/processor/agentpulse_processor.py:3422`
**Issue:** The 60% length floor lives as a literal `0.60` in `run_sentinels` and as
`_LENGTH_FLOOR_PCT = 60` in the renderer. The two services cannot share a constant (no shared
package), so this is unavoidable duplication, but if the processor floor is ever retuned the
renderer copy will silently print the wrong "< 60%" detail. Because the renderer only displays a
bool (it does not recompute), a drift produces a misleading label, not a wrong flag.
**Fix:** Add a cross-reference comment on each constant pointing at the other (the gato_brain
comment already notes the processor stores a bool; add the reciprocal pointer in the processor at
the `0.60` site, e.g. `# Mirrored as _LENGTH_FLOOR_PCT in gato_brain _render_validator_flags`).

---

_Reviewed: 2026-06-02T18:26:16Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
