# Concerns

> Last mapped: 2026-05-26

## Critical: Processor Monolith

**File:** `docker/processor/agentpulse_processor.py` (10,079 lines)

The processor is a single file containing all scrapers, extraction pipelines, X posting, newsletter data prep, queue processing, and 30+ scheduled jobs. This creates:
- **High blast radius** — any change risks breaking unrelated pipelines
- **Untestable** — no dedicated test file exists for the 10K-line monolith
- **Memory pressure** — all pipelines loaded into one process
- **Deploy coupling** — any fix requires rebuilding the entire processor container

## High: Broad Exception Handling

Broad `except Exception:` is used pervasively:
- `code_session.py`: 13 occurrences
- `agentpulse_processor.py`: 13 occurrences
- `llm-proxy/proxy.py`: 5 occurrences
- `newsletter_poller.py`: 3 occurrences

This silently swallows errors, making debugging difficult. Failures in LLM calls, database writes, and API requests are caught and logged but never surface to callers or monitoring.

## High: No CI/CD Pipeline

No automated testing or deployment detected:
- No `.github/workflows/`, `Jenkinsfile`, or `.gitlab-ci.yml`
- No pre-commit hooks
- No linting/formatting enforcement
- Tests must be run manually: `python3 -m pytest tests/`
- Deployment is manual: `docker compose up -d --build`

## High: Test Coverage Gaps

Major untested areas:
- **Processor** (10K lines): Zero dedicated tests
- **X posting pipeline**: No tests for posting, editorial arcs, candidate surfacing
- **Scrapers**: No unit tests for RSS/HN/X/Moltbook parsing
- **Gato Brain**: 227 lines of tests for 2100+ lines of code
- **Intent Router**: No tests
- **Code Session**: No tests (1285 lines)
- **Block Pipeline**: No dedicated tests

## Medium: Security Concerns

### Secrets Management
- All secrets in a single `config/.env` file
- 26+ `os.getenv()` calls in the processor alone
- Secrets loaded at module level as global variables
- Docker socket mounted into gato_brain container (read-only, but gives container info access)

### Input Validation
- No input sanitization on Telegram command arguments
- LLM outputs parsed with `json.loads()` — no schema validation before database writes
- X posting has no content sanitization beyond length splitting

### Auth
- LLM proxy uses prefix-based API keys (`ap_<agent>_<hash>`) — key derivation is custom, not a standard auth library
- No rate limiting on Gato Brain endpoints (only LLM proxy has rate limiting)

## Medium: Configuration Coupling

- `config/agentpulse-config.json` is loaded by multiple services with different expectations
- Model routing, budget limits, pipeline intervals, and pricing all in one JSON file
- No config validation — typos or missing keys fail at runtime
- RSS feed definitions hardcoded in the processor (100+ feed URLs as Python dicts)

## Medium: Database Access Patterns

- Direct Supabase client calls everywhere — no repository/DAO layer
- No connection pooling configuration visible
- Multiple services poll the same tables on different intervals
- No database query logging or slow-query detection
- Migrations are raw SQL with no rollback strategy

## Low: Module Import Fragility

- `schemas.py` exists in 3 different service directories with different contents
- conftest.py has a 107-line workaround to handle `sys.modules` collisions
- Tests use `sys.path.insert()` to import service code — fragile path resolution
- No shared package or library between services

## Low: Legacy Documentation Bloat

- 40+ markdown files in the project root (phase plans, prompts, architecture docs)
- Many appear to be from earlier development phases and may be outdated
- No clear separation between current docs and historical artifacts
- `ARCHITECTURE.md` at root level coexists with architecture info in `CLAUDE.md`

## Low: Scheduling Fragility

- 30+ scheduled jobs in the processor, all in one `schedule` loop
- Jobs checked every 60s (or 5s in some paths) — missed windows if process restarts
- No dead-letter queue or retry for failed scheduled tasks
- No monitoring/alerting for missed schedules (except a basic health check every 30 min)
- Pipeline watchdog runs every 15 min but detection is basic

## Performance Considerations

- Processor runs all scrapers sequentially in a single thread
- Newsletter generation involves 10+ LLM calls (~135s for block pipeline)
- No caching layer between services and Supabase
- Embedding similarity search relies on pgvector — performance depends on index maintenance
- X API budget tracking queries run on every post attempt
