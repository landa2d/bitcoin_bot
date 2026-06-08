---
phase: 12-newsletter-section-restyle
verified: 2026-06-04T20:50:13Z
status: passed
human_verified: 2026-06-04T21:05:00Z
human_verified_note: "Operator validated all 4 visual items in a local substituted preview — all pass. (Out-of-scope observation: Agent Economy blocks render vertically — that is Phase 13's deliverable, not a Phase 12 gap.)"
score: 3/3 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open the Newsletter list view and confirm the toggle pill renders visually — filled violet active segment, white text/weight-600, the inactive segment in ink-soft, the pill wrapper with a visible border"
    expected: "The active segment (Technical or Strategic) shows a solid filled violet background with white text; the pill has a 1px border matching var(--line-strong)"
    why_human: "CSS token values (--accent, --surface, --line-strong) require visual rendering against actual computed colors; there is no way to verify the rendered hex from source alone"
  - test: "Switch mode (Technical <-> Strategic) on the list view; confirm the hint line copy updates to 'Architecture, code, implementation' / 'Markets, strategy, implications'"
    expected: "Hint line text updates immediately below the pill on each switch; the filled segment moves to the newly-active side"
    why_human: "setMode() DOM mutation is runtime behavior; must be confirmed in a rendered browser session (container substitutes __SUPABASE_URL__ at startup — use the running agentpulse-web container)"
  - test: "Navigate to a single edition (reader view) and confirm no toggle appears; the article view shows a mono kicker, a large serif display title, and a mono byline"
    expected: "No Technical/Strategic pill visible on the reader route; the article header shows: 'Edition #N · Technical|Strategic' kicker (mono, small), the edition title in large serif, and a one-line mono byline below it"
    why_human: "Toggle hiding is controlled by showView() display:none at runtime; the magazine header layout depends on font rendering and class resolution that requires a live page"
  - test: "In the edition list, verify each row shows 'EDITION #N · {date}' in the kicker (not just the edition number), and body text / excerpt reads in serif (not monospace)"
    expected: "Kicker shows e.g. 'EDITION #34 · June 1, 2026'; all body text, excerpt, and article prose are in Source Serif 4 — no IBM Plex Mono paragraph text anywhere"
    why_human: "Font rendering is visual; the date append in renderList() is code-verified but the actual locale-formatted date display and the absence of monospace body text must be confirmed visually"
---

# Phase 12: Newsletter Section Restyle — Verification Report

**Phase Goal:** Restyle the Newsletter edition list and article views on the new design-system shell, and relocate the Technical/Strategic mode toggle so it lives only inside the Newsletter section — without changing any dual-mode content logic (only the toggle's placement and styling move).

**Verified:** 2026-06-04T20:50:13Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Locked Decision Applied (D-01)

Per `12-CONTEXT.md` D-01: the toggle lives at the top of the **list view only**. The single-article view has **no toggle of its own** — it inherits the persisted mode via localStorage/URL. Success criterion 1's parenthetical "(both list and article views)" in the ROADMAP was refined by D-01, which is the authoritative contract. Verification judges criterion 1 against D-01: the toggle is absent from global/shared routes and scoped to the Newsletter list route in `showView()`. The article view rendering whatever mode is currently selected (without its own toggle) fully satisfies TGL-01 as locked.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The Technical/Strategic mode toggle appears only inside the Newsletter section and no longer occupies any global/shared position; switching mode still re-renders the same dual-mode content as before | VERIFIED | `showView()` (app.js:163): `hero.style.display = viewName === 'list' ? 'block' : 'none'` — the `.hero` (toggle host) is hidden on every non-list route. Belt-and-suspenders: toggle/subtitle `display:none` off-list (app.js:153-157). Toggle markup lives exclusively inside `.hero` in `index.html` (lines 37-41). `setMode()` logic is byte-for-byte intact — `getModeTitle()`/`getModeContent()`, localStorage, URL param, body class all unchanged. |
| 2 | The active mode shows a filled accent and a hint line below it ("Architecture, code, implementation" for Technical; "Markets, strategy, implications" for Strategic) | VERIFIED | CSS: `.toggle-btn.active { background: var(--accent); color: #fff; font-weight: 600; }` (style-shared.css:98-102). Hint line: `.mode-subtitle` mono 11px/400 `var(--ink-faint)` (css:104-110). Copy: `MODES.technical.subtitle = 'Architecture, code, implementation'`, `MODES.strategic.subtitle = 'Markets, strategy, implications'` (app.js:14,21). `setMode()` writes `MODES[mode].subtitle` to `#mode-subtitle` textContent (app.js:89). |
| 3 | The edition list and single-article views render in the new serif typography and light-mode palette, reading cleanly with no monospace body paragraphs | VERIFIED | `grep -A4 'article p \{' ... \| grep -c 'var(--mono)'` = **0**. All reading rules verified: `article p` → `var(--serif)` 18px/400/1.62 `--ink-soft`; `article ul,ol` → `var(--serif)` 18px/400/1.62; `article td` → `var(--serif)` 16px/400 `--ink-soft`; `.entry-preview` → `var(--serif)` 18px/400/1.5 `--ink-soft`; `article h2` → `var(--serif)` 24px/600 `--ink` (no uppercase); `article h3` → `var(--serif)` 20px/600 `--ink` (no uppercase). Mono survives only on `article th` (label row, 600), `code`/`pre`, and chrome elements. |

**Score: 3/3 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/web/site/style-shared.css` | Serif prose rules (TYPE-01), B1 list rows, A1 segmented pill, minimal-header rules, `.preview-banner` class | VERIFIED | All named rules present and substantive. `.preview-banner` at line 115. No `var(--mono)` on reading selectors. `.hero-tagline` rule fully absent (0 grep hits). Off-grid `7px 16px` mobile override absent (0 grep hits). |
| `docker/web/site/index.html` | Minimal D3 header markup; `.page-title` on `#hero-headline`; toggle markup with load-bearing IDs | VERIFIED | `<h1 class="page-title hero-headline" id="hero-headline">` (line 35). `id="btn-technical" onclick="setMode('technical')"` (line 38), `id="btn-strategic"` (line 39), `id="mode-subtitle"` (line 41). `WEEKLY INTELLIGENCE BRIEFING` = 0 grep hits. Toggle IDs verbatim as required. |
| `docker/web/site/app.js` | `showView()` hero scoped to list; `renderList()` date-appended kicker; `renderArticle()` magazine header + `.preview-banner` | VERIFIED | `showView()`: `hero.style.display = viewName === 'list' ? 'block' : 'none'` with `if (hero)` null-check (lines 162-163). `renderList()`: `'EDITION #' + n.edition_number + ' · ' + formatDate(n.published_at)` (line 187). `renderArticle()`: `.article-header` with `.eyebrow` kicker, `.page-title` title (`escapeHtml(title)`), `.byline` (lines 244-248). `preview-banner` class at line 233. `f59e0b` = 0 grep hits. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `index.html .mode-toggle (btn-technical/btn-strategic)` | `app.js setMode()` | `onclick="setMode('technical'|'strategic')"` + getElementById IDs | VERIFIED | IDs present verbatim in index.html (lines 38-39); `setMode()` calls `getElementById('btn-technical')` and `getElementById('btn-strategic')` (app.js:85-86). |
| `app.js showView()` | `.hero` block (toggle host) | Hero shown only on list route | VERIFIED | `hero.style.display = viewName === 'list' ? 'block' : 'none'` at app.js:163; defensive `if (hero)` check preserved. |
| `app.js renderList()` | `EDITION #N · {date}` kicker | `formatDate(n.published_at)` appended to `section-label` | VERIFIED | `'EDITION #' + n.edition_number + ' · ' + formatDate(n.published_at)` at app.js:187. |
| `style-shared.css .toggle-btn.active` | `var(--accent)` fill + `#fff` text + weight 600 | `.active` class toggled by `setMode()` | VERIFIED | CSS at lines 98-102. `setMode()` toggles `.active` via `classList.toggle('active', mode === 'technical'|'strategic')` at app.js:85-86. |
| `style-shared.css article p / .entry-preview` | `var(--serif)` | TYPE-01 font-family migration | VERIFIED | `article p { font-family: var(--serif); }` (css:211); `.entry-preview { font-family: var(--serif); }` (css:174). |

---

### Data-Flow Trace (Level 4)

Not applicable for this phase. The phase modifies static CSS and frontend rendering logic only — no data source or API route changes. The `renderList()` and `renderArticle()` functions that produce the restyled output consume the same Supabase `newsletters` table via the unchanged `loadList()`/`loadEdition()` fetch paths. No data-flow regression possible from CSS-only or markup-only changes.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| No `var(--mono)` on reading selectors (article p/ul/ol/td, .entry-preview) | `grep -A4 -e 'article p {' -e 'article ul, article ol {' -e 'article td {' docker/web/site/style-shared.css \| grep -c 'var(--mono)'` | 0 | PASS |
| Amber `#f59e0b` eliminated from app.js | `grep -c 'f59e0b' docker/web/site/app.js` | 0 | PASS |
| `WEEKLY INTELLIGENCE BRIEFING` eliminated from index.html | `grep -c 'WEEKLY INTELLIGENCE BRIEFING' docker/web/site/index.html` | 0 | PASS |
| Off-grid `7px 16px` mobile toggle override eliminated | `grep -c '7px 16px' docker/web/site/style-shared.css` | 0 | PASS |
| `.preview-banner` class defined in CSS | `grep -c '\.preview-banner' docker/web/site/style-shared.css` | 1 | PASS |
| Toggle IDs preserved in index.html | `grep -c 'id="btn-technical"' docker/web/site/index.html` | 1 | PASS |
| Hero scoped to list route | `grep -A24 'function showView' docker/web/site/app.js \| grep "hero.*list"` | `hero.style.display = viewName === 'list' ? 'block' : 'none'` | PASS |
| renderList date kicker | `grep -n 'section-label.*formatDate\|edition_number.*formatDate' docker/web/site/app.js` | line 187 confirmed | PASS |
| All 6 plan commits exist in git log | `git log --oneline \| grep -E '424c91f|6d89072|9f42bc1|4cf4a78|abedebb|2c5ab6a'` | All 6 found | PASS |

---

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` declared or present for this phase. This is a frontend-only restyle with no runnable probes.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TGL-01 | 12-02-PLAN.md | Toggle appears only inside Newsletter section; removed from global/shared position | SATISFIED | `showView()` scopes `.hero` (toggle host) to `viewName === 'list'` only. Toggle markup in `index.html` inside `.hero`. Belt-and-suspenders hides toggle/subtitle off-list. `getModeTitle()`/`getModeContent()` logic untouched. |
| TGL-02 | 12-01-PLAN.md, 12-02-PLAN.md | Active mode: filled accent + hint line ("Architecture, code, implementation" / "Markets, strategy, implications") | SATISFIED | `.toggle-btn.active { background: var(--accent); color: #fff; font-weight: 600; }`. Hint copy in `MODES[*].subtitle`. `setMode()` writes subtitle text to `#mode-subtitle`. `.mode-subtitle` CSS mono 11px `--ink-faint`. |

No orphaned requirements. REQUIREMENTS.md maps both TGL-01 and TGL-02 to Phase 12 and marks them `Complete`. Both are fully covered.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app.js` | 46 | `const LIVE_TENSION_PLACEHOLDER = 'TBD — set via /map-tension'` | Info | Pre-existing constant from Phase 2 — not introduced by Phase 12. Used in live logic at line 551-553 as a sentinel value (not a debt marker). Not a blocker. |

No `TBD`, `FIXME`, or `XXX` markers introduced by Phase 12. No `return null` / empty stub implementations in the three modified files. The SUMMARY's "Known Stub" (`.byline` CSS lacking a dedicated rule) is **resolved**: `style-shared.css` now contains `.article-header .byline { font-family: var(--mono); font-size: 14px; font-weight: 400; color: var(--ink-faint); margin: var(--space-xs) 0 0; }` at lines 250-255, added as a post-merge integration fix. The stub is closed.

---

### Human Verification Required

#### 1. Toggle pill visual rendering (active segment fill)

**Test:** Open the Newsletter list view in a browser against the running `agentpulse-web` container (account for `__SUPABASE_URL__` sed-substitution by `entrypoint.sh` — use the container's resolved URL, not the raw file). Observe the Technical/Strategic pill.

**Expected:** The active segment shows a solid filled violet background (`#5b3df5`) with white text at visibly heavier weight; the inactive segment is in muted ink-soft text on a transparent background; the pill wrapper has a visible 1px border.

**Why human:** CSS token values (`--accent`, `--surface`, `--line-strong`) resolve to specific hex values only in a rendered browser. Source-level verification confirms the token assignments are correct but cannot confirm the computed colors render as intended.

---

#### 2. Mode switching interaction (hint line copy update)

**Test:** Click Technical then Strategic (and back) in the list view. Observe the hint line below the pill.

**Expected:** Hint line reads "Architecture, code, implementation" when Technical is active; "Markets, strategy, implications" when Strategic is active. The filled segment moves to the newly-active button. Edition list re-renders with the appropriate content field.

**Why human:** `setMode()` DOM mutation and re-render are runtime behaviors. Code verification confirms the correct logic, but the live toggle interaction (transition animation, hint-line swap, list re-render) requires a browser session.

---

#### 3. Reader view — no toggle visible; magazine header present

**Test:** Click an edition title from the list to enter the reader view. Confirm the Technical/Strategic pill is absent. Scroll to the top of the article content and confirm the header sequence: mono kicker line, large serif display title, mono byline.

**Expected:** No pill visible anywhere in the reader view. Header reads (from top): `Edition #N · Technical` (small mono), the edition title in clamp(30-46px) serif, and `Edition #N · {date} · Technical` in small mono below. The `← Back to Newsletter` link appears above the header.

**Why human:** The `showView('reader')` hiding of `.hero` is code-verified, but visual confirmation that the toggle does not bleed through (e.g., residual CSS stacking or z-index) requires a rendered browser session. The magazine header's visual hierarchy (three-line sequence with correct font sizes and spacing) requires visual confirmation.

---

#### 4. Edition list — serif body text, date-bearing kicker

**Test:** On the list view, inspect two or three edition rows. Confirm the kicker shows a date, and the excerpt text and all body text read in Source Serif 4.

**Expected:** Each kicker reads `EDITION #N · {Month D, YYYY}` (uppercase, small mono). The edition title is a noticeably heavier serif. The excerpt paragraph is in serif at a comfortable reading size. No monospace paragraph text anywhere on the page.

**Why human:** Font rendering requires visual inspection. The date appended in `renderList()` requires real data from the Supabase `newsletters` table (not available in static source analysis). The TYPE-01 "no monospace body paragraphs" rule is code-verified at the CSS level but the rendered appearance with actual content must be confirmed.

---

### Gaps Summary

No structural gaps found. All three ROADMAP success criteria are satisfied in source code:

1. SC1 (toggle scoped to Newsletter list): `showView()` gates `.hero` display to `viewName === 'list'`; belt-and-suspenders hides toggle/subtitle off-list; `setMode()` logic intact; content re-render unchanged.
2. SC2 (filled accent + hint line): `.toggle-btn.active` uses `var(--accent)` / `#fff` / `font-weight:600`; `.mode-subtitle` mono 11px `--ink-faint`; correct hint copy in `MODES[*].subtitle`; `setMode()` writes it.
3. SC3 (serif typography, no mono body paragraphs): all reading selectors (`article p/ul/ol/td`, `.entry-preview`) use `var(--serif)`; the TYPE-01 mono-count grep returns 0; `article h2/h3` are serif 24/20px 600 with no `text-transform:uppercase`.

The four human verification items above are runtime/visual checks that source analysis cannot substitute for. They do not represent code gaps — they represent unverifiable-by-grep behaviors that require a browser session against the running container.

---

_Verified: 2026-06-04T20:50:13Z_
_Verifier: Claude (gsd-verifier)_
