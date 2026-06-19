---
phase: 23-distinct-newsletter-excerpts
plan: 01
subsystem: web-frontend
tags: [excerpt, newsletter-list, render-only, strip-at-render, indexed-row, css-clamp, xss]
requires:
  - "Phase 22 getModeTitle()/EDITION_SUFFIX_RE title chokepoint (reused, not regressed)"
  - "Phase 21 #newsletter landing section + currentMode mode-toggle (re-render on flip)"
  - "Phase 20 --wide axis + :root tokens (--line/--accent/--ink*/--serif/--mono/--space-*/--radius-dot)"
provides:
  - "RECAP_OPENER_RE + cleanExcerptMarkdown / splitSentences / extractDistinctExcerpt pure DOM-free helpers (app.js)"
  - "indexed-row renderList() markup (num·title·sum·date as one #/edition/<n> deep-link)"
  - "token-only .row / .num / .title / .sum (2-line clamp) / .date / .archive-label CSS"
affects:
  - "docker/web/site/app.js (renderList render path only — loadList untouched)"
  - "docker/web/site/style-shared.css (net-new block; legacy .article-entry family left dormant)"
tech-stack:
  added: []
  patterns:
    - "render-only / never-over-strip defensive-no-op spine (mirrors trimHubBody/stripLeadingTitleH1)"
    - "escapeHtml at every DB-derived innerHTML sink; numeric edition_number interpolated raw"
    - "net-new 4-property -webkit-line-clamp:2 (visual clamp, full text retained in DOM)"
key-files:
  created:
    - "/tmp/excerpt_check.mjs (executor-authored offline harness — NOT shipped/committed)"
  modified:
    - "docker/web/site/app.js"
    - "docker/web/site/style-shared.css"
decisions:
  - "Fixtures sourced from the documented real ed28/29/30 structure (CONTEXT + Plan 02 + discussion log); a read-only DB fetch to author authentic text was blocked by the auto-mode classifier per the plan's no-network/no-config constraint — honored. Live verification on real rows is Plan 02."
  - "extractDistinctExcerpt splices ONLY the exact `## Read This, Skip the Rest` boilerplate heading line (defensive, no-op otherwise) — matches D-01 precisely rather than blanket-stripping any leading heading."
  - "EXCERPT_MIN_CHARS finalized at 40 (ed29-tech 'This week it got specific.' = 26 is the sole corpus trigger)."
metrics:
  duration: ~14min
  tasks: 3
  files: 2
  completed: 2026-06-15
---

# Phase 23 Plan 01: Distinct Newsletter Excerpts Summary

Strip-at-render excerpt pipeline + indexed-row archive markup that skips the `## Read This, Skip the Rest` boilerplate header and the shared recap intro, surfaces each edition's first genuinely-distinct "This week…" sentence (mode-aware, link-URLs cleaned), and renders it in the mockup's number·title·summary·date grid with a 2-line CSS clamp — implementing all ten CONTEXT decisions D-01..D-10. Frontend-only; no schema change, no new Supabase query, no content-pipeline change.

## What Was Built

**Task 1 — pure DOM-free excerpt helpers (`app.js`, commit `bbda2f4`)**
A contiguous block wrapped in `// --- excerpt helpers (node-testable) START/END ---` sentinels, placed after `stripLeadingTitleH1`, mirroring the codebase's render-only defensive-no-op spine:
- `RECAP_OPENER_RE` — `^`-anchored, case-insensitive look-back detector covering `Last week[/'s/ we]`, `Last month`, `For weeks`, `For <N> editions` and `<N> editions ago` (N = digit run OR `one`..`ten`/`several`/`many`) (D-03).
- `EXCERPT_MIN_CHARS = 40` — thin-pivot floor (D-04).
- `cleanExcerptMarkdown(md)` — `[text](url)`→`text`, drop bare URLs, strip residual inline markers (no blanket bracket strip, no 150-char truncation) (D-05).
- `splitSentences(text)` — terminator/closing-quote-aware split; never splits on a colon or em-dash (D-02).
- `extractDistinctExcerpt(md)` — header splice → clean → split → recap-skip (keep ≥1) → thin-pivot append → trimmed result or `''` (D-01/D-02/D-03/D-04/D-07).

**Task 2 — `renderList()` rewrite (`app.js`, commit `fba0478`)**
Replaced the `data.map(...)` body (and removed the crude `…replace(…).substring(0,150)+'...'` strip and `.article-entry` markup). Each edition now renders as one `<a class="row" href="#/edition/<n>">` wrapping `<span class="num">` (raw numeric), a nested `<span>` with `<p class="title">` (via `getModeTitle`) + a CONDITIONAL `<p class="sum">` (via `extractDistinctExcerpt(getModeContent(n))`), and `<span class="date">`. A static `<p class="archive-label">Archive</p>` precedes the rows. Every DB-derived string is `escapeHtml`'d; `edition_number` is the only raw interpolation (D-06 DOM-side / D-07 conditional sum / D-08 mode-aware / D-09 row grid). The empty-state branch, hero update, and `loadList()` are byte-identical.

**Task 3 — token-only indexed-row CSS (`style-shared.css`, commit `0754a32`)**
Net-new `.archive-label` / `.row` (grid `56px 1fr auto`) / `.num` / `.title` / `.sum` / `.date` block after `.entry-preview`, plus `.row:hover`, `.row:focus-visible`, and a `@media (max-width: 600px)` reflow. The D-06 4-property `-webkit-line-clamp:2` clamp is the net-new idiom (visual only; full text stays in the DOM). Mockup→prod token mapping applied per the 23-PATTERNS gotcha: `--line-soft`→`--line`, `--violet`→`--accent` (neither mockup token exists in `:root` — porting verbatim silently no-ops). Zero hex literals. The legacy `.article-entry` family is left DORMANT (not deleted — `.entry-preview` is still consumed by the map error state + list empty-state) (D-10).

## Verification

| Gate | Result |
|------|--------|
| `node --check docker/web/site/app.js` | exits 0 |
| `node /tmp/excerpt_check.mjs` (offline harness, 24 assertions) | ALL PASS |
| SC#1 ed29 ≠ ed30, Technical AND Strategic | pass (both modes) |
| ed30 link leak gone (no `https://`, no `](`) | pass |
| ed29 thin-pivot append (`>40`, "This week it got specific…") | pass |
| ed28 recap skip / ed29 closing-quote split / stacked recap / no-recap keep / empty→'' | pass |
| XSS: hostile `<img onerror>` title escaped | pass |
| CSS verify (braces balanced, no `--line-soft`/`--violet`, has `-webkit-line-clamp:2`) | pass |
| Frozen invariants | `.in('status',['published','preview'])`=2, `.eq('status'`=11, `substring(0, 150)`=0, `class="article-entry"`=0, `__SUPABASE_*__`=2 |

The harness is offline + deterministic (embedded ed28/29/30-shaped fixtures, no network, no `config/.env`) and was run before each commit (`class="row"`-conditional, so it passed at the Task 1 helpers-only stage and the Task 2 row-builder stage). It is NOT shipped/committed.

## Deviations from Plan

None — plan executed exactly as written across all three tasks. All Rules 1–4 untriggered.

**Methodology note (not a code deviation):** to author authentic fixtures, an attempt was made to read editions 28/29/30 from Supabase via the main-tree `config/.env`. The auto-mode classifier correctly blocked it as a violation of the plan's explicit "no network / no config/.env" worktree-safety constraint. Fixtures were instead constructed from the documented real structure (23-CONTEXT.md observed structure, 23-02-PLAN.md expected ed29/ed30 shapes, 23-DISCUSSION-LOG.md), which is sufficient for SC#1 at the unit level. Acceptance against the actual live ed29/30 rows (both modes) is explicitly Plan 02's orchestrator-owned live-render verification.

## Known Stubs

None. The excerpt pipeline is fully data-wired (reads real `content_markdown` / `content_markdown_impact` via the existing `getModeContent()`); no hardcoded empty values, placeholder text, or unwired components introduced. The `#signals` static shell is a prior-phase (21) artifact owned by Phase 24, untouched here.

## Threat Surface

No new network endpoints, auth paths, file-access patterns, or schema/trust-boundary changes introduced beyond the plan's `<threat_model>`. T-23-01/02 (XSS) mitigated — every DB-derived interpolation `escapeHtml`'d at the innerHTML sink; the list path never calls `marked.parse`. T-23-03 (silent content drop) mitigated — fail-loud recap-skip keeps ≥1 sentence, no-recap keeps sentence 1, empty omits the `.sum` line.

## Self-Check: PASSED

- Modified files exist: `docker/web/site/app.js` FOUND, `docker/web/site/style-shared.css` FOUND
- Commits exist: `bbda2f4` FOUND, `fba0478` FOUND, `0754a32` FOUND

## Handoff to Plan 02

Source is ready for the orchestrator-owned, worktree-unsafe scoped `web` rebuild + live verification (Plan 02): drift-check → `/diff` of the two web files → scoped `docker compose up -d --build web` (SERVICE key `web`, NO `--delete`) → operator approval → confirm ed29 ≠ ed30 in both modes on the substituted live render.
