# Structure

> Last mapped: 2026-05-26

## Directory Layout

```
bitcoin_bot/
├── config/                          # Configuration files
│   ├── .env                         # All secrets (Supabase, OpenAI, DeepSeek, X, Resend, etc.)
│   ├── agentpulse-config.json       # Model routing, budgets, pipeline intervals, pricing
│   └── persona.md                   # Bot personality/voice definition
│
├── docker/                          # All service code
│   ├── docker-compose.yml           # 8-service orchestration
│   ├── processor/
│   │   └── agentpulse_processor.py  # 10K-line monolith (scrapers, extraction, X pipeline, scheduling)
│   ├── gato_brain/
│   │   ├── gato_brain.py            # FastAPI middleware (2101 lines)
│   │   ├── intent_router.py         # 6-intent classifier
│   │   ├── corpus_probe.py          # pgvector similarity search
│   │   ├── web_search.py            # Tavily integration
│   │   ├── code_commands.py         # /code* handlers
│   │   ├── code_session.py          # Claude CLI session management
│   │   ├── cto_commands.py          # Docker status/logs
│   │   ├── query_templates.py       # Structured query templates
│   │   ├── repo_resolver.py         # Git repo resolution for code engine
│   │   └── embed_pipeline.py        # Embedding generation
│   ├── newsletter/
│   │   ├── newsletter_poller.py     # Main orchestrator (2258 lines)
│   │   ├── block_selection.py       # Phase A: block selection
│   │   ├── block_pipeline.py        # Phases B/C/E
│   │   ├── verification.py          # Phase D: claim verification
│   │   └── schemas.py               # Pydantic models
│   ├── analyst/
│   │   ├── analyst_poller.py        # Analysis pipeline (1213 lines)
│   │   └── schemas.py
│   ├── research/
│   │   ├── research_agent.py        # Deep research (999 lines)
│   │   ├── IDENTITY.md              # Research agent persona
│   │   └── schemas.py
│   ├── llm-proxy/
│   │   └── proxy.py                 # LLM gateway (1424 lines)
│   ├── gato/
│   │   ├── Dockerfile
│   │   └── inject-gato-brain.mjs    # Node.js Telegram→Brain bridge
│   ├── web/
│   │   ├── Caddyfile
│   │   └── site/app.js              # Frontend
│   └── lab-data-provider/
│       └── data_provider.py         # Lab data API
│
├── supabase/
│   └── migrations/                  # 001-029 SQL migrations
│
├── tests/                           # pytest suite (24 files, ~13K lines)
│   ├── conftest.py                  # Module loading workaround for name collisions
│   └── test_*.py                    # Phase-organized tests + integration tests
│
├── templates/                       # Newsletter/email templates
├── skills/                          # OpenClaw skill definitions
├── scripts/                         # Utility scripts
├── data/                            # Runtime data (mounted into containers)
├── edition_backups/                 # Newsletter edition backups
├── newsletters/                     # Generated newsletter archive
├── reports/                         # Generated reports
├── docs/                            # Project documentation
│
├── CLAUDE.md                        # Claude Code instructions
├── ARCHITECTURE.md                  # High-level architecture doc
├── IDENTITY.md                      # Platform identity
├── SYSTEM.md                        # System documentation
└── *.md                             # ~40+ planning/phase docs (legacy)
```

## Key Locations

| What | Where |
|------|-------|
| All service source code | `docker/<service>/` |
| Docker orchestration | `docker/docker-compose.yml` |
| Secrets / env vars | `config/.env` |
| Model routing / budgets | `config/agentpulse-config.json` |
| Database migrations | `supabase/migrations/` |
| Test suite | `tests/` |
| Newsletter templates | `templates/newsletter/` |
| Bot skills | `skills/agentpulse/` |
| Claude Code config | `.claude/settings.local.json` |

## Naming Conventions

### Files
- Python services: `<name>_poller.py` for poll-based services, `<name>.py` for others
- Each service has its own `Dockerfile`, `requirements.txt`, `entrypoint.sh`
- Shared schema definitions: `schemas.py` per service (causes import collision — handled in conftest.py)
- Migrations: `NNN_descriptive_name.sql` (zero-padded 3 digits)

### Code
- Python: snake_case functions and variables throughout
- Constants: UPPER_SNAKE_CASE
- No type annotations on most functions (processor, analyst); partial annotations in newer code (llm-proxy, newsletter)
- Config keys in JSON: snake_case

### Tests
- File naming: `test_<phase>_<topic>.py` (e.g., `test_2a_research_core.py`)
- Some use class-based grouping (`class TestApiKeyValidation`), some use flat functions
- conftest.py handles module name collisions between `schemas.py` files across services

## Where to Add New Code

- **New service**: Create `docker/<name>/` with Dockerfile, requirements.txt, entrypoint.sh, main .py file. Add to `docker-compose.yml`.
- **New pipeline/scraper**: Add to `docker/processor/agentpulse_processor.py` (the monolith)
- **New Telegram command**: Add handler in `docker/gato_brain/gato_brain.py` (for `/x-*`) or `docker/gato_brain/code_commands.py` (for `/code*`)
- **New newsletter phase**: Add to `docker/newsletter/block_pipeline.py` or create new module
- **New DB table**: Add migration in `supabase/migrations/NNN_name.sql`
- **New test**: Add `tests/test_<topic>.py`
