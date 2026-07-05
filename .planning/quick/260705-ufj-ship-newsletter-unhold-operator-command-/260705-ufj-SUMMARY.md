---
phase: quick-260705-ufj
plan: 01
subsystem: gato_brain
tags: [telegram-command, owner-gate, newsletter-hold, pre-enforce-blocker, tdd]
requires:
  - migration 046 (do_not_publish + do_not_publish_reason columns on newsletters)
  - Phase 30 processor publish guards (agentpulse_processor.py:5886 manual, :10965 auto)
  - Phase 31 /newsletter_eval helpers (_eval_read_by_edition, _format_eval_trend)
provides:
  - "/newsletter_unhold <edition#> [confirm] owner-gated two-step release of a held edition"
  - "isNewsletterUnhold allowlist entry in inject-gato-brain.mjs (gato forwards the command)"
affects:
  - enforce-flip todo (2026-07-03-flip-eval-enforce-after-calibration.md) — step 2 unblocked
tech-stack:
  added: []
  patterns:
    - "owner gate FIRST, before any DB read (D-12/T-UNH-01)"
    - "two-step confirm for verdict-overriding mutations (preview → confirm)"
    - "targeted .eq('id', row_id) update — never by edition number, never .in_()"
key-files:
  created:
    - tests/test_unhold_handler.py
  modified:
    - docker/gato_brain/gato_brain.py
    - docker/gato/inject-gato-brain.mjs
    - .planning/todos/pending/2026-07-03-flip-eval-enforce-after-calibration.md
decisions:
  - "Primary-not-held + held-shadow (the live edition-104 shape) returns the 'found but not held' message reporting the primary's row id + status, APPENDING the 'shadow held by design, not releasable' note — reconciles behavior cases (b) and (c) and matches the plan's human-check expectation"
  - "Shadow detection is belt-and-suspenders: data_snapshot.ab_comparison truthy (dict only — a JSON-string snapshot falls back to the title check, never json.loads) OR title startswith '[BLOCK PIPELINE A/B]'"
metrics:
  duration: ~7min
  completed: 2026-07-05
---

# Quick Task 260705-ufj: Ship /newsletter_unhold Operator Command Summary

**One-liner:** Owner-gated two-step (preview → confirm) Telegram release of a held edition's primary row — clears do_not_publish/status='held' by row id so both processor publish guards accept it again, with block_v1 A/B shadow rows structurally un-releasable; the P1 pre-enforce blocker is resolved.

## What Was Built

- **`handle_newsletter_unhold`** (gato_brain.py, after the eval handler): owner gate as the FIRST statement (refusal before any DB read), arg parse with usage message, `.eq("edition_number", N)`-only select of explicit columns, Python-side partition into primary vs shadow (`_unhold_is_shadow`) and held vs not (`do_not_publish` truthy OR `status=='held'`). Bare form renders a PREVIEW (bounded 400-char whitespace-collapsed hold reason, target row id, labels/counts-only eval summary via the reused `_eval_read_by_edition` + `_format_eval_trend`, confirm instruction) with zero `.update()` calls; `confirm` performs the ONE targeted update `{do_not_publish: False, status: 'draft', do_not_publish_reason: None}` via `.eq("id", row_id)`. Multiple held primaries target the newest by `created_at` and say so. `[UNHOLD]` logs carry edition + row id only (T-30-LOG). One top-level try/except returns "⚠ unhold failed: {e}".
- **Dispatch branch 2c-4** directly after the 2c-3 `/newsletter_eval` block, before the intent router — identical ChatResponse shape (`intent="NEWSLETTER_COMMAND"`), `access_tier` threaded. No prefix collision with `/newsletter_eval`/`/newsletter_preview`.
- **Gato allowlist** (inject-gato-brain.mjs): distinct `isNewsletterUnhold` regex (template-literal escaping mirrored verbatim) OR'd into `isGatoBrainCommand`, plus a help-list line — the Phase 9 dead-command landmine avoided; gato rebuilt so the injected allowlist survived patch + compile.
- **`tests/test_unhold_handler.py`** (12 cases, TDD RED→GREEN): multi-table `.eq()`-only StubSupabase with update capture + post-state assertion + `raise_on_execute`; covers owner gate (zero DB calls), preview non-mutation, eval-summary presence/absence, confirm releases primary only (shadow provably unchanged), shadow-only refusal (both sub-cases, even with confirm), not-found / not-held / supabase-error distinct messages, newest-of-multiple targeting, usage, structural no-`.in_()`.

## Verification

- `python3 tests/test_unhold_handler.py` — 12/12 (RED phase first proved 11/12 failing pre-implementation).
- `python3 tests/test_31_newsletter_eval_handler.py` — 18/18 regression green (shared module + reused helpers).
- Task 1 automated gate: ast.parse clean, exactly 1 handler def, dispatch present, `isNewsletterUnhold` OR'd in, `node --check` clean.
- **In-container (v2.3 packaging lesson):** `agentpulse-gato-brain` `/home/openclaw/gato_brain.py` carries the handler (grep=1) + dispatch (grep=1); `openclaw-gato` compiled output carries `isNewsletterUnhold` in 5 `/app/dist/*.js` files (not just .ts). Both containers Up (healthy), clean startup logs (no traceback; the gato groupPolicy doctor warning is pre-existing config advisory).
- Newsletter container untouched — still `Up 47 hours` (calibration freeze honored).
- `git diff --stat HEAD~3 HEAD` — only the three planned files + the two todo files; zero processor diff, zero deletions.

## Deviations from Plan

**1. [Compose behavior] llm-proxy image rebuilt + container recreated during the scoped deploy**
- **Found during:** Task 3 deploy
- **Issue:** `docker compose up -d --build gato_brain gato` also built/recreated `agentpulse-llm-proxy` — compose builds/recreates `depends_on` dependencies of the named services; this is not selectable off without `--no-deps` (which would also skip needed startup ordering).
- **Impact:** None — llm-proxy source unchanged (identical code, image rebuild from same context), container healthy immediately. Newsletter service was NOT touched.
- **Files modified:** none

**2. [Behavior reconciliation] not-held-primary + held-shadow message combines cases (b) and (c)**
- **Found during:** Task 1 design
- **Issue:** Behavior case (c) ("no held primary but a held shadow exists → shadow message") and case (b) ("primary rows exist, none held → found-but-not-held") overlap for the live edition-104 shape; the plan's human-check expects (b) for 104.
- **Fix:** (b) message (primary row id + status) with the (c) "held by design, not releasable" note appended when a held shadow also exists; pure shadow-only editions (no primary) get the standalone (c) message. Both plan test expectations satisfied.
- **Commit:** e1bf55b

Otherwise executed as written.

## Todo Bookkeeping

- `.planning/todos/pending/2026-07-04-newsletter-unhold-command.md` → `.planning/todos/done/` (git mv).
- `.planning/todos/pending/2026-07-03-flip-eval-enforce-after-calibration.md` step 2 → "✅ SHIPPED (quick task 260705-ufj)"; the `enforce=true` flip is now unblocked (remaining steps: calibration review → config flip → optional processor restart for the notify tag).

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| cd51100 | test | RED — 12-case failing suite for the unhold handler |
| e1bf55b | feat | GREEN — handler + 2c-4 dispatch + gato allowlist |
| bd33650 | docs | todo moved to done/ + enforce-flip blocker marked shipped |

## Known Stubs

None — the command is fully wired end-to-end (Telegram → gato allowlist → gato_brain dispatch → handler → newsletters update) and deployed.

## Threat Flags

None beyond the plan's threat model — the new surface (owner-gated verdict-override write) is exactly T-UNH-01..05, all mitigations implemented and test-proven (owner-gate-before-read, two-step confirm, row-id-targeted update, shadow exclusion, labels-only logging, distinct allowlist regex).

## Optional Operator Smoke (from the plan)

Send `/newsletter_unhold 104` from the owner chat — expect the "found but not held" message naming primary row `666a8dea-…` (status=draft) with the shadow noted as held by design, not offered for release.

## Self-Check: PASSED

All 5 claimed files exist on disk; all 3 commit hashes (cd51100, e1bf55b, bd33650) present in git log; test file is 474 lines (min_lines 150 satisfied); in-container greps and health checks verified post-deploy.
