---
phase: 06-telegram-read-only-scaffolding
plan: 01
subsystem: api
tags: [telegram, gato-brain, economy-map, postgrest, read-only, fastapi]

# Dependency graph
requires:
  - phase: 02-economy-map-schema-seven-block-seed
    provides: economy_map.blocks / block_body_versions / timeline_entries schema + seven-block seed + partial draft index + anon RLS that hides 'unsorted'
  - phase: 04-hub-block-and-status-renderer
    provides: web MATURITY_STAGE map + TIER_LABELS + 5-segment maturity pill markup (the renderer mirrored into Python text)
provides:
  - "/map-status (CMD-01) — tier-grouped block maturity + ·N new (unabsorbed) + ·N draft + 'unsorted: N awaiting' footer"
  - "/map-pending (CMD-02) — drafts-awaiting-approval (full version UUID + /map-approve line) + unsorted-awaiting-assignment (full entry UUID + conf: + /map-assign line) with explicit empty states"
  - "read-only economy_map GET wrapper in gato_brain (get_blocks, get_draft_versions, get_unsorted_entries, get_unsorted_count, get_unabsorbed_count) — GET-only by construction"
  - "maturity_pill() Python text renderer mirroring the web pill"
  - "handle_map_command dispatcher + /map- routing branch (same /x-* ladder, before intent router)"
affects: [09-write-commands-approve-reject, 10-write-commands-assign-entry-synth-tension, 07-synthesis]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-only-by-construction wrapper: economy_map touched ONLY via httpx.get + Accept-Profile; zero httpx write verb, zero Content-Profile (D-09)"
    - "Fail-loud reads: every economy_map GET raises RuntimeError on non-2xx; dispatcher catches and returns 'Command failed: <e>' (never a false-empty state)"
    - "Stateless full-UUID surfacing in /map-pending (no ephemeral per-listing short-index — the daily_index anti-pattern)"

key-files:
  created: []
  modified:
    - docker/gato_brain/gato_brain.py

key-decisions:
  - "Maturity pill uses the operator-approved preview glyphs ◉ (filled) / ○ (empty) verbatim — the locked contract is 5-segment fill + word label (D-02)"
  - "Unabsorbed count compares on created_at (D-05 default: absorption is ingestion-time, consistent with Phase 7 SYNT-01 windowing)"
  - "Exact counts via PostgREST Prefer: count=exact + Content-Range header (per-block GETs acceptable for 7 low-volume blocks)"
  - "service_role read path confined to the gated /map-* handlers (anon RLS hides 'unsorted'); DB-level read-only role deferred to Phase 9 per D-09"

patterns-established:
  - "GET-only economy_map access surface in gato_brain (ports the processor's Accept-Profile read shape, exposes no write method)"
  - "/map-* routed in the same prefix-dispatch ladder as /x-*, before intent_router.route — no parallel infrastructure"

requirements-completed: [CMD-01, CMD-02]

# Metrics
duration: ~18min
completed: 2026-05-30
---

# Phase 6 Plan 1: Telegram Read-Only Scaffolding Summary

**Two read-only Telegram commands — `/map-status` (tier-grouped maturity + unabsorbed/draft counts + unsorted footer) and `/map-pending` (full-UUID draft & unsorted queues with pre-filled forward-contract write lines) — backed by a GET-only economy_map PostgREST wrapper that is read-only by construction.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-30T20:54Z (approx)
- **Completed:** 2026-05-30
- **Tasks:** 4
- **Files modified:** 1 (docker/gato_brain/gato_brain.py, +339 lines)

## Accomplishments
- Read-only economy_map GET wrapper ported into gato_brain: `get_blocks()`, `get_draft_versions()`, `get_unsorted_entries()`, `get_unsorted_count()`, `get_unabsorbed_count()` — all `httpx.get` + `Accept-Profile: economy_map`, service_role headers, `timeout=10`, raise-on-non-2xx (fail-loud).
- `maturity_pill()` Python text renderer mirroring the web `MATURITY_STAGE` map (nascent→mature = 1→5), 5-segment fill + word label, `.get(m, 1)` guard for unknown enums.
- `handle_map_status()` — SUBSTRATE/BEHAVIOR/FRAME tier grouping, monospace code-fence table, `·N new` always shown, `·N draft` omitted at zero, `unsorted: N awaiting` footer.
- `handle_map_pending()` — `DRAFTS AWAITING APPROVAL` (full `block_body_versions.id` + `/map-approve` line) and `UNSORTED AWAITING ASSIGNMENT` (snippet + `conf:` + full `timeline_entries.id` + `/map-assign` line), explicit "Nothing awaiting …" empty states, CHAR_BUDGET truncation safety net.
- `handle_map_command()` dispatcher (mirrors `handle_x_command`) + `/map-` routing branch wired in the `/chat` ladder beside `/x-`, before `intent_router.route`, returning `ChatResponse(intent="MAP_COMMAND")`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Read-only economy_map GET wrapper + maturity pill renderer** - `ced9e15` (feat)
2. **Task 2: handle_map_status() and handle_map_pending() renderers** - `5ca7076` (feat)
3. **Task 3: handle_map_command() dispatcher + /map- routing branch** - `55aa549` (feat)
4. **Task 4: Read-only-by-construction code-review gate + syntax check** - `07c97a6` (chore)

## Files Created/Modified
- `docker/gato_brain/gato_brain.py` - Added the GET-only economy_map wrapper, `maturity_pill()`, `handle_map_status()`, `handle_map_pending()`, `handle_map_command()`, and the `/map-` routing branch (intent `MAP_COMMAND`). No new files, no migrations, no writes to economy_map.

## Criterion-4 / D-09 read-only-by-construction evidence
- `python3 -c "import ast; ast.parse(open('docker/gato_brain/gato_brain.py').read())"` exits 0.
- `grep -c 'httpx.post\|httpx.patch\|httpx.delete\|Content-Profile' docker/gato_brain/gato_brain.py` = **0** (no httpx write verb, no schema-WRITE profile header anywhere in the file).
- `grep -c 'Accept-Profile' docker/gato_brain/gato_brain.py` = **3** (read header present on every economy_map GET).
- `grep -c 'httpx.get'` = **4** (the only economy_map verb used).
- `grep -c 'handle_map_command\|handle_map_status\|handle_map_pending\|MAP_COMMAND'` = **7** (>= 4).
- `/map-` branch line (2195) < `intent_router.route` line (2263) — routes before the intent router.
- **Statement:** the economy_map access wrapper exposes ONLY GET methods; there is no insert/update/delete method, no httpx write call, and no Content-Profile header. It is read-only by construction, not by convention.

## Decisions Made
- Maturity pill glyphs: used the operator-approved preview glyphs `◉` (filled) / `○` (empty) verbatim. The locked contract (D-02) is the 5-segment fill + word label; the glyphs match the CONTEXT preview exactly. No substitution was made (no evidence they fail in Telegram monospace; if a future render issue surfaces, only the two `_PILL_*` constants need changing — the contract is glyph-agnostic).
- Unabsorbed count comparison column = `created_at` (D-05 default; ingestion-time absorption, reconciled with Phase 7 SYNT-01).
- Exact counts via `Prefer: count=exact` + `Content-Range` parsing (clear and correct for the 7 low-volume blocks; per-block GETs accepted per CONTEXT discretion).

## Deviations from Plan

None - plan executed exactly as written.

The only non-task adjustment was rewording explanatory comments in Task 4 so the file does not contain the literal tokens `httpx.post` / `Content-Profile` even inside documentation — required for the criterion-4 grep gate (`count == 0`) and the phase-level verification to pass. This is gate-mandated cleanup within Task 4's own scope (the gate explicitly says "if ANY httpx write verb or Content-Profile header is found, fix it"), not a scope change: the comments still document the read-only boundary, now using "httpx write call" / "schema-WRITE profile" phrasing.

## Issues Encountered
- Initial Task 4 grep gate returned a write-verb count of 3 — all three were documentary mentions of the forbidden tokens inside my own read-only-boundary comments (lines describing what the wrapper must NOT do). Resolved by rewording the comments to avoid the literal tokens; the actual code has always used only `httpx.get`. Gate then returned 0.

## User Setup Required

None - no external service configuration required. Note: the container is NOT rebuilt/deployed in this plan (Plan 06-02 handles the operator-gated rebuild). The file syntax-checks clean and is ready for that step.

## Next Phase Readiness
- `/map-status` and `/map-pending` are implemented and route through the gated `/map-*` ladder; ready for the Plan 06-02 rebuild + live operator verification.
- The full UUIDs surfaced by `/map-pending` are the exact identifiers the Phase 9 `/map-approve` and Phase 10 `/map-assign` write commands will consume — stateless, no translation layer needed.
- Phase 9 should introduce the DB-level read-only role / RLS hardening and resolve the "anon hides unsorted" gap (deferred here per D-09).

## Self-Check: PASSED

- FOUND: `.planning/phases/06-telegram-read-only-scaffolding/06-01-SUMMARY.md`
- FOUND commits: ced9e15, 5ca7076, 55aa549, 07c97a6

---
*Phase: 06-telegram-read-only-scaffolding*
*Completed: 2026-05-30*
