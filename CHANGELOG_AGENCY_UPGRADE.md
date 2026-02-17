# AgentPulse Agency Upgrade — Changelog

**Date:** February 17, 2026
**Session:** Agency upgrade implementation, testing, and deployment fixes

---

## Summary

Transformed the AgentPulse system from a task-queue-with-workers model into one supporting autonomous agents with self-correction, proactive behavior, inter-agent collaboration, and a budget enforcement system.

---

## Changes by File

### Code Changes

#### `docker/processor/agentpulse_processor.py`
- Added `get_full_config()` — loads and caches `agentpulse-config.json`
- Added `AgentBudget` class — tracks per-task budget limits (LLM calls, time, subtasks, retries)
- Added `get_budget_config()` — reads budget limits for agent + task type with defaults
- Added `check_daily_budget()` — checks if agent has remaining daily LLM call budget
- Added `increment_daily_usage()` — upserts daily usage row in `agent_daily_usage` table
- Added `get_daily_usage()` — returns daily usage stats for all or specific agents
- Added `detect_anomalies()` — pure Python/SQL anomaly detection (problem frequency spikes, tool sentiment crashes, post volume anomalies)
- Added `check_proactive_budget()` — checks daily proactive alert limit
- Added `check_proactive_cooldown()` — enforces minimum time between proactive scans
- Added `proactive_scan()` — runs anomaly detection, delegates `proactive_analysis` to Analyst
- Added `create_negotiation()` — creates agent-to-agent negotiation with pair validation and active count limits
- Added `respond_to_negotiation()` — records negotiation response, advances state (closed/follow_up)
- Added `check_negotiation_timeouts()` — marks stale negotiations as timed_out
- Added new task types in `execute_task()`:
  - `get_budget_status` — returns daily usage data
  - `get_budget_config` — returns budget section of config
  - `targeted_scrape` — fetches posts for specific submolts on agent request
  - `can_create_subtask` — checks processor overload
  - `send_alert` — sends Telegram notification, increments system alerts
  - `proactive_scan` — triggers proactive monitoring
  - `create_negotiation` — initiates negotiation
  - `respond_to_negotiation` — responds to negotiation
  - `get_active_negotiations` — queries active negotiations
  - `check_negotiation_timeouts` — runs timeout check
  - `get_recent_alerts` — queries recent alert tasks
- Added scheduled jobs: `proactive_scan` (60 min), `check_negotiation_timeouts` (10 min)
- Added all new task types to argparse choices
- **Bug fix:** Skip empty UUID fields (`request_task_id`, `response_task_id`) in negotiation insert/update to avoid Postgres `invalid input syntax for type uuid` error

#### `docker/analyst/analyst_poller.py`
- Added `get_budget_config()` — reads budget limits from config for analyst tasks
- Added `increment_daily_usage()` — upserts daily usage for the analyst agent
- Added `check_stale_tasks()` — force-fails tasks stuck in_progress longer than 2x budget timeout
- Added `PROACTIVE_ANALYSIS_PROMPT` — system prompt for anomaly assessment
- Added `ENRICHMENT_PROMPT` — system prompt for newsletter enrichment requests
- Added `handle_data_requests()` — creates `targeted_scrape` subtasks when analyst output includes `data_requests`
- Added `handle_proactive_alert()` — creates `send_alert` tasks when proactive analysis flags an alert
- Added `handle_negotiation_response()` — creates `respond_to_negotiation` tasks for negotiation flows
- Updated `process_task()`:
  - Injects budget config into `input_data` before LLM call
  - Tracks `budget_usage` from LLM response
  - Calls `handle_data_requests()`, `handle_proactive_alert()`, `handle_negotiation_response()`
  - Added `proactive_analysis` and `enrich_for_newsletter` to supported task types
- Updated `run_analysis()` with `elif` branches for `proactive_analysis` and `enrich_for_newsletter`
- Updated `main()` to call `check_stale_tasks()` at start of each poll cycle

#### `docker/newsletter/newsletter_poller.py`
- Added `handle_negotiation_request()` — checks output for `negotiation_request` and creates corresponding negotiation + enrichment tasks
- Updated `process_task()` to call `handle_negotiation_request()` after saving newsletter

#### `config/agentpulse-config.json`
- Added `budgets` section with per-task limits for analyst and newsletter agents
- Added `budgets.global` with daily limits (100 LLM calls, 5 proactive alerts, 60 min cooldown)
- Added `negotiation` section (max rounds, active limits, timeout, allowed pairs)
- Version bumped to `1.1.0`

### Docker/Infrastructure Changes

#### `docker/docker-compose.yml`
- **Fix:** Added `../config:/home/openclaw/.openclaw/config:ro` volume mount for analyst container (was missing — analyst couldn't read budget config)
- **Fix:** Added `../config:/home/openclaw/.openclaw/config:ro` volume mount for newsletter container

#### `docker/analyst/Dockerfile`, `docker/analyst/entrypoint.sh`, `docker/analyst/requirements.txt`
- No functional changes in this session (pre-existing modifications from Phase 3)

#### `docker/newsletter/Dockerfile`, `docker/newsletter/entrypoint.sh`, `docker/newsletter/requirements.txt`
- No functional changes in this session (pre-existing modifications from Phase 3)

### Skill/Documentation Changes

#### `skills/agentpulse/SKILL.md`
- Added `/budget` command — displays per-agent usage today vs global limits
- Added `/alerts` command — displays recent proactive alerts
- Added `/negotiations` command — displays active agent negotiations
- **Fix:** Renamed all hyphenated commands to use underscores for Telegram `setMyCommands` compatibility:
  - `/pulse-status` → `/pulse_status`
  - `/invest-scan` → `/invest_scan`
  - `/newsletter-full` → `/newsletter_full`
  - `/newsletter-publish` → `/newsletter_publish`
  - `/newsletter-revise` → `/newsletter_revise`
  - `/deep-dive` → `/deep_dive`

#### `skills/agentpulse/HEARTBEAT.md`
- **Fix:** `/pulse-status` → `/pulse_status`

#### `skills/analyst/SKILL.md`
- Added `proactive_analysis` task type documentation
- Added `enrich_for_newsletter` task type documentation
- Added `Budget Object` section (input format and output tracking)
- Added `Autonomous Data Requests` output format documentation

#### `skills/newsletter/SKILL.md`
- Added `Requesting Enrichment (Negotiation)` section with output format
- Added `Budget Object` section for newsletter agent

#### `skills/newsletter/package.json`
- No functional changes in this session

#### `data/openclaw/workspace/AGENTS.md` (gitignored — updated on server)
- **Fix:** `/pulse-status` → `/pulse_status`, `/crew-status` → `/crew_status`

### Identity Files Created (gitignored — local only)

#### `data/openclaw/agents/analyst/agent/IDENTITY.md`
- Full analyst identity with budget awareness, self-correction protocol, autonomous data requests, proactive analysis, and negotiation responses
- **Note:** Not needed at runtime — analyst_poller.py has system prompts embedded

#### `data/openclaw/agents/newsletter/agent/IDENTITY.md`
- Full newsletter identity with voice guidelines, negotiation request capability, budget awareness
- **Note:** Not needed at runtime — newsletter_poller.py has system prompts embedded

### New Files

#### `test_agency.sh`
- Comprehensive test script covering all 10 sections of the agency upgrade
- Tests: services running, config validation, database tables, budget system, model routing, task routing, proactive monitoring, analyst/newsletter pollers, negotiation system, smoke test commands

#### `AGENTPULSE_AGENCY_PROMPTS.md` (planning doc)
#### `AGENTPULSE_AGENCY_TESTING.md` (testing doc)
#### `AGENTPULSE_AGENCY_UPGRADE.md` (architecture doc)
#### `AGENTPULSE_PHASE3_WEEKS2_3.md` (roadmap doc)
#### `AGENTPULSE_PHASE3_WEEKS2_3_PROMPTS.md` (prompts doc)

---

## Database Tables Required

These tables must exist in Supabase (verified in testing):

| Table | Status | Purpose |
|-------|--------|---------|
| `agent_daily_usage` | New | Tracks daily LLM calls, subtasks, alerts per agent |
| `agent_negotiations` | New | Agent-to-agent negotiation records |
| `agent_tasks` | Existing | Task queue (new task types added) |
| `analysis_runs` | Existing | Analysis run history |
| `cross_signals` | Existing | Cross-pipeline signal detection |
| `opportunities` | Modified | Added `analyst_reasoning`, `signal_sources`, `last_reviewed_at`, `review_count` columns |

---

## Bugs Found and Fixed

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Telegram `BOT_COMMAND_INVALID` error | Commands with hyphens (e.g. `/pulse-status`) invalid for Telegram API | Renamed all commands to use underscores |
| Analyst can't read budget config | `docker-compose.yml` didn't mount config directory for analyst/newsletter | Added `../config:/home/openclaw/.openclaw/config:ro` volume |
| Negotiation creation fails with UUID error | Empty string `""` passed for `request_task_id` (UUID column) | Only include UUID fields in insert when non-empty |

---

## Test Results (February 17, 2026)

All 16/16 tests passed:

| Section | Result |
|---------|--------|
| 0. Services Running | 4/4 containers up |
| 1. Config Validation | All sections valid (models, budgets, negotiation) |
| 2. Database Tables | All 14 tables OK |
| 3. Budget System | AgentBudget class, tracking, daily checks working |
| 4. Model Routing | Correct model selection per task |
| 5. Task Routing | All 12 new task types registered |
| 6. Proactive Monitoring | All functions working |
| 7. Analyst Poller | Running, budget config accessible |
| 8. Newsletter Poller | Running |
| 9. Negotiation System | Create, query, pair validation all working |
| 10. Smoke Test | /budget, /alerts, /negotiations return real data |

---

## Git Commits (this session)

1. `c572b39` — Add agency upgrade: budget enforcement, self-correction, proactive monitoring, and agent negotiation
2. `9ac88f7` — Fix Telegram BOT_COMMAND_INVALID: replace hyphens with underscores in command names
3. `c5cc673` — Fix: mount config volume for analyst/newsletter, add agency test script
4. `ad386d8` — Fix test script: execute_task takes a single dict arg, not two args
5. `7f522ec` — Fix test: call init_clients() before execute_task to initialize Supabase
6. `28616b7` — Fix: skip empty UUID fields in negotiation insert/update to avoid Postgres error
