# Conventions

> Last mapped: 2026-05-26

## Language and Style

- **Python 3.11+** throughout (f-strings, `str | None` union syntax, `match` not used)
- **snake_case** for all functions, variables, and module names
- **UPPER_SNAKE_CASE** for constants (API keys, config values, prompt templates)
- No enforced linter/formatter — no `.flake8`, `pyproject.toml[tool.ruff]`, or `black` config detected
- No pre-commit hooks configured

## Function Design

- Functions are long — many 100-300+ line functions in the processor and newsletter modules
- Top-level functions preferred over classes (processor has zero classes; gato_brain uses FastAPI app)
- LLM proxy uses classes for domain concepts: `RateLimiter`, wallet operations
- Test files mix class-based grouping (`class TestApiKeyValidation`) and flat `def test_*()` functions

## Error Handling

- **Broad `except Exception:` throughout** — 223 except clauses in the processor alone
- Pattern: try/except around entire pipeline functions, log error, continue
- `code_session.py` is particularly aggressive — 10+ bare `except Exception:` blocks
- No custom exception hierarchy
- No structured error types returned to callers
- LLM calls use `tenacity` retry with exponential backoff in the processor

## Logging

- Standard `logging` module everywhere
- Logger names: `"agentpulse"` (processor), `"gato-brain"` (gato_brain), `"llm-proxy"` (proxy)
- Log format: plain text, no structured/JSON logging
- Heavy use of `logger.info()` for pipeline progress tracking
- `logger.error()` with `exc_info=True` for exception logging

## Configuration

- `config/.env` for secrets (loaded via `dotenv`)
- `config/agentpulse-config.json` for model routing, budgets, pipeline intervals
- Config loaded at module level (not injected) — global variables throughout
- `get_model(task_type)` resolves model from config JSON

## LLM Call Patterns

- All LLM calls route through `routed_llm_call()` in processor or via LLM proxy HTTP API
- Prompts defined as module-level string constants (e.g., `ROUTER_PROMPT`, `MULTISOURCE_EXTRACTION_PROMPT`)
- JSON output parsing: `json.loads()` with regex fallback to extract JSON from markdown fences
- Temperature and max_tokens specified per-call, not centralized

## Database Access

- Direct Supabase client calls (`supabase.table("x").select("*").execute()`)
- No ORM, no repository pattern
- Supabase client initialized at module level as global
- Migrations are raw SQL in `supabase/migrations/`
- No migration runner in code — applied via Supabase CLI or MCP tool

## Async vs Sync

- **Gato Brain**: async FastAPI with `async def` handlers
- **LLM Proxy**: async FastAPI with `httpx.AsyncClient` for upstream calls
- **Processor**: synchronous — `schedule` library + `httpx.Client` (sync)
- **Analyst/Newsletter/Research**: synchronous poll loops with `time.sleep()`

## Import Patterns

- `sys.path.insert()` used to import across service boundaries (especially in tests)
- conftest.py has elaborate module-loading workaround for `schemas.py` name collisions
- No shared library or package — each service is self-contained
- Common dependencies: `httpx`, `supabase`, `openai`, `schedule`, `tenacity`

## Message Formatting

- Telegram messages split at 4000 chars (limit is 4096)
- Markdown sent first via `parse_mode="Markdown"`, falls back to plain text on failure
- Newsletter uses HTML for email delivery via Resend
