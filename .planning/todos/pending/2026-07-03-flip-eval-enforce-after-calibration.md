---
created: 2026-07-03T08:20:00Z
updated: 2026-07-03T08:20:00Z
title: Flip edition_eval enforce=true after ~2-edition report-only calibration window (30-04 Task 6)
area: newsletter/config
priority: P1
phase_candidate: false
files:
  - config/agentpulse-config.json
---

## Action

The v2.3 pre-publish eval is LIVE in report-only mode (`edition_eval.enabled=true`,
`enforce=false`). NOTE: although armed 2026-07-02, the pipeline was actually broken until
2026-07-03 (newsletter image was missing the eval modules — see `.planning/v2.3-MILESTONE-AUDIT.md`);
the working calibration window starts 2026-07-03, and edition #104 carries no eval (its in-memory
fact base was unrecoverable). The remaining activation step — deliberately operator-owned
(Phase 30 plan 30-04 Task 6) — is:

1. Observe ~2 editions' verdicts in `edition_evals` (now legible without SQL via the Friday
   notify eval section and the `/newsletter_eval` + `/newsletter_eval trend` Telegram commands,
   Phase 31). Watch for `⚠ WOULD HAVE HELD (report-only)` tags: confirm they flag real problems,
   not false positives.
2. **✅ SHIPPED (quick task 260705-ufj, 2026-07-05)** — `/newsletter_unhold <edition#> [confirm]`
   is live (owner-gated two-step preview→confirm release in gato_brain + gato allowlist,
   deployed and verified in-container; todo moved to `done/2026-07-04-newsletter-unhold-command.md`).
   The enforce flip is no longer blocked on an escape hatch.
3. When calibrated, set `edition_eval.enforce=true` in `config/agentpulse-config.json`.
   Config is read per-call via the live ro `../config` mount — NO rebuild needed.
4. Rollback if needed: `enforce=false` (or `enabled=false` to disarm entirely).

Companion prevention/auto-fix work sized by the calibration data:
`2026-07-04-writer-grounding-constraint.md` (P2) and `2026-07-04-grounding-rewrite-iteration.md` (P3).

**This flip is also the newsletter-container FREEZE-LIFT event** (added 2026-07-06): the
calibration freeze is event-gated on this todo, not open-ended. Downstream chain (see
ROADMAP.md "Block-Pipeline Cut-Over Timeline"): freeze lift → fact-base-persistence rebuild
(047 cut-over criterion 3) → block-primary eval live-proof (criterion 5) →
`block_pipeline.enabled=true` flip (target 2026-08-01, retires `/newsletter_promote`).
Calibration Fridays 2026-07-10 + 2026-07-17 ⇒ earliest lift ≈ 2026-07-17/20; zero slack to
the 08-01 target — a failed calibration week triggers the 047 bridge→keeper reassessment.

## Why a todo

Milestone v2.3 closes with this pending — the calibration window needs real Friday editions,
which arrive after the archive. This todo keeps the flip from getting lost. The newsletter
container was rebuilt 2026-07-03 (audit-blocker packaging fix, superseding Phase 31 D-14);
from here, avoid further `newsletter` rebuilds until enforce is flipped unless a change
requires it. Also note: the processor caches config for its process lifetime, so after
flipping `enforce=true`, restart the processor if you want the Friday-notify's report-only
tag to update immediately (the hold action itself reads live, newsletter-side).
