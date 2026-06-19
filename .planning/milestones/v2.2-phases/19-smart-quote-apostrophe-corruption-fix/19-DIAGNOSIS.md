# Phase 19 — Apostrophe Corruption Root-Cause Diagnosis

> ## ⚠ CORRECTION (2026-06-10, supersedes §4 below)
>
> **The original conclusion in this document was WRONG.** The operator confirmed at
> phase verification that the live site still rendered `Cash App"s`. A systematic
> re-investigation of the full storage→render pipeline found the true root cause:
>
> **The corruption is a DOUBLED APOSTROPHE (`''` — two adjacent U+0027), not a
> double-quote character.** Two straight apostrophes side-by-side render as a *visual*
> double-quote in the Source Serif 4 body face, so `Cash App''s` looks like
> `Cash App"s`. Proven: **103 `''` runs across published editions 26, 29, 30**
> (ed30 cm=35/impact=33, ed26 cm=6/impact=24, ed29 cm=5). Recent editions (31–36)
> are clean, so the source (model emission of `''` in those runs) is dormant.
>
> **Why the original diagnosis missed it:** it searched only for a literal U+0022 `"`
> (and curly variants) and spot-checked the *first* `Cash App's` occurrence — which is
> a clean single apostrophe — so it never saw the doubled `''` in the *other*
> occurrences and wrongly declared the corpus clean. The real signature is `'{2}`,
> not `"`. The render layer is genuinely clean (verified end-to-end: anon REST
> delivery → marked v15.0.12 → `App&#39;s`); the corruption was in stored bytes.
>
> **Resolution:**
> - Write-path guard `normalize_apostrophe_corruption` corrected to collapse
>   word-flanked `''` → `'` (proven signature) + keep the defensive mid-word
>   double-quote repair; fail-loud. Regression suite 36 passing.
> - Scoped backfill applied to the 3 published rows (by primary-key `id`): 103
>   doubled runs collapsed; post-UPDATE re-read = 0 remaining; genuine `"` quotes
>   preserved (counts unchanged). `newsletter` service rebuilt to ship the guard.
> - Live render re-verified clean (edition 30 anon-fetch → marked → `Cash App's`).
>
> The original byte analysis below remains accurate *as far as it went* (edition 30
> does contain clean U+0027 apostrophes and zero U+0022) — it simply asked the wrong
> question and never counted `''`. Kept for the record.

**Date:** 2026-06-10
**Method:** READ-ONLY SELECT against the live production Supabase `newsletters` table
(`SUPABASE_URL` + `SUPABASE_SERVICE_KEY` from `config/.env`, supabase-py `create_client`,
exactly as `tests/test_3c_newsletters.py` wires its client). No stored data was mutated.

The corruption signature under investigation (from the ROADMAP): an apostrophe
(`'` U+2019 or `'` U+0027) appearing in edition bodies as a stray **straight double-quote**
`"` (U+0022) — e.g. `Cash App's` → `Cash App"s`, `It's` → `It"s`, `world's`, `agent's`.

---

## 1. Raw stored-byte evidence — edition 30 (the named exemplar)

Edition 30 has two rows (`status=held` and `status=published`). For each ROADMAP-named
token, the diagnostic located every occurrence and printed `ord()` of the character standing
in the apostrophe slot. Results:

### Edition 30 — `status=published` (the live row)

| Token (stored context)            | Apostrophe-slot codepoint | Verdict |
|-----------------------------------|---------------------------|---------|
| `...ed off Cash App's phased...`  | **ord=39 → U+0027** (straight apostrophe) | CORRECT |
| `...Last week's BadHost-an...`    | **ord=39 → U+0027** | CORRECT |

- `content_markdown` (len 12202): U+2019 curly apostrophes = **0**; U+0027 straight apostrophes = **72**;
  **mid-word U+0022 double-quotes = 0**.
- `content_markdown_impact` (len 8389): U+2019 = 0; U+0027 = 66; **mid-word U+0022 = 0**.

### Edition 30 — `status=held`

- `content_markdown`: `An agent's authority` → middle char **ord=39 (U+0027)**.
  Curly = 0, straight = 21, **mid-word U+0022 = 0**.
- `content_markdown_impact`: `It's like giving` / `It's the early` / `agent's authority`
  → every apostrophe slot **ord=39 (U+0027)**. Curly = 0, straight = 25, **mid-word U+0022 = 0**.

**Every apostrophe in edition 30 is stored as a clean straight apostrophe (U+0027 / ord 39).
Zero are stored as a double-quote. The `App"s` / `It"s` corruption is NOT present in the
stored bytes of edition 30.**

A deep follow-up scan for *any* anomalous codepoint (non-ASCII inventory, mid-word U+0022,
U+FFFD replacement char, control chars, and mojibake signatures `Ã` / `â€™` / `Â`) found
**none** in editions 29/30/31 — only legitimate em-dashes (U+2014), arrows (U+2192), and
status emoji (🔴/🟡). No mojibake, no encoding round-trip damage.

## 2. Corpus-wide confirmation (whole `newsletters` table)

A table-wide scan of **every** newsletter row (editions 1–100+, all statuses) counted the
corruption signature (a U+0022 double-quote flanked by word characters — the literal `App"s`
shape) in both body fields:

```
mid-word U+0022 (App"s signature) across the ENTIRE newsletters table: 0
```

Apostrophes are stored uniformly as straight **U+0027** in every edition; curly **U+2019**
appears essentially never (0–1 incidental). **No row in the table contains the
apostrophe→double-quote corruption in its stored markdown.**

## 3. Render layer ruled out

`docker/web/site/app.js` fetches `content_markdown` / `content_markdown_impact` verbatim
(`getModeContent`, lines ~452–455 — a plain field read, no substitution) and renders with
`marked.parse(content)` (line ~321). There is **no** `marked.setOptions` / `marked.use`
call anywhere in `app.js`, so `smartypants` / typographer is OFF (and `smartypants` was
removed from `marked` entirely in v5+; the CDN build at `index.html:147` loads `marked.min.js`
with defaults). `marked` therefore performs no `'`→`"` or `'`→`"` transform. The render path
introduces no apostrophe corruption.

---

## 4. Conclusion — STORAGE is clean; the write path does NOT corrupt apostrophes

**The corruption is NOT in stored markdown and is NOT introduced at render.** The stored
bytes are correct (clean U+0027 apostrophes, zero mid-word double-quotes, corpus-wide), and
the renderer has no typographer. The plan's primary hypothesis ("write-path storage
corruption that must be repaired") is **refuted by the bytes** — there is no stored corruption
to repair.

Whatever stray-double-quote the ROADMAP screenshot captured is therefore a **presentation
artifact** (a font/glyph rendering of the straight U+0027 apostrophe in the serif body face,
or a since-resolved/deploy-skew render state), **not** a data-integrity defect in the pipeline
or the stored editions. No backfill of stored bodies is warranted by the evidence (this
de-risks Plan 02 — there is no corrupt data to UPDATE; Plan 02 should confirm-and-close, not
mass-edit).

## 5. Chosen fix site — a fail-loud, no-op-on-clean write-path GUARD

Because storage is already clean, the QUOTE-01 mandate ("fix forward so the corruption cannot
recur") and the QUOTE-02 regression both attach to a single **defensive normalization guard**
installed on the write path, NOT a destructive repair of (non-existent) corruption:

- **Function:** `normalize_apostrophe_corruption(text: str) -> str` — a new pure helper in
  **`docker/newsletter/newsletter_poller.py`**, called inside **`save_newsletter`**
  (newsletter_poller.py, the `row = {...}` assembly at **lines ~1467–1478**) for both
  `content_markdown` and `content_markdown_impact` immediately before the
  `supabase.table("newsletters").insert(row)` at line ~1481.

- **Behavior (targets ONLY the proven signature; preserves genuine quotes):**
  - Repairs ONLY the exact corruption shape — a straight double-quote (U+0022) flanked by
    word characters where an apostrophe belongs (`App"s`, `It"s`, `world"s`) → U+0027.
    This is a tightly-scoped regex (`(?<=[A-Za-z])"(?=[A-Za-z])`), **never** a blanket
    `"`→`'` replacement (that would destroy legitimate quotation marks — threat T-19-03).
  - **No-op on the entire existing clean corpus** (corpus mid-word-U+0022 count = 0), and a
    **no-op on genuine quotations** like `He said "ship it"` (the `"` there is flanked by a
    space, not word chars), so it cannot regress the 30+ clean editions.
  - **Fail-loud (project "the wallet bug" rule):** raises `TypeError` on non-`str` input and
    `logger.error`s loudly (with edition + count) whenever it actually rewrites a character —
    so any future recurrence is surfaced, never silently passed through.

- **Block-pipeline path:** the block writer's assembled bodies (`block_pipeline.py`
  `generate_from_blocks`, `content_markdown` / `content_markdown_impact` at ~681–682) flow
  into the SAME `save_newsletter` insert, so guarding at `save_newsletter` covers both the
  single-pass and block-pipeline write paths with one fix site. No change to `block_pipeline.py`
  logic is required; the guard at the shared insert is sufficient.

- **Canonical function + import path the regression test (Task 3) uses:**
  `import newsletter_poller as nl` (conftest preloads it) → `nl.normalize_apostrophe_corruption`.
  **Plan 02's backfill MUST reuse this exact function** so any backfill repair matches the
  write-path fix byte-for-byte.

**One-line justification:** the bytes prove there is nothing to repair in storage, so the
"fix forward" is a scoped, fail-loud, no-op-on-clean guard at the single shared write-path
insert (`save_newsletter`) — it cannot damage the clean corpus or genuine quotes, and it
locks the corruption out for newly generated editions (QUOTE-01) under a real regression test
(QUOTE-02).
