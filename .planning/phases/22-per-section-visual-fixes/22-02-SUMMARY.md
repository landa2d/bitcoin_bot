---
phase: 22-per-section-visual-fixes
plan: 02
subsystem: ui
tags: [html, css, design-tokens, frontend, about-section, rhythm-01]

# Dependency graph
requires:
  - phase: 20-width-tokens-centering-foundation
    provides: ".prose/.wide width axes + --measure/--wide/--gutter tokens the made-cols block sits on"
  - phase: 21-single-scroll-landing-scroll-spy-nav
    provides: "#about as a landing section inside #landing (intra-section edit, no nav touch)"
provides:
  - "#about agent grid rewritten from the uniform 5-pill .agent-row to a two-column .made-cols split"
  - "LEFT: ordered numbered 01-04 pipeline (Processor/Analyst/Research/Newsletter)"
  - "RIGHT: unordered bulleted supporting layer (Gato, Gato Brain, LLM proxy, web front end)"
  - "Distinct violet .approval callout surfacing the human-approval spine"
  - "Net-new token-only .made-cols/.made-head/.agent/.idx/.dot/.name/.desc/.approval CSS (collapses 2->1 at 880px)"
affects: [22-04-deploy-verify, phase-25-responsive-a11y]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Token-only net-new CSS (RHYTHM-01): mockup palette mapped to prod tokens (--accent/--accent-soft/--accent-ink/--line); zero hex"
    - "Compact single-line CSS rule bodies so [^}]* acceptance gates match"

key-files:
  created: []
  modified:
    - "docker/web/site/index.html — #about made-cols markup + D-11/D-12 intro de-dup"
    - "docker/web/site/style-shared.css — net-new made-cols/agent/approval token-only CSS"

key-decisions:
  - "Kept Gato Brain as a distinct supporting-layer entry (D-12) — NOT folded into Gato; 4 pipeline + 4 supporting = the 'eight cooperating services' the intro commits to"
  - "Recast intro P3 as a one-line lead-in (dropped the 'five content agents' enumeration that contradicted the new 4-item pipeline and double-stated the supporting layer)"
  - "Pulled the approval clause out of intro P2 (D-11) — now stated once, in the violet .approval callout"
  - ".approval text reuses --accent-ink; no new token added to style-base.css"

patterns-established:
  - "Net-new component CSS ported from an in-codebase analog (.agent-row/.agent-pill) with every mockup palette token mapped per the Token Mapping table"
  - "Comments in token-discipline CSS must NOT contain the forbidden literal tokens/hex (the RHYTHM-01 gate scans the whole file, comments included)"

requirements-completed: [AGENTS-01]

# Metrics
duration: 3min
completed: 2026-06-12
---

# Phase 22 Plan 02: About #about Agent Grid Rewrite Summary

**The About `#about` section now reads as an ordered numbered 01-04 pipeline + an unordered bulleted supporting layer with a distinct violet "nothing publishes without human approval" callout — the orphaned 5th card is gone, and all net-new CSS is token-only (zero hex).**

## Performance

- **Duration:** 3 min 22 sec
- **Started:** 2026-06-12T10:30:06Z
- **Completed:** 2026-06-12T10:33:28Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Replaced the uniform 5-pill `.agent-row` (which left Gato orphaned alone on row 2) with the mockup's `made-cols` two-column split: LEFT numbered 01-04 pipeline, RIGHT bulleted supporting layer (D-10).
- Surfaced the editorial-integrity spine as a distinct violet `.approval` callout ("Nothing publishes without human approval.").
- De-duped the approval clause from intro P2 and recast intro P3 so the supporting layer / pipeline count is stated once and is internally consistent (D-11/D-12).
- Added net-new token-only CSS (`.made-cols`/`.made-head`/`.agent`/`.idx`/`.dot`/`.name`/`.desc`/`.approval`) that collapses 2-col -> 1-col at `max-width:880px`; `style-base.css` needed no new token.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite #about markup to the made-cols pipeline/supporting split + intro de-dup** - `54070be` (feat)
2. **Task 2: Net-new token-anchored CSS for made-cols/agent/idx/dot/name/desc/approval** - `d717711` (feat)

## Files Created/Modified
- `docker/web/site/index.html` - `#about` section: `.agent-row` 5-pill grid replaced by the `.made-cols` two-column block (numbered 01-04 pipeline + bulleted supporting layer + violet `.approval` callout); intro P2 approval clause removed (D-11); intro P3 recast as a one-line lead-in (D-12).
- `docker/web/site/style-shared.css` - Appended a clearly-commented net-new block: `.made-cols` (1fr 1fr grid), `.made-head` (mono section label matching `.tier-label` chrome), `.agent` (26px 1fr row), `.idx`, `.dot` (`var(--accent)` bullet), `.name`, `.desc`, `.approval` (`var(--accent-ink)` text on `var(--accent-soft)`); `@media (max-width:880px)` collapse to 1 column.

## D-12 Copy-Accuracy Point — FOR OPERATOR SIGN-OFF AT 22-04

The mockup folded the conversational middleware ("Gato Brain") into a single "Gato" supporting-layer entry. This plan did **not** silently drop Gato Brain — it preserves the v2.0 accuracy bar. The final About copy the operator must review at the 22-04 live verify is:

**Intro (`.prose`) — final wording:**
- P1 (unchanged): "...Each edition is produced by **eight cooperating services** that ingest the week's signals, synthesize findings, and draft the briefing."
- P2 (approval clause removed): "...so the cost of producing an edition is itself part of what we track." *(no longer ends with "— and nothing is published without human approval")*
- P3 (recast lead-in): "Four of those services form the content pipeline that runs in sequence each week; the others make up the supporting layer beneath it."

**The pipeline · in order (LEFT, numbered):**
1. Processor — Background scheduler — scrapes sources, runs the pipelines, and posts.
2. Analyst — Scores and clusters incoming signals into findings.
3. Research — Deepens context on the week's tier-1 stories.
4. Newsletter — Synthesizes the dual-mode (Technical / Strategic) editions.

**The supporting layer (RIGHT, bulleted):**
- Gato — Telegram operator interface and coding surface.
- **Gato Brain** — Conversational middleware that routes operator commands. *(kept distinct from Gato — the D-12 point)*
- LLM proxy — Governs budgets and per-agent wallets across every model call.
- web front end — Serves the published site you are reading now.

**Approval callout:** "**Nothing publishes without human approval.** Every edition is drafted by the system and shipped only after an operator signs off."

**Service-count reconciliation:** 4 pipeline + 4 supporting = **8** = the "eight cooperating services" P1 commits to. Gato moved from a "content agent" pill to the supporting layer, so the previous "five content agents" phrasing in P3 was dropped (it would now contradict the 4-item numbered pipeline). Operator decisions to confirm at 22-04: (a) keep Gato Brain distinct vs. fold into Gato; (b) the supporting-layer descriptions above; (c) the "eight cooperating services" count phrasing.

## Decisions Made
- **Gato Brain kept distinct (D-12):** retained as its own supporting-layer entry rather than folded into "Gato" (mockup did fold it), preserving the v2.0 "eight cooperating services" accuracy bar. Surfaced above for operator sign-off.
- **P3 recast, not just trimmed:** the original P3 enumerated the supporting layer (now shown in the grid) AND said "five content agents" (now contradicts the 4-item pipeline). Recast as a one-line lead-in introducing the two columns.
- **No new token:** `.approval` text reuses the existing `--accent-ink`; `style-base.css` is unmodified (per D-07 / discretion: add a token only if needed).

## Deviations from Plan

None - plan executed exactly as written. (Both tasks' automated gates printed PASS; see Issues Encountered for one self-inflicted gate trip resolved within the task.)

## Issues Encountered
- **Task 2 gate tripped on my own comment text.** The first version of the net-new CSS block's header comment spelled out the token mapping using the literal forbidden strings (`--violet`, `--line-soft`) and the hex `#2d2585`. The RHYTHM-01 gate scans the *whole file* (comments included), so it failed conditions 6/7/8. Fixed by rewriting the comment to reference the mapping by token *names* only ("accent / accent-soft / accent-ink / line") with no forbidden literal or hex. Gate then printed PASS. No code change — comment-only. (Lesson captured in patterns-established.)

## User Setup Required
None - no external service configuration required. This is a source-only frontend edit; the live render is verified by the orchestrator-owned plan 22-04 (scoped `docker compose ... web` rebuild + operator verify).

## Next Phase Readiness
- AGENTS-01 ships at source: `#about` is the `made-cols` numbered-pipeline + bulleted-supporting split with the violet `.approval` callout; the orphaned card is gone; all net-new CSS is token-only.
- **22-04 owns:** the live render verification (no orphaned card; ordered pipeline + bulleted supporting; violet callout renders correctly) AND the D-12 copy sign-off captured above.
- No blockers.

## Self-Check: PASSED
- FOUND: docker/web/site/index.html (made-cols markup present)
- FOUND: docker/web/site/style-shared.css (.made-cols CSS present)
- FOUND commit: 54070be (Task 1)
- FOUND commit: d717711 (Task 2)

## Note for Orchestrator
- STATE.md / ROADMAP.md were NOT modified by this executor (tracking is orchestrator-owned, per sequential-execution contract).
- REQUIREMENTS.md traceability for AGENTS-01 was NOT updated here (GSD SDK not invoked) — flagged for the orchestrator to mark complete centrally.

---
*Phase: 22-per-section-visual-fixes*
*Completed: 2026-06-12*
