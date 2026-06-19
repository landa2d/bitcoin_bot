# Phase 23: Distinct Newsletter Excerpts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 23-distinct-newsletter-excerpts
**Areas discussed:** Excerpt extraction logic, Summary line treatment, Fallback & mode-awareness

---

## Gray-area selection

| Area | Description | Selected for discussion |
|------|-------------|-------------------------|
| Excerpt extraction logic | What becomes the row summary after stripping the header | ✓ |
| Latest vs uniform rows | Mockup's featured "Latest" block vs uniform indexed rows | (skipped — defaulted to mockup intent / planner discretion) |
| Summary line treatment | Length/wrapping of the extracted summary | ✓ |
| Fallback & mode-awareness | Behavior on extraction failure + Technical/Strategic mode | ✓ |

---

## Excerpt extraction logic

### Q1 — What should the row's one-line summary BE (after stripping the `## Read This, Skip the Rest` header)?

| Option | Description | Selected |
|--------|-------------|----------|
| This-week thesis | Skip header + leading "Last week…" recap sentence(s); show the first pivot sentence. Keeps the editorial thesis; risk of thin pivots. | ✓ |
| First content sentence | Skip the ENTIRE recap section to the next `##`; show the first content sentence. Most concrete, loses thesis framing. | |
| First sentence after header | Strip only the H2; show the first (recap) sentence as-is. Simplest; both editions read "Last week's…" so similar at a glance — fails SC#1's "shared intro sentence skipped". | |

**User's choice:** This-week thesis
**Notes:** Previews used real ed 29/30 technical bodies. Surfaced the thin-pivot risk (ed29 → "This week it got specific."), handled in Q2.

### Q2 — When the pivot sentence is very short / low-information, what should the summary do?

| Option | Description | Selected |
|--------|-------------|----------|
| Append next sentence | If chosen sentence < ~40 chars, append the following sentence for substance (ed29 → "This week it got specific. Researchers exposed BadHost…"). | ✓ |
| Skip to substantive | Treat short connective pivots as boilerplate; keep skipping to the first content-carrying sentence. | |
| Accept as-is | Show the pivot verbatim even if terse. Simplest, but some rows thin/uninformative. | |

**User's choice:** Append next sentence
**Notes:** Pairs with the 2-line clamp chosen in the Summary area to bound combined length. ~40-char floor is the starting point (planner finalizes).

### Q3 — How should the renderer decide WHICH leading sentence(s) are the recap to skip?

| Option | Description | Selected |
|--------|-------------|----------|
| Match look-back phrases | Only skip leading sentences matching a recap pattern ("Last week", "For weeks", "Two editions ago", "For N editions", "Last month"…); if none match, keep the first sentence — never over-strip. | ✓ |
| Always skip first sentence | Drop sentence 1 unconditionally. Simpler, but an edition opening straight into content loses its real first sentence (silent content loss). | |

**User's choice:** Match look-back phrases
**Notes:** Conservative / no-silent-loss — aligns with the fail-loud spine. May need to skip more than one stacked recap sentence.

---

## Summary line treatment

### Q1 — How should the row summary be bounded when the extracted text runs long?

| Option | Description | Selected |
|--------|-------------|----------|
| Clamp to 2 lines | CSS line-clamp to 2 lines + ellipsis; full text stays in the DOM. Pairs with the append-next-sentence rule; scannable, no mid-word cuts. | ✓ |
| Clamp to 1 line | Densest, closest to mockup; but largely defeats the append rule (clips appended substance). | |
| Hard char cap (~160) + … | Layout-independent, predictable; but cuts real text out of the DOM, needs word-boundary handling. | |

**User's choice:** Clamp to 2 lines
**Notes:** Also captured (no fork): proper markdown cleanup is required — convert `[text](url)` → `text` and drop URLs, since the current crude strip leaks link URLs into the text.

---

## Fallback & mode-awareness

### Q1 — When extraction can't produce a clean distinct sentence, what should that row show?

| Option | Description | Selected |
|--------|-------------|----------|
| First sentence, else drop summary | Fall back to body's first cleaned sentence; if empty/missing, render number · title · date with no summary. Never boilerplate, never fabricate, never break the row. | ✓ |
| Reuse legacy 150-char clamp | Always shows something, but can reintroduce the exact boilerplate-leak this phase fixes. | |
| Title + date only | On any miss, no summary at all — no raw-body fallback. Cleanest, but loses usable summaries for non-standard editions. | |

**User's choice:** First sentence, else drop summary

### Q2 — Should the row summary stay mode-aware or be fixed to one mode?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep mode-aware | Summary derives from content_markdown / content_markdown_impact, flipping with the toggle — same as today, consistent with the mode-aware title. | ✓ |
| Fix to one mode | Always one mode regardless of toggle. More stable, but could diverge from the article a Technical reader opens and from the title. | |

**User's choice:** Keep mode-aware

---

## Claude's Discretion

- **Latest vs uniform rows** (not selected for discussion): default to uniform indexed rows following the mockup's `.row` format; adopting the mockup's featured "Latest" block (display title + lede + readlink) is optional polish left to planner, and must not duplicate the existing Phase 21 hero + mode toggle.
- Exact sentence-segmentation algorithm (markdown-link dots, colon clauses, em-dashes, abbreviations); the exact recap-pattern regex and the ~40-char length floor; grid-vs-flex for the row; delete-vs-leave-dormant for the legacy `.article-entry` CSS.
- `num` = `edition_number` (per mockup), `title` = `getModeTitle` (Phase 22 suffix strip reused), `date` = `formatDate(published_at)`.

## Deferred Ideas

- **Stored/generated `summary` field (EXCERPT-F1)** — the cleaner long-term path (Newsletter agent emits a one-line summary at generation time; schema + pipeline change). Deferred out of this milestone by the strip-at-render decision.
- **Mockup "Latest" featured block** — magazine-style top treatment above the archive rows; candidate for a later iteration.
