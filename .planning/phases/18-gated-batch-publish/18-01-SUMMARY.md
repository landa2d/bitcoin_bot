---
phase: 18-gated-batch-publish
plan: 01
subsystem: web-frontend
tags: [economy-map, hub-render, app.js, deploy-first, no-op]
requires:
  - "economy_map.blocks.current_body_version_id (mig 043 — hub agent-economy row, tier 'hub')"
  - "economy_map.block_body_versions.body_md (anon published-only RLS, 033:367-370)"
  - "loadBlock published-body path (app.js :674-677 — the mirrored analog)"
  - "trimHubBody() + HUB_STORYLINE constant + renderHub :594-597 fork (reused unchanged)"
provides:
  - "loadHub prod published-hub-body fetch (flag-independent) feeding the existing trimHubBody/HUB_STORYLINE render fork"
  - "deploy-first visual no-op proof (D-04) documented in-code: NULL current_body_version_id pre-publish -> HUB_STORYLINE fallback"
affects:
  - "docker/web/site/app.js (loadHub only)"
  - "Wave-2 go-live plan (this is the renderer change it deploys via scoped agentpulse-web rebuild)"
tech-stack:
  added: []
  patterns:
    - "supabase-js schema-scoped read: sb.schema('economy_map') auto-sets Accept-Profile (D-16); fetch by .eq('id', current_body_version_id).single(); NO defensive .eq('status','published') (D-17, RLS is the boundary)"
    - "draft-first / published-fallback precedence (mirrors loadBlock :655-677): published fetch gated on !hubBodyMd so the Phase-17 preview draft keeps precedence in preview mode"
key-files:
  created: []
  modified:
    - "docker/web/site/app.js (loadHub — added prod published-hub-body fetch + D-04 no-op reasoning comment)"
decisions:
  - "D-01: prod renders the PUBLISHED hub body via a flag-INDEPENDENT fetch (not gated on PREVIEW_ENABLED)"
  - "D-02: published article rendered trimmed via existing trimHubBody(); HUB_STORYLINE kept as the pre-publish fallback (NOT deleted)"
  - "D-04: deploy-first visual no-op pre-publish — NULL current_body_version_id -> hubBodyMd null -> HUB_STORYLINE; provable before any content goes live"
  - "D-16: sb.schema('economy_map') sets Accept-Profile automatically"
  - "D-17: no defensive .eq('status','published') filter — anon RLS exposes only published versions"
metrics:
  duration: "~6 min"
  completed: "2026-06-09"
  tasks: 2
  files-changed: 1
---

# Phase 18 Plan 01: Published Hub Render at #/map Summary

Authored the single prod `app.js` change that renders the PUBLISHED hub `agent-economy` body as a trimmed framing article at `#/map`, via a new flag-INDEPENDENT `loadHub` fetch mirroring the `loadBlock` published-body path — a provable deploy-first visual no-op until the Wave-2 publish batch flips the hub body live.

## What Was Built

`loadHub` (docker/web/site/app.js) now carries a NEW published-hub-body fetch placed AFTER the existing Phase-17 `PREVIEW_ENABLED` draft fetch and BEFORE the preview proposed_maturity fetch. The new path:

- Resolves the hub row from the EXISTING `loadHub` `blocks` select via `data.find(b => b.slug === 'agent-economy')` — no separate hub-row read (the select reads all rows ordered by `sort_order` with no tier filter, so the tier-`hub` `agent-economy` row from migration 043 is returned).
- Is flag-INDEPENDENT — it is NOT inside an `if (PREVIEW_ENABLED)` block, so prod renders the published hub article once the hub body is published (D-01).
- Is gated on `!hubBodyMd` so the Phase-17 preview DRAFT fetch keeps precedence in preview mode — the exact draft-first / published-fallback precedence `loadBlock` uses (:655-677).
- Uses `sb.schema('economy_map').from('block_body_versions').select('body_md').eq('id', hubRow.current_body_version_id).single()` — `sb.schema('economy_map')` auto-sets `Accept-Profile` (D-16); NO defensive `.eq('status','published')` filter (D-17 — anon RLS is the boundary).
- Graceful-degrades: any error/empty leaves `hubBodyMd` null, never throws (mirrors :676).

It feeds the EXISTING `renderHub` `trimHubBody`/`HUB_STORYLINE` fork at :594-597 UNCHANGED: once `hubBodyMd` is populated it renders the trimmed published article (D-02); when null (pre-publish) it renders the `HUB_STORYLINE` constant (the graceful pre-publish fallback — NOT deleted).

An in-code comment documents the DOUBLE-SAFE deploy-first no-op proof (D-04), mirroring the Phase-17 preview comment reasoning: `agent-economy.current_body_version_id` is NULL until the Phase-18 publish batch runs -> `hubBodyMd` stays null -> `HUB_STORYLINE` fallback; AND independently, anon RLS exposes only `status='published'` versions, so even a non-null pointer resolves only to published content.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Add flag-independent prod published-hub-body fetch to loadHub | 2ad3615 | docker/web/site/app.js |
| 2 | Prove deploy-first visual no-op pre-publish + placeholder integrity | cec4d49 | (verification milestone — D-04 comment authored with Task 1) |

Note on Task 2: its required artifacts are (a) the D-04 deploy-first no-op reasoning comment and (b) placeholder/leak-guard verification. The comment was authored in the SAME contiguous `loadHub` block as the Task-1 fetch (one logical change, so splitting the hunk would be artificial). Task 2 is therefore committed as a verification-milestone marker (`--allow-empty`) recording that its `<automated>` gate passes against the live modified file — keeping the per-task atomic commit record while keeping the diff confined to `loadHub`.

## Verification Gates (run against live modified code)

Task 1 gate:
```
node --check docker/web/site/app.js && echo "JS-SYNTAX-OK"
=> JS-SYNTAX-OK   (exit 0)
```

Task 2 gate:
```
grep -c '__SUPABASE_URL__\|__SUPABASE_ANON_KEY__' docker/web/site/app.js
=> 2   (>= 2 — both placeholders intact in the tracked file)

python3 scripts/verify_economy_map_crosslinks.py --guard-only
=> exit 0; prints:
   PLACEHOLDER-INTACT: docker/web/site/app.js still holds __SUPABASE_URL__ / __SUPABASE_ANON_KEY__
   SVC-ROLE-NOT-IN-WEB-DEPLOY-PATH: the service_role key appears in NONE of the web-deploy-path files
```

Diff confinement: `git diff` (Task-1 commit) shows a single hunk `@@ -487,6 +487,37 @@ async function loadHub()` — additions only, no change to `renderHub`'s :594-597 fork, `HUB_STORYLINE`, `PREVIEW_ENABLED`, the Phase-17 preview draft fetch, or any CSS/route/view/component/`blocks`-select column.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' actions and acceptance criteria were met; both `<automated>` gates pass against live code with the expected printed output.

## Threat Surface

No new threat surface introduced. The new fetch uses the anon-keyed `sb.schema('economy_map')` client (T-18-01 mitigated: anon RLS returns only `status='published'` bodies). T-18-02 mitigated: both `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders intact and `--guard-only` confirms no service_role key in any web-deploy-path file. T-18-03 (premature live content) accepted: the change is a documented no-op until the Wave-2 publish batch (NULL `current_body_version_id` -> `HUB_STORYLINE`); no write surface here.

The pre-existing `.claude/settings.local.json` service_role leak (DEF-17-01) remains out-of-scope advisory — correctly classified by the guard as a pre-existing, non-web-deploy-path finding for separate operator key rotation.

## Known Stubs

None. `HUB_STORYLINE` is an intentional pre-publish fallback (D-02), not a stub — it is the documented graceful render until the Wave-2 publish batch sets `agent-economy.current_body_version_id` non-null. This is the deploy-first no-op behavior the phase requires.

## Notes for Downstream

- This plan does NOT deploy and does NOT run any live DB publish — it only authors the renderer code. The Wave-2 go-live plan ships this via the scoped `agentpulse-web` rebuild (worktree-unsafe — run no-worktree/sequential from the main tree) and runs the gated publish batch that flips the hub body + 7 block bodies live.
- Web-deploy gotcha (MEMORY: web_static_preview_substitution): the deployed image substitutes the `__SUPABASE_*__` placeholders at container start via entrypoint.sh; the tracked file must keep the placeholders (verified).
- The published path is reached for anon visitors only after the publish RPC points `blocks.current_body_version_id` at the published hub body version (mig 039 atomic flip).

## Self-Check: PASSED

- FOUND: `.planning/phases/18-gated-batch-publish/18-01-SUMMARY.md`
- FOUND commit 2ad3615 (Task 1 — published-hub-body fetch)
- FOUND commit cec4d49 (Task 2 — verification milestone)
- FOUND commit b65b12e (SUMMARY)
- Task-1 app.js diff confined to 1 hunk inside `loadHub` (verified `@@` count == 1)
- `.planning/STATE.md` / `.planning/ROADMAP.md` NOT in any of my commits (orchestrator-owned, correctly untouched; STATE.md shows a pre-existing working-tree modification not introduced by this plan)
