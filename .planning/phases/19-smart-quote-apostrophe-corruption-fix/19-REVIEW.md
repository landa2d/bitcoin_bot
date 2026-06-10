---
phase: 19-smart-quote-apostrophe-corruption-fix
reviewed: 2026-06-10T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - docker/newsletter/newsletter_poller.py
  - tests/test_19_smartquote.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-06-10
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Scope: the Phase 19 diff (`bbdbdb3..HEAD`) only — the new `normalize_apostrophe_corruption`
write-path guard, its wiring into `save_newsletter` and the block-pipeline A/B held insert, the
soft-import of `anthropic`, and the QUOTE-02 regression test `tests/test_19_smartquote.py`.

Overall assessment: **the four named project constraints are all honored.** Specifically:

- **FAIL-LOUD:** non-`str` input raises `TypeError` (never coerces); a repair always emits
  `logger.error` with edition/field/count. The function never silently passes a string that
  it has *detected* as corrupt — when it matches, it both repairs and logs.
- **No blanket `"`→`'`:** the regex `(?<=[A-Za-z0-9])"(?=[A-Za-z0-9])` requires word-char flanks
  on both sides, so genuine quotations (`He said "ship it"`) are left untouched. Verified by
  direct probe and by the test `test_genuine_double_quotes_preserved`.
- **Soft-import does not mask a missing SDK:** `init()` re-checks `if anthropic is None: raise
  RuntimeError(...)` before instantiating the client, so a genuinely-missing SDK still fails loud
  at runtime. The `try/except ModuleNotFoundError` only enables pure-helper import under test.
- **Test exercises the REAL function:** `tests/test_19_smartquote.py` imports the conftest-preloaded
  module (`import newsletter_poller as nl`) and calls `nl.normalize_apostrophe_corruption` directly —
  no reimplementation. The suite passes (17 passed in 0.02s).

The implementation is well-documented and the diagnosis (`19-DIAGNOSIS.md`) shows the stored corpus
is already clean, so this guard is correctly a no-op on production data. No BLOCKERs found.

The findings below are non-blocking: coverage gaps relative to the documented signature, a couple
of inconsistencies in *which* fields are guarded, and one tautological test.

## Structural Findings (fallow)

No structural pre-pass payload was provided for this review.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: `content_telegram`, `title`, and `title_impact` bypass the guard

**File:** `docker/newsletter/newsletter_poller.py:1564-1568`, `2273-2274`
**Issue:** The guard is applied to `content_markdown` and `content_markdown_impact` only. The same
`row`/`bp_row` dicts also store `content_telegram` (line 1568) and `title` / `title_impact`
(lines 1565, 2273-2274) verbatim from `result`, with no normalization. These fields come from the
same LLM emission that the guard exists to defend against — the QUOTE-01 mandate is "the corruption
*cannot recur*," and an `App"s` shape could just as easily land in a title or in the Telegram body.
The DIAGNOSIS scanned `content_markdown` / `content_markdown_impact` corpus-wide but did not
establish that titles/telegram are equally immune to a *future* recurrence. The guard's own framing
("locks the corruption out for newly generated editions") is undermined if three sibling text fields
are left unguarded.
**Fix:** Route the remaining user-visible text fields through the same guard, e.g.:
```python
row = {
    ...
    "title": normalize_apostrophe_corruption(
        result.get("title", f"Edition #{edition}"), field="title", edition=edition),
    "title_impact": normalize_apostrophe_corruption(
        title_impact, field="title_impact", edition=edition),
    "content_telegram": normalize_apostrophe_corruption(
        result.get("content_telegram", ""), field="content_telegram", edition=edition),
    ...
}
```
(and the analogous `title`/`title_impact` at the A/B `bp_row`, lines 2273-2274). If titles/telegram
are intentionally out of scope, document that exclusion at the call site so a future reader does not
read the partial coverage as an oversight.

### WR-02: Guard only catches straight-double-quote (U+0022); curly-double-quote corruption variants slip through silently

**File:** `docker/newsletter/newsletter_poller.py:1466`
**Issue:** `_APOSTROPHE_CORRUPTION_RE` matches only the literal `"` (U+0022). The ROADMAP signature
under investigation was an apostrophe rendered as a *double-quote*, and the most common real-world
mechanism for apostrophe corruption is a typographer/smart-quote transform that emits **curly**
double-quotes (U+201C `"` / U+201D `"`), not the straight ASCII one. A mid-word curly double-quote
(`App"s`, `App"s`) is exactly the same corruption class but is a silent **no-op** here — verified by
probe:
```
in='App“s' -> out='App“s'  (MISSED, no-op)
in='App”s' -> out='App”s'  (MISSED, no-op)
```
Because the function only logs when it *rewrites* a character, a curly-double-quote recurrence would
pass through **without** the loud `logger.error` — i.e. it is silently passed to storage, which is
precisely the fail-loud failure mode the guard was built to prevent. The DIAGNOSIS confirms current
storage has zero mid-word U+0022, but it did not rule out a future U+201C/U+201D mechanism (and
typographer transforms emit curly, not straight, quotes — so this is the *more* likely future
recurrence shape, not a less likely one).
**Fix:** Broaden the character class in the lookaround target to cover the curly double-quote
variants while still mapping to a straight apostrophe and still requiring word-char flanks (so
genuine curly quotations `"shipped"` remain untouched — those are flanked by whitespace):
```python
_APOSTROPHE_CORRUPTION_RE = re.compile(r'(?<=[A-Za-z0-9])["“”](?=[A-Za-z0-9])')
```
This keeps the tight word-flank discipline (no blanket replacement) but closes the most probable
recurrence vector. If straight-only is a deliberate scoping decision, state it in the docstring so
the gap is intentional and auditable.

## Info

### IN-01: Two core test cases are tautological — they assert against the unmodified input

**File:** `tests/test_19_smartquote.py:58-63`, `82-89`, `143-153`
**Issue:** `test_quote02_core_clean_inputs_preserve_apostrophe` feeds `"it's"` / `"the agent's
wallet"` — strings that already contain a clean U+0027 apostrophe and zero corruption signature.
The function is a guaranteed no-op on them, so `_has_real_apostrophe(out)` and
`_stray_apostrophe_quote_count(out) == 0` would pass even if `fix` were the identity function.
The same is true of `test_roadmap_tokens_clean_roundtrip` and `test_clean_long_body_is_noop`.
These document the no-op-on-clean property (which has value), but they do not exercise the repair
logic — the *repair* assertions live only in the `_corrupt_inputs_repaired` / `_corruption_repaired`
parametrizations, which is where the real coverage is.
**Fix:** This is acceptable as documentation of the no-op contract; no change required. If
tightening is desired, add a negative assertion that the clean-input branch is identity
(`assert fix(text) == text`) so the intent is explicit rather than incidental.

### IN-02: `field=` default of `"content_markdown"` can produce a misleading log label

**File:** `docker/newsletter/newsletter_poller.py:1469`
**Issue:** The `field` parameter defaults to `"content_markdown"`. All current call sites pass
`field=` explicitly (good), but if a future caller (e.g. the Plan 02 backfill, which the docstring
mandates must reuse this function) calls `fix(some_impact_body)` without the keyword, a real
recurrence would be logged as occurring in `content_markdown` regardless of the true field —
sending an investigator to the wrong column.
**Fix:** Either make `field` a required keyword (drop the default) so callers must label the field,
or set the default to a neutral sentinel like `"<unspecified>"` so a mislabel is obvious in logs.

### IN-03: `edition` default `"?"` is typed as `object` but only ever a label

**File:** `docker/newsletter/newsletter_poller.py:1470`
**Issue:** `edition: object = "?"` is a defensible "anything stringifiable" annotation, but `object`
is unusually loose for a value that is, in practice, an `int` edition number or the string `"?"`.
A reader can't tell from the signature what's expected.
**Fix:** Narrow to `edition: int | str = "?"` for documentation clarity. Cosmetic only; no behavior
change.

### IN-04: Module-level mutable annotation comment is informative but the runtime annotation is a string literal

**File:** `docker/newsletter/newsletter_poller.py:72`
**Issue:** `claude_client: "anthropic.Anthropic | None" = None` uses a string annotation so the
module imports cleanly when `anthropic is None`. This is correct and intentional (and the inline
comment explains it). Noting only that the surrounding sibling globals (`supabase`, `client`,
`deepseek_client`) use real (non-string) annotations, so this is the lone stringized one — a reader
skimming may not immediately see why. The existing inline comment mitigates this adequately.
**Fix:** None required; the inline comment already documents the rationale. Listed for completeness.

---

_Reviewed: 2026-06-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
