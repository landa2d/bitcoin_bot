# AgentPulse — System Architecture Reference

> **Last updated:** February 2026
> **Status:** Live on Hetzner. All 6 services running, all 7 migrations applied.

---

## 1. What Is This System

AgentPulse is a multi-agent intelligence pipeline that monitors the agent economy (primarily Moltbook), extracts signals and opportunities, runs research and analysis, and publishes a weekly newsletter. It wraps around Gato, an existing Bitcoin-maximalist Telegram bot built on the OpenClaw framework.

---

## 2. Services & Agents

**6 Docker services total. 4 are LLM agents. 2 are infrastructure.**

| Service | Container | Role | LLM | Model |
|---|---|---|---|---|
| `gato` | `openclaw-gato` | User-facing Telegram bot | Anthropic (via OpenClaw) | Claude (configured in auth-profiles.json) |
| `analyst` | `agentpulse-analyst` | Intelligence analyst — theses, analysis runs | OpenAI | gpt-4o |
| `newsletter` | `agentpulse-newsletter` | Weekly brief writer | OpenAI | gpt-4o |
| `research` | `agentpulse-research` | Deep-dive thesis builder | Anthropic | claude-sonnet-4-20250514 |
| `processor` | `agentpulse-processor` | Scraper + task orchestrator | — | none |
| `web` | `agentpulse-web` | Newsletter archive (Caddy + static SPA) | — | none |

All services share `agentpulse-net` (bridge network). Only `web` exposes external ports (80/443).

---

## 3. The Monday Pipeline

The primary automated pipeline runs weekly and produces the newsletter.

```
Every 6h:  Processor scrapes Moltbook → moltbook_posts + source_posts

Monday AM:
  Processor → enqueues analyse_posts task for Analyst
  Analyst   → reads posts, produces analysis_run (theses, key findings)
  Processor → selects spotlight candidate → enqueues research task
  Research  → builds conviction thesis → writes to spotlight_history
  Processor → prepares newsletter data package → enqueues write_newsletter for Newsletter
  Newsletter → calls OpenAI → saves draft to newsletters table + local .md file
  (Manual)  → operator sends /publish or /send to Gato to deliver to Telegram
```

The newsletter is saved as `status: draft` and is NOT auto-sent. An operator command via Telegram is required to publish.

---

## 4. Task System

Agents communicate through the `agent_tasks` Supabase table. Tasks are claimed atomically via `FOR UPDATE SKIP LOCKED` to prevent race conditions.

### Key RPC Functions (Migration 003)

```sql
claim_agent_task(p_assigned_to TEXT, p_limit INT)   -- used by analyst, newsletter
claim_research_task(p_limit INT)                     -- used by research agent
```

### Task Types

| Task Type | Assigned To | Created By |
|---|---|---|
| `analyse_posts` | analyst | processor |
| `enrich_for_newsletter` | analyst | newsletter (negotiation) |
| `write_newsletter` | newsletter | processor |
| `revise_newsletter` | newsletter | gato (operator) |
| `research_spotlight` | research | processor |
| `create_negotiation` | processor | newsletter |

### Budget System

Every task includes a `budget` object in `input_data` (from `config/agentpulse-config.json`). Agents track and return `budget_usage` in their output. Daily budget exhaustion is checked via `is_daily_budget_exhausted()` in `analyst_poller.py`.

### Agent Negotiations

When Newsletter needs richer data, it can request enrichment from Analyst by including a `negotiation_request` in its JSON output. The poller creates:
1. A `create_negotiation` task for Processor (to log the negotiation record)
2. An `enrich_for_newsletter` task for Analyst

Max 2 negotiations per newsletter.

---

## 5. Database Schema

**7 migrations applied.** Supabase (PostgreSQL) with RLS enabled (agents use service_role key).

### Migration Map

| Migration | Contents |
|---|---|
| 001 | `moltbook_posts`, `problems`, `problem_clusters`, `opportunities`, `tool_mentions`, `pipeline_runs` |
| 002 | `research_queue`, `spotlight_history`, `predictions` |
| 003 | `claim_agent_task()` and `claim_research_task()` RPC functions (atomic claiming) |
| 004 | `source_posts`, `agent_tasks`, `agent_daily_usage`, `analysis_runs`, `newsletters`, `topic_evolution`, `cross_signals`, `trending_topics`, `agent_negotiations` |
| 005 | Performance indexes on all major tables |
| 006 | Row Level Security (RLS) policies |
| 007 | Staleness columns on newsletter-related tables (`appearances`, `last_featured_at`, `effective_score`) |

### Core Tables Quick Reference

```
moltbook_posts       — Raw scraped Moltbook posts
source_posts         — Deduplicated posts from all sources (incl. thought leader feeds)
agent_tasks          — Task queue for analyst / newsletter / processor
agent_daily_usage    — Per-agent budget tracking
analysis_runs        — Analyst output: theses, key findings, analyst notes
spotlight_history    — Research agent's conviction theses
research_queue       — Queue for research tasks (claimed via claim_research_task)
newsletters          — Newsletter drafts and published editions
predictions          — Tracked predictions with status (active/confirmed/faded)
topic_evolution      — Topic lifecycle tracking (emerging → growing → mature → fading)
trending_topics      — Current trending topics with scores
problem_clusters     — Grouped problem signals with opportunity scores
opportunities        — Business opportunities derived from clusters
tool_mentions        — Individual tool/product mentions with sentiment
```

### Staleness / Freshness System

`prepare_newsletter_data()` in `agentpulse_processor.py` applies decay:

```python
effective_score = confidence * 0.7 ^ appearances
```

Opportunities that have appeared too many times get excluded via `freshness_rules.excluded_opportunity_ids` in the newsletter input package.

---

## 6. Key File Paths

### Python Agents

| File | Service | Purpose |
|---|---|---|
| `docker/processor/agentpulse_processor.py` | processor | Main 5500+ line orchestrator and scraper |
| `docker/analyst/analyst_poller.py` | analyst | Polls agent_tasks, calls OpenAI, produces analysis_runs |
| `docker/newsletter/newsletter_poller.py` | newsletter | Polls agent_tasks, calls OpenAI, saves newsletters |
| `docker/research/research_agent.py` | research | Polls research_queue, calls Anthropic, saves spotlight_history |

### Identity & Skills

| File | Mounted Into | Used By |
|---|---|---|
| `templates/newsletter/IDENTITY.md` | → synced to `data/openclaw/agents/newsletter/agent/IDENTITY.md` | newsletter |
| `templates/research/IDENTITY.md` | `/home/openclaw/IDENTITY.md` (direct mount) | research |
| `skills/newsletter/SKILL.md` | `/home/openclaw/.openclaw/skills/newsletter/SKILL.md` | newsletter |
| `skills/analyst/SKILL.md` | `/home/openclaw/.openclaw/skills/analyst/SKILL.md` | analyst |
| `config/persona.md` | `/home/openclaw/persona.md` | gato |

### Configuration

| File | Purpose |
|---|---|
| `config/.env` | All secrets (Supabase keys, API keys, Telegram tokens) |
| `config/agentpulse-config.json` | Budget limits, model routing, pipeline settings |
| `docker/docker-compose.yml` | Service definitions, volumes, health checks |

---

## 7. Model Routing

The `get_model(task_name)` function in `agentpulse_processor.py` reads from `config.models` in `agentpulse-config.json`. This allows per-task model overrides without redeploying.

Default models:
- Analyst: `gpt-4o` (env: `ANALYST_MODEL`)
- Newsletter: `gpt-4o` (env: `NEWSLETTER_MODEL`)
- Research: `claude-sonnet-4-20250514` (env: `RESEARCH_MODEL`)

---

## 8. Data Sources

The processor ingests from multiple sources at different tiers:

| Tier | Sources | Notes |
|---|---|---|
| Tier 1 | a16z, HBR, MIT Tech Review | High-authority, cited directly |
| Tier 1.5 | Thought leader feeds (6 configured) | GitHub, personal blogs of key figures |
| Tier 2 | TLDR AI, Ben's Bites, and similar | Aggregators, mentioned naturally |
| Tier 3 | Moltbook, Hacker News | Community signal, not cited as authorities |

Deduplication runs on `source_posts` to prevent the same story from appearing twice across sources.

---

## 9. Newsletter Flow Detail

```
processor.prepare_newsletter_data()
  ├── Queries: opportunities (with staleness decay)
  ├── Queries: emerging signals, curious topics, radar_topics
  ├── Queries: trending tools, tool warnings
  ├── Queries: spotlight_history (latest Research output)
  ├── Queries: predictions (active/confirmed/faded)
  ├── Queries: topic_evolution
  ├── Queries: analyst_insights (latest analysis_run)
  └── Applies freshness_rules (exclusions, returning item limits)

→ Enqueues write_newsletter task for newsletter agent

newsletter_poller.process_task()
  ├── Loads IDENTITY.md + SKILL.md from disk (mtime-cached)
  ├── Builds system prompt = IDENTITY + SKILL + CRITICAL RULES
  ├── Calls OpenAI gpt-4o (max_tokens=16000, response_format=json_object)
  ├── Validates output via NewsletterOutput Pydantic schema
  ├── Optionally appends Looking Back blurbs (generate_scorecard)
  ├── Saves to newsletters table (status=draft)
  ├── Saves .md file to workspace/agentpulse/newsletters/
  └── Handles any negotiation_request (enrichment from Analyst)
```

**To publish:** Send `/publish` or `/send` to Gato via Telegram.

---

## 10. Health Checks & Dependencies

All Python services use `pgrep -f <script_name>` for health checks. Gato uses `pgrep -f node`.

Startup order (enforced via `depends_on: condition: service_healthy`):
```
processor (must be healthy first)
  ↳ analyst
  ↳ newsletter
  ↳ research
gato (no dependency on processor, starts independently)
web (no dependencies)
```

---

## 11. Deployment

**Host:** Hetzner VPS
**Deploy:** `git pull && docker compose -f docker/docker-compose.yml up -d --build <service>`
**Restart single service:** `docker compose -f docker/docker-compose.yml restart <service>`

The `data/` directory is gitignored and lives only on the server. The `skills/` and `templates/` directories are git-tracked and contain the agent identity and skill files that get mounted read-only into containers (skills) or synced manually (newsletter IDENTITY.md → data/).

### After changing IDENTITY.md locally:
```bash
# Sync template to data/ then restart
cp templates/newsletter/IDENTITY.md data/openclaw/agents/newsletter/agent/IDENTITY.md
docker compose -f docker/docker-compose.yml restart newsletter
```

### After changing SKILL.md or newsletter_poller.py:
```bash
git push
# On server:
git pull && docker compose -f docker/docker-compose.yml restart newsletter
```

---

## 12. Tests

```bash
pytest tests/ -v    # from project root
```

| Test File | Coverage |
|---|---|
| `tests/test_schemas.py` | Pydantic schema validation |
| `tests/test_migrations.py` | Migration SQL correctness |
| `tests/test_error_paths.py` | Error handling paths |

`tests/conftest.py` pre-imports pollers at startup to avoid `sys.modules["schemas"]` conflicts.

---

## 13. Existing Architecture Docs (Historical)

Two older planning documents exist in the project root — they document design decisions from earlier phases and are useful as historical context but do not reflect the current system:

- `AGENTPULSE_ARCHITECTURE.md` — Phase 1 MVP planning (single-service, file-queue based)
- `AGENTPULSE_PHASE2_ARCHITECTURE (1).md` — Phase 2 planning (clustering, investment scanner, newsletter as 4th service)

This document (`ARCHITECTURE.md`) is the authoritative current reference.
