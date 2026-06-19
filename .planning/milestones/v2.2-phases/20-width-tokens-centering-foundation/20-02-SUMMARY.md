---
phase: 20-width-tokens-centering-foundation
plan: 02
subsystem: web-frontend
tags: [css, color-tokens, section-rhythm, rhythm-01, deploy]
requires:
  - "20-01 width-token foundation (.prose/.wide axes, --measure/--wide/--gutter, nav on --wide)"
  - "v2.0 :root token system (--line / --line-strong / --btn-text) in style-base.css"
provides:
  - "--on-accent token: the two raw on-accent #fff literals (.subscribe, .toggle-btn.active) aliased to it — color audit 100% token-only on loaded routes"
  - "D-05 section-rhythm hierarchy: 1px --line-strong at the four major boundaries (content-area / tier-section / subscribe-section / bottom-bar), 0.5px --line for the list-row hairline"
  - "Scoped web rebuild deployed live to aiagentspulse.com (Phase 20 foundation live)"
affects:
  - "Phase 21 (single-scroll landing) re-verifies WIDTH-01 + RHYTHM-01 holistically on the assembled scroll page — the layout-agnostic foundation carries over"
  - "Phases 22-25 conform to the RHYTHM-01 color + rhythm baseline rather than redefining it"
tech-stack:
  added: []
  patterns:
    - "On-accent white via a semantic --on-accent token instead of raw #fff"
    - "Section-rhythm hierarchy via existing --line-strong (major) / --line (within) tokens"
key-files:
  created: []
  modified:
    - "docker/web/site/style-base.css — --on-accent token def + .subscribe color aliased"
    - "docker/web/site/style-shared.css — .toggle-btn.active aliased; D-05 rhythm rules (tier-section/subscribe/bottom-bar/content-area major, article-entry hairline)"
decisions:
  - "Aliased the two raw on-accent #fff to --on-accent (RESEARCH Open Question #2: lowest-risk reading of token-only-verified-holistically)"
  - "Locked UI-SPEC literals (#ddd2ff active-tab border, rgba(250,248,245,.86) header bg) preserved — out of RHYTHM-01 surface-color scope"
  - "body > header sticky rule untouched (Pitfall 1 — maturity-overlap fix preserved)"
  - "Task 3 per-ROUTE holistic visual sign-off SUPERSEDED by the 2026-06-11 hybrid single-scroll pivot — WIDTH-01/RHYTHM-01 re-verified holistically on the assembled landing (Phase 21); foundation is layout-agnostic"
metrics:
  duration: ~5min (code) + scoped deploy
  completed: 2026-06-11
  tasks: 3
  files: 2
---

# Phase 20 Plan 02: RHYTHM-01 Baseline + Live Deploy Summary

The RHYTHM-01 baseline — token-only color (no raw hex on a surface) + a deliberate section-rhythm hierarchy (1px `--line-strong` between major sections, 0.5px `--line` within) — is established site-wide and **deployed live**. Phase 20's full width+rhythm foundation now runs on `aiagentspulse.com`.

## What Was Built

- **On-accent token (Task 1):** Added `--on-accent:#fff` to `style-base.css :root` (semantic: text/icon on a solid `--accent` fill). Aliased the two raw on-accent whites — `.subscribe` (`style-base.css`) and `.toggle-btn.active` (`style-shared.css`) — to `color: var(--on-accent)`. The color audit is now literally 100% token-only on loaded routes. The two locked UI-SPEC literals (`#ddd2ff` active-tab border, `rgba(250,248,245,.86)` header bg) were preserved unchanged.
- **D-05 section-rhythm hierarchy (Task 2):** Applied the major-vs-within rule weights using the existing tokens — `1px solid var(--line-strong)` at the four MAJOR boundaries (`.content-area` top, `.tier-section + .tier-section`, `#subscribe-section` top, `.bottom-bar` top), and demoted the `.article-entry` row divider to `0.5px solid var(--line)` as a within-section hairline. The `body > header` sticky rule was untouched.
- **Live deploy (Task 3):** Orchestrator-owned scoped rebuild from the main tree — prod↔main drift check first (clean: `web` drift = exactly this Phase 20 work; `newsletter` drift was a false build-then-commit artifact with the corrected guard `437cdb1` confirmed live; `lab-data-provider` = accepted D-07; migration 043 unapplied = pre-existing advisory). `docker compose up -d --build web` (service key, no `--delete`). Verified over the wire: HTTPS 200, served CSS carries `--on-accent`, `.tier-section + .tier-section` major rule, `--line-strong` (×6), and the `--measure`/`--wide` width tokens.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Alias on-accent #fff → --on-accent | `c813005` | style-base.css, style-shared.css |
| 2 | D-05 section-rhythm hierarchy | `33002fa` | style-shared.css, style-base.css |
| 3 | Live deploy + over-the-wire verify (orchestrator-run) | (deploy, no commit) | — |

## Verification

- **Task 1 & 2 automated gates:** both run against live code → PASS (`--on-accent:#fff` present; `.subscribe`/`.toggle-btn.active` use `var(--on-accent)`; zero non-comment `color:#fff` in style-shared.css; locked literals preserved; four major boundaries at `1px var(--line-strong)`; `.article-entry` at `0.5px var(--line)`; `position:sticky` intact).
- **Deploy:** drift check clean for the `web` scope; container recreated; over-the-wire HTTPS fetch (`--resolve aiagentspulse.com:443:127.0.0.1`) returned 200 with the Phase 20 markers in the served bytes (not inferred from source — Phase-19 lesson).
- **Per-route holistic visual sign-off:** intentionally NOT performed as a standalone gate — superseded by the hybrid single-scroll pivot (below). WIDTH-01 + RHYTHM-01 are re-verified holistically on the assembled single-scroll landing in Phase 21.

## Deviations from Plan

**1. Task 3 scope changed by the 2026-06-11 hybrid single-scroll pivot.** The plan's Task 3 was a per-route holistic visual sign-off (no dead gutter / nav edges == content edges, per separate route). Mid-resume, the operator reversed the "keep separate routes" decision in favor of a hybrid single-scroll landing (top-level sections merge into one scroll page + scroll-spy; editions/blocks stay routes — see PROJECT.md / STATE.md decisions, memory `project_v22_hybrid_single_scroll_pivot`). A per-route visual sign-off on a layout about to be merged is low-value, so it was folded into the new Phase 21's holistic verification. The CODE (Tasks 1-2) and the DEPLOY (the foundation is live and serving) are complete and verified; only the per-route *visual* checkpoint moved.

## Authentication Gates

None for the code tasks. The deploy is the only privileged action — orchestrator-owned, scoped to the `web` service, drift-checked, no `--delete`, on the main tree (not a worktree executor).

## Threat Flags

None. Tasks 1-2 are value-preserving CSS edits (color-token aliasing + border-rule weights) — no new trust boundary, sink, network call, or auth path (consistent with the plan's threat register T-20-04/05/06/SC). The sticky-header scoping is preserved; the Supabase substitution path is untouched; no package installs.

## Self-Check: PASSED

- SUMMARY.md created at the expected path.
- Both code task commits exist (`c813005`, `33002fa`); both gates pass against live code.
- Web service rebuilt + deployed live; served bytes confirmed over the wire.
- Phase 20 requirements WIDTH-01 + RHYTHM-01 satisfied in code and live; holistic visual re-verification carried into Phase 21 per the pivot.
