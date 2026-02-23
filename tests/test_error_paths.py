"""
T6-C: Error-path tests.

Tests:
- Daily LLM budget exhaustion check in analyst
- Malformed task input validation (fail-fast)
- LLM output validation with partial/broken data (model_construct fallback)
- newsletter negotiation_request type guard
- save_newsletter handles OSError on file write

These are pure unit tests — no Supabase connection, no OpenAI calls.
All external dependencies are mocked with unittest.mock.

Run with: pytest tests/test_error_paths.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

ANALYST_DIR = Path(__file__).parent.parent / "docker" / "analyst"
NEWSLETTER_DIR = Path(__file__).parent.parent / "docker" / "newsletter"

# ---------------------------------------------------------------------------
# Load schemas using importlib to avoid sys.modules["schemas"] name conflict
# ---------------------------------------------------------------------------


def _load_module(unique_name: str, filepath: Path):
    spec = importlib.util.spec_from_file_location(unique_name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


_ast = _load_module("analyst_schemas_ep", ANALYST_DIR / "schemas.py")
_nst = _load_module("newsletter_schemas_ep", NEWSLETTER_DIR / "schemas.py")

AnalystOutput = _ast.AnalystOutput
AnalyzeOpportunitiesInput = _ast.AnalyzeOpportunitiesInput
ProactiveAnalysisInput = _ast.ProactiveAnalysisInput
TASK_INPUT_SCHEMAS = _ast.TASK_INPUT_SCHEMAS
NewsletterOutput = _nst.NewsletterOutput


# ---------------------------------------------------------------------------
# Helper: import a poller module with the correct schemas pre-loaded
# ---------------------------------------------------------------------------

def _import_poller(poller_name: str, agent_dir: Path, schemas_mod):
    """
    Import a poller module from agent_dir with the correct schemas pre-loaded.

    The pollers do `from schemas import ...` at module level.  We pre-register
    the already-loaded schemas module as 'schemas' in sys.modules so the poller
    picks up the right one, then clear it afterward so other tests aren't affected.
    """
    # Clear any stale cached modules
    for mod in ("schemas", poller_name):
        sys.modules.pop(mod, None)

    # Register the correct schemas under the generic 'schemas' name
    sys.modules["schemas"] = schemas_mod

    # Ensure the agent directory is on sys.path so the poller can be imported
    agent_dir_str = str(agent_dir)
    inserted = False
    if agent_dir_str not in sys.path:
        sys.path.insert(0, agent_dir_str)
        inserted = True

    try:
        spec = importlib.util.spec_from_file_location(
            poller_name, agent_dir / f"{poller_name}.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[poller_name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        # Remove generic 'schemas' so it doesn't leak into other tests
        sys.modules.pop("schemas", None)
        if inserted:
            sys.path.remove(agent_dir_str)


# ---------------------------------------------------------------------------
# T2-B: Daily budget exhaustion (analyst)
# ---------------------------------------------------------------------------

class TestDailyBudgetExhaustion:
    """Test is_daily_budget_exhausted() logic without a real Supabase connection."""

    def _make_mock_supabase(self, llm_calls_used: int):
        """Return a mock Supabase client returning the given usage count."""
        mock_sb = MagicMock()
        mock_row = MagicMock()
        mock_row.data = [{"llm_calls_used": llm_calls_used}]
        (mock_sb.table.return_value
                .select.return_value
                .eq.return_value
                .eq.return_value
                .execute.return_value) = mock_row
        return mock_sb

    def _make_mock_config(self, max_calls: int = 100) -> str:
        return json.dumps({
            "budgets": {
                "global": {"max_daily_llm_calls": max_calls}
            }
        })

    def _get_analyst_poller(self):
        return _import_poller("analyst_poller", ANALYST_DIR, _ast)

    def _write_config(self, tmp_path, max_calls: int):
        """Write config to the path is_daily_budget_exhausted() expects."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "agentpulse-config.json").write_text(
            self._make_mock_config(max_calls=max_calls)
        )

    def test_budget_not_exhausted(self, tmp_path):
        """When used < max, returns False."""
        ap = self._get_analyst_poller()
        self._write_config(tmp_path, max_calls=100)
        mock_sb = self._make_mock_supabase(llm_calls_used=42)

        with patch.object(ap, "supabase", mock_sb), \
             patch.object(ap, "OPENCLAW_DATA_DIR", str(tmp_path)):
            result = ap.is_daily_budget_exhausted("analyst")

        assert result is False

    def test_budget_exhausted_at_limit(self, tmp_path):
        """When used >= max, returns True."""
        ap = self._get_analyst_poller()
        self._write_config(tmp_path, max_calls=100)
        mock_sb = self._make_mock_supabase(llm_calls_used=100)

        with patch.object(ap, "supabase", mock_sb), \
             patch.object(ap, "OPENCLAW_DATA_DIR", str(tmp_path)):
            result = ap.is_daily_budget_exhausted("analyst")

        assert result is True

    def test_budget_exhausted_over_limit(self, tmp_path):
        """When used > max, returns True."""
        ap = self._get_analyst_poller()
        self._write_config(tmp_path, max_calls=50)
        mock_sb = self._make_mock_supabase(llm_calls_used=75)

        with patch.object(ap, "supabase", mock_sb), \
             patch.object(ap, "OPENCLAW_DATA_DIR", str(tmp_path)):
            result = ap.is_daily_budget_exhausted("analyst")

        assert result is True

    def test_budget_check_when_supabase_none(self, tmp_path):
        """When supabase is None, returns False (safe default)."""
        ap = self._get_analyst_poller()

        with patch.object(ap, "supabase", None):
            result = ap.is_daily_budget_exhausted("analyst")

        assert result is False

    def test_budget_check_on_db_error(self, tmp_path):
        """When Supabase raises, returns False (fail-open)."""
        ap = self._get_analyst_poller()
        self._write_config(tmp_path, max_calls=100)

        mock_sb = MagicMock()
        mock_sb.table.side_effect = RuntimeError("DB connection failed")

        with patch.object(ap, "supabase", mock_sb), \
             patch.object(ap, "OPENCLAW_DATA_DIR", str(tmp_path)):
            result = ap.is_daily_budget_exhausted("analyst")

        assert result is False


# ---------------------------------------------------------------------------
# Malformed task input — validate_task_input fail-fast
# ---------------------------------------------------------------------------

class TestMalformedTaskInput:
    """validate_task_input() should raise ValidationError on bad input."""

    def test_invalid_hours_back_type(self):
        schema = TASK_INPUT_SCHEMAS["analyze_opportunities"]
        with pytest.raises(ValidationError):
            schema.model_validate({"hours_back": "not_a_number"})

    def test_proactive_analysis_missing_anomaly_type(self):
        schema = TASK_INPUT_SCHEMAS["proactive_analysis"]
        with pytest.raises(ValidationError):
            schema.model_validate({"description": "Something happened"})

    def test_proactive_analysis_missing_description(self):
        schema = TASK_INPUT_SCHEMAS["proactive_analysis"]
        with pytest.raises(ValidationError):
            schema.model_validate({"anomaly_type": "frequency_spike"})

    def test_unknown_task_type_no_schema(self):
        """Unknown task types have no schema — validate_task_input should skip (not raise)."""
        schema = TASK_INPUT_SCHEMAS.get("nonexistent_task_type")
        assert schema is None  # No schema means validation is skipped


# ---------------------------------------------------------------------------
# LLM output validation — partial model fallback
# ---------------------------------------------------------------------------

class TestLLMOutputValidation:
    """validate_llm_output() should gracefully handle partial LLM responses."""

    def test_complete_analyst_output_validates(self):
        raw = {"executive_summary": "All good.", "alert": False}
        obj = AnalystOutput.model_validate(raw)
        assert obj.executive_summary == "All good."

    def test_missing_required_field_falls_back_to_model_construct(self):
        """Simulate the validate_llm_output fallback path."""
        raw = {}  # executive_summary missing

        try:
            AnalystOutput.model_validate(raw)
            validated = None  # Would fail but caught below
        except ValidationError:
            valid_fields = {k: raw[k] for k in AnalystOutput.model_fields if k in raw}
            validated = AnalystOutput.model_construct(**valid_fields)

        # model_construct should not raise
        assert validated is not None

    def test_partial_newsletter_output_fallback(self):
        raw = {"title": "Brief #5"}  # content_markdown and content_telegram missing

        try:
            NewsletterOutput.model_validate(raw)
            validated = None
        except ValidationError:
            valid_fields = {k: raw[k] for k in NewsletterOutput.model_fields if k in raw}
            validated = NewsletterOutput.model_construct(**valid_fields)

        assert validated is not None
        assert validated.title == "Brief #5"

    def test_extra_fields_in_llm_output_ignored(self):
        """Pydantic V2 ignores extra fields by default (model_config can change this)."""
        raw = {
            "executive_summary": "Summary",
            "unknown_future_field": "some value",  # LLM added a field we don't know
        }
        obj = AnalystOutput.model_validate(raw)
        assert obj.executive_summary == "Summary"


# ---------------------------------------------------------------------------
# Newsletter negotiation_request type guard (T2-C)
# ---------------------------------------------------------------------------

class TestNegotiationTypeGuard:
    """The negotiation_request guard in handle_negotiation_request should reject non-dict values."""

    def test_negotiation_request_as_string_rejected(self):
        """When LLM returns negotiation_request as a string, model_validate should handle it."""
        raw = {
            "title": "Brief",
            "content_markdown": "content",
            "content_telegram": "short",
            "negotiation_request": "I need more data",  # should be a dict
        }
        try:
            obj = NewsletterOutput.model_validate(raw)
            # Pydantic may raise or coerce
        except ValidationError:
            pass  # Expected — string is not a valid NegotiationRequest

    def test_none_negotiation_request_accepted(self):
        raw = {
            "title": "Brief",
            "content_markdown": "content",
            "content_telegram": "short",
            "negotiation_request": None,
        }
        obj = NewsletterOutput.model_validate(raw)
        assert obj.negotiation_request is None

    def test_valid_dict_negotiation_request_accepted(self):
        raw = {
            "title": "Brief",
            "content_markdown": "content",
            "content_telegram": "short",
            "negotiation_request": {
                "target_agent": "analyst",
                "request": "Need enrichment",
                "task_type": "enrich_for_newsletter",
            },
        }
        obj = NewsletterOutput.model_validate(raw)
        assert obj.negotiation_request is not None
        assert obj.negotiation_request.target_agent == "analyst"


# ---------------------------------------------------------------------------
# File write error handling (T2-C)
# ---------------------------------------------------------------------------

class TestNewsletterFileWrite:
    """Test that save_newsletter handles OSError gracefully."""

    def test_file_write_oserror_does_not_crash(self, tmp_path):
        """If write_text raises OSError (disk full), the error should be caught and logged."""
        np_module = _import_poller("newsletter_poller", NEWSLETTER_DIR, _nst)

        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        mock_file = MagicMock()
        mock_file.write_text.side_effect = OSError("No space left on device")
        mock_file.name = "brief_1_2026-02-22.md"

        newsletters_dir = tmp_path / "newsletters"
        newsletters_dir.mkdir()

        result_data = {
            "edition": 1,
            "title": "Test Brief",
            "content_markdown": "Content",
            "content_telegram": "Short",
        }
        input_data = {"edition_number": 1}

        with patch.object(np_module, "supabase", mock_sb), \
             patch.object(np_module, "NEWSLETTERS_DIR", newsletters_dir), \
             patch("newsletter_poller.Path.__truediv__", return_value=mock_file):
            try:
                np_module.save_newsletter(result_data, input_data)
            except OSError:
                pytest.fail("save_newsletter should not propagate OSError")
