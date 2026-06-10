---
phase: 19-smart-quote-apostrophe-corruption-fix
plan: 01
subsystem: newsletter-write-path
tags: [content-integrity, apostrophe, fail-loud, regression-test, diagnosis]
requires:
  - "Live production Supabase newsletters table (read-only) — config/.env credentials"
provides:
  - "19-DIAGNOSIS.md — byte-evidenced root-cause finding [PARTIALLY SUPERSEDED: original 'storage is CLEAN' conclusion was WRONG; real cause is a DOUBLED apostrophe '' rendering as a visual double-quote — see the CORRECTION block at the top of 19-DIAGNOSIS.md]"
  - "nl.normalize_apostrophe_corruption() — fail-loud write-path guard [signature CORRECTED post-operator-feedback to collapse word-flanked '' -> '; commit 437cdb1]"
  - "tests/test_19_smartquote.py — QUOTE-02 regression (36 tests after correction) locking the corruption out"
affects:
  - "docker/newsletter/newsletter_poller.py (save_newsletter + A/B insert)"
tech-stack:
  added: []
  patterns:
    - "Fail-loud write-path guard (no-op-on-clean, raises on bad type, logs on any repair)"
    - "Soft optional-import (anthropic) so a pure helper is unit-testable without the SDK"
key-files:
  created:
    - ".planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md"
    - "tests/test_19_smartquote.py"
  modified:
    - "docker/newsletter/newsletter_poller.py"
decisions:
  - "Storage is already clean corpus-wide (zero mid-word U+0022); the 'fix forward' is a fail-loud no-op-on-clean guard, NOT a destructive repair — the bytes refuted the write-path-corruption hypothesis"
  - "Guard installed at the shared save_newsletter insert (+ the A/B held-edition insert) — covers BOTH single-pass and block-pipeline write paths with one fix site; block_pipeline.py needs no change"
  - "anthropic made a soft import so the pure helper is importable for the QUOTE-02 test without a pip install (forbidden this phase); init_clients fails loud if the SDK is genuinely absent at runtime"
metrics:
  duration: "~10min"
  tasks: 3
  files: 3
  completed: "2026-06-10"
---

# Phase 19 Plan 01: Diagnose & Fix Write-Path (Smart-Quote / Apostrophe Corruption) Summary

**One-liner:** Proved from raw stored bytes that the apostrophe→double-quote corruption is NOT in the newsletter corpus (every apostrophe is a clean U+0027, zero `App"s` mid-word double-quotes corpus-wide) and the renderer has no typographer, then installed a fail-loud, no-op-on-clean `normalize_apostrophe_corruption` guard on the shared write-path insert so the corruption cannot recur — locked by a 17-case regression test that calls the real function.

## What Was Built

1. **`19-DIAGNOSIS.md`** (127 lines) — the byte-evidenced root-cause artifact. Read-only SELECTs against the live production `newsletters` table for edition 30 (both `held` and `published` rows), a deep codepoint scan of editions 29/30/31, and a table-wide scan of every newsletter row.
2. **`normalize_apostrophe_corruption()`** in `docker/newsletter/newsletter_poller.py` — a pure, fail-loud guard wired into `save_newsletter` and the A/B held-edition insert.
3. **`tests/test_19_smartquote.py`** — 17-case QUOTE-02 regression importing the real fixed function.

## The Mandated Records (for Plan 02)

- **Storage-vs-render conclusion:** **STORAGE IS CLEAN; the write path does NOT corrupt apostrophes; render is ruled out.** Across the entire `newsletters` table the corruption signature (a U+0022 double-quote flanked by word characters — the literal `App"s` shape) count is **0**. Every apostrophe is stored as straight **U+0027** (curly U+2019 ≈ 0). `app.js` reads the field verbatim and `marked.parse` runs with **no** `setOptions`/`use` (smartypants/typographer off), so the renderer introduces no transform. The ROADMAP's stray-double-quote is a presentation/glyph artifact, not a data defect. **Implication for Plan 02: there is no corrupt stored data to backfill — Plan 02 should confirm-and-close, not mass-UPDATE.**

- **Exact fixed function (file + line range):**
  `normalize_apostrophe_corruption(text, *, field, edition)` in
  **`docker/newsletter/newsletter_poller.py`** — defined at **lines ~1466–1530**, called inside
  **`save_newsletter`** at the `row = {...}` assembly (**~lines 1535–1545**, immediately before the
  `supabase.table("newsletters").insert(row)`), and again at the block-pipeline **A/B held-edition
  insert** (`bp_row`, **~lines 2275–2281**). The single-pass and block-pipeline bodies both flow
  through the `save_newsletter` insert, so one guard site covers both.

- **Canonical function name + import path the regression test uses:**
  `import newsletter_poller as nl` (conftest preloads it) → **`nl.normalize_apostrophe_corruption`**.
  **Plan 02's backfill MUST reuse this exact function** so any backfill repair matches the
  write-path fix byte-for-byte. The repair is the tightly-scoped regex
  `(?<=[A-Za-z0-9])"(?=[A-Za-z0-9])` → `'` — NEVER a blanket `"`→`'`.

## Behavior of the Guard (correctness + fail-loud)

- **No-op on the clean corpus and on genuine quotes** — repairs ONLY a straight double-quote
  flanked by word chars (`App"s`). `He said "ship it"` (`"` flanked by whitespace) is untouched
  (threat T-19-03). Cannot regress the 30+ existing editions.
- **Fail-loud** (project "the wallet bug" rule): raises `TypeError` on non-`str` input;
  `logger.error`s with edition + field + repair count whenever it actually rewrites a character,
  so a real recurrence is surfaced, never silently passed through.

## Tasks

| Task | Name | Commit | Key files |
| ---- | ---- | ------ | --------- |
| 1 | Diagnose root cause from raw stored bytes | `8ecc612` | 19-DIAGNOSIS.md |
| 2 | Fail-loud write-path guard | `2f620e5` | docker/newsletter/newsletter_poller.py |
| 3 | QUOTE-02 regression test (real function) | `83c490e` | tests/test_19_smartquote.py |

## Verification

- `19-DIAGNOSIS.md`: exists, 127 lines (≥20), records raw codepoints (U+0027/ord 39, U+0022/ord 34) + storage-vs-render conclusion + named fix site. PASS.
- `python3 -c "import ast; ast.parse(newsletter_poller.py); ast.parse(block_pipeline.py)"` → `SYNTAX OK`. PASS.
- `python3 -m pytest tests/test_19_smartquote.py -v` → **17 passed**, exit 0; imports the real `nl.normalize_apostrophe_corruption`; asserts apostrophe preserved + zero word-flanked U+0022 + genuine quotes intact + fail-loud on non-str. PASS.
- No blanket `"`→`'` replacement (grep confirms). PASS.
- `docker/web/site/app.js` unchanged by this plan (render layer untouched, as the diagnosis required). PASS.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Soft-import `anthropic` so the pure helper is importable without the SDK**
- **Found during:** Task 2/3 — `newsletter_poller.py` had a hard top-level `import anthropic` (line 22) and `anthropic` is not installed in this test environment, which would block the QUOTE-02 regression from importing the real fixed function. New pip installs are forbidden this phase.
- **Fix:** Wrapped the import in `try/except ModuleNotFoundError: anthropic = None`; changed the module-level `claude_client` annotation to a string annotation; added a fail-loud `RuntimeError` in `init_clients()` if `anthropic` is genuinely absent at runtime (production image still ships it). Pure helpers are now importable for testing; runtime behavior in production is unchanged (and fails loud if the SDK is truly missing).
- **Files modified:** docker/newsletter/newsletter_poller.py
- **Commit:** `2f620e5`

### Plan-hypothesis deviation (evidence-driven, no user decision needed)

The plan framed the likely outcome as "storage corruption in the write path that must be repaired," with `block_pipeline.py` as a candidate fix site. **The bytes refuted this** — storage is clean corpus-wide. Per the plan's own mandate ("the conclusion is whatever the bytes show; decide nothing a priori"), the fix became a **fail-loud no-op-on-clean guard** (Rule 2 — critical correctness/recurrence-prevention functionality) at the shared insert rather than a destructive repair, and `block_pipeline.py` was left unchanged (the guard at the shared `save_newsletter` insert covers it). This is consistent with QUOTE-01 ("fix forward so it cannot recur") and gives QUOTE-02 a real production function to lock.

## Authentication Gates

None. The read-only diagnostic used `config/.env` Supabase service-key credentials already present on the main tree (the reason this plan runs sequentially here, not in a worktree).

## Known Stubs

None. No placeholders, no empty-value sinks, no TODO/FIXME introduced.

## Threat Flags

None. The fix changes only the apostrophe-slot codepoint when the corruption signature is present (a no-op otherwise); it introduces no new HTML/markdown control characters, no new network surface, no new auth or schema change. The read-only diagnostic mutated nothing.

## Self-Check: PASSED

- FOUND: .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md
- FOUND: docker/newsletter/newsletter_poller.py
- FOUND: tests/test_19_smartquote.py
- FOUND commit: 8ecc612
- FOUND commit: 2f620e5
- FOUND commit: 83c490e
