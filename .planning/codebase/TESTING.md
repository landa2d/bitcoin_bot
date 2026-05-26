# Testing

> Last mapped: 2026-05-26

## Framework

- **pytest** — standard test runner
- **pytest-asyncio** — for async test functions (LLM proxy tests)
- No CI/CD pipeline detected (no `.github/workflows/`, no `Jenkinsfile`, no `.gitlab-ci.yml`)
- Run: `python3 -m pytest tests/` or `python3 -m pytest tests/test_<file>.py -v`

## Test Organization

24 test files, ~12,944 lines total in `tests/`:

| File | Lines | Focus |
|------|-------|-------|
| `conftest.py` | 107 | Module loading, path setup |
| `test_1a_source_ingestion.py` | 251 | RSS/scraper ingestion |
| `test_1b_schema.py` | 340 | Database schema validation |
| `test_1c_research_prompt.py` | 396 | Research prompt quality |
| `test_1d_radar_section.py` | 383 | Radar section generation |
| `test_2a_research_core.py` | 714 | Research agent core logic |
| `test_2b_selection_heuristic.py` | 700 | Content selection scoring |
| `test_2c_handoff_wiring.py` | 575 | Inter-service handoff |
| `test_2d_quality.py` | 662 | Output quality checks |
| `test_2d_research_iteration.py` | 870 | Research iteration loops |
| `test_3a_spotlight_template.py` | 623 | Spotlight template rendering |
| `test_3b_e2e_pipeline.py` | 781 | End-to-end newsletter pipeline |
| `test_3c_newsletters.py` | 618 | Newsletter generation variants |
| `test_4b_prediction_monitoring.py` | 561 | Prediction tracking |
| `test_4c_scorecard.py` | 610 | Scorecard generation |
| `test_error_paths.py` | 352 | Error handling edge cases |
| `test_gato_brain_e2e.py` | 227 | Gato Brain API tests |
| `test_integration_phase1.py` | 413 | Phase 1 integration |
| `test_llm_proxy.py` | 840 | LLM proxy unit + integration |
| `test_migrations.py` | 213 | Migration validation |
| `test_newsletter_quality.py` | 1412 | Newsletter quality review (uses real APIs) |
| `test_phase2_integration.py` | 514 | Phase 2 integration |
| `test_prediction_extraction.py` | 495 | Prediction extraction |
| `test_schemas.py` | 287 | Schema validation |

## Test Patterns

### Module Loading
The conftest.py handles a critical challenge: multiple services have `schemas.py` files. It pre-loads each poller module with the correct schemas registered in `sys.modules` to prevent import collisions.

```python
# conftest.py pattern:
_load_module("newsletter_schemas", _DOCKER / "newsletter" / "schemas.py")
_preload_poller("newsletter_poller.py", _DOCKER / "newsletter", newsletter_schemas)
```

### Test Structure
- **Class-based grouping** in newer tests (LLM proxy):
  ```python
  class TestApiKeyValidation:
      @pytest.mark.asyncio
      async def test_missing_api_key_returns_401(self, client):
  ```
- **Flat functions** in older tests:
  ```python
  def test_delivery():
  def test_resilience_no_spotlight():
  ```

### Mocking
- `unittest.mock.patch` and `unittest.mock.MagicMock` for sync code
- `unittest.mock.AsyncMock` for async code (LLM proxy)
- Fixtures for common mocks: `mock_auth_internal`, `mock_reserve_ok`, `mock_settle`
- No shared mock factories or fixture libraries

### Integration vs Unit
- LLM proxy has explicit separation: `--run-integration` flag for real API tests
- Most other test files use real Supabase/OpenAI calls (not purely unit tests)
- `test_newsletter_quality.py` is a quality review script (runs real newsletter generation)

## Coverage

### Well-Covered
- LLM proxy: auth, rate limiting, wallet reserve/settle, streaming
- Newsletter pipeline: template rendering, quality checks, e2e flow
- Research agent: core logic, selection heuristics, handoff wiring
- Prediction system: extraction, monitoring, scorecard

### Gaps
- Processor monolith (10K lines) has no dedicated test file
- X posting pipeline: no tests for `post_approved_x_content()` or editorial arc
- Scraper functions: no unit tests for RSS/HN/X parsing
- Gato Brain: only 227 lines of e2e tests for 2100+ lines of code
- Intent router: no dedicated tests
- Code session management: no tests
- Block pipeline (newsletter): no dedicated tests (covered indirectly by quality tests)

## Running Tests

```bash
# All tests
python3 -m pytest tests/

# Single file
python3 -m pytest tests/test_llm_proxy.py -v

# With integration tests
python3 -m pytest tests/test_llm_proxy.py -v --run-integration

# Syntax check before rebuild
python3 -c "import ast; ast.parse(open('docker/processor/agentpulse_processor.py').read())"
```
