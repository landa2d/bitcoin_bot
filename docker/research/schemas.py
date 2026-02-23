"""Pydantic schemas for the Research agent — LLM output validation."""

from typing import Literal

from pydantic import BaseModel


class SpotlightOutput(BaseModel):
    mode: Literal["spotlight", "synthesis"] = "spotlight"
    topic_name: str = ""
    topic_id: str = ""
    thesis: str
    evidence: str
    counter_argument: str
    prediction: str
    builder_implications: str
    key_sources: list[str] = []
