---
phase: 19-smart-quote-apostrophe-corruption-fix
plan: 02
subsystem: newsletter-content-integrity
tags: [content-integrity, apostrophe, backfill, confirm-and-close, scoped-update, operator-gate]

# Dependency graph
requires:
  - phase: 19-01
    provides: "nl.normalize_apostrophe_corruption() (the canonical write-path guard reused as the backfill repair logic) + 19-DIAGNOSIS.md (storage-clean root-cause finding)"
provides:
  - "19-BACKFILL-REVIEW.md — read-only scan proving the affected-edition set is EMPTY (zero corrupt rows corpus-wide); the confirm-and-close disposition"
  - "Operator-approved confirm-and-close: no scoped UPDATE warranted (nothing to backfill); newsletter content service rebuilt to ship the Plan 01 write-path guard live"
affects: [phase-20-width-tokens, phase-22-distinct-excerpts, deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Confirm-and-close backfill: when a scoped reviewed scan finds zero corrupt rows, the spine-correct action is NO UPDATE (an empty WHERE set means a no-op or a forbidden table-wide statement) — close, do not manufacture a mutation"
    - "Backfill repair logic reuses the exact write-path guard (nl.normalize_apostrophe_corruption), never a second divergent regex — scan signature == repair == write-path fix, byte-identical"

key-files:
  created:
    - ".planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md"
  modified: []

key-decisions:
  - "Affected-edition set is EMPTY (43 rows scanned, 0 mid-word U+0022 corpus-wide) — confirm-and-close, no scoped UPDATE, no web rebuild"
  - "Reused the Plan 01 canonical guard (nl.normalize_apostrophe_corruption) as the would-be repair — running it over edition 30 returned the identical string (zero replacements), independently reproducing the storage-clean diagnosis from live bytes"
  - "Operator chose 'Close + rebuild newsletter' at the blocking-human gate — approved confirm-and-close with no DB mutation, plus a scoped newsletter rebuild to ship the Plan 01 write-path guard live for newly generated editions"

patterns-established:
  - "Empty-affected-set → confirm-and-close (no UPDATE) — honoring the spine's 'never a blind table-wide find-replace' by recognizing that the scoped path has nothing to target"

requirements-completed: [QUOTE-01]

# Metrics
duration: ~5min (continuation finalization; Task 1 scan + Task 2 gate + Task 3 rebuild already executed)
completed: 2026-06-10
---

# Phase 19 Plan 02: Scoped Reviewed Backfill (Confirm-and-Close) Summary

**An independent read-only scan of all 43 newsletter rows reproduced Plan 01's storage-clean finding from live bytes (corruption-signature count 0 corpus-wide, affected-edition list EMPTY, the canonical repair a no-op on edition 30), so there was nothing to backfill — the operator approved "Close + rebuild newsletter" and the newsletter content service was rebuilt to ship the Plan 01 write-path guard live, with no DB mutation and the renderer untouched.**

## Performance

- **Duration:** ~5 min (continuation finalization)
- **Started:** 2026-06-10 (Task 1 scan)
- **Completed:** 2026-06-10T15:02:52Z
- **Tasks:** 3 (Task 1 read-only scan; Task 2 blocking-human approval gate; Task 3 scoped rebuild — no UPDATE)
- **Files modified:** 1 created (`19-BACKFILL-REVIEW.md`); 0 DB rows mutated; 0 source files changed

## Accomplishments

- **Proved there is nothing to backfill.** A read-only SELECT over all 43 `newsletters` rows (every `edition_number`, every status), checking `content_markdown`, `content_markdown_impact`, and `content_telegram` for the proven corruption signature (`(?<=[A-Za-z0-9])"(?=[A-Za-z0-9])` — the literal `App"s` shape), returned **0** occurrences corpus-wide. The **affected-edition list is EMPTY**, including the ROADMAP-named exemplar edition 30.
- **Reused the canonical Plan 01 fix as the repair logic — not a divergent regex.** Edition 30's candidate columns were run through `nl.normalize_apostrophe_corruption` (`import newsletter_poller as nl`); BEFORE == AFTER for every column (zero replacements). This independently reproduces 19-DIAGNOSIS.md / 19-01-SUMMARY.md from live stored bytes.
- **Genuine double-quotes preserved.** Edition 30 carries genuine `"` quotes (24 + 26 in the published rows, 2 + 4 in the held rows); all classified as genuine (corruption-sig 0) — a scoped UPDATE, were one warranted, would have left every one intact (threats T-19-03 / T-19-11).
- **Operator-gated close.** At the blocking-human checkpoint the operator was presented `19-BACKFILL-REVIEW.md` and explicitly chose **"Close + rebuild newsletter"** — approving confirm-and-close (no DB UPDATE) plus a scoped newsletter rebuild.
- **Shipped the write-path guard live.** A scoped `docker compose up -d --build newsletter` recreated the content service so the Plan 01 fail-loud guard now runs on every newly generated edition.

## Task Commits

1. **Task 1: Read-only scan + single-edition before/after review** — `5a44998` (docs) — `19-BACKFILL-REVIEW.md` (the affected-edition list [empty] + edition-30 BEFORE/AFTER [identical] + the confirm-and-close UPDATE plan). No DB mutation.
2. **Task 2: Operator approval of the backfill review** — blocking-human checkpoint (no commit). Operator chose "Close + rebuild newsletter" — the recorded approval that authorizes the disposition.
3. **Task 3: Apply scoped backfill + scoped content-service rebuild** — orchestrator-owned, no commit. Affected-edition set empty → **no UPDATE run** (a scoped `WHERE edition_number IN (...)` has no values; issuing one would be a pointless no-op or a spine-forbidden table-wide statement). Scoped `docker compose up -d --build newsletter` ran from `/root/bitcoin_bot/docker`.

**Plan metadata:** this commit (docs: complete plan).

## Final Affected-Edition List + Per-Column Replacement Counts

**Affected `edition_number` set: `∅` (EMPTY).** 43 rows scanned; total mid-word U+0022 corruption-signature occurrences corpus-wide: **0**.

| Edition | content_markdown | content_markdown_impact | content_telegram |
|---------|------------------|-------------------------|------------------|
| _(none — no edition carries the signature)_ | 0 | 0 | 0 |

**Per-edition / per-column replacement counts: all 0.** Edition 30 (both `held` and `published` rows) ran through the canonical `nl.normalize_apostrophe_corruption`: zero repairs, BEFORE == AFTER in every column; the four ROADMAP tokens (`Cash App's`, `It's`, `world's`, `agent's`) — wherever they occur — already store a clean straight apostrophe (U+0027). No other edition (held 25–29/32, published, or draft 34) carries the signature in any of the three columns.

## Operator Approval

At the Task 2 blocking-human gate the operator reviewed `19-BACKFILL-REVIEW.md` and **explicitly chose "Close + rebuild newsletter"** — i.e. approved confirm-and-close (no scoped DB UPDATE, because the affected set is empty) **plus** a scoped newsletter rebuild to ship the Plan 01 write-path guard. This is the recorded approval; it is what authorized Task 3's disposition. The gate is `blocking-human` and was never auto-approved.

## Post-Rebuild Verification

- **Service rebuilt:** `newsletter` (the write-path owner). Scoped `docker compose up -d --build newsletter` from `/root/bitcoin_bot/docker` (absolute main tree — worktree-unsafe step, orchestrator-owned). The `agentpulse-newsletter` container was recreated (new id `df332806…`, replacing old `4d61849…`), **running + healthy**.
- **Guard live in the running container:** `nl.normalize_apostrophe_corruption` confirmed present at `/home/openclaw/newsletter_poller.py` inside the recreated container — the Plan 01 fix now runs on newly generated editions.
- **No DB mutation:** zero rows updated. The affected set is empty; the spine forbids a table-wide find-replace and a no-op self-rewrite is pointless, so no UPDATE was issued.
- **`web` NOT rebuilt:** the renderer is unchanged (render-layer cause ruled out in 19-DIAGNOSIS.md §3; `marked.parse` runs with no typographer). Correcting storage was unnecessary because storage was already clean.
- **Incidental recreations:** the newsletter `depends_on` chain (`llm-proxy`, `processor`) was incidentally recreated by compose and all returned healthy with identical (unchanged) code — no behavior change.

## QUOTE-01 Outcome

**QUOTE-01 satisfied.** The requirement (apostrophes render correctly on existing + new editions; root cause documented; fix-forward so it cannot recur; scoped reviewed backfill of existing editions) is met:

- **Existing editions:** already correct in storage (zero corruption corpus-wide) — confirmed by this plan's independent live scan. No backfill needed because storage was clean.
- **New editions:** protected by Plan 01's now-deployed fail-loud `nl.normalize_apostrophe_corruption` guard at the shared `save_newsletter` insert (covers single-pass + block-pipeline write paths), shipped live by this plan's `newsletter` rebuild.
- **Root cause documented:** 19-DIAGNOSIS.md (Plan 01) — the ROADMAP's stray double-quote is a presentation/glyph artifact, not a data defect.
- **Backfill discipline honored:** the "scoped reviewed UPDATE, before/after on ONE edition first, never a blind find-replace" spine was satisfied by recognizing the scoped path had nothing to target — confirm-and-close is the spine-correct outcome of an empty affected set, not a shortcut around it.

QUOTE-02 was already completed in Plan 01 (the 17-case regression test through the real fixed function).

## Decisions Made

- **Confirm-and-close over manufactured mutation.** With the affected set empty, the spine-correct action is NO UPDATE. A scoped `WHERE edition_number IN (...)` would have no values; widening it to "have something to change" would be the forbidden blind table-wide find-replace. Both rejected.
- **Reuse, don't re-derive.** The repair was computed by reusing the Plan 01 guard (`nl.normalize_apostrophe_corruption`), guaranteeing the scan signature, the would-be repair, and the live write-path fix are byte-identical — no risk of a divergent transform reintroducing drift.
- **Rebuild `newsletter` only.** The write-path owner ships the guard; `web` stays untouched because the renderer was never the cause.

## Deviations from Plan

**None affecting outcome — an evidence-driven disposition shift, fully anticipated by Plan 01.**

The PLAN framed the expected path as "apply a scoped UPDATE to the affected editions." The live read-only scan (Task 1) found **zero** corrupt rows — the affected set is empty — exactly as Plan 01's 19-01-SUMMARY.md predicted ("Plan 02 should confirm-and-close, not mass-UPDATE"). Per that prediction and the spine, Task 3's UPDATE became a no-op (correctly: no statement issued), while the content-service rebuild proceeded as written. This is the plan's own anticipated branch, not an unplanned deviation — no user decision was needed beyond the recorded Task 2 approval.

## Issues Encountered

None. The scan, the approval gate, and the rebuild all proceeded cleanly. The only "surprise" (an empty affected set) was the explicitly predicted outcome from Plan 01.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Phase 19 complete (2/2 plans).** The highest-visibility content-integrity item is closed: storage proven clean, the fail-loud write-path guard is live in the recreated `newsletter` container, QUOTE-02 regression locks it, and QUOTE-01 is satisfied.
- **No carry-over blockers.** No DB mutation occurred; no schema change; the renderer is untouched. Phase 20 (width tokens & centering foundation — the layout substrate) can proceed independently.
- The pre-existing advisories noted in STATE (service_role leak DEF-17-01, dead `.about-lede` rule) are unaffected by this plan and remain parked.

## Known Stubs

None. This plan created one documentation artifact and rebuilt a service; it introduced no code, no placeholders, no empty-value sinks, no TODO/FIXME.

## Threat Flags

None. The plan mutated no data, added no network/auth/schema surface, and rebuilt an existing service with unchanged code (the Plan 01 guard was already merged). All STRIDE threats in the plan's register (T-19-10..14) resolved benignly: an empty affected set means the blast-radius (T-19-10), genuine-quote-loss (T-19-11), and blind-find-replace (T-19-13) threats had no surface to act on; the rebuild ran from the absolute main tree (T-19-12); only `newsletter` was rebuilt, not `web` (T-19-14).

## Self-Check: PASSED

- FOUND: .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md
- FOUND commit: 5a44998 (Task 1 — backfill review)
- VERIFIED: affected-edition set EMPTY (0 corrupt rows corpus-wide); per-edition/per-column replacement counts all 0
- VERIFIED: operator approval recorded ("Close + rebuild newsletter")
- VERIFIED: no DB mutation; `web` not rebuilt; `newsletter` rebuilt + healthy with the guard live (orchestrator-reported)
- NOTE: Tasks 2 (checkpoint) and 3 (no-UPDATE + rebuild) carry no commit by design — the gate is human approval and the apply had nothing to mutate

---
*Phase: 19-smart-quote-apostrophe-corruption-fix*
*Completed: 2026-06-10*
