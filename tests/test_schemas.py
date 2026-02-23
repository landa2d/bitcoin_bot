"""
T6-A: Unit tests for Pydantic schemas across all three agents.

Tests:
- Valid input round-trips
- Missing required fields raise ValidationError
- Type coercion (int from string, etc.)
- Partial LLM output via model_construct
- Default values are correct

Run with: pytest tests/test_schemas.py -v
"""
import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Load each schemas module from its specific file using importlib.
# This avoids the sys.modules["schemas"] name conflict that occurs when
# multiple agent directories are on sys.path simultaneously.
# ---------------------------------------------------------------------------

ANALYST_DIR = Path(__file__).parent.parent / "docker" / "analyst"
NEWSLETTER_DIR = Path(__file__).parent.parent / "docker" / "newsletter"
RESEARCH_DIR = Path(__file__).parent.parent / "docker" / "research"


def _load_module(unique_name: str, filepath: Path):
    spec = importlib.util.spec_from_file_location(unique_name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod  # register under unique name, not "schemas"
    spec.loader.exec_module(mod)
    return mod


_ast = _load_module("analyst_schemas", ANALYST_DIR / "schemas.py")
_nst = _load_module("newsletter_schemas", NEWSLETTER_DIR / "schemas.py")
_rst = _load_module("research_schemas", RESEARCH_DIR / "schemas.py")

# Analyst exports
AnalystOutput = _ast.AnalystOutput
BudgetUsage = _ast.BudgetUsage
DataRequest = _ast.DataRequest
EnrichForNewsletterInput = _ast.EnrichForNewsletterInput
AnalyzeOpportunitiesInput = _ast.AnalyzeOpportunitiesInput
ProactiveAnalysisInput = _ast.ProactiveAnalysisInput
TASK_INPUT_SCHEMAS = _ast.TASK_INPUT_SCHEMAS

# Newsletter exports
NewsletterBudgetUsage = _nst.BudgetUsage
GenerateNewsletterInput = _nst.GenerateNewsletterInput
NegotiationRequest = _nst.NegotiationRequest
NewsletterOutput = _nst.NewsletterOutput
NEWSLETTER_TASK_INPUT_SCHEMAS = _nst.TASK_INPUT_SCHEMAS

# Research exports
SpotlightOutput = _rst.SpotlightOutput


# ===========================================================================
# Analyst schemas
# ===========================================================================

class TestAnalystOutput:
    def test_valid_minimal(self):
        obj = AnalystOutput(executive_summary="Markets look interesting.")
        assert obj.executive_summary == "Markets look interesting."
        assert obj.key_findings == []
        assert obj.alert is False
        assert isinstance(obj.budget_usage, BudgetUsage)

    def test_valid_full(self):
        data = {
            "executive_summary": "Summary",
            "key_findings": [{"finding": "x", "significance": "high"}],
            "reasoning_steps": ["step 1", "step 2"],
            "opportunities": [{"title": "Opp A", "confidence_score": 0.8}],
            "cross_signals": [],
            "alert": True,
            "alert_message": "Something big happened",
            "negotiation_criteria_met": True,
            "negotiation_response_summary": "Criteria met.",
            "budget_usage": {"llm_calls_used": 3, "elapsed_seconds": 42.0},
        }
        obj = AnalystOutput.model_validate(data)
        assert obj.alert is True
        assert obj.budget_usage.llm_calls_used == 3

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            AnalystOutput.model_validate({})  # executive_summary is required

    def test_partial_via_model_construct(self):
        """Simulate partial LLM output using model_construct (no validation)."""
        raw = {"executive_summary": "Partial output from LLM"}
        valid_fields = {k: raw[k] for k in AnalystOutput.model_fields if k in raw}
        obj = AnalystOutput.model_construct(**valid_fields)
        assert obj.executive_summary == "Partial output from LLM"

    def test_budget_usage_defaults(self):
        usage = BudgetUsage()
        assert usage.llm_calls_used == 0
        assert usage.elapsed_seconds == 0.0
        assert usage.retries_used == 0
        assert usage.subtasks_created == 0

    def test_data_request_type_coercion(self):
        req = DataRequest(type="targeted_scrape", submolts=["agents"], posts_per=50)
        assert req.posts_per == 50


class TestAnalyzeOpportunitiesInput:
    def test_defaults(self):
        obj = AnalyzeOpportunitiesInput()
        assert obj.hours_back == 48
        assert obj.min_frequency == 2
        assert obj.top_n == 5

    def test_custom_values(self):
        obj = AnalyzeOpportunitiesInput(hours_back=72, min_frequency=3, top_n=10)
        assert obj.hours_back == 72

    def test_type_coercion_from_string(self):
        """Pydantic coerces strings to int for int fields."""
        obj = AnalyzeOpportunitiesInput(hours_back="24")  # type: ignore[arg-type]
        assert obj.hours_back == 24


class TestProactiveAnalysisInput:
    def test_valid(self):
        obj = ProactiveAnalysisInput(
            anomaly_type="frequency_spike",
            description="Mentions tripled in 1 hour",
            metrics={"multiplier": 3.2, "current": 45},
        )
        assert obj.anomaly_type == "frequency_spike"
        assert obj.metrics["multiplier"] == 3.2

    def test_missing_anomaly_type_raises(self):
        with pytest.raises(ValidationError):
            ProactiveAnalysisInput(description="Something happened")  # type: ignore[call-arg]

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            ProactiveAnalysisInput(anomaly_type="frequency_spike")  # type: ignore[call-arg]

    def test_metrics_defaults_to_empty(self):
        obj = ProactiveAnalysisInput(anomaly_type="sentiment_crash", description="Crash")
        assert obj.metrics == {}


class TestEnrichForNewsletterInput:
    def test_valid(self):
        obj = EnrichForNewsletterInput(topic="agent payments")
        assert obj.topic == "agent payments"
        assert obj.needed_by == ""

    def test_missing_topic_raises(self):
        with pytest.raises(ValidationError):
            EnrichForNewsletterInput()  # type: ignore[call-arg]


class TestTaskInputSchemas:
    def test_all_task_types_registered(self):
        expected = {"full_analysis", "analyze_opportunities", "proactive_analysis", "enrich_for_newsletter"}
        assert expected == set(TASK_INPUT_SCHEMAS.keys())

    def test_schemas_are_pydantic_models(self):
        from pydantic import BaseModel
        for schema_cls in TASK_INPUT_SCHEMAS.values():
            assert issubclass(schema_cls, BaseModel)


# ===========================================================================
# Newsletter schemas
# ===========================================================================

class TestNewsletterOutput:
    def test_valid_minimal(self):
        obj = NewsletterOutput(
            title="AgentPulse #42",
            content_markdown="## The Big Insight\n...",
            content_telegram="Short version",
        )
        assert obj.edition is None
        assert obj.negotiation_request is None

    def test_valid_with_negotiation(self):
        data = {
            "title": "Brief #5",
            "content_markdown": "content",
            "content_telegram": "short",
            "negotiation_request": {
                "target_agent": "analyst",
                "request": "Need more opportunities",
                "task_type": "enrich_for_newsletter",
            },
        }
        obj = NewsletterOutput.model_validate(data)
        assert isinstance(obj.negotiation_request, NegotiationRequest)
        assert obj.negotiation_request.target_agent == "analyst"

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError):
            NewsletterOutput(content_markdown="x", content_telegram="y")  # type: ignore[call-arg]

    def test_partial_via_model_construct(self):
        raw = {"title": "Brief #1", "content_markdown": "...", "content_telegram": "short"}
        valid_fields = {k: raw[k] for k in NewsletterOutput.model_fields if k in raw}
        obj = NewsletterOutput.model_construct(**valid_fields)
        assert obj.title == "Brief #1"

    def test_budget_usage_defaults(self):
        obj = NewsletterOutput(
            title="Test", content_markdown="x", content_telegram="y"
        )
        assert obj.budget_usage.llm_calls_used == 0


class TestNegotiationRequest:
    def test_valid(self):
        req = NegotiationRequest(
            target_agent="analyst",
            request="Need more data",
            task_type="enrich_for_newsletter",
        )
        assert req.min_quality == ""
        assert req.input_data == {}

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            NegotiationRequest(target_agent="analyst", request="x")  # type: ignore[call-arg]


# ===========================================================================
# Research schemas
# ===========================================================================

class TestSpotlightOutput:
    def test_valid(self):
        obj = SpotlightOutput(
            thesis="MCP is winning the protocol war",
            evidence="12 repos, 3 Tier-1 sources",
            counter_argument="Enterprise adoption is lagging",
            prediction="Broad adoption by Q3 2026",
            builder_implications="Build on MCP now or retrofit later",
        )
        assert obj.mode == "spotlight"
        assert obj.key_sources == []

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            SpotlightOutput(
                thesis="Thesis only",
                # evidence, counter_argument, prediction, builder_implications missing
            )

    def test_mode_literal_validation(self):
        with pytest.raises(ValidationError):
            SpotlightOutput(
                mode="invalid_mode",  # type: ignore[arg-type]
                thesis="x", evidence="x", counter_argument="x",
                prediction="x", builder_implications="x",
            )

    def test_synthesis_mode(self):
        obj = SpotlightOutput(
            mode="synthesis",
            thesis="x", evidence="x", counter_argument="x",
            prediction="x", builder_implications="x",
        )
        assert obj.mode == "synthesis"

    def test_partial_via_model_construct(self):
        raw = {
            "thesis": "The thesis",
            "evidence": "The evidence",
            "counter_argument": "Counter",
            "prediction": "Prediction",
            "builder_implications": "Implications",
        }
        valid_fields = {k: raw[k] for k in SpotlightOutput.model_fields if k in raw}
        obj = SpotlightOutput.model_construct(**valid_fields)
        assert obj.thesis == "The thesis"
