---
phase: 13-agent-economy-grid
verified: 2026-06-04T23:00:00Z
status: passed
human_verified: 2026-06-08T11:45:00Z — live-site browser UAT all pass (see 13-HUMAN-UAT.md); 2-col grid not visually demonstrable yet due to 5/7 blocks deferred (content state, not a frontend defect — parked for the content milestone)
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Navigate to #/map on the substituted preview container. Confirm 2-column card grid renders on desktop (not a vertical stack)."
    expected: "SUBSTRATE / BEHAVIOR / FRAME tier labels, 2-column grid below each label, tight ~16px gaps, no long vertical scroll."
    why_human: "CSS grid rendering and pixel-level layout require a live browser; node --check only validates syntax."
  - test: "Hover over a normal card (e.g. identity-trust) on the substituted preview."
    expected: "Card lifts upward (-3px translate), box-shadow appears, left accent stripe deepens to --accent-ink."
    why_human: "CSS hover transitions cannot be verified by static code inspection."
  - test: "Narrow the browser viewport to <= 640px and observe the hub grid."
    expected: "Grid collapses to a single column; full-width DEFERRED cards look the same as normal cards (every card spans full width)."
    why_human: "Responsive collapse is only observable in a live browser at actual viewport widths."
  - test: "Click a DEFERRED card (e.g. memory-context) from the hub."
    expected: "Block reading view opens with serif H1 24px, empty progress dots, and (no body, no tension — both gated). No dark background, no monospace body text."
    why_human: "Click-through navigation and visual appearance of the reading view require browser rendering."
  - test: "Click a normal card (e.g. identity-trust) from the hub."
    expected: "Block reading view opens: serif H1 24px (smaller than the hub page-title display), single-accent filled dots, serif body prose at 18px/1.62 --ink-soft, --accent-ink inline links, de-darkened Evolution timeline. No Courier New, no dark background."
    why_human: "Visual comparison of serif vs display size, hover lift, and link color require a live browser."
  - test: "Deep-link #/status in the browser."
    expected: "Status rows render with serif titles, serif subtitles, mono synth timestamps, 3px --accent left stripe. Light background throughout, no dark surface."
    why_human: "Visual rendering of the de-darkened status view requires a live browser."
---

# Phase 13: Agent Economy Grid Verification Report

**Phase Goal:** Re-render the Agent Economy section as a tight, responsive card grid grouped by the canonical block taxonomy from the live data source, replacing the long vertical scroll so related blocks are visible together with minimal scrolling.
**Verified:** 2026-06-04T23:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Hub renders as 2-col desktop / 1-col mobile grid with ~16px gaps (MAP-01) | VERIFIED | `style-shared.css:244` `.grid { display:grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-md); }` + `@media (max-width: 640px)` collapse at line 321 |
| 2 | Each block is a bordered card with serif 20px/600 title, serif 18px/400 description, progress dots, 3px accent left-border, hover lift (MAP-02) | VERIFIED | `.card` rule (lines 253-266): `border-left: 3px solid var(--accent)`, `.card .tile-title` (serif 20px/600), `.card .tile-subtitle` (serif 18px/400 `--ink-soft`), `.card:hover { transform: translateY(-3px); ... }` |
| 3 | Cards grouped under SUBSTRATE / BEHAVIOR / FRAME mono labels from live data (MAP-03) | VERIFIED | `app.js` `renderHub()`: groups by `b.tier` field from DB, emits `<h2 class="tier-label">` + `TIER_LABELS` constant (`{ substrate: 'SUBSTRATE', behavior: 'BEHAVIOR', frame: 'FRAME' }`); label sits above `<div class="grid">` |
| 4 | Blocks with null `current_body_version_id` span full width with DEFERRED tag + empty dots (MAP-04) | VERIFIED | `renderTile(b)`: `var deferred = !b.current_body_version_id`; adds `.card-deferred` class (`grid-column: 1 / -1`); emits `.card-dots-row` with `renderMaturityPill(b, true)` (forces `data-stage="0"`) + `<span class="deferred-tag">· DEFERRED</span>` |
| 5 | Only single --accent violet on cards/dots; per-tier color machinery deleted (D-05, COLOR-02) | VERIFIED | `style-map.css` deleted entirely; no `--accent-tier`, no `[data-accent]`, no per-tier hex in any active CSS; `.maturity-pill` fill selectors use `var(--accent)`; `renderTile`/`renderMaturityPill`/`renderBlock`/`renderStatusRow` emit no `data-accent` attribute |
| 6 | Serif "The Agent Economy" page-title + optional mono date sub-line + serif HUB_STORYLINE in `#map-view .content-area` (D-06) | VERIFIED | `renderHub()` writes `<h1 class="page-title">The Agent Economy</h1>` + conditional `<p class="hero-date">updated {date}</p>` + `<div class="hub-storyline">{HUB_STORYLINE}</div>` directly to `document.getElementById('map-view').querySelector('.content-area').innerHTML`; no `updateHero()` call (only in comments) |
| 7 | Block reading view de-darkened onto light/serif system; no dark bg, no Courier, no per-tier color (D-01, D-03) | VERIFIED | `.block-header h1` (serif 24px/600), `.block-body p/li` (serif 18px/400 `--ink-soft` 1.62), `.block-body h2` (serif 24px/600), `.block-body a` (`--accent-ink`), `.block-tension` (3px `--accent` stripe, serif italic, `--accent-soft` bg); no `'Courier New'` or `Georgia,` literal in `style-shared.css` |
| 8 | Block body markdown prose in serif 18px/1.62 --ink-soft; no monospace body paragraphs (D-03, TYPE-01) | VERIFIED | `.block-body p, .block-body li { font-family: var(--serif); font-size: 18px; ... line-height: 1.62; color: var(--ink-soft); }`; no Courier/mono on body text |
| 9 | `#/status` renders cleanly on light system (serif titles/subtitles, mono synth, --accent stripe) (D-02) | VERIFIED | `.status-row { border-left: 3px solid var(--accent); }`, `.status-title { font-family: var(--serif); 18px; var(--ink) }`, `.status-subtitle { var(--serif); var(--ink-soft) }`, `.status-synth { var(--mono); 14px; var(--ink-faint) }` |
| 10 | No `.eq('status', …)` filter added to `loadHub`/`loadBlock`/`loadStatus` — RLS is the boundary (D-17) | VERIFIED | Stripped (comments removed) app.js has zero `.eq('status'` occurrences; all three loaders confirmed clean; DEFERRED derived from `current_body_version_id` null in JS |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/web/site/style-shared.css` | Light-system card grid + card + DEFERRED + maturity-pill + tier-label + hub-storyline + block-detail + status rules | VERIFIED | Contains all required rule sets: `.grid`, `.card`, `.card-deferred`, `.card-dots-row`, `.deferred-tag`, `.maturity-pill`, `.tier-label`, `.hub-storyline`, `.block-header`, `.block-body p/li/h2/a`, `.block-tension`, `.evolution > h2`, `.timeline-*`, `.timeline-show-all`, `.status-row`, `.status-title`, `.status-subtitle`, `.status-synth` |
| `docker/web/site/app.js` | renderHub grid + renderTile DEFERRED branch + recolored renderMaturityPill + in-content hub header; renderBlock + renderStatusRow drop data-accent | VERIFIED | `node --check` passes. All required functions implemented: `renderMaturityPill(b, deferred)`, `renderTile(b)`, `renderHub(data)` with in-content header, `renderBlock` without data-accent, `renderStatusRow` without data-accent |
| `docker/web/site/style-map.css` | DELETED — delete-and-fold disposition complete | VERIFIED | File does not exist; `index.html` references only `style-base.css` + `style-shared.css` |
| `docker/web/site/index.html` | style-map.css `<link>` removed; 2-stylesheet cascade | VERIFIED | Only two CSS `<link>` tags: `/style-base.css` and `/style-shared.css` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.js renderTile` | `.card` / `.card-deferred` in `style-shared.css` | `class="card"` / `class="card card-deferred"` emitted in `renderTile` | WIRED | `renderTile` emits `cls = deferred ? 'card card-deferred' : 'card'` into `<a class="...">` |
| `app.js renderMaturityPill` | `.maturity-pill [data-stage]` fill rules | `data-stage="N"` attribute; `data-stage="0"` for deferred | WIRED | `stage = deferred ? 0 : (MATURITY_STAGE[b.maturity] || 1)` → `data-stage="${stage}"` |
| `renderHub grid wrapper` | `#map-view .content-area` | `innerHTML` write of header + grouped grid | WIRED | `document.getElementById('map-view').querySelector('.content-area').innerHTML = html` |
| `app.js renderBlock body section` | `.block-body p/li/h2` serif rules | `<section class="block-body">` wrapping `marked.parse(bodyMd)` | WIRED | `bodyHtml = '<section class="block-body">' + marked.parse(bodyMd) + '</section>'` |
| `app.js renderStatusRow` | `.status-row` light rules | `class="status-row"` on emitted div | WIRED | `return '<div class="status-row">' + renderMaturityPill(b) + ...` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `renderHub` / `renderTile` | `data` (blocks array) | `loadHub()` → `sb.schema('economy_map').from('blocks').select(...)` | Yes — live PostgREST query to `economy_map.blocks` | FLOWING |
| `renderBlock` | `block`, `bodyMd`, `entries` | `loadBlock()` → parallel queries to `blocks` + `timeline_entries` + `block_body_versions` | Yes — live DB queries | FLOWING |
| `renderStatus` / `renderStatusRow` | `data` (blocks array) | `loadStatus()` → `sb.schema('economy_map').from('blocks').select(...)` | Yes — live PostgREST query | FLOWING |

No hardcoded empty arrays or static returns. All three view loaders query the live `economy_map` schema.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `app.js` syntax check | `node --check docker/web/site/app.js` | Exit 0 | PASS |
| Per-tier hex absent from active CSS | grep `--accent-teal-base\|--accent-purple-base` in `style-shared.css` + `style-base.css` | No matches | PASS |
| `[data-accent]` cascade absent from all active CSS | grep `\[data-accent=` in `style-shared.css` | No matches | PASS |
| `data-accent` not emitted in app.js live code (non-comment) | grep stripped code | 0 occurrences | PASS |
| `.eq('status')` filter absent from loaders | grep stripped app.js | 0 occurrences (D-17 boundary intact) | PASS |
| `style-map.css` deleted, `<link>` removed from index.html | `fs.existsSync` + html check | File absent, 2-`<link>` cascade confirmed | PASS |
| `.block-body p` uses `var(--serif)` | grep style-shared.css | Confirmed | PASS |
| `.timeline-show-all` uses `var(--radius-btn)` and `var(--accent-ink)` | grep style-shared.css | Confirmed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MAP-01 | Plan 01 + Plan 02 | 2-col desktop / 1-col mobile grid, ~16px gaps | SATISFIED | `.grid { grid-template-columns: repeat(2, 1fr); gap: var(--space-md); }` + `@media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }` |
| MAP-02 | Plan 01 + Plan 02 | Bordered card: serif title, description, dots, 3px accent left-border, hover lift | SATISFIED | `.card` rule with `border-left: 3px solid var(--accent)`, `.card .tile-title` serif 20px/600, `.card:hover { transform: translateY(-3px); }` |
| MAP-03 | Plan 01 + Plan 02 | Cards grouped under canonical SUBSTRATE/BEHAVIOR/FRAME taxonomy from live data | SATISFIED | `renderHub()` groups by `b.tier` from DB, emits `<h2 class="tier-label">` above each `<div class="grid">` |
| MAP-04 | Plan 01 + Plan 02 | Deferred blocks span full grid width with DEFERRED tag and empty dots | SATISFIED | `card-deferred` (`grid-column: 1/-1`), `data-stage="0"` empty dots, `· DEFERRED` tag in `.card-dots-row` |

All four phase requirements covered by both plans (declared `requirements: [MAP-01, MAP-02, MAP-03, MAP-04]` in both plan frontmatters).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app.js` | 210, 266 | `--text-secondary` in Newsletter empty-states | INFO | Explicitly out-of-scope for Phase 13 (Phase 12 surfaces; noted in 13-02-SUMMARY.md "Out of Scope" section) — not a Phase 13 gap |
| `docker/web/site/tokens-preview.html` | 8 | Dangling `<link href="/style-map.css">` (file deleted) | INFO (IN-01 from REVIEW.md) | Dev-only token preview page, not in the production SPA load path, not `<link>`ed by index.html; no user impact |

No debt marker comments (TBD/FIXME/XXX) found in Phase 13 modified files.

The REVIEW.md WR-01 warning (`escapeHtml()` not encoding double quotes) is a latent foot-gun, but the reviewer confirmed it is NOT exploitable through Phase 13 changes (the `b.maturity` attribute sink is a Postgres ENUM that cannot hold a quote). This is pre-existing behavior, not introduced by Phase 13.

### Human Verification Required

Visual rendering and interactive behavior require the substituted preview container (entrypoint.sh sed-substitutes `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders — serving raw `docker/web/site` crashes app.js at `createClient('__SUPABASE_URL__')`). Deploy is deferred to batch-ship after Phase 14 (decision D-01). Human UAT covers:

#### 1. Hub Grid Layout

**Test:** Load `#/map` on the substituted preview. Observe the Agent Economy section.
**Expected:** Three tier sections (SUBSTRATE / BEHAVIOR / FRAME) each with a mono section label above a 2-column card grid. Cards have a visible left accent stripe (violet), rounded corners (~10px), and tight ~16px gaps. The page does NOT show a long single-column vertical stack.
**Why human:** CSS grid rendering and column layout are only observable in a live browser.

#### 2. Card Hover Lift

**Test:** Hover over a normal (non-DEFERRED) card such as `identity-trust`.
**Expected:** Card translates upward by ~3px, a subtle box shadow appears, and the left accent stripe deepens slightly.
**Why human:** CSS hover transitions cannot be verified by static code inspection.

#### 3. Mobile Viewport Collapse

**Test:** Narrow the viewport to <= 640px on the hub `#/map`.
**Expected:** Grid collapses to a single column. All cards (normal and DEFERRED) fill the full container width.
**Why human:** Responsive layout only observable in a live browser at actual viewport width.

#### 4. Block Reading View — Normal Block

**Test:** Click the `identity-trust` card from the hub.
**Expected:** Block reading view renders: serif H1 at ~24px (visibly smaller than the hub "The Agent Economy" display title), single-accent filled violet dots, serif body prose at 18px/1.62 in `--ink-soft`, inline links in `--accent-ink` with underline. Light background. No dark theme, no Courier New body paragraphs.
**Why human:** Visual comparison of type scale and surface color requires live browser rendering.

#### 5. Block Reading View — DEFERRED Block

**Test:** Click a DEFERRED card (e.g. `memory-context`) from the hub.
**Expected:** Block reading view renders with: serif H1, empty dots (all five segments showing the `--line-strong` gray empty state), NO body section, NO tension card, Evolution section with "No timeline entries yet." in serif `--ink-soft`. Clean light surface.
**Why human:** Gated sections (body/tension hidden when null) and empty dot visual appearance require live rendering.

#### 6. Status Deep-Link

**Test:** Navigate directly to `#/status`.
**Expected:** Status rows with serif titles and subtitles, mono synth timestamps (right-aligned), 3px violet left-accent stripe on each row. Light background (no dark surface), tier section labels.
**Why human:** Visual rendering of the de-darkened status view requires live browser.

### Gaps Summary

None. All 10 observable truths are verified in code. The 6 human verification items above are required for visual/interactive confirmation but represent expected browser-only behaviors (hover, layout, responsive collapse, click-through navigation). No functional gaps or blockers.

---

_Verified: 2026-06-04T23:00:00Z_
_Verifier: Claude (gsd-verifier)_
