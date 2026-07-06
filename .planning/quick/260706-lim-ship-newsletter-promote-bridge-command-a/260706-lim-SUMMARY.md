---
phase: quick-260706-lim
plan: 01
subsystem: newsletter-operations
tags: [telegram-command, bridge-scope, block-pipeline, promotion, atomic-rpc]
requires:
  - migration 046 do_not_publish column (applied 2026-07-02)
  - handle_newsletter_unhold pattern + _unhold_is_shadow (quick 260705-ufj)
provides:
  - "supabase/migrations/047_promote_block_edition.sql — atomic promote RPC (AUTHORED, NOT applied)"
  - "/newsletter_promote <edition#> [confirm] owner command live over Telegram"
affects:
  - gato_brain dispatch (2c-5 branch)
  - gato OpenClaw allowlist (isNewsletterPromote)
tech-stack:
  added: []
  patterns:
    - "atomic plpgsql SECURITY DEFINER RPC with SET search_path = public (transfer_between_agents trap avoided)"
    - "two-step preview→confirm owner command (unhold pattern mirror)"
key-files:
  created:
    - supabase/migrations/047_promote_block_edition.sql
    - tests/test_promote_handler.py
  modified:
    - docker/gato_brain/gato_brain.py
    - docker/gato/inject-gato-brain.mjs
decisions:
  - "Preview reads eval verdicts by newsletter_id (shadow row id), rendered labels/verdicts-only (T-PROM-04)"
  - "Confirm's ONLY mutation path is the RPC — the handler never .update()s newsletters"
  - "do_not_publish_reason deliberately untouched by the RPC (cosmetic; publish gate reads boolean + status)"
metrics:
  duration: ~9min
  completed: 2026-07-06
---

# Quick Task 260706-lim: /newsletter_promote Bridge Command Summary

**One-liner:** Atomic `promote_block_edition` Postgres RPC (migration 047, authored-only) + owner-gated two-step `/newsletter_promote <edition#> [confirm]` Telegram command that promotes the block-pipeline A/B shadow row to the public edition series and supersedes the single-pass primary — replacing the manual SQL workflow that missed the migration-046 `do_not_publish` column and blocked edition #34's auto-publish on 2026-07-06.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Author migration 047 — atomic promote_block_edition RPC + durable bridge-scope header | 9abf654 | supabase/migrations/047_promote_block_edition.sql (149 lines) |
| 2 (RED) | Bridge-scope sanity tests for /newsletter_promote | 7f06a54 | tests/test_promote_handler.py (5 cases, 0/5 → RED confirmed) |
| 2 (GREEN) | handle_newsletter_promote + 2c-5 dispatch + gato allowlist | 70cad1b | docker/gato_brain/gato_brain.py, docker/gato/inject-gato-brain.mjs |
| 3 | Scoped rebuild gato_brain + gato + in-container verification | (no code change — docs commit is orchestrator-owned) | — |

## What Shipped

- **Migration 047** (`promote_block_edition(p_shadow_id uuid, p_primary_id uuid, p_new_edition_number int, p_reason text) RETURNS jsonb`): SECURITY DEFINER + `SET search_path = public`, 3 RAISE validations (shadow exists+is-shadow / primary exists / published edition-number collision), shadow promotion (title/title_impact prefix strip via `substring(... from 22)`, `edition_number`, `status='draft'`, `do_not_publish=false` column, data_snapshot cleanup of `ab_comparison` + retired `do_not_publish` key + 4 promotion stamps matching the operator's manual schema), primary supersede (`status='held'` + `data_snapshot.superseded_by`). Header carries the operator's durable record: bridge-scope cut-over criteria (target 2026-08-01), the definitive 6-marker shadow inventory + edition-#34 history note, and the content_telegram limitation.
- **Handler** (`handle_newsletter_promote`, gato_brain.py after unhold): owner gate before any read (T-PROM-01), `.eq()`-only reads (EVAL-03), reuses `_unhold_is_shadow`, newest-by-created_at on multi-candidate editions, suggested number = max published + 1, preview with eval verdicts (by `newsletter_id`) or the explicit `⚠ no eval recorded for this row` line, confirm via the atomic RPC only, RPC failure surfaced verbatim with the nothing-was-mutated atomicity note, `[PROMOTE]` logs ids/numbers only (T-30-LOG).
- **Dispatch**: 2c-5 branch after 2c-4 unhold, before `/x-`; no prefix collisions among `/newsletter_preview` / `/newsletter_eval` / `/newsletter_unhold` / `/newsletter_promote` / `/newsletter_publish` (distinct literals).
- **Gato allowlist**: distinct `isNewsletterPromote` regex OR'd into `isGatoBrainCommand` + help-list line (Phase 9 dead-command landmine avoided).

## Verification

- Tests: `tests/test_promote_handler.py` 5/5; regressions `tests/test_unhold_handler.py` 12/12 + `tests/test_31_newsletter_eval_handler.py` 18/18.
- In-container (v2.3 packaging lesson): `def handle_newsletter_promote` present in `/home/openclaw/gato_brain.py` of the RUNNING agentpulse-gato-brain (grep=1; `newsletter_promote`=11); `isNewsletterPromote` present in openclaw-gato at `/tmp/inject-gato-brain.mjs` (grep=2) AND injected into the compiled `/app/dist` tree (`reply-BQ1yj1_D.js` + dispatch chunks).
- Container health: gato_brain + gato both Up (healthy), clean uvicorn startup (no ImportError/SyntaxError), telegram provider started.
- Newsletter container UNTOUCHED — Up 2 days (calibration freeze preserved).

## Deviations from Plan

**1. [Observation] llm-proxy container recreated during the scoped rebuild**
- **Found during:** Task 3
- **Issue:** `docker compose up -d --build gato_brain gato` also rebuilt/recreated `agentpulse-llm-proxy` because gato_brain `depends_on` it — compose dependency behavior, not an extra service in the command.
- **Outcome:** llm-proxy back Up (healthy); newsletter untouched. No action needed.

Otherwise: plan executed exactly as written.

## HANDOFF — migration 047 apply is ORCHESTRATOR-OWNED

Migration 047 is **AUTHORED ONLY**. The executor did NOT apply it (no psql, no supabase CLI, no MCP apply call in this run). The orchestrator applies `supabase/migrations/047_promote_block_edition.sql` via MCP (project ref `zxzaaqfowtqvmsbitqpu`).

**Expected until applied:** the command's `confirm` path will 404/error on the missing `promote_block_edition` RPC — this is expected and fail-loud (the handler surfaces the error with the nothing-was-mutated note). The bare preview form works immediately (reads only).

## Known Unknowns (iterate-live — deliberately outside bridge-scope test coverage)

Recorded in the test module docstring and here:

1. **Multi-shadow editions** — several A/B shadow rows on one edition number: the handler targets the newest by `created_at`, but this posture is unproven by the sanity suite.
2. **Republish collision** — promoting into an edition number that gets published concurrently: the RPC's published-collision RAISE is the guard; race timing unexamined.
3. **Concurrent promotion** — two confirms racing: last-write posture unexamined; the RPC's validations (shadow-marker check fails on the second run after the first strips the markers) bound the damage.

## Self-Check: PASSED

- supabase/migrations/047_promote_block_edition.sql: FOUND
- tests/test_promote_handler.py: FOUND
- Commits 9abf654 / 7f06a54 / 70cad1b: FOUND in git log
- Migration 047 NOT applied: confirmed (no apply command in this run)
