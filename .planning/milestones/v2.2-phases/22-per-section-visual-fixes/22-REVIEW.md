---
phase: 22-per-section-visual-fixes
reviewed: 2026-06-12T13:30:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/web/site/app.js
  - docker/web/site/index.html
  - docker/web/site/style-shared.css
findings:
  critical: 0
  warning: 0
  info: 4
  total: 4
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-06-12
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 22 frontend-only diff (`git diff 7ae30a8..HEAD -- docker/web/site/`): HEAD-01 (edition-suffix strip + eyebrow removal in `app.js`), GRID-01/02 (3-col tier grid + maturity legend), and AGENTS-01 (About `made-cols` rewrite). All stated project constraints hold: the CSS is token-only (every new `var(--…)` — `--accent-soft`, `--accent-ink`, `--space-2xl`, `--radius`, `--line`, etc. — resolves to a real `:root` token in `style-base.css`; no hardcoded hex, no `--violet`, no `--line-soft`), the `__SUPABASE_*__` placeholders are intact (`app.js:4-5`), and no new `economy_map` query was added. The XSS posture is correct: `EDITION_SUFFIX_RE` runs on the raw string inside `getModeTitle` (`app.js:582`) and the result is `escapeHtml`'d only later at the H1/anchor sinks (`renderArticle:445`, `renderList:383`) — escape order is preserved with no bypass; the legend and About copy are static literals with no DB interpolation.

The regex itself is sound: it is non-global (no shared-`lastIndex` hazard under `.replace`), anchored to `$` (trailing-only), and the mandatory `\|` after `#\d+` prevents over-stripping interior "Edition #N" headline text. The `.grid` 2→3 change is correctly scoped (only the hub tier cards use `.grid`; `renderStatus` does not), and `.card-deferred { grid-column: 1 / -1 }` still spans full width under 3 columns. No BLOCKER or correctness WARNING was found. The remaining findings are maintainability/standards Info items — the AGENTS-01 markup swap left dead CSS, stale comments, and one non-conformant HTML nesting.

## Info

### IN-01: Orphaned `.agent-row` / `.agent-pill` CSS after AGENTS-01 markup swap

**File:** `docker/web/site/style-shared.css:929-966`
**Issue:** AGENTS-01 replaced the `#about` markup from `.agent-row` / `.agent-pill` / `.agent-pill .an` / `.agent-pill .ad` to the new `.made-cols` / `.agent` structure. The old selectors are now dead — a repo-wide grep finds no remaining markup consumer (only a stale comment at `index.html:114`). This is dead code that will mislead future maintainers into thinking two About layouts coexist.
**Fix:** Delete the orphaned rule block (`.agent-row`, `.agent-pill`, `.agent-pill .an`, `.agent-pill .ad`) and its now-inaccurate comment header at `style-shared.css:886-894`.
**Disposition:** DEFERRED by plan — 22-02 explicitly scoped this cleanup out ("Do NOT modify the existing `.agent-row` rules (now unused but harmless — leave them; cleanup is out of scope)"). Candidate for Phase 25 holistic pass.

### IN-02: Stale comments describe the removed 5-pill agent row

**File:** `docker/web/site/index.html:108-116` (also `docker/web/site/style-base.css:327`)
**Issue:** The `#about` section comment still describes the deleted layout — "5-pill agent row", "5 content-agent pills only", ".agent-row tiled grid spans the wide axis" — none of which exist after AGENTS-01. `style-base.css:327` similarly references an ".about .agent-row .wide" de-dupe that no longer applies to this markup. Misleading documentation against the shipped DOM.
**Fix:** Update the `#about` comment to describe the `made-cols` numbered-pipeline + supporting-layer + `.approval` callout structure; reword/remove the `.agent-row` reference in the `style-base.css` width de-dupe comment.
**Disposition:** Advisory (doc drift, no behavior). Candidate for Phase 25 holistic pass.

### IN-03: Block-level `<p>` nested inside inline `<span>` in `.agent` rows

**File:** `docker/web/site/index.html:134-145`
**Issue:** Each agent row wraps its text column as `<span><p class="name">…</p><p class="desc">…</p></span>`. A `<p>` (flow content) inside a `<span>` (phrasing content) is non-conformant HTML. Browsers parse it leniently (the `<p>` does not auto-close the `<span>`, so it renders correctly today because the span is blockified as a grid item), but it is invalid markup that can surprise tooling/validators and is fragile to future CSS that assumes inline semantics on `.agent > span`.
**Fix:** Use a block wrapper for the text column, e.g. replace the inner `<span>…</span>` with `<div>…</div>` (the grid `1fr` column behaves identically), so the `.name` / `.desc` paragraphs sit in valid flow content.
**Disposition:** Advisory — renders correctly; markup/A11Y full pass is Phase 25. Low-risk, low-effort; could fold into Phase 25.

### IN-04: Dead `.article-header .eyebrow` rule after eyebrow removal

**File:** `docker/web/site/style-shared.css:657`
**Issue:** HEAD-01 removed the `<p class="eyebrow">` line from `renderArticle` (`app.js`), so the `.article-header .eyebrow` selector no longer matches any rendered element. The bare `.eyebrow` rule (`style-base.css:103`) is still used by the `#signals`/`#about` static eyebrows, but the `.article-header`-scoped variant is now dead.
**Fix:** Remove the `.article-header .eyebrow` rule (and trim the adjacent comment that lists "eyebrow → serif display title → mono byline") to match the new headline-only magazine header.
**Disposition:** DEFERRED by plan — 22-01 explicitly noted "the now-dead `.article-header .eyebrow` rule at `style-shared.css:649-651` is harmless and is NOT removed in this phase." Candidate for Phase 25 holistic pass.

---

_Reviewed: 2026-06-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
