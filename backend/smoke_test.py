"""End-to-end smoke test for GentDesk.

Uses a fresh SQLite database and the configured backends (real or mock) to
exercise the full planner → research → evaluate → correct → synthesis loop.

When the env has real keys, this still talks to the real LLM/search providers;
when keys are absent it falls back to the deterministic mocks.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use a throwaway DB so this test never clobbers production state.
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(os.path.dirname(__file__), "smoke_test.db"))

from app.config import settings
from app.database import init_db, SessionLocal
from app.event_bus import bus
from app.llm import LLMClient
from app.models import Research, ResearchStatus
from app.orchestrator import Orchestrator, cancellations
from app.search import SearchTool


def _new_research_id() -> str:
    return f"smoke_{uuid.uuid4().hex[:10]}"


async def run() -> None:
    init_db()

    # Deterministic, repeatable demo goal for smoke testing.
    goal = (
        "Compare the top 3 competitors of Zoom and compare their pricing and major features for 2026."
    )

    research_id = _new_research_id()
    with SessionLocal() as session:
        research = Research(
            id=research_id,
            goal=goal,
            depth="standard",
            status=ResearchStatus.PLANNING,
            progress=0,
        )
        session.add(research)
        session.commit()

    bus.ensure(research_id)
    cancellations.register(research_id)

    orchestrator = Orchestrator(llm=LLMClient(), search=SearchTool())
    try:
        await orchestrator.run(research_id)
    finally:
        cancellations.clear(research_id)

    with SessionLocal() as session:
        research = session.get(Research, research_id)
        tasks = session.query(Research.tasks).all() if hasattr(Research, "tasks") else []
        searches = session.query(Research.searches).all() if hasattr(Research, "searches") else []
        evidence = session.query(Research.evidence).all() if hasattr(Research, "evidence") else []
        logs = session.query(Research.logs).all() if hasattr(Research, "logs") else []
        report = session.query(Research.report).first() if hasattr(Research, "report") else None

    print(f"research_id      = {research_id}")
    print(f"status           = {research.status if research else 'missing'}")
    print(f"progress         = {research.progress if research else 'missing'}")
    print(f"searches_count   = {research.searches_count if research else 'missing'}")
    print(f"corrections_count= {research.corrections_count if research else 'missing'}")
    print(f"sources_count    = {research.sources_count if research else 'missing'}")
    print(f"tasks_total      = {len(tasks)}")
    print(f"tasks_completed  = {sum(1 for t in tasks if t.status in ('COMPLETED', 'FAILED'))}")
    print(f"searches         = {len(searches)}")
    print(f"corrections(searches with was_correction=1) = {sum(1 for s in searches if s.was_correction)}")
    print(f"evidence         = {len(evidence)}")
    print(f"top evidence domains = {[e.source_domain for e in evidence][:6]}")
    print(f"logs             = {len(logs)}")
    print(f"log agents       = {[l.agent_name for l in logs]}")
    print(f"report_present   = {report is not None}")
    print(f"report_chars     = {len(report.content) if report else 0}")

    if searches:
        top = searches[0]
        print(f"first_search     = {top.query!r} (attempt {top.attempt_number}, results {top.result_count}, score {top.relevance_score}, status {top.status})")

    if searches and any(s.was_correction for s in searches):
        corrected = [s for s in searches if s.was_correction]
        print("correction chain:")
        for s in corrected:
            print(f"  attempt {s.attempt_number}: {s.query!r} (score {s.relevance_score}, status {s.status})")

    print()
    print("---- Agent log audit trail ----")
    if logs:
        for log in logs:
            print(f"[{log.agent_name}] {log.action}")
            if log.input:
                print(f"    input : {log.input}")
            if log.output:
                print(f"    output: {log.output}")
    else:
        print("no agent logs recorded")


if __name__ == "__main__":
    asyncio.run(run())
