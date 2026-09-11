"""Pydantic response/request schemas for the API."""

from datetime import datetime

from pydantic import BaseModel, Field


class ResearchCreate(BaseModel):
    goal: str = Field(..., min_length=3, max_length=2000, description="Natural-language research goal")
    depth: str = Field("standard", pattern="^(standard|deep)$")
    user_id: str | None = None


class ResearchStartResponse(BaseModel):
    research_id: str
    status: str


class ResearchTaskOut(BaseModel):
    id: int
    task: str
    status: str
    order_index: int
    result: str | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class SearchOut(BaseModel):
    id: int
    task_id: int | None = None
    query: str
    attempt_number: int
    result_count: int
    relevance_score: float | None = None
    status: str
    was_correction: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceOut(BaseModel):
    id: int
    claim: str
    supporting_content: str = ""
    source_title: str
    source_url: str
    source_domain: str
    source_tier: str = "medium"
    freshness: float = 0.5
    confidence_score: float
    verified: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentLogOut(BaseModel):
    id: int
    agent_name: str
    action: str
    input: str | None = None
    output: str | None = None
    status: str
    timestamp: datetime
    duration_ms: int | None = None

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    research_id: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchStatusOut(BaseModel):
    id: str
    goal: str
    depth: str
    status: str
    progress: int
    current_agent: str | None = None
    current_task: str | None = None
    searches_count: int
    corrections_count: int
    sources_count: int
    tasks_total: int
    tasks_completed: int
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class HistoryItem(BaseModel):
    id: str
    goal: str
    status: str
    depth: str
    progress: int
    searches_count: int
    corrections_count: int
    sources_count: int
    tasks_total: int
    tasks_completed: int
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}