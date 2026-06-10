---
phase: 19-smart-quote-apostrophe-corruption-fix
verified: 2026-06-10T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Visit the live site (aiagentspulse.com), navigate to edition 30 (or any published edition containing apostrophes such as 'Cash App's', 'It's', 'world's', 'agent's'). Inspect the rendered body in the browser."
    expected: "All apostrophes render as real apostrophes — no stray straight double-quote (U+0022) flanking a word character (no 'App\"s' / 'It\"s' shape). The stored bytes are already clean (proved by 19-DIAGNOSIS.md and independently confirmed by 19-BACKFILL-REVIEW.md), and the renderer has no typographer, so the live site should render correctly."
    why_human: "The original bug was observed as a visual/presentation artifact on the live site. Byte-level evidence proves storage is clean and the renderer introduces no transform, but the human eye on the live URL is the only way to confirm the presentation artifact is gone (it may have been a transient deploy-skew or font-glyph issue). This is the QUOTE-01 Success Criterion #1 visual check — it cannot be satisfied by grep alone."
---

# Phase 19: Smart-Quote / Apostrophe Corruption Fix — Verification Report

> ## ⚠ CORRECTION (2026-06-10) — this report trusted a wrong diagnosis
>
> This verification PASSED 5/5 must-haves and flagged only the live-site visual as
> `human_needed`. The operator then performed that visual check and found the `"` was
> **still present** — proving Truth #1 ("storage is clean") was wrong. Root cause
> re-investigation (see the CORRECTION block in `19-DIAGNOSIS.md`) found the real
> corruption: a **doubled apostrophe** (`''`), 103 runs across published editions
> 26/29/30, which renders as a visual `"`. The original diagnostic searched for the
> wrong character (`"` / U+0022) and never counted `''`.
>
> **Resolution applied:** write-path guard corrected to collapse word-flanked
> `''`→`'` (36 tests passing); operator-approved scoped backfill of editions
> 26/29/30 (103 repaired, 0 remaining, genuine quotes preserved); `newsletter`
> rebuilt; live render re-verified end-to-end (anon fetch → marked → `Cash App's`).
> The phase goal is now genuinely met; the only open item is the operator's final
> visual re-confirmation on the live site (tracked in `19-HUMAN-UAT.md`).
>
> The per-truth evidence below is preserved as-written; note Truths #1–#3 describe
> the *superseded* (wrong-signature) fix — see the corrected guard/backfill above.

**Phase Goal:** The highest-visibility live-site bug is gone — edition bodies render apostrophes correctly everywhere, the root cause is documented (not papered over), the write path is fixed so it cannot recur, existing editions are backfilled via a scoped reviewed UPDATE, and a regression test locks it.
**Verified:** 2026-06-10
**Status:** human_needed (gap found + resolved; awaiting operator visual re-confirmation)
**Re-verification:** No — initial verification, corrected post-operator-feedback

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Root cause documented from raw stored bytes — storage vs render conclusion stated (QUOTE-01 SC #2) | VERIFIED | `19-DIAGNOSIS.md` (127 lines): byte-level SELECT against live Supabase `newsletters` table, `ord()` of every apostrophe-slot codepoint in edition 30; zero mid-word U+0022 corpus-wide (43 rows); `marked.parse` confirmed typographer-off; conclusion: "STORAGE IS CLEAN; the write path does NOT corrupt apostrophes; render is ruled out." |
| 2 | Write path fixed so corruption cannot recur — fail-loud, covers single-pass + block-pipeline paths (QUOTE-01 SC #3) | VERIFIED | `normalize_apostrophe_corruption()` defined at `newsletter_poller.py:1472–1527`. Regex `(?<=[A-Za-z0-9])["""](?=[A-Za-z0-9])` covers straight U+0022 AND curly U+201C/U+201D (WR-02 fix, commit 36169a2). Called for `content_markdown` (1558), `content_markdown_impact` (1561), `title` (1568), `title_impact` (1571), `content_telegram` (1574) — all five user-visible fields in the single-pass path. Block-pipeline A/B held insert (`bp_row`) also guarded at 2290–2299. Raises `TypeError` on non-str; `logger.error` with `[QUOTE-FIX]` on any repair. |
| 3 | Regression test locks `it's` / `the agent's wallet` through the real fixed function (QUOTE-02) | VERIFIED | `tests/test_19_smartquote.py`: 26 tests, all passing (`26 passed in 0.03s` from live run). Imports the real `nl.normalize_apostrophe_corruption` via conftest-preloaded module — no reimplementation. Covers straight corrupt inputs, curly corrupt inputs (WR-02), genuine-quote preservation (T-19-03), fail-loud on non-str, loud-log-on-repair / silent-on-clean, and the 4 ROADMAP tokens. |
| 4 | Backfill performed via scoped reviewed process, operator-approved, spine-honored (QUOTE-01 SC #1 backfill clause) | VERIFIED | `19-BACKFILL-REVIEW.md` (130 lines): independent read-only scan of all 43 newsletter rows using the canonical `nl.normalize_apostrophe_corruption` as repair logic. Corpus-wide corruption-signature count: **0**. Affected-edition list: **EMPTY**. Edition 30 BEFORE == AFTER in every column (zero replacements). Operator explicitly approved "Close + rebuild newsletter" at the blocking-human Task 2 gate. No scoped UPDATE was warranted (an empty `WHERE edition_number IN (...)` set is spine-correct confirm-and-close, not a gap). No data mutated. |
| 5 | Normalization code is fail-loud on unexpected input — never silently passes corruption (project constraint) | VERIFIED | `normalize_apostrophe_corruption`: `TypeError` raised on non-str (line 1506–1511, tested by `test_fail_loud_on_non_str`). `logger.error("[QUOTE-FIX] ...")` emitted with edition/field/count on any repair (lines 1521–1526, tested by `test_repair_logs_loudly`). `test_clean_input_does_not_log` confirms no false-alarm on clean input. |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md` | Root-cause finding: raw codepoints, storage-vs-render conclusion, named fix site | VERIFIED | 127 lines (≥20). Records `ord=39 → U+0027` in edition 30's apostrophe slots, `mid-word U+0022 = 0` corpus-wide, named fix site `normalize_apostrophe_corruption` in `newsletter_poller.py` at `save_newsletter`. Conclusion stated: storage clean, render ruled out. |
| `docker/newsletter/newsletter_poller.py` | Fixed write path — `content_markdown` guarded | VERIFIED | Guard defined at lines 1469–1527. Called for all five user-visible text fields in `save_newsletter` (1558–1576) and the block-pipeline A/B insert (2290–2299). Syntax valid (`python3 -c "import ast; ast.parse(...)"` → OK). |
| `tests/test_19_smartquote.py` | QUOTE-02 regression importing the real fixed function | VERIFIED | 207 lines. `import newsletter_poller as nl` at line 36; `fix = nl.normalize_apostrophe_corruption` at line 39. 26 tests, all passing. |
| `.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md` | Before/after diff of edition 30, affected-edition list, scoped UPDATE plan presented for operator approval | VERIFIED | 130 lines (≥25). Section 1: affected-edition list (EMPTY, 43 rows scanned). Section 2: edition-30 BEFORE/AFTER via Plan 01 canonical logic (zero replacements). Section 3: genuine-quote preservation. Section 4: scoped UPDATE plan — confirm-and-close, no UPDATE warranted. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_19_smartquote.py` | `nl.normalize_apostrophe_corruption` in `newsletter_poller.py` | `import newsletter_poller as nl` (conftest-preloaded) | WIRED | `import newsletter_poller as nl` confirmed at line 36; `fix = nl.normalize_apostrophe_corruption` at line 39; the test calls `fix(text)` throughout — the real function, not a reimplementation. |
| `save_newsletter` (single-pass insert) | `normalize_apostrophe_corruption` | direct call before `supabase.table("newsletters").insert(row)` | WIRED | Five call sites (lines 1558–1576) produce normalized values assigned to the `row` dict, which is inserted at line 1592. Data flows: LLM result → guard → `row["content_markdown"]` etc. → Supabase INSERT. |
| Block-pipeline A/B held insert (`bp_row`) | `normalize_apostrophe_corruption` | inline calls in `bp_row` dict literal | WIRED | Four call sites at lines 2290–2299 in the `bp_row` dict that feeds `supabase.table("newsletters").insert(bp_row)` at line 2314. |
| `19-DIAGNOSIS.md` | Named fix site in `newsletter_poller.py` | `normalize_apostrophe_corruption` at `save_newsletter`, lines ~1467–1478 per diagnosis §5 | WIRED | 19-DIAGNOSIS.md §5 names `normalize_apostrophe_corruption` in `newsletter_poller.py` called inside `save_newsletter`. Implementation found at lines 1472–1527 and wired at lines 1558–1576. Diagnosis → implementation → call site all consistent. |
| Backfill repair logic | Plan 01 canonical guard (no divergent regex) | `nl.normalize_apostrophe_corruption` imported from `newsletter_poller` | WIRED | `19-BACKFILL-REVIEW.md` documents: "Repair logic: the canonical Plan 01 write-path fix `nl.normalize_apostrophe_corruption` (`import newsletter_poller as nl`). Not a second, divergent regex." |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `normalize_apostrophe_corruption` (pure string transform) | `text` parameter | Caller passes the LLM-emitted body string; no DB query involved | N/A — pure guard, not a data-rendering component | VERIFIED — the function's role is a write-path guard; it transforms (or no-ops) a string and returns it. The call sites wire it correctly into `row["content_markdown"]` etc. before the INSERT. Level 4 data-flow does not apply to a pure guard function. |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 26 regression tests pass | `python3 -m pytest tests/test_19_smartquote.py -q` | `26 passed in 0.03s` | PASS |
| Syntax valid | `python3 -c "import ast; ast.parse(open('docker/newsletter/newsletter_poller.py').read()); print('OK')"` | `OK` | PASS |
| Regex catches straight U+0022 | `re.compile(r'(?<=[A-Za-z0-9])["""](?=[A-Za-z0-9])').search('App"s')` | match | PASS |
| Regex catches curly U+201C | `re.compile(r'(?<=[A-Za-z0-9])["""](?=[A-Za-z0-9])').search('App"s')` | match | PASS |
| Regex catches curly U+201D | `re.compile(r'(?<=[A-Za-z0-9])["""](?=[A-Za-z0-9])').search('App"s')` | match | PASS |
| Genuine quotation not matched | `re.compile(r'(?<=[A-Za-z0-9])["""](?=[A-Za-z0-9])').search('He said "ship it"')` | no match | PASS |
| Newsletter container healthy | `docker compose ps newsletter` | `Up ... (healthy)` | PASS |
| `docker/web/site/app.js` unchanged | `git diff --name-only bbdbdb3..HEAD` | `app.js` absent from changed-files list | PASS |

---

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes defined for this phase. Step 7c: SKIPPED (no declared probes; phase is not a migration/tooling phase with a probe convention).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| QUOTE-01 | Plan 01, Plan 02 | Edition bodies render apostrophes correctly; root cause documented; write path fixed (cannot recur); existing editions corrected via scoped reviewed process | SATISFIED | 19-DIAGNOSIS.md proves storage is clean (root cause documented). `normalize_apostrophe_corruption` deployed in newsletter container (fix-forward). `19-BACKFILL-REVIEW.md` confirms zero corrupt rows — confirm-and-close is spine-correct when the affected set is empty; operator approved. REQUIREMENTS.md marks QUOTE-01 `[x]` Complete. |
| QUOTE-02 | Plan 01 | A test feeds `it's` and `the agent's wallet` through the fixed path and asserts output contains apostrophe and zero stray `"` | SATISFIED | `tests/test_19_smartquote.py`: `test_quote02_core_clean_inputs_preserve_apostrophe` and `test_quote02_core_corrupt_inputs_repaired` exercise exactly these inputs and assertions. 26 passed. REQUIREMENTS.md marks QUOTE-02 `[x]` Complete. |

**Orphaned requirements check:** REQUIREMENTS.md traceability table assigns only QUOTE-01 and QUOTE-02 to Phase 19. Both covered. No orphans.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX markers in phase-touched files | — | None |

No debt markers, no stubs, no hardcoded empty returns in phase-modified files (`newsletter_poller.py`, `tests/test_19_smartquote.py`). `19-01-SUMMARY.md` explicitly records "Known Stubs: None" and "Threat Flags: None."

---

### Human Verification Required

#### 1. Live site apostrophe rendering on a published edition

**Test:** Visit `aiagentspulse.com`, navigate to edition 30 (or any published edition). Read the body for any word containing an apostrophe (e.g. `Cash App's`, `It's`, `world's`, `agent's`). Alternatively use browser DevTools to inspect the rendered text of the edition body element.

**Expected:** All apostrophes display as real apostrophes. No stray straight double-quote character appears flanking a word character (no `App"s` / `It"s` shape). The text looks typographically normal.

**Why human:** The original defect was observed as a visual/presentation artifact on the live rendered site. The byte-level evidence (19-DIAGNOSIS.md, 19-BACKFILL-REVIEW.md) proves the stored corpus has zero mid-word U+0022 characters and `marked.parse` runs with no typographer, meaning the stored bytes and the render pipeline cannot produce the corruption. However the original ROADMAP report was based on a visual observation of the live site. A human eye on the live URL is the only way to confirm the presentation artifact is gone (it may have been a transient deploy-skew state that no longer exists, or a browser-font glyph rendering quirk). This is the QUOTE-01 Success Criterion #1 visual check: "the highest-visibility live-site bug is gone."

---

### Gaps Summary

No blocking gaps. All five must-have truths are verified by codebase evidence:

1. Root-cause documentation: 19-DIAGNOSIS.md (127 lines, byte-evidenced, storage-clean conclusion, named fix site).
2. Write-path fix: `normalize_apostrophe_corruption` deployed and wired to five fields in `save_newsletter` plus the block-pipeline A/B insert; catches straight and curly double-quote variants; fail-loud.
3. Regression test: 26 tests passing, importing the real production function.
4. Scoped reviewed backfill: `19-BACKFILL-REVIEW.md` documents the operator-gated confirm-and-close — the scoped path found zero corrupt rows, so no UPDATE was issued (spine-correct).
5. Fail-loud constraint: `TypeError` on non-str; `logger.error("[QUOTE-FIX]")` on any repair.

The one human verification item (live site visual check) is not a blocking gap — it is the expected end-of-phase visual confirmation that the presentation artifact is absent. All automatable success criteria are verified.

**Note on the "backfill UPDATE" goal clause:** The phase goal originally assumed a stored-data backfill UPDATE would be needed. Plan 01's diagnosis — confirmed independently by Plan 02's scan of all 43 rows — proved storage is already clean (zero corrupt bytes corpus-wide). The confirm-and-close outcome honors the "scoped reviewed" spine constraint: a scoped WHERE on an empty affected set means no UPDATE is the correct, evidence-justified outcome. This is not a deviation from the goal; it is the goal's backfill clause satisfied by verified absence of corruption.

---

_Verified: 2026-06-10_
_Verifier: Claude (gsd-verifier)_
