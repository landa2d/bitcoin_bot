---
phase: 13-agent-economy-grid
plan: 02
subsystem: web-frontend
tags: [ui, block-detail, status, timeline, css, app.js, de-dark, single-accent, delete-and-fold]
requires:
  - "13-01 (hub card grid + de-darkened .maturity-pill/.tier-label/.hub-storyline + per-tier cascade deleted)"
  - "Phase 12 style-shared.css serif-prose article rules (article p/h2/a/blockquote — the exact TYPE-01 blocks the block-body scoped rules copy)"
  - "Phase 11 style-base.css :root tokens (--serif/--mono, --ink*, --accent*, --line-strong, --radius-btn/-dot, --space-*)"
provides:
  - "De-darkened block-detail CSS in style-shared.css (.block-header/.block-header h1, .block-tension, .block-body p/li/ul/ol/h2/a, .evolution > h2, .timeline-* entries, .timeline-show-all)"
  - "De-darkened status CSS in style-shared.css (.status-row/.status-title/.status-subtitle/.status-synth) on the light/serif single-accent system"
  - "renderBlock + renderStatusRow with data-accent dropped; empty-states (Block not found / No timeline entries yet / Status data unavailable) restyled to serif --ink-soft"
  - "style-map.css fully retired (deleted) + its <link> removed from index.html — final cascade is style-base.css + style-shared.css"
affects:
  - "docker/web/site/style-shared.css (block-detail + status rules folded in)"
  - "docker/web/site/style-map.css (DELETED — delete-and-fold complete)"
  - "docker/web/site/index.html (style-map.css <link> removed)"
  - "docker/web/site/app.js (renderBlock / renderStatusRow / renderTimelineEntries / loadBlock / loadStatus empty-states)"
tech-stack:
  added: []
  patterns:
    - "Delete-and-fold completed (PATTERNS §CSS-DISPOSITION option 1): style-map.css deleted, all rules de-darkened into style-shared.css; cascade collapses to 2 <link>s (Phase 12 topology)"
    - "Scoped serif-prose migration (TYPE-01, D-03): .block-body p/li/h2/a copy the Phase 12 article rules WITHOUT adding .block-body to the article selector list — keeps the magazine layer Newsletter-only"
    - "Single-accent collapse (D-05/COLOR-02): --accent-tier fallback retired across block/status/timeline; data-accent dropped from renderBlock + renderStatusRow markup"
    - "Security model preserved verbatim: escapeHtml on every DB string, safeHttpUrl scheme-gate on timeline source_url, marked.parse(bodyMd) as sole escape-bypass, no .eq('status') filter (RLS is the boundary, D-17)"
key-files:
  created: []
  modified:
    - "docker/web/site/style-shared.css"
    - "docker/web/site/index.html"
    - "docker/web/site/app.js"
  deleted:
    - "docker/web/site/style-map.css"
decisions:
  - "Delete-and-fold taken to completion (D-01..D-03): style-map.css deleted entirely (every remaining rule was the status row + comments) and its index.html <link> removed; the end-state cascade is style-base.css (tokens) + style-shared.css (all component rules) only"
  - "Status-row padding snapped to symmetric 12px var(--space-lg) (24px) sides per the plan's literal token form — 4px-grid conformant; the stripe sits inside the left pad"
  - "One stray legacy Georgia literal (.subscribe-heading font-family: Georgia, serif) migrated to var(--serif) — gate-conformance + a genuine missed TYPE-01 serif migration; the only Georgia, literal that was left in the shared sheet"
metrics:
  duration: 6min
  completed: 2026-06-04
  tasks: 3
  files: 4
---

# Phase 13 Plan 02: Agent Economy Grid (Block Detail + Status De-Dark) Summary

De-darkened the per-block reading view (`renderBlock`) and the deep-link-only `#/status` view (`renderStatus`) onto the Phase 11 light/serif single-accent system — folding every remaining `style-map.css` rule into `style-shared.css`, then **deleting `style-map.css` entirely** and removing its `<link>` so the dark theme is fully retired and the site loads only `style-base.css` + `style-shared.css`. The block view keeps its 4-part structure (header / live-tension card / markdown body / Evolution timeline) restyled-not-redesigned, with no second magazine layer; the security model (`escapeHtml` / `safeHttpUrl` / `marked.parse`-only-bypass) and the RLS read boundary are preserved verbatim.

## What Shipped

- **Task 1 — Block-detail de-dark CSS (`ded9872`):** Folded the de-darkened block rules into `style-shared.css` and deleted the dark originals from `style-map.css`. `.block-header h1` → serif 24px/600 reading-view title (smaller than the hub `.page-title` display hero, D-06; replaces inherited Georgia 29px). `.block-body p/li` → scoped serif copies of the Phase 12 `article p` (18px/400 `--ink-soft`, 1.62, 16px margin) — without adding `.block-body` to the `article` selector list (keeps the magazine layer Newsletter-only, D-03); `.block-body h2` → serif 24px/600 (was Georgia 21px); `.block-body a` → `--accent-ink` underline; `.block-body ul/ol` padding preserved. `.block-tension` → 3px `--accent` stripe + `--accent-soft` surface, serif italic 18px/1.6 `--ink-soft` (Phase 12 blockquote analog). `.evolution > h2` → mono section-label step (11px/600 UPPERCASE `.18em` `--ink-faint`, was Courier 13px). Timeline entries de-darkened: `what`/`why` serif 18px/400 `--ink-soft`; `date`/`sep` mono `--ink-faint`; `source` → mono 12.5px `--accent-ink` (the `var(--accent-tier, …)` fallback became plain `--accent-ink`); the `:not([data-source])` defensive rule moved too. `.timeline-show-all` → mono 12.5px, `--radius-btn` (8px, from 4px), `--line` border, `--accent-ink` text, `--surface` hover (replacing the dark `rgba(255,255,255,.02)`).
- **Task 2 — Status de-dark + style-map.css retirement (`797098c`):** Folded `.status-row` (3px `--accent` stripe, was `--accent-tier`; sits on `--bg`; `12px 24px 12px 24px` padding), `.status-title` (serif 18px/400 `--ink`, was Georgia 17px), `.status-subtitle` (serif 18px/400 `--ink-soft`, was Courier 14px — TYPE-01), `.status-synth` (mono 14px `--ink-faint`, was Courier 13px) into `style-shared.css`. **Deleted `docker/web/site/style-map.css`** (every rule was folded; only comments + the status row remained) and removed its `<link rel="stylesheet" href="/style-map.css">` from `index.html`. End-state cascade: `style-base.css` + `style-shared.css` only.
- **Task 3 — renderBlock/renderStatusRow JS cleanup (`67cf40b`):** Dropped the dead `data-accent="…"` attribute from `<header class="block-header">` and `<div class="status-row">` (the cascade it fed is deleted, D-05). Preserved verbatim: the `live_tension !== LIVE_TENSION_PLACEHOLDER` gate, the `marked.parse(bodyMd)` body path (sole escape-bypass), and the `safeHttpUrl()` + `escapeHtml()` security model in `renderTimelineEntries`. Restyled the three Plan-02 empty-states ("Block not found.", "No timeline entries yet.", "Status data unavailable.") from `--text-secondary` to serif `--ink-soft`, wording unchanged. No `.eq('status',…)` filter added to `loadBlock`/`loadStatus` (RLS is the boundary, D-17).

## How It Meets the Success Criteria

- **D-01 / D-03:** Clicking a card from the hub now lands on a clean light reading view — serif H1 24px, single-accent dots, serif body prose (18px/1.62 `--ink-soft`), `--accent-ink` links, de-darkened Evolution timeline. Structure preserved (header / tension / body / Evolution); no second magazine layer (no mono-kicker/display-title/lead/blockquote markup in `renderBlock`).
- **D-02:** `#/status` de-darked (serif titles/subtitles, mono synth timestamps, single-accent stripe) — no layout redesign, no re-link into nav.
- **D-05 / COLOR-02:** Every block/status accent (left stripes, filled dots, links) is the single `--accent`/`--accent-ink`; the `--accent-tier` fallback and all `data-accent` emission are retired. No per-tier color survives.
- **TYPE-01:** No monospace body paragraphs anywhere in the block reading view — `.block-body p/li`, timeline `what`/`why`, status title/subtitle are all serif; mono survives only on chrome (Evolution heading, Show-all button, `source ↗`, `date`, synth timestamp).
- **Delete-and-fold:** `style-map.css` is deleted and its `<link>` removed; the dark theme is fully retired.

## Deviations from Plan

Plan executed as written, with two gate-conformance adjustments (neither changes any rendered behavior beyond the intended restyle):

**1. [Gate-conformance] Migrated the one stray legacy `.subscribe-heading` Georgia literal to `var(--serif)`**
- **Found during:** Task 1 — running the embedded `<automated>` gate against live code.
- **Issue:** The Task 1 gate's segment regex (`/\.block-[\s\S]*?\.status|\.timeline[\s\S]*$/`) over-reaches to EOF when no `.status` rule exists yet in `style-shared.css` (it didn't until Task 2), sweeping in the pre-existing `.subscribe-heading { font-family: Georgia, serif }` and tripping the `Georgia,` literal check. That subscribe-heading Georgia is a genuine missed TYPE-01 serif migration (the only `Georgia,` literal left in the shared sheet) — restyling it to `var(--serif)` is content-neutral, correct per the design system, and bounds the gate to its stated intent ("no Georgia in folded block rules").
- **Fix:** `font-family: Georgia, serif` → `var(--serif)` in `.subscribe-heading`.
- **Files modified:** docker/web/site/style-shared.css
- **Commit:** `ded9872`

**2. [Gate-conformance] Reworded a comment that contained the literal `.block-body prose`**
- **Found during:** Task 1 gate run.
- **Issue:** The gate matches `/\.block-body p[\s\S]*?\}/` and asserts `var(--serif)` is in that match. My block-detail comment used the phrase "the `.block-body prose` rules" — the regex matched `.block-body p` inside the word "prose" (a comment), capturing a comment span with no `var(--serif)` → false-fail (same regex-matches-comments trap class noted in the project memory).
- **Fix:** Reworded the comment to "the scoped prose rules" (no `.block-body p` literal). No CSS rule changed.
- **Files modified:** docker/web/site/style-shared.css
- **Commit:** `ded9872`

The `data-accent`-in-comments precedent from Plan 01 was applied proactively in Task 3 (the block/status header comments say "the per-tier accent attribute is dropped", not the literal `data-accent`), so the Task 3 gate passed on the first run with no rewording needed.

## Out of Scope (untouched, by design)

- The two Newsletter empty-states still using `--text-secondary` (`app.js:210` "No newsletters published yet.", `:266` "Edition not found.") — Phase 12 surfaces, outside Plan 02 scope.
- `docker/web/site/tokens-preview.html` still contains `data-accent` / `var(--accent-tier)` references — it is a standalone Phase-4 token-preview reference page, NOT `<link>`ed by index.html and not in the live SPA render path; explicitly outside the project's "do not touch files other than files_modified" boundary.
- `style-base.css:49` `--serif:'Source Serif 4', Georgia, serif` — the intentional Georgia *fallback* in the serif token stack (Phase 11 lock), not a dark-theme literal.
- No `docker compose` / build / deploy — code-edit only; the operator owns deploy (batch-ships after Phase 14 per D-01).

## Known Stubs

None. All four render paths (`renderBlock`, `renderStatusRow`, `renderTimelineEntries`, the empty-states) are wired to the live `economy_map.blocks` / `timeline_entries` read path. With today's data the tension card and body are hidden on bodyless blocks (gated, not stubbed): 5 of 7 blocks are DEFERRED (no body), and `live_tension` is the placeholder on all 7 — both are existing data-state gates, not placeholders this plan introduced.

## Threat Surface

No new surface. T-13-04 (XSS) mitigated — `escapeHtml()` preserved on every DB string in `renderBlock`/`renderStatusRow`; dropping `data-accent` removes markup, never adds an unescaped field. T-13-05 (XSS-via-markdown) unchanged — `marked.parse(bodyMd)` remains the single escape-bypass; no other field switched to raw innerHTML. T-13-06 (XSS-via-URL) mitigated — `safeHttpUrl()` scheme-gating + `escapeHtml()` on the timeline `source_url` preserved verbatim. T-13-07 (data boundary) mitigated — no `.eq('status',…)` filter added to `loadBlock`/`loadStatus`; RLS stays the read boundary. No new endpoints, auth paths, or schema changes.

## Verification

- `node --check docker/web/site/app.js` passes.
- All three embedded `<automated>` gates printed `OK` before each commit (Task 1 after the two gate-conformance fixes; Tasks 2 & 3 first-run).
- Plan-level sweep: `style-map.css` deleted; no `/style-map.css` reference in `index.html`; no live `var(--accent-tier)` usage in active CSS (only documentary comment mentions); no `'Courier New'` in any active CSS; no dark `rgba(255,255,255,…)` in active CSS; no `data-accent` emission in `app.js`. Final cascade confirmed: `style-base.css` + `style-shared.css` (2 `<link>`s).
- Browser verification (`#/map` → `identity-trust` reading view, a DEFERRED block, and `#/status` deep-link via the substituted preview per the `web-static-preview-substitution` memory) is deferred to the end-of-phase human-verify gate (config `human_verify_mode: end-of-phase`).

## Self-Check: PASSED

- Files: `13-02-SUMMARY.md`, `style-shared.css`, `index.html`, `app.js` present; `style-map.css` confirmed deleted (delete-and-fold).
- Commits: `ded9872` (Task 1), `797098c` (Task 2), `67cf40b` (Task 3) all in git log.
