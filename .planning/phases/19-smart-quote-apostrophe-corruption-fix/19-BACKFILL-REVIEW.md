# Phase 19 Plan 02 — Backfill Review (CONFIRM-AND-CLOSE)

**Date:** 2026-06-10
**Task:** 19-02 Task 1 — read-only scan + single-edition before/after review
**Method:** READ-ONLY SELECT against the live production Supabase `newsletters` table
(`SUPABASE_URL` + `SUPABASE_SERVICE_KEY`/`SUPABASE_KEY` from `config/.env`, supabase-py
`create_client`, wired exactly as `tests/test_3c_newsletters.py`). **No data was mutated.**
**Repair logic:** the canonical Plan 01 write-path fix
`nl.normalize_apostrophe_corruption` (`import newsletter_poller as nl`), regex
`(?<=[A-Za-z0-9])"(?=[A-Za-z0-9])` → `'`. **Not** a second, divergent regex — the scan's
signature and the would-be repair are byte-identical to the write-path guard.

> **Bottom line for the operator: there is NOTHING to backfill.** The independent scan
> reproduces Plan 01's diagnosis from live stored bytes — the corruption signature count
> is **0** corpus-wide, the affected-edition list is **EMPTY**, and running the canonical
> repair over edition 30 returns the **identical** string (zero replacements). This is a
> **confirm-and-close** review: **no scoped UPDATE is warranted because there is no corrupt
> data to repair.**

---

## 1. Affected-edition list (the scoped-UPDATE target set)

A read-only scan of **all 43** newsletter rows (every `edition_number`, every status),
checking `content_markdown`, `content_markdown_impact`, and `content_telegram` for the
proven corruption signature (a U+0022 `"` flanked by word characters — the literal `App"s`
shape):

```
Scanned 43 newsletter rows
TOTAL mid-word U+0022 corruption-signature occurrences corpus-wide: 0
AFFECTED EDITIONS: NONE (empty list)
```

| Edition | content_markdown | content_markdown_impact | content_telegram |
|---------|------------------|-------------------------|------------------|
| _(none)_ | 0 | 0 | 0 |

**Per-column occurrence counts: 0 / 0 / 0 across the entire table.** The affected-edition
list is empty — including the ROADMAP-named exemplar, edition 30. No edition (held 25–29/32,
published, or draft 34) carries the signature in any of the three columns.

---

## 2. Edition 30 BEFORE / AFTER (computed via the canonical Plan 01 fix)

Edition 30 has **two rows** (`status=held`, `status=published`). Each affected-candidate
column was run through `nl.normalize_apostrophe_corruption(...)`. Because storage is clean,
**BEFORE == AFTER** for every column (zero replacements):

| Row | Column | len | mid-word U+0022 (BEFORE) | Repairs made | mid-word U+0022 (AFTER) | BEFORE == AFTER |
|-----|--------|-----|--------------------------|--------------|--------------------------|-----------------|
| published | `content_markdown` | 12202 | 0 | **0** | 0 | **YES (identical)** |
| published | `content_markdown_impact` | 8389 | 0 | **0** | 0 | **YES (identical)** |
| published | `content_telegram` | (empty/absent) | 0 | 0 | 0 | YES |
| held | `content_markdown` | 6640 | 0 | **0** | 0 | **YES (identical)** |
| held | `content_markdown_impact` | 5038 | 0 | **0** | 0 | **YES (identical)** |
| held | `content_telegram` | 299 | 0 | 0 | 0 | YES |

### ROADMAP tokens — apostrophe-slot codepoint (BEFORE) → (AFTER, unchanged)

The four ROADMAP-named tokens (`Cash App's`, `It's`, `world's`, `agent's`) — wherever they
occur in edition 30 — already store a clean straight apostrophe (U+0027 / ord 39) in the
apostrophe slot. There is no stray `"` to repair, so AFTER is identical:

| Row | Column | Token | BEFORE slot | AFTER slot |
|-----|--------|-------|-------------|------------|
| published | `content_markdown` | `Cash App's` | `...kicked off Cash App's phased stab...` → U+0027 (ord 39) | unchanged — U+0027 |
| published | `content_markdown` | `week's` | `...Last week's BadHost...` → U+0027 (ord 39) | unchanged — U+0027 |
| held | `content_markdown` | `agent's` | `...An agent's authority...` → U+0027 (ord 39) | unchanged — U+0027 |
| held | `content_markdown_impact` | `It's` (×2) | `...gets lost. It's like giving...` / `...methods. It's the early...` → U+0027 | unchanged — U+0027 |
| held | `content_markdown_impact` | `agent's` | `...An agent's authority...` → U+0027 (ord 39) | unchanged — U+0027 |

`world's` does not occur as a token in edition 30's stored bodies (it was a ROADMAP example,
not a guaranteed edition-30 string); every token that DOES occur is already clean. **AFTER ==
BEFORE in every case — the canonical repair is a no-op on edition 30.**

---

## 3. Genuine double-quote preservation (sanity)

The transform repairs ONLY the apostrophe signature (word-char + `"` + word-char). Genuine
double-quotes (flanked by whitespace/punctuation) are left untouched. Edition 30 contains
genuine `"` quotes, and **all** are correctly classified as genuine (corruption-sig = 0):

| Row | Column | total `"` | corruption-sig | genuine (untouched) |
|-----|--------|-----------|----------------|---------------------|
| published | `content_markdown` | 24 | 0 | **24** |
| published | `content_markdown_impact` | 26 | 0 | **26** |
| held | `content_markdown` | 2 | 0 | **2** |
| held | `content_markdown_impact` | 4 | 0 | **4** |

A scoped UPDATE (were one warranted) would leave every one of these genuine quotes intact,
per threat T-19-03 / T-19-11.

---

## 4. Scoped UPDATE plan — CONFIRM-AND-CLOSE: no UPDATE to run

The spine (PROJECT.md) requires that any backfill be a **scoped, reviewed UPDATE** with a
`WHERE edition_number IN (...)` clause targeting only the affected editions — **never a blind
table-wide find-replace**. Applying that rule here:

- **Affected `edition_number` set = `∅` (empty).** The scoped `WHERE edition_number IN (...)`
  clause would have **no values** to populate. There is no in-scope row to mutate.
- **Therefore no UPDATE statement is proposed or warranted.** Issuing any UPDATE here would
  either be (a) a no-op rewriting already-correct bytes to themselves (pointless mutation of
  production rows), or (b) — if widened to "have something to change" — a blind table-wide
  find-replace, which the spine **forbids** (threat T-19-13). Both are rejected.
- **This closes the backfill.** The QUOTE-01 "fix forward so it cannot recur" mandate is
  already satisfied by Plan 01's fail-loud `nl.normalize_apostrophe_corruption` guard at the
  shared `save_newsletter` insert (covers single-pass + block-pipeline write paths) and the
  17-case QUOTE-02 regression. New editions are protected; existing editions need nothing.

**Recommended disposition for the Task 2 operator gate:** approve **CONFIRM-AND-CLOSE** — no
scoped UPDATE, no `web` rebuild (renderer ruled out in 19-DIAGNOSIS.md §3), proceed to close
Plan 02 / Phase 19. The Task 3 live-mutation + content-service rebuild is **not needed**
because there is no corrupt data to backfill and the write-path fix already shipped in Plan 01.

---

## 5. Plan-01 consistency

This scan **independently reproduces** 19-DIAGNOSIS.md and the 19-01-SUMMARY.md conclusion
from live stored bytes (43 rows, signature count 0, edition-30 slots all U+0027). There is
**no contradiction** with Plan 01 — both agree the stored corpus is clean and the ROADMAP's
stray double-quote is a presentation/glyph artifact, not a data defect. No "fabricated"
corruption was invented to manufacture a backfill; the honest result is an empty affected set.

**No data was mutated by this task (SELECT only).**
