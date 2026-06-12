---
phase: 22-per-section-visual-fixes
plan: 01
subsystem: ui
tags: [frontend, app.js, web, edition-header, renderArticle, getModeTitle, regex]

# Dependency graph
requires:
  - phase: 21-single-scroll-landing-scroll-spy-nav
    provides: "the #reader-view detail route + renderArticle reader chrome this plan de-duplicates"
provides:
  - "Edition H1 carries only the headline — baked `— Edition #N | <date>` suffix stripped at render (both Technical + Strategic modes)"
  - "Edition number/date/mode appear exactly once in the reader chrome — single byline below the title; duplicate eyebrow line removed"
  - "Module-level EDITION_SUFFIX_RE + getModeTitle() single-chokepoint strip pattern (render-only, defensive no-op when absent)"
affects: [22-04-deploy-verify, phase-23-newsletter-excerpts, phase-25-responsive-a11y]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Render-only title normalization: strip the RAW string in the mode accessor (getModeTitle) BEFORE escapeHtml at the H1 sink — single chokepoint covers both data.title and data.title_impact, escape order preserved, no storage mutation"

key-files:
  created:
    - .planning/phases/22-per-section-visual-fixes/22-01-SUMMARY.md
  modified:
    - docker/web/site/app.js

key-decisions:
  - "EDITION_SUFFIX_RE = /\\s*[—–-]\\s*Edition\\s*#\\d+\\s*\\|.*$/i — matches the CONFIRMED stored suffix (U+2014 em-dash separator, ` | ` pipe delimiter, full-month date); anchored to $, tolerant of em/en-dash/hyphen, case-insensitive"
  - "Strip applied in getModeTitle (single chokepoint for both modes), unconditional/defensive so future suffixed editions are covered (D-03)"
  - "Eyebrow line dropped entirely with no replacement kicker; byline kept verbatim (D-01/D-02)"

patterns-established:
  - "Strip-raw-then-escape: title normalization runs on the unescaped string at the accessor, leaving the existing escapeHtml(title) H1 sink intact"

requirements-completed: [HEAD-01]

# Metrics
duration: ~10min
completed: 2026-06-12
---

# Phase 22 Plan 01: Edition-Header De-Duplication Summary

**Edition detail H1 now shows only the headline (baked `— Edition #N | <date>` suffix stripped at render for both modes via a single getModeTitle chokepoint), and the duplicate eyebrow line is gone — edition/date/mode appear exactly once, in the byline.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-12
- **Completed:** 2026-06-12
- **Tasks:** 2
- **Files modified:** 1 (`docker/web/site/app.js`)

## Accomplishments
- Added module-level `EDITION_SUFFIX_RE` and applied it as the single render-only strip chokepoint in `getModeTitle()`, covering both Technical (`data.title`) and Strategic (`data.title_impact`) titles before `escapeHtml` runs at the H1 sink — no stored-data mutation (HEAD-01/D-03).
- Removed the duplicate `.eyebrow` `Edition #N · Mode` line from `renderArticle`'s reader header; the `.byline` (`Edition #N · date · Mode`) survives verbatim with its U+00B7 separator + `MODES[currentMode].label` (HEAD-01/D-01/D-02).
- Confirmed the stored title bytes via a read-only anon PostgREST query (D-04, Phase-19 discipline) before authoring the regex.

## D-04 Stored-Bytes Finding (CONFIRMED via read-only anon PostgREST, 2026-06-12)

A trailing suffix IS baked into BOTH `newsletters.title` AND `newsletters.title_impact`. Confirmed against editions 29 and 30 via `GET $SUPABASE_URL/rest/v1/newsletters?edition_number=in.(29,30)&select=edition_number,title,title_impact` (anon key, read-only — no write, no mutation):

| Edition | Field | Stored value (suffix in bold) |
|---------|-------|-------------------------------|
| 30 | `title` | `The Permissions Bottleneck Gets Named. Cash App Brings Stablecoins to 60M Users.` **` — Edition #30 \| June 8, 2026`** |
| 30 | `title_impact` | `Cash App Brings Stablecoins to 60 Million Users. Workday Names the Real Bottleneck.` **` — Edition #30 \| June 8, 2026`** |
| 29 | `title` | `The Agent Identity Crisis` **` — Edition #29 \| June 1, 2026`** |
| 29 | `title_impact` | `The AI Economy's New Gatekeeper Problem` **` — Edition #29 \| June 1, 2026`** |

**Exact pattern (byte-verified):**
- **Separator:** ` — ` = SPACE (U+0020) + **EM-DASH (U+2014)** + SPACE (U+0020). Confirmed via hex dump: `['0x20', '0x2014', '0x20']`. NOT a hyphen, NOT an en-dash.
- **Delimiter:** ` | ` (space + pipe + space) between the edition number and the date.
- **Edition token:** `Edition #<N>` (literal `#`, integer N).
- **Date format:** full month name, no leading-zero day, comma, 4-digit year — e.g. `June 8, 2026`, `June 1, 2026`.

The brief's starting pattern (` — Edition #\d+ \| .*$`) matched reality. The shipped `EDITION_SUFFIX_RE = /\s*[—–-]\s*Edition\s*#\d+\s*\|.*$/i` is anchored to `$` (trailing-suffix only — interior em-dashes in a headline are NOT touched, verified), tolerant of em/en-dash/hyphen, and case-insensitive. It is applied unconditionally so it is a no-op when no suffix is present (future-proof). No storage mutation (D-03).

## Task Commits

Each task was committed atomically:

1. **Task 1: Confirm stored title bytes (D-04) + add render-only suffix strip to getModeTitle** - `3e0d450` (feat)
2. **Task 2: Drop the duplicate eyebrow line from the reader header** - `ccef387` (feat)

## Files Created/Modified
- `docker/web/site/app.js` - Added `EDITION_SUFFIX_RE` constant (near `MATURITY_STAGE`/`TIER_LABELS`); rewrote `getModeTitle()` to resolve the mode title then `.replace(EDITION_SUFFIX_RE, '').trim()` on the raw string (single chokepoint, both modes); removed the `.eyebrow` line from `renderArticle`'s header and refreshed the header comment.

## Decisions Made
- None beyond the locked CONTEXT decisions (D-01..D-04). The shipped regex matches the byte-confirmed suffix; the eyebrow was dropped with no replacement kicker; the byline format/order is unchanged.

## Deviations from Plan

None — plan executed exactly as written. (One minor in-scope clarity touch: the stale header comment above `renderArticle`'s builder that described the now-deleted `.eyebrow` kicker was refreshed to match the de-duplicated structure. Same function, directly tied to the Task 2 change; committed in `ccef387`.)

## Issues Encountered
- Sourcing `config/.env` for the D-04 curl emitted a few harmless shell warnings (some non-KEY=VALUE lines in `.env`), but `SUPABASE_URL` + `SUPABASE_ANON_KEY` loaded correctly and the read-only query succeeded. No impact on the diagnostic.

## Verification
- Task 1 automated gate: PASS (`node --check`, `EDITION_SUFFIX_RE` present, `replace(EDITION_SUFFIX_RE` present, `__SUPABASE_URL__` placeholder intact).
- Task 2 automated gate: PASS (`node --check`, no `class="eyebrow">Edition #`, `class="byline">Edition #` present, `MODES[currentMode].label` present).
- Functional sanity: regex strips the confirmed suffix from both modes and is a no-op on suffix-less / interior-em-dash headlines.
- `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders preserved verbatim.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- HEAD-01 ships at source. Live confirmation (edition 30 H1 = headline only; one byline) is owned by the orchestrator deploy/verify plan **22-04** (worktree-unsafe scoped `docker compose ... web` rebuild — NOT run here).
- Source-only edit; no deploy/rebuild performed in this plan.

## Note for Orchestrator
- Per sequential-executor instructions, I did NOT modify `.planning/STATE.md` or `.planning/ROADMAP.md` (orchestrator-owned). REQUIREMENTS.md traceability (mark HEAD-01 complete) requires the GSD SDK — left for the orchestrator.

---
*Phase: 22-per-section-visual-fixes*
*Completed: 2026-06-12*
