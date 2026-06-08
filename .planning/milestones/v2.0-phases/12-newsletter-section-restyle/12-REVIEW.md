---
phase: 12-newsletter-section-restyle
reviewed: 2026-06-04T20:45:20Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/web/site/style-shared.css
  - docker/web/site/index.html
  - docker/web/site/app.js
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-06-04T20:45:20Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

This phase restyled the Newsletter section onto the Phase 11 light-palette/serif
design system (`style-shared.css`), relocated the Technical/Strategic mode toggle
to live only inside the Newsletter list route (`app.js` `showView`,
`index.html` `.hero`), and added a magazine-style reader header
(`renderArticle`). The change is small, well-scoped, and the load-bearing
contracts hold up under adversarial inspection:

- **XSS is clean.** Every DB-derived *string* (`title` in both list rows and the
  reader header) flows through `escapeHtml()`. The two new unescaped
  interpolations introduced this phase — `n.edition_number` /
  `data.edition_number` and `formatDate(...)` output — are provably safe:
  `edition_number` is `INTEGER NOT NULL` (confirmed `supabase/migrations/004_core_tables.sql:108`)
  so it cannot carry HTML metacharacters, and `formatDate()` returns a
  `toLocaleDateString('en-US', …)` value containing only digits, commas, spaces,
  and month names. The markdown body via `marked.parse()` is a pre-existing
  accepted residual (threat T-04-03-01, gated by the operator publish approval),
  not introduced here.
- **Substitution placeholders match.** `__SUPABASE_URL__` /
  `__SUPABASE_ANON_KEY__` in `app.js` are sed-substituted verbatim by
  `docker/web/entrypoint.sh` lines 3-4. Intentional, not bugs.
- **Route-scoping is correct.** `showView()` renders the `.hero` (and its hosted
  toggle/subtitle) only on `viewName === 'list'`; reader/map/block/status/about
  all hide it.
- **No broken element references.** Every `getElementById`/`querySelector` target
  resolves; all load-bearing IDs (`btn-technical`, `btn-strategic`,
  `mode-subtitle`, `hero-headline`, `hero-date`) are preserved; the removed
  `hero-tagline` has zero remaining references. `evolution-entries` is created
  dynamically by `renderBlock()`, not a missing static ID.
- **CSS is sound.** All `var()` references resolve to tokens in `style-base.css`,
  braces balance (65/65), no invalid properties, and the new
  `#newsletter-content > p:first-of-type` lead rule correctly avoids the nested
  `.article-header` eyebrow/byline `<p>`s because `.article-header` is a `<div>`
  (its child `<p>`s are not direct children of `#newsletter-content`).

The findings below are quality/robustness items only. No blocker-class defects.

## Warnings

### WR-01: `escapeHtml(title)` coerces a missing strategic title to the literal string `"null"`

**File:** `docker/web/site/app.js:355-359` (sink at `188`, `246`); `getModeTitle` at `376-379`
**Issue:** `getModeTitle(data)` returns `data.title` when not in strategic mode (or
when `title_impact` is falsy), but if a newsletter row has a NULL `title`
(e.g. a malformed/partial preview record), `getModeTitle` returns `null` / `undefined`.
That value is passed to `escapeHtml(title)`, where
`document.createTextNode(str)` stringifies `null` → the literal text `"null"`.
The list row and reader `<h1 class="page-title">` would then display the word
**null** to the user. This is not an XSS issue (it is HTML-escaped), but it is a
visible data-integrity defect on degraded rows, and it is silent — there is no
fallback or guard. `getModeContent` already defends this case (`return ... || ''`);
`getModeTitle` does not, so the two helpers are inconsistent.
**Fix:** Coalesce in the title helper so a missing title renders empty (or a
placeholder) rather than `"null"`:
```javascript
function getModeTitle(data) {
    if (currentMode === 'strategic' && data.title_impact) return data.title_impact;
    return data.title || '';
}
```
(Optionally also harden `escapeHtml` itself: `document.createTextNode(str == null ? '' : str)`.)

## Info

### IN-01: Toggle/subtitle hide logic in `showView` is redundant with the hero hide

**File:** `docker/web/site/app.js:153-163`
**Issue:** `showView()` explicitly sets `display:none` on `.mode-toggle` and
`#mode-subtitle` for non-list routes (lines 155, 157), then *also* hides the
entire `.hero` for non-list routes (line 163). Because both elements are children
of `.hero`, the hero hide alone fully hides them; the two intermediate lines are
dead belt-and-suspenders. The code comment acknowledges this ("belt-and-suspenders").
Not a bug — it is harmless and intentional — but it is dead conditional surface
that a future edit to the hero structure could silently desync.
**Fix:** Optional. Either keep (documented) or collapse the toggle/subtitle
visibility into the single `.hero` display toggle to remove the duplicated
route predicate.

### IN-02: `renderArticle` recomputes the magazine header on every `setMode()`, but the rendered date can come from `created_at` for non-published rows

**File:** `docker/web/site/app.js:221-251`
**Issue:** `renderArticle` derives `date` from `data.published_at || data.created_at`.
For a `preview`-status edition (which this view explicitly supports, line 232),
`published_at` may be NULL, so the byline date silently falls back to
`created_at` — i.e. the *authoring* timestamp, not a publication date — while the
eyebrow/byline still frame it as edition metadata. This is a minor correctness/UX
ambiguity (a preview shows its draft-creation date dressed as an edition date),
not a crash. Behavior is unchanged from before this phase, but the phase newly
surfaces this date prominently in the byline, raising its visibility.
**Fix:** Optional. For preview rows, either omit the date in the byline or label
it (e.g. `date ? date : 'unpublished preview'`) so a draft timestamp is not
presented as a publication date.

### IN-03: Error-state `<p>` on the reader route inherits the emphasized-lead size

**File:** `docker/web/site/app.js:265-266`; `docker/web/site/style-shared.css:260-264`
**Issue:** The "Edition not found." error message is injected as a direct-child
`<p>` of `#newsletter-content`, so it is matched by the new
`#newsletter-content > p:first-of-type` lead rule (font-size 20px / line-height
1.45). Its inline `color:var(--text-secondary)` wins on color via inline-style
specificity, but the larger lead font-size still applies — so the error message
renders one type-step larger than an ordinary muted message. Purely cosmetic on
an error path.
**Fix:** Optional. Give the error `<p>` a class (e.g. `class="entry-preview"`,
matching the empty-list state on line 171) instead of an inline style so it is
styled as a normal muted message rather than picking up the lead rule.

---

_Reviewed: 2026-06-04T20:45:20Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
