# Phase 19 — Backfill Review (CORRECTED)

> **This supersedes the original "confirm-and-close" version of this file.** That
> version concluded there was nothing to backfill, because it relied on the original
> (wrong) diagnosis that searched for a literal `"` character. The operator's
> live-site re-check proved corruption was still present; systematic re-investigation
> found the real signature is a **doubled apostrophe** (`''`). See the CORRECTION
> block at the top of `19-DIAGNOSIS.md`. A real, scoped, operator-approved backfill
> was therefore performed.

**Date:** 2026-06-10
**Mutation:** scoped per-row UPDATE on the `newsletters` table, by primary-key `id`
**Approval:** operator approved "full remediation" after reviewing the edition-30
before/after below (production data mutation — operator-gated, per the spine).
**Repair logic:** the REAL production guard `newsletter_poller.normalize_apostrophe_corruption`
(word-flanked `'{2,}` → `'`), reused — not a divergent regex.

## Affected editions (the real signature: word-flanked `''`)

| Edition | Status | Row id | content_markdown | content_markdown_impact | Total |
|---------|--------|--------|------------------|-------------------------|-------|
| 30 | published | `d0d8c978-7feb-4e39-b0fa-9ae7a0426a73` | 35 | 33 | 68 |
| 26 | published | `8cffa0d0-4e66-4b9e-81f8-2bf5d94090ef` | 6 | 24 | 30 |
| 29 | published | `6dca40c3-87c4-4d63-b8c3-ff4b411f278f` | 5 | 0 | 5 |
| **Total** | | | **46** | **57** | **103** |

`content_telegram`, `title`, `title_impact` were clean for all three (no `''`). Held
rows of these editions were clean. Editions 1–25, 27, 28, 31–36, 99, 100 were clean.

## Edition-30 before/after (the operator-reviewed sample)

```
content_markdown:
  BEFORE: ...bottleneck isn''t model pe...   AFTER: ...bottleneck isn't model pe...
  BEFORE: ...erformance, it''s permissi...   AFTER: ...erformance, it's permissi...
  BEFORE: ...ions), Workday''s engineer...   AFTER: ...ions), Workday's engineer...
  BEFORE: ... because there''s no scala...   AFTER: ... because there's no scala...
content_markdown_impact:
  BEFORE: ...d off Cash App''s phased s...   AFTER: ...d off Cash App's phased s...
  BEFORE: ...week the world''s second-l...   AFTER: ...week the world's second-l...
  BEFORE: ...out — and that''s the poin...   AFTER: ...out — and that's the poin...
```

Genuine double-quotes untouched: ed30 cm `"` 24→24, impact `"` 26→26 (asserted per
column before each UPDATE; the transform only removes a duplicated apostrophe char).

## Scope discipline

- UPDATE targeted each affected row by its exact primary-key `id` (the tightest
  possible scope), columns limited to those actually carrying `''`.
- NOT a table-wide or unconditional statement; NOT a blind find-replace.
- Genuine `"` quotations preserved (word-flank discipline + per-column count assert).

## Result (post-UPDATE re-read)

- ed26: doubled-apostrophe runs remaining = 0 — clean tokens present: `it's`, `isn't`
- ed29: doubled-apostrophe runs remaining = 0 — clean tokens present: `it's`
- ed30: doubled-apostrophe runs remaining = 0 — clean tokens present: `Cash App's`, `It's`, `agent's`, `isn't`
- **103/103 repaired, 0 remaining corpus-wide.**
- Live render re-verified end-to-end: edition 30 anon REST fetch → marked v15.0.12 →
  `Cash App&#39;s` (single apostrophe), zero word-flanked double-quotes in output.
- `newsletter` service rebuilt so the corrected guard runs for future editions.
- `web` NOT rebuilt — the renderer is unchanged; correcting stored bytes fixes the
  live render directly.
