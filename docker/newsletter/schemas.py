"""Pydantic schemas for the Newsletter agent — input validation and LLM output validation."""

from pydantic import BaseModel, Field


class BudgetUsage(BaseModel):
    llm_calls_used: int = 0
    elapsed_seconds: float = 0
    retries_used: int = 0
    subtasks_created: int = 0


class NegotiationRequest(BaseModel):
    target_agent: str
    request: str
    task_type: str
    input_data: dict = {}
    min_quality: str = ""
    needed_by: str = ""


class NewsletterOutput(BaseModel):
    title: str
    content_markdown: str
    content_telegram: str
    edition: int | None = None
    primary_theme: str | None = None
    negotiation_request: NegotiationRequest | None = None
    budget_usage: BudgetUsage = Field(default_factory=BudgetUsage)
    quality_warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Input schemas per task_type
# ---------------------------------------------------------------------------

class GenerateNewsletterInput(BaseModel):
    opportunities: list[dict] = []
    edition_number: int | None = None
    enrichment_data: dict | None = None


TASK_INPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "generate_newsletter": GenerateNewsletterInput,
    "generate_newsletter_full": GenerateNewsletterInput,
    "generate_scorecard": GenerateNewsletterInput,
}
