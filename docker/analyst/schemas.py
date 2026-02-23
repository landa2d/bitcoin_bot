"""Pydantic schemas for the Analyst agent — input validation and LLM output validation."""

from typing import Literal

from pydantic import BaseModel, Field


class BudgetUsage(BaseModel):
    llm_calls_used: int = 0
    elapsed_seconds: float = 0
    retries_used: int = 0
    subtasks_created: int = 0


class DataRequest(BaseModel):
    type: Literal["targeted_scrape"]
    submolts: list[str] = []
    posts_per: int = 50
    reason: str = ""


class AnalystOutput(BaseModel):
    executive_summary: str
    key_findings: list[dict] = []
    reasoning_steps: list[str] = []
    opportunities: list[dict] = []
    cross_signals: list[dict] = []
    data_requests: list[DataRequest] = []
    self_critique: dict = {}
    alert: bool = False
    alert_message: str = ""
    negotiation_criteria_met: bool = False
    negotiation_response_summary: str = ""
    budget_usage: BudgetUsage = Field(default_factory=BudgetUsage)


# ---------------------------------------------------------------------------
# Input schemas per task_type
# ---------------------------------------------------------------------------

class AnalyzeOpportunitiesInput(BaseModel):
    hours_back: int = 48
    min_frequency: int = 2
    top_n: int = 5


class ProactiveAnalysisInput(BaseModel):
    anomaly_type: str
    description: str
    metrics: dict = {}


class EnrichForNewsletterInput(BaseModel):
    topic: str
    needed_by: str = ""
    quality_criteria: str = ""
    negotiation_id: str | None = None


TASK_INPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "full_analysis": AnalyzeOpportunitiesInput,
    "analyze_opportunities": AnalyzeOpportunitiesInput,
    "proactive_analysis": ProactiveAnalysisInput,
    "enrich_for_newsletter": EnrichForNewsletterInput,
}
