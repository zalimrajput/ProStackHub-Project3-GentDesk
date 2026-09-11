"""Research API endpoints.

POST   /api/research                 start a new research session
GET    /api/research/history         list past sessions
GET    /api/research/{id}            current status / snapshot
GET    /api/research/{id}/tasks      planned tasks
GET    /api/research/{id}/searches   all search records
GET    /api/research/{id}/logs       agent audit trail
GET    /api/research/{id}/evidence   collected evidence
GET    /api/research/{id}/report     final report
POST   /api/research/{id}/cancel     cancel a running session
GET    /api/research/{id}/events     SSE live progress stream
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.event_bus import bus
from app.models import (
    AgentLog,
    Evidence,
    LogStatus,
    Report,
    Research,
    ResearchStatus,
    ResearchTask,
    SearchRecord,
)
from app.orchestrator import cancellations, orchestrator
from app.schemas import (
    AgentLogOut,
    EvidenceOut,
    HistoryItem,
    ReportOut,
    ResearchCreate,
    ResearchStartResponse,
    ResearchStatusOut,
    ResearchTaskOut,
    SearchOut,
)

router = APIRouter(prefix="/api/research", tags=["research"])

_ACTIVE_STATUSES = {
    ResearchStatus.PLANNING,
    ResearchStatus.RESEARCHING,
    ResearchStatus.VERIFYING,
    ResearchStatus.SYNTHESIZING,
}


@router.post("", response_model=ResearchStartResponse, status_code=201)
async def start_research(payload: ResearchCreate, db: Session = Depends(get_db)) -> ResearchStartResponse:
    research = Research(
        goal=payload.goal.strip(),
        depth=payload.depth,
        user_id=payload.user_id,
        status=ResearchStatus.PLANNING,
        progress=0,
    )
    db.add(research)
    db.commit()
    db.refresh(research)

    bus.ensure(research.id)
    cancellations.register(research.id)
    asyncio.create_task(orchestrator.run(research.id))
    return ResearchStartResponse(research_id=research.id, status="started")


@router.get("/history", response_model=list[HistoryItem])
def history(db: Session = Depends(get_db)) -> list[HistoryItem]:
    rows = db.query(Research).order_by(desc(Research.created_at)).limit(50).all()
    return [_to_status_out(db, row) for row in rows]


@router.get("/{research_id}", response_model=ResearchStatusOut)
def get_status(research_id: str, db: Session = Depends(get_db)) -> ResearchStatusOut:
    research = _get_or_404(db, research_id)
    return _to_status_out(db, research)


@router.get("/{research_id}/tasks", response_model=list[ResearchTaskOut])
def get_tasks(research_id: str, db: Session = Depends(get_db)) -> list[ResearchTaskOut]:
    _get_or_404(db, research_id)
    rows = (
        db.query(ResearchTask)
        .filter(ResearchTask.research_id == research_id)
        .order_by(ResearchTask.order_index)
        .all()
    )
    return rows


@router.get("/{research_id}/searches", response_model=list[SearchOut])
def get_searches(research_id: str, db: Session = Depends(get_db)) -> list[SearchOut]:
    _get_or_404(db, research_id)
    rows = (
        db.query(SearchRecord)
        .filter(SearchRecord.research_id == research_id)
        .order_by(SearchRecord.created_at)
        .all()
    )
    return rows


@router.get("/{research_id}/logs", response_model=list[AgentLogOut])
def get_logs(research_id: str, db: Session = Depends(get_db)) -> list[AgentLogOut]:
    _get_or_404(db, research_id)
    rows = (
        db.query(AgentLog)
        .filter(AgentLog.research_id == research_id)
        .order_by(AgentLog.timestamp)
        .all()
    )
    return rows


@router.get("/{research_id}/evidence", response_model=list[EvidenceOut])
def get_evidence(research_id: str, db: Session = Depends(get_db)) -> list[EvidenceOut]:
    _get_or_404(db, research_id)
    rows = (
        db.query(Evidence)
        .filter(Evidence.research_id == research_id)
        .order_by(Evidence.confidence_score.desc())
        .all()
    )
    return rows


@router.get("/{research_id}/report", response_model=ReportOut)
def get_report(research_id: str, db: Session = Depends(get_db)) -> ReportOut:
    _get_or_404(db, research_id)
    report = db.query(Report).filter(Report.research_id == research_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not available yet.")
    return report


@router.post("/{research_id}/cancel")
def cancel_research(research_id: str, db: Session = Depends(get_db)) -> dict:
    research = _get_or_404(db, research_id)
    if research.status not in _ACTIVE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Research is already {research.status.lower()}.")
    cancellations.cancel(research_id)
    db.add(
        AgentLog(
            research_id=research_id,
            agent_name="Orchestrator",
            action="Cancel requested",
            output="User requested cancellation; stopping after the current step.",
            status=LogStatus.WARNING,
        )
    )
    db.commit()
    return {"research_id": research_id, "status": "cancelling"}


@router.get("/{research_id}/events")
async def events(research_id: str, request: Request) -> StreamingResponse:
    """Server-Sent Events stream of live progress for a research session."""
    queue = bus.subscribe(research_id)

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(research_id, queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- helpers -------------------------------------------------------------------

def _get_or_404(db: Session, research_id: str) -> Research:
    research = db.get(Research, research_id)
    if research is None:
        raise HTTPException(status_code=404, detail="Research session not found.")
    return research


def _to_status_out(db: Session, research: Research) -> ResearchStatusOut:
    tasks = (
        db.query(ResearchTask)
        .filter(ResearchTask.research_id == research.id)
        .all()
    )
    completed = sum(1 for t in tasks if t.status in ("COMPLETED", "FAILED"))
    return ResearchStatusOut(
        id=research.id,
        goal=research.goal,
        depth=research.depth,
        status=research.status,
        progress=research.progress,
        current_agent=research.current_agent,
        current_task=research.current_task,
        searches_count=research.searches_count,
        corrections_count=research.corrections_count,
        sources_count=research.sources_count,
        tasks_total=len(tasks),
        tasks_completed=completed,
        error=research.error,
        created_at=research.created_at,
        completed_at=research.completed_at,
    )