"""Database models for the full research lifecycle.

Mirrors the GentDesk schema: researches, tasks, searches, evidence,
agent logs, and reports.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_research_id() -> str:
    return f"res_{uuid.uuid4().hex[:10]}"


def utcnow() -> datetime:
    return datetime.utcnow()


# --- Status constants ---------------------------------------------------------

class ResearchStatus:
    PLANNING = "PLANNING"
    RESEARCHING = "RESEARCHING"
    VERIFYING = "VERIFYING"
    SYNTHESIZING = "SYNTHESIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus:
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SearchStatus:
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


class LogStatus:
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Research(Base):
    __tablename__ = "researches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_research_id)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    goal: Mapped[str] = mapped_column(Text)
    depth: Mapped[str] = mapped_column(String(16), default="standard")
    status: Mapped[str] = mapped_column(String(16), default=ResearchStatus.PLANNING, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_agent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_task: Mapped[str | None] = mapped_column(Text, nullable=True)
    searches_count: Mapped[int] = mapped_column(Integer, default=0)
    corrections_count: Mapped[int] = mapped_column(Integer, default=0)
    sources_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tasks: Mapped[list["ResearchTask"]] = relationship(
        back_populates="research", cascade="all, delete-orphan", order_by="ResearchTask.order_index"
    )
    searches: Mapped[list["SearchRecord"]] = relationship(
        back_populates="research", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="research", cascade="all, delete-orphan"
    )
    logs: Mapped[list["AgentLog"]] = relationship(
        back_populates="research", cascade="all, delete-orphan", order_by="AgentLog.timestamp"
    )
    report: Mapped["Report | None"] = relationship(
        back_populates="research", cascade="all, delete-orphan", uselist=False
    )


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_id: Mapped[str] = mapped_column(ForeignKey("researches.id"), index=True)
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.PENDING)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    research: Mapped["Research"] = relationship(back_populates="tasks")


class SearchRecord(Base):
    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_id: Mapped[str] = mapped_column(ForeignKey("researches.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("research_tasks.id"), nullable=True)
    query: Mapped[str] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=SearchStatus.COMPLETED)
    was_correction: Mapped[bool] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    research: Mapped["Research"] = relationship(back_populates="searches")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_id: Mapped[str] = mapped_column(ForeignKey("researches.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("research_tasks.id"), nullable=True)
    claim: Mapped[str] = mapped_column(Text)
    # Raw supporting passage from the source the claim was extracted from.
    supporting_content: Mapped[str] = mapped_column(Text, default="")
    source_title: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_domain: Mapped[str] = mapped_column(String(255), default="")
    # Source authority tier: official | high | medium | low.
    source_tier: Mapped[str] = mapped_column(String(16), default="medium")
    # Estimated freshness 0-1 based on dates found in title/snippet.
    freshness: Mapped[float] = mapped_column(Float, default=0.5)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    verified: Mapped[bool] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    research: Mapped["Research"] = relationship(back_populates="evidence")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_id: Mapped[str] = mapped_column(ForeignKey("researches.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=LogStatus.OK)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    research: Mapped["Research"] = relationship(back_populates="logs")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_id: Mapped[str] = mapped_column(ForeignKey("researches.id"), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    research: Mapped["Research"] = relationship(back_populates="report")