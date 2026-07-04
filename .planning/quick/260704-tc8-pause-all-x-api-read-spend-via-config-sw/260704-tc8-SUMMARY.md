---
phase: quick-260704-tc8
plan: 01
subsystem: processor
tags: [x-api, budget, config-switch, health-check, pause]
requires: []
provides:
  - "x_scraping.enabled config pause switch for all X API read spend"
  - "_x_scraping_enabled() fresh-read fail-open helper in the processor"
  - "x_budget health check paused branch (ok + 'paused via config')"
affects: []
tech-stack:
  added: []
  patterns:
    - "Per-call fresh json.load of the live ro config mount (bypasses get_full_config cache) for restart-free flips"
    - "Fail-OPEN gate: config read error keeps scraping enabled (pause is the explicit opt-in state)"
key-files:
  created: []
  modified:
    - config/agentpulse-config.json
    - docker/processor/agentpulse_processor.py
decisions:
  - "Gate placed at the single funnel _x_api_search (all 5 X read call sites route through it) — one guard stops all read spend before any network call or cost log"
  - "Helper fresh-reads /home/openclaw/.openclaw/config/agentpulse-config.json per call (NOT get_full_config — process-lifetime cache); flip needs no rebuild/restart"
  - "Fail-open inversion vs _read_edition_eval_config: any read error returns True (enabled) so a broken config can never silently disable scraping"
metrics:
  duration: ~4min
  tasks: 2
  completed: 2026-07-04
---

# Quick 260704-tc8: Pause All X API Read Spend via Config Switch Summary

**One-liner:** Config-only reversible pause of all X/Twitter API read spend via a fail-open `x_scraping.enabled` gate at the `_x_api_search` funnel, with the hourly x_budget health alert silenced ('ok' + 'paused via config') while paused — deployed via scoped processor rebuild and verified inside the running container.

## What Was Done

### Task 1: Config switch + gate + health-check branch (commit f76b71e)
- `config/agentpulse-config.json`: top-level `"x_scraping": {"enabled": false}` added right after `"version"`. Pauses immediately on deploy (repo `config/` is bind-mounted ro into the container).
- `docker/processor/agentpulse_processor.py`:
  - `_x_scraping_enabled()` added adjacent to `_check_x_budget()` (:8355). Fresh `json.load` of `/home/openclaw/.openclaw/config/agentpulse-config.json` on every call; returns `cfg.get('x_scraping', {}).get('enabled', True)`; any exception logs a warning and returns True (fail-open). `get_full_config()` and its cache untouched.
  - `_x_api_search()` (:8390): guard at the very top, before the `X_BEARER_TOKEN` check — logs INFO `[X-SCRAPE] X API reads paused via config (x_scraping.enabled=false)` and returns `[]`, before any network call or `_log_x_api_cost` write.
  - Health check `# 9. X API budget` (:11405): paused branch sets `results['x_budget'] = {'status': 'ok', 'note': 'paused via config'}` and skips the budget query + `remaining <= 0.50` fail entirely; else branch keeps prior logic verbatim; outer `except` unchanged.
- Automated gate passed: ast.parse clean, config asserts `enabled is False`, `_x_scraping_enabled` occurs 3× (def + search gate + health check).

### Task 2: Scoped processor rebuild + in-container verification
- `docker compose up -d --build processor` from `/root/bitcoin_bot/docker` (operator-approved).
- `agentpulse-processor` Up (healthy); logs show a clean scheduler startup (scrape cycle completed: 98 new posts, workspace cache refreshed, no tracebacks from the new code).
- In-container proof (packaging lesson honored — verified INSIDE the container, no module import):
  - `grep 'X-SCRAPE' /home/openclaw/agentpulse_processor.py` → deployed module carries the gate at :8392; `_x_scraping_enabled` 3 occurrences; paused health branch at :11407-11408.
  - `json.load` of the mounted config from inside the container → `{'enabled': False}` — `paused: OK`.

## Deviations from Plan

**1. [Compose dependency] llm-proxy was also rebuilt/recreated by the scoped processor rebuild**
- **Found during:** Task 2
- **Issue:** `docker compose up -d --build processor` also built and recreated `agentpulse-llm-proxy` — standard compose behavior (processor `depends_on` llm-proxy, so `--build` includes the dependency). No llm-proxy code changed; the image was rebuilt from identical sources.
- **Outcome:** `agentpulse-llm-proxy` came back Up (healthy) before processor start (compose waited on its healthcheck). No action needed; noted for transparency since the constraint said processor-only.

No code deviations — plan executed exactly as written.

## Deferred Issues (pre-existing, out of scope)

- `store_post` moltbook insert failure: `null value in column "content" of relation "moltbook_posts" violates not-null constraint` (post `f908d76f-…`, a text post whose content came through null). Pre-existing Moltbook scraper issue observed in startup logs, unrelated to this change (98/100 posts stored fine). Not fixed per scope boundary.

## Verification

- All X read spend stops on deploy: every path through `_x_api_search` returns `[]` at the top of the function — before the bearer-token check, budget check, network call, and cost log. All 5 call sites (:1432, :1505, :8805, :8838, :8857 pre-edit numbering) funnel through it.
- Hourly health check now reports `x_budget: {'status': 'ok', 'note': 'paused via config'}` — never 'fail' while paused.
- Re-enable = flip `"enabled": true` (or delete the `x_scraping` block) in `config/agentpulse-config.json` — live via the ro mount, no rebuild/restart (per-call fresh read).
- Fail-open proven by code shape: the helper's `except Exception` logs a warning and returns True.
- Opportunistic (not blocked on): next scheduled scrape/hourly cycle should show the `[X-SCRAPE]` INFO line and the operator's hourly x_budget fail pings should stop.

## Commits

- `f76b71e` — feat(processor): pause X API reads via x_scraping config switch, silence x_budget alert while paused

## Self-Check: PASSED

- FOUND: config/agentpulse-config.json (x_scraping.enabled=false)
- FOUND: docker/processor/agentpulse_processor.py (_x_scraping_enabled ×3)
- FOUND: commit f76b71e on main
- FOUND: [X-SCRAPE] gate + paused health branch in the deployed module inside agentpulse-processor
- FOUND: {'enabled': False} read from the mounted config inside the container
