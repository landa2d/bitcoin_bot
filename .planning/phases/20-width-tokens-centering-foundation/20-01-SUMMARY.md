---
phase: 20-width-tokens-centering-foundation
plan: 01
subsystem: web-frontend
tags: [css, layout, width-tokens, centering, spa]
requires:
  - "v2.0 light-mode token system (style-base.css :root) + Source Serif/IBM Plex typography"
  - "body > header sticky nav scoping (quick task 260609-ivq maturity-overlap fix)"
provides:
  - "Two coexisting centered axes: .prose (--measure 64ch) for reading copy, .wide (--wide 1080px) for tiled content"
  - "--measure / --wide / --gutter width tokens in style-base.css :root"
  - "Nav widened onto the --wide axis (D-02) — chrome and content share one centered axis"
  - "Per-route axis application in index.html; renderHub prose-intro wrap in app.js"
affects:
  - "Phase 21 (per-route visual fixes — map 3-col grid, About agent grid) sits on these axes"
  - "Phases 22-23 (excerpts, Signals) reuse the .prose/.wide classes"
tech-stack:
  added: []
  patterns:
    - "Per-route .prose/.wide axis wrappers replacing a single global .container"
    - "padding-inline:var(--gutter) responsive side padding via clamp()"
key-files:
  created: []
  modified:
    - "docker/web/site/style-base.css — width tokens + .prose/.wide classes; nav max-width -> var(--wide)"
    - "docker/web/site/index.html — per-route .wide/.prose wrappers; 720px .container removed"
    - "docker/web/site/style-shared.css — legacy 720px .container rule + mobile override retired"
    - "docker/web/site/app.js — renderHub wraps the hub header trio in .prose"
decisions:
  - "Naming reconciled to .wide/.prose (not .container-wide) per D-01"
  - "About route explicitly split: intro prose -> .prose, agent-row grid -> .wide (D-03)"
  - "Nav widened via the .nav rule only (no .wide on nav markup) to avoid double padding (Pitfall 3)"
  - "Comments worded to avoid the literal '.container' token so the retirement gate (grep -c '.container' == 0) passes"
metrics:
  duration: ~4min
  completed: 2026-06-10
  tasks: 3
  files: 4
---

# Phase 20 Plan 01: Width Tokens & Centering Foundation Summary

Two coexisting, both-centered max-widths (`--measure: 64ch` prose / `--wide: 1080px` tiled) replace the single 720px `.container`, killing the dead left gutter (D-06); the sticky nav now shares the `--wide` axis so chrome and content edges line up (D-02).

## What Was Built

The structural layout foundation every later v2.2 visual phase (21-23) sits on:

- **Width tokens (Task 1):** Added `--measure: 64ch`, `--wide: 1080px`, and `--gutter: clamp(1.25rem, 5vw, 3.5rem)` to the `:root` block in `style-base.css` (after the radius block, so they load first and win the cascade — Pitfall 2). Added two centered display classes: `.prose { max-width: var(--measure); margin-inline: auto; padding-inline: var(--gutter) }` and `.wide { max-width: var(--wide); ... }`. Naming is `.wide`/`.prose` per the D-01 reconciliation (not the brief's `--container-wide`).
- **Nav onto the wide axis (Task 1, D-02):** Changed only the `.nav` `max-width` from `880px` to `var(--wide)`; kept `margin:0 auto` and the existing padding. No `.wide` class on the nav markup (that would double the padding — Pitfall 3); the `.nav` rule cap is sufficient. The `body > header { position:sticky }` rule is untouched (Pitfall 1 — the maturity-overlap fix is preserved).
- **Per-route axis wrappers (Task 2, D-03/D-04):** Removed the single 720px `<div class="container">` that wrapped the hero, all six route-views, subscribe, and footer (the D-06 dead-gutter root cause). Each region now carries its correct axis per the apply-map:
  - `.wide` (tiled): hero band, newsletter list, map content-area, status, About agent-row grid, subscribe + footer.
  - `.prose` (reading copy): reader/edition body, block detail, About intro.
  - The About route is explicitly split — the eyebrow/title/sub + `.about` prose in `.prose`, the `.agent-row` grid in `.wide`, the backlink in `.prose`.
- **Legacy container retired (Task 2):** Deleted the `.container { max-width:720px }` rule (`style-shared.css`) and removed its `.container` selector from the `@media (max-width:600px)` override, replacing both with retirement comments worded to avoid the literal `.container` token.
- **renderHub prose wrap (Task 3, D-03):** Wrapped the hub header trio (`<h1>The Agent Economy</h1>` + `subline` + `hubIntroHtml`) in a single `.prose` div, leaving the three `tierSection(...)` grid calls outside it so the narrative reads at ~64ch while the tier grids span the wide band established by the `#map-view .content-area.wide` wrapper.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Width tokens + .prose/.wide classes + nav widening | `5ce580e` | style-base.css |
| 2 | Per-route .wide/.prose wrappers; retire 720px .container | `76888c9` | index.html, style-shared.css |
| 3 | renderHub prose-intro wrap | `c974018` | app.js |

## Verification

Each task's `<verify><automated>` gate was run against live code and PASSed before its commit:

- **Task 1:** tokens present (`--measure: 64ch`, `--wide: 1080px`, `--gutter: clamp(...)`); `.prose`/`.wide` defs present; nav has `max-width: var(--wide)` and no `max-width:880px`; `body > header` present. → PASS
- **Task 2:** no `class="container"` in index.html; ≥1 `.wide` and ≥1 `.prose`; `grep -c '.container' style-shared.css` == 0; `agent-row` + `tab` markup intact; div tags balanced (32 open / 32 close). → PASS
- **Task 3:** app.js parses (`new Function(...)`); `.prose` present; `tierSection(TIER_LABELS.substrate` and the `<h1>The Agent Economy</h1>` literal and `trimHubBody` unchanged. → PASS

Scope-guard re-checks after all commits: `body > header` sticky preserved; map grid still 2-col (`repeat(2, 1fr)` unchanged — 3-col is Phase 21); nav markup unchanged (no `.wide` on the nav element); 5 About pills intact; no stubs introduced.

**Live-render verification deferred:** the holistic behavioral check (no large left band, both axes centered, ~60-70 char reading line, nav edges == content edges) is owned by Plan 02's orchestrator-run live check — NOT inferred from source bytes here (Phase-19 lesson).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Retirement comments contained the literal `.container` token, failing the Task 2 gate**
- **Found during:** Task 2 (first gate run exited non-zero)
- **Issue:** The Task 2 acceptance criterion requires `grep -c '\.container' style-shared.css` to return 0. My initial retirement comments replacing the deleted rule and the mobile override each mentioned `.container` literally, so the count was 2, not 0.
- **Fix:** Reworded both comments to describe the change without the literal `.container` token ("Legacy 720px container axis retired", "Legacy container rule retired"). Re-ran the full Task 2 gate → PASS.
- **Files modified:** docker/web/site/style-shared.css
- **Commit:** `76888c9` (the corrected comments are in the same Task 2 commit — fixed before commit)

No other deviations — the rest of the plan executed exactly as written.

## Authentication Gates

None — this plan is source-only static front-end edits (no auth, no network calls, no package installs, no deploy).

## Threat Flags

None. This is a presentation-layer change to four static files. No new trust boundary, input sink, network call, or auth path was introduced (consistent with the plan's threat register: T-20-01/02/03/SC all dispositioned accept/mitigate). The `body > header` sticky scoping (T-20-02 mitigate) is preserved; no Supabase URL/key substitution path touched (T-20-03); no package installs (T-20-SC).

## Self-Check: PASSED

- SUMMARY.md created at the expected path.
- All three task commits exist (`5ce580e`, `76888c9`, `c974018`).
- All four target files modified.
