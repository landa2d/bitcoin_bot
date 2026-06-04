---
phase: 04-hub-block-and-status-renderer
plan: 06
status: complete
requirements: [RNDR-04, RNDR-05]
completed: 2026-05-28
---

# Plan 04-06 Summary — Deploy & Verify

## What happened

Deployed the Wave 1–5 SPA renderers to production and verified all five Phase 4
ROADMAP Success Criteria against the live `https://aiagentspulse.com`. No
application code shipped in this plan (frontmatter `files_modified: []`); the
output is the verification artifact.

- **Deploy date/time:** 2026-05-28 ~08:01 UTC (web container rebuild).
- **Deploy commit (head of main at deploy):** `e5e31d5`.
- **VERIFY.md artifact:** `.planning/phases/04-hub-block-and-status-renderer/04-06-VERIFY.md`.
- **Result:** all five ROADMAP Success Criteria verified — deploy + data path
  machine-verified; visual/interactive steps operator-verified ("all checks
  passed"); production state restored after the RNDR-04/06 mutation tests.

## Deviations from plan

1. **Deploy mechanism (scoped, not `scripts/deploy.sh --force-rebuild web`).**
   A dry-run showed production had drifted far behind local `main`; the script's
   directory-level rsync (`--delete`) would have deleted
   `llm-proxy/governance_config.json`, pushed stray artifacts, synced unrelated
   WIP across 5 services, and restarted all 7 services via the `docker-compose.yml`
   delta. To honor RNDR-05 ("zero new infrastructure") without that blast radius,
   deployed a scoped rsync of `docker/web/` only + `docker compose build web &&
   up -d web`. Operator-authorized.

2. **economy_map schema not exposed in prod PostgREST (prerequisite gap, fixed).**
   First live data query returned `PGRST106 / 406` — the `economy_map` schema was
   absent from the PostgREST `db_schemas` list, though the data (7 blocks), RLS,
   and anon SELECT grants were already in place. Applied a reversible,
   operator-authorized fix via Supabase MCP:
   `ALTER ROLE authenticator SET pgrst.db_schemas = '...,economy_map'` +
   `NOTIFY pgrst, 'reload schema'/'reload config'`. After the reload the anon
   blocks query returned HTTP 200 with all 7 rows.

3. **SSH access bootstrap.** This environment's key was not authorized on the
   production host; operator added it to `root@`'s `authorized_keys` before the
   deploy could run.

4. **`new Function` parse check** in Task 1 is a false-positive on the file's
   top-level `const`s; used `node --check` as the authoritative parse (same
   reconciliation as plans 04-02..05).

## Requirements

- **RNDR-04** (hub + status one source of truth): cross-surface maturity mutation
  test passed — flipping `memory-context` nascent→emerging reflected on both
  surfaces and the block page, then restored.
- **RNDR-05** (publish via existing path, zero new infra): single `agentpulse-web`
  container, no siblings; scoped web rebuild only.

## Self-Check: PASSED

VERIFY.md exists with all six RNDR IDs, no anon-key leak, and the sign-off line;
live `app.js` serves `HUB_STORYLINE` (HTTP 200); anon reads `economy_map.blocks`
(7 rows) and `timeline_entries` via PostgREST. Production state restored.
