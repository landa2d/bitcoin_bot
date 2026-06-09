---
phase: 18-gated-batch-publish
plan: 03
subsystem: infra
tags: [economy_map, postgrest, supabase, docker-compose, caddy, publish-rpc, anon-rls]

# Dependency graph
requires:
  - phase: 18-gated-batch-publish (plan 18-01)
    provides: loadHub flag-independent published-hub-body fetch (renders the published hub article at #/map)
  - phase: 18-gated-batch-publish (plan 18-02)
    provides: publish_economy_map_batch.py (gated RPC loop) + verify_economy_map_publish.py (anon post-publish assertions)
provides:
  - The v2.1 go-live cutover (PUB-01): 8 in-scope economy_map bodies published live via the atomic publish_block_version RPC
  - Scoped agentpulse-web redeploy carrying the plan-18-01 app.js, proven a visual no-op pre-publish (D-04)
  - Programmatic anon-key proof that the published set is visitor-visible (count 2 -> 8, all cross-links resolve)
affects: [v2.1 milestone close, future economy_map content/timeline phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deploy-first gated cutover: ship the renderer as a provable no-op, then flip content live behind a single operator approval"
    - "Orchestrator-owned live actions: the scoped docker rebuild + publish RPC run from the main tree (worktree-unsafe), gated in-chat"

key-files:
  created: []
  modified: []  # runtime/live actions only — no source diff (docker/web files unchanged; live change is in economy_map + the running agentpulse-web container)

key-decisions:
  - "D-04 deploy-first: rebuilt agentpulse-web with the new app.js BEFORE publishing; verified visual no-op (hub still HUB_STORYLINE, anon published count still 2)"
  - "Scoped rebuild used `docker compose up -d --build web` (service key) from /root/bitcoin_bot/docker, never a blanket deploy (deploy_scoped_and_approved)"
  - "Two operator gates honored: Gate A (cross into prod / deploy-first) + Gate B (the single publish approval, D-06)"
  - "regulation-legal excluded from PUBLISH_ORDER (count published = 8 = hub + 7, never 9)"

patterns-established:
  - "Pattern 1: Repo->prod boundary stop validated by the operator before each consequential prod action (prod_cutover_discipline)"
  - "Pattern 2: Programmatic anon-key verification as the post-publish proof — no manual live walk-through (D-05)"

requirements-completed: [PUB-01]

# Metrics
duration: ~10min
completed: 2026-06-09
---

# Phase 18 (Plan 03): Gated Batch Publish — Go-Live Summary

**The v2.1 cutover: deployed the published-hub renderer as a verified no-op, then on a single operator approval published all 8 in-scope economy_map bodies live via the atomic publish_block_version RPC (count 2 -> 8); anon-key verification proves the hub article + 7 block pillars + all cross-links are visitor-visible.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-09T10:24:00Z
- **Completed:** 2026-06-09T10:33:00Z
- **Tasks:** 3 (Task 1 deploy-first, Task 2 operator gate, Task 3 publish + verify)
- **Files modified:** 0 source files (runtime/live actions; live change is in economy_map + the agentpulse-web container)

## Accomplishments
- Scoped `agentpulse-web` rebuild from the main tree shipping the plan-18-01 `app.js`; proven a **visual no-op pre-publish** (D-04): hub still rendered `HUB_STORYLINE`, anon published-block count still 2.
- Single operator-approval gate (Gate B / D-06) surfaced the manifest in-chat; on "approved", `publish_block_version` flipped all 8 in-scope drafts live (7 blocks first, hub `agent-economy` last — D-07), no halts, no skips.
- Programmatic anon verification (D-05) PASS: all 8 bodies published & anon-visible, hub published article resolves, all 22 cross-link instances -> 7 distinct targets resolve against PUBLISHED content, published-block count **2 -> 8**.
- `regulation-legal` stays deferred (excluded — count is 8, not 9).

## Task Commits

Tasks 1–3 are runtime/live actions (scoped rebuild, operator gate, publish RPC + verification) with **no source diff** — the only repo artifact is this SUMMARY:

1. **Task 1: Deploy-first scoped agentpulse-web rebuild + leak pre-gate** — no source commit (runtime: `docker compose up -d --build web`; leak guard PASS; no-op confirmed)
2. **Task 2: Single operator-approval gate** — no source commit (in-chat manifest approval, Gate B)
3. **Task 3: Live publish batch + anon verification** — no source commit (live `economy_map` write via RPC; verification exit 0)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified
- None (source). Live changes: `economy_map` block_body_versions/blocks (8 rows published via RPC) + the running `agentpulse-web` container (new app.js). `docker/web/entrypoint.sh`, `docker/web/Dockerfile`, `docker/docker-compose.yml` were listed in `files_modified` for ownership/serialization but required no change (expected diff: none).

## Decisions Made
- **Two-gate prod discipline:** added an explicit Gate A (approve crossing into prod / the deploy-first rebuild) on top of the plan's single publish gate (Gate B), honoring `prod_cutover_discipline` (boundary-stop validated by operator). The deploy is a provable no-op, so it is safe before the publish gate.
- Used the `web` compose **service** key (not the `agentpulse-web` container_name) for the scoped rebuild — the container_name fails `docker compose ... <service>`.
- Verification is programmatic (anon key, no preview flag, no service_role) — it proves exactly what a real visitor sees; no manual live walk-through (the Phase-17 preview click-through already covered the content-identical drafts).

## Deviations from Plan
None — plan executed exactly as written. Both `<automated>` gates passed against live state (DEPLOY-UP-OK; PUBLISH-VERIFIED-OK, count 2 -> 8).

## Issues Encountered
- `verify key-links` reported "Source file not found" for both 18-03 links — a false negative: the link `from` fields are descriptive prose, not file paths. The real artifacts exist and the dry-run exercising the publish script is the definitive wiring proof. No real gap.
- The leak pre-gate surfaced a **pre-existing, out-of-scope** advisory: the service_role key's distinguishing substring is present in `.claude/settings.local.json` (committed 2026-04-30, `0e42a5a`) — NOT in the web-deploy path, NOT introduced by this phase. Tracked as a separate credentials/infra task (rotate + scrub).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- PUB-01 satisfied; v2.1 "Agent Economy Content" milestone content is fully live. The hub renders its published article at `#/map`; each published block renders at `#/map/<slug>` with the full reading surface.
- Deferred (carried forward): `regulation-legal` first-publish disposition; manual timeline authoring (bodies publish now with possibly-empty timelines); the pre-existing service_role-in-settings.local.json credentials cleanup.

---
*Phase: 18-gated-batch-publish*
*Completed: 2026-06-09*
