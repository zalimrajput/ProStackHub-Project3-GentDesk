"""Agent Orchestrator — the central controller.

Coordinates the five agents, decides what runs next, enforces execution
limits (retries, tasks, searches, evidence), streams progress events,
and writes the complete audit trail.

Workflow: plan → research tasks (search → evaluate → correct → retry)
→ coverage check (gap-driven second research pass) → synthesize → report
→ complete.

Verification is intentionally folded into the Evaluator behavior, so only
five agents remain visible in the audit trail:
Planner, Research, Evaluator, Correction, Synthesis.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime

from app.agents.correction import CorrectionAgent
from app.agents.evaluator import EvaluatorAgent
from app.agents.planner import PlannerAgent
from app.agents.research import ResearchAgent
from app.agents.synthesis import SynthesisAgent
from app.authority import authority_tier, freshness_from_text
from app.config import settings
from app.database import SessionLocal
from app.event_bus import bus
from app.llm import LLMClient, LLMError
from app.models import (
    AgentLog,
    Evidence,
    LogStatus,
    Report,
    Research,
    ResearchStatus,
    ResearchTask,
    SearchRecord,
    SearchStatus,
    TaskStatus,
)
from app.schemas import AgentLogOut, EvidenceOut, ResearchTaskOut, SearchOut
from app.search import SearchTool, looks_like_pricing_claim
from app.types import Evaluation, SearchResult


class ResearchCancelled(Exception):
    pass


@dataclass
class CancellationManager:
    _events: dict[str, asyncio.Event] = field(default_factory=dict)

    def register(self, research_id: str) -> None:
        self._events.setdefault(research_id, asyncio.Event())

    def cancel(self, research_id: str) -> None:
        event = self._events.get(research_id)
        if event is not None:
            event.set()

    def is_cancelled(self, research_id: str) -> bool:
        event = self._events.get(research_id)
        return bool(event and event.is_set())

    def clear(self, research_id: str) -> None:
        self._events.pop(research_id, None)


cancellations = CancellationManager()


class Orchestrator:
    def __init__(self, llm: LLMClient | None = None, search: SearchTool | None = None) -> None:
        self.llm = llm or LLMClient()
        self.search = search or SearchTool()
        self.planner = PlannerAgent(self.llm)
        self.research_agent = ResearchAgent(self.llm, self.search)
        self.evaluator = EvaluatorAgent(self.llm)
        self.correction = CorrectionAgent(self.llm)
        self.synthesis = SynthesisAgent(self.llm)
        self._running: set[str] = set()

    # ------------------------------------------------------------------ public

    async def run(self, research_id: str) -> None:
        """Run the full research lifecycle for a session (called as a task)."""
        if research_id in self._running:
            return
        self._running.add(research_id)
        try:
            await self._run_phases(research_id)
        except ResearchCancelled:
            await self._finalize(research_id, ResearchStatus.CANCELLED)
        except Exception as exc:  # noqa: BLE001 - orchestrator must never die silently
            await self._fail(research_id, exc)
        finally:
            self._running.discard(research_id)
            cancellations.clear(research_id)

    # ------------------------------------------------------------------- phases

    async def _run_phases(self, research_id: str) -> None:
        research = self._get_research(research_id)
        if research is None:
            return
        depth = research.depth

        # ---- Phase 1: Planning -------------------------------------------------
        await self._set_state(
            research_id,
            status=ResearchStatus.PLANNING,
            progress=2,
            current_agent="planner",
            current_task="Analyzing goal and creating research plan",
        )
        tasks = await self._plan(research_id)

        # ---- Phase 2: Research tasks -------------------------------------------
        await self._set_state(
            research_id,
            status=ResearchStatus.RESEARCHING,
            progress=10,
            current_agent="research",
            current_task="Researching tasks",
        )
        await self._research_tasks(research_id, tasks, depth)

        # ---- Phase 2b: Coverage check + gap-driven second pass -----------------
        if depth == "deep" or settings.gap_research_enabled:
            await self._coverage_pass(research_id)

        # ---- Phase 3: Synthesis ------------------------------------------------
        await self._synthesize(research_id)

        await self._finalize(research_id, ResearchStatus.COMPLETED)

    async def _plan(self, research_id: str) -> list[str]:
        self._check_cancelled(research_id)
        research = self._get_research(research_id)
        assert research is not None
        started = _now_ms()
        tasks: list[str] | None = None
        last_exc: Exception | None = None
        for plan_attempt in range(3):
            try:
                tasks = await self.planner.plan(research.goal)
                break
            except LLMError as exc:
                last_exc = exc
                if plan_attempt < 2:
                    await asyncio.sleep(2 ** plan_attempt + 1)
        if not tasks:
            raise RuntimeError(f"Planner Agent failed to produce a research plan: {last_exc}")

        with SessionLocal() as session:
            for index, task in enumerate(tasks):
                session.add(
                    ResearchTask(
                        research_id=research_id,
                        task=task,
                        status=TaskStatus.PENDING,
                        order_index=index,
                    )
                )
            session.commit()

        await self._log(
            research_id,
            agent_name="Planner Agent",
            action="Research plan created",
            input=research.goal,
            output=json.dumps(tasks, ensure_ascii=False),
            duration_ms=_now_ms() - started,
        )
        await self._publish(research_id, "plan_created", {"tasks": tasks})
        await self._publish(research_id, "tasks_updated", {"tasks_total": len(tasks), "tasks_completed": 0})
        return tasks

    async def _research_tasks(self, research_id: str, tasks: list[str], depth: str, phase_label: str = "Researching tasks") -> None:
        total = len(tasks)
        deep = depth == "deep"
        max_retries = settings.max_retries + (1 if deep else 0)
        searches_left = settings.max_total_searches

        # Evidence/query dedupe across tasks and retry passes.
        seen_urls: set[str] = set()
        used_queries: set[str] = set()

        for index, task_text in enumerate(tasks):
            self._check_cancelled(research_id)
            progress = 10 + int(60 * index / max(total, 1))
            await self._set_state(
                research_id,
                status=ResearchStatus.RESEARCHING,
                progress=progress,
                current_agent="research",
                current_task=task_text,
            )

            task_row = self._mark_task_in_progress(research_id, task_text)
            if task_row is None:
                continue
            await self._publish_task(research_id, task_row)

            # HARD CAP: max_attempts search→evaluate→correct cycles per task,
            # regardless of how many queries the Research Agent generated.
            max_attempts = settings.max_attempts_per_task
            queries = await self._generate_queries_safe(research_id, task_text)
            task_completed = False
            attempt = 0
            task_evidence_count = 0
            current_query = queries[0] if queries else task_text

            while attempt < max_attempts:
                if searches_left <= 0:
                    await self._log(
                        research_id,
                        agent_name="Orchestrator",
                        action="Search budget exhausted",
                        input=task_text,
                        output=f"Stopped after {settings.max_total_searches} total searches.",
                        status=LogStatus.WARNING,
                    )
                    break

                self._check_cancelled(research_id)
                attempt += 1

                # ---- Step 1: RESEARCH --------------------------------------
                if current_query.strip().lower() in used_queries:
                    await self._log(
                        research_id,
                        agent_name="Orchestrator",
                        action="Skipped duplicate query",
                        input=current_query,
                        status=LogStatus.WARNING,
                    )
                    current_query = f"{current_query} {attempt}"  # force uniqueness
                used_queries.add(current_query.strip().lower())
                searches_left -= 1

                await self._set_state(
                    research_id,
                    current_agent="research",
                    current_task=f"[attempt {attempt}/{max_attempts}] {task_text}",
                )
                await self._publish(research_id, "search_started", {"task": task_text, "query": current_query, "attempt": attempt, "max_attempts": max_attempts})

                results = []
                try:
                    results = await self.research_agent.search(current_query)
                except Exception as exc:  # noqa: BLE001
                    self._record_search(
                        research_id, task_row.id, current_query, attempt, 0, None, SearchStatus.FAILED, attempt > 1
                    )
                    await self._publish_counts(research_id)
                    await self._log(
                        research_id,
                        agent_name="Research Agent",
                        action="Search failed",
                        input=current_query,
                        output=str(exc),
                        status=LogStatus.ERROR,
                    )
                    break

                search_row = self._record_search(
                    research_id, task_row.id, current_query, attempt, len(results), None, SearchStatus.COMPLETED, attempt > 1
                )
                # Research Agent step must be visible in the Activity feed and
                # audit trail — previously only evaluations/corrections were
                # logged, so the feed looked like Evaluator → Correction loops
                # with an invisible Research step.
                await self._log(
                    research_id,
                    agent_name="Research Agent",
                    action=f"Search executed (attempt {attempt}/{max_attempts})",
                    input=current_query,
                    output=f"{len(results)} result(s)"
                    + (
                        f"; top: {results[0].title[:100]} ({results[0].domain})"
                        if results
                        else "; no results"
                    ),
                    status=LogStatus.OK if results else LogStatus.WARNING,
                )
                await self._publish(
                    research_id,
                    "search_completed",
                    {
                        "task": task_text,
                        "query": current_query,
                        "result_count": len(results),
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "top_results": [
                            {"title": r.title, "url": r.url, "domain": r.domain, "snippet": r.snippet[:220]}
                            for r in results[:5]
                        ],
                    },
                )
                await self._publish_counts(research_id)

                # ---- Step 2: EVALUATOR -------------------------------------
                await self._set_state(
                    research_id,
                    current_agent="evaluator",
                    current_task=f"[attempt {attempt}/{max_attempts}] Evaluating results for: {task_text[:80]}",
                )
                evaluation = await self._evaluate_safe(research_id, task_text, current_query, results)
                self._update_search_score(search_row.id, evaluation.score, evaluation.status)
                await self._publish(
                    research_id,
                    "results_evaluated",
                    {
                        "query": current_query,
                        "score": evaluation.score,
                        "status": evaluation.status,
                        "reason": evaluation.reason,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                    },
                )
                # Full audit-trail entry for every evaluation decision.
                await self._log(
                    research_id,
                    agent_name="Evaluator Agent",
                    action=f"Evaluation {evaluation.status}",
                    input=f"task: {task_text}\nquery: {current_query}",
                    output=(
                        f"score={evaluation.score:.2f} status={evaluation.status}\n"
                        f"reason: {evaluation.reason}"
                        + (f"\nmissing: {evaluation.missing}" if evaluation.missing else "")
                    ),
                    status=LogStatus.OK if evaluation.status == "ACCEPTED" else LogStatus.WARNING,
                )

                if evaluation.status == "ACCEPTED":
                    accepted_count = 0
                    for item in evaluation.evidence:
                        if len(seen_urls) >= settings.max_evidence:
                            break
                        url_key = _norm_url(item.source_url)
                        if url_key in seen_urls:
                            continue
                        seen_urls.add(url_key)
                        evidence_row = self._save_evidence(research_id, task_row.id, item)
                        await self._publish(
                            research_id, "evidence_collected", {"evidence": _evidence_out(evidence_row)}
                        )
                        accepted_count += 1
                    await self._publish_counts(research_id)
                    if accepted_count > 0:
                        row = self._complete_task(
                            research_id,
                            task_row.id,
                            f"Completed on attempt {attempt}/{max_attempts} with {accepted_count} grounded evidence item(s).",
                        )
                        await self._publish_task(research_id, row)
                        task_completed = True
                        break
                    # All evidence was duplicate → treat as rejection and correct.
                    evaluation = Evaluation(
                        score=evaluation.score,
                        status="REJECTED",
                        reason="All extracted evidence duplicated previously collected sources.",
                    )

                # ---- Rejected ----------------------------------------------
                # Bank whatever real facts WERE grounded in the rejected
                # results (e.g. an official pricing page among mixed results)
                # instead of discarding everything. Only on-topic rejections
                # (score >= 0.3) with non-UGC sources qualify.
                if evaluation.evidence and evaluation.score >= 0.3:
                    banked = 0
                    for item in evaluation.evidence:
                        if len(seen_urls) >= settings.max_evidence:
                            break
                        url_key = _norm_url(item.source_url)
                        if url_key in seen_urls or item.source_tier == "low":
                            continue
                        seen_urls.add(url_key)
                        evidence_row = self._save_evidence(research_id, task_row.id, item)
                        await self._publish(
                            research_id, "evidence_collected", {"evidence": _evidence_out(evidence_row)}
                        )
                        banked += 1
                    if banked:
                        task_evidence_count += banked
                        await self._log(
                            research_id,
                            agent_name="Evaluator Agent",
                            action=f"Partial evidence banked ({banked} item(s))",
                            input=current_query,
                            output=(
                                f"Results rejected overall (score={evaluation.score:.2f}) but {banked} grounded "
                                "fact(s) from authoritative sources were retained."
                            ),
                            status=LogStatus.WARNING,
                        )
                        await self._publish_counts(research_id)

                        # Enough grounded facts collected across attempts →
                        # complete the task instead of burning the remaining
                        # retry budget on the same broad question.
                        if task_evidence_count >= 2:
                            row = self._complete_task(
                                research_id,
                                task_row.id,
                                f"Completed with {task_evidence_count} grounded evidence item(s) across {attempt} attempt(s); some requested facts may remain unverified.",
                            )
                            await self._publish_task(research_id, row)
                            task_completed = True
                            break

                if attempt >= max_attempts:
                    break  # hard cap reached → stop researching this task

                # ---- Step 3: CORRECTION ------------------------------------
                await self._set_state(
                    research_id,
                    current_agent="correction",
                    current_task=f"[attempt {attempt}/{max_attempts}] Refining query for: {task_text[:80]}",
                )
                await self._publish(research_id, "correction_started", {"query": current_query, "reason": evaluation.reason, "attempt": attempt, "max_attempts": max_attempts})
                refined = await self._refine_safe(research_id, current_query, evaluation, task_text, attempt)
                self._increment_corrections(research_id)
                await self._log(
                    research_id,
                    agent_name="Correction Agent",
                    action="Query refinement",
                    input=f"{current_query} (reason: {evaluation.reason[:150]})",
                    output=refined,
                    status=LogStatus.WARNING,
                )
                await self._publish(research_id, "correction_completed", {"from": current_query, "to": refined, "attempt": attempt, "max_attempts": max_attempts})
                await self._publish_counts(research_id)
                current_query = refined

            if not task_completed:
                if task_evidence_count > 0:
                    # Partial evidence was banked across attempts — the task
                    # contributed real facts even though some questions remain
                    # open. Mark completed rather than insufficient.
                    row = self._complete_task(
                        research_id,
                        task_row.id,
                        f"Completed with {task_evidence_count} partially-relevant evidence item(s) after {attempt} attempt(s); some requested facts remain unverified.",
                    )
                    await self._publish_task(research_id, row)
                    await self._log(
                        research_id,
                        agent_name="Orchestrator",
                        action=f"Task finished after {attempt}/{max_attempts} attempts with partial evidence",
                        input=task_text,
                        output=f"{task_evidence_count} evidence item(s) retained; unresolved facts flagged for the report.",
                        status=LogStatus.WARNING,
                    )
                    continue
                stop_reason = (
                    f"Insufficient relevant evidence found after {attempt} search attempt(s). "
                    "The task was stopped and marked as insufficient evidence."
                    if attempt >= max_attempts
                    else f"Insufficient relevant evidence found after {attempt} search attempt(s) (stopped early). "
                    "The task was stopped and marked as insufficient evidence."
                )
                row = self._fail_task(research_id, task_row.id, stop_reason)
                await self._publish_task(research_id, row)
                await self._log(
                    research_id,
                    agent_name="Orchestrator",
                    action=f"Task stopped after {attempt}/{max_attempts} attempts — insufficient evidence",
                    input=task_text,
                    output=stop_reason,
                    status=LogStatus.WARNING,
                )
                await self._publish(
                    research_id,
                    "task_insufficient",
                    {"task": task_text, "attempts": attempt, "max_attempts": max_attempts, "reason": stop_reason},
                )

    async def _coverage_pass(self, research_id: str) -> None:
        """Detect uncovered goal aspects and run targeted follow-up tasks."""
        self._check_cancelled(research_id)
        with SessionLocal() as session:
            research = session.get(Research, research_id)
            tasks = (
                session.query(ResearchTask)
                .filter(ResearchTask.research_id == research_id)
                .order_by(ResearchTask.order_index)
                .all()
            )
            evidence_rows = session.query(Evidence).filter(Evidence.research_id == research_id).all()
            goal = research.goal if research else ""
            task_texts = [t.task for t in tasks]
            evidence_items = [_evidence_item(row) for row in evidence_rows]

        await self._set_state(
            research_id,
            status=ResearchStatus.RESEARCHING,
            current_agent="synthesis",
            current_task="Checking evidence coverage of the goal",
        )
        gap_tasks = await self.synthesis.find_gaps(goal, task_texts, evidence_items)
        await self._log(
            research_id,
            agent_name="Synthesis Agent",
            action="Coverage check",
            input=f"{len(evidence_items)} evidence items",
            output=(f"gaps found: {len(gap_tasks)}\n" + "\n".join(gap_tasks)) if gap_tasks else "coverage sufficient",
            status=LogStatus.WARNING if gap_tasks else LogStatus.OK,
        )
        if not gap_tasks:
            return

        self._check_cancelled(research_id)
        await self._log(
            research_id,
            agent_name="Orchestrator",
            action="Second research pass started (gap-driven)",
            output=json.dumps(gap_tasks, ensure_ascii=False),
        )
        await self._research_tasks(research_id, gap_tasks[:3], "standard", phase_label="Second pass")

    async def _synthesize(self, research_id: str) -> None:
        self._check_cancelled(research_id)
        await self._set_state(
            research_id,
            status=ResearchStatus.SYNTHESIZING,
            progress=90,
            current_agent="synthesis",
            current_task="Generating final report",
        )

        with SessionLocal() as session:
            research = session.get(Research, research_id)
            tasks = (
                session.query(ResearchTask)
                .filter(ResearchTask.research_id == research_id)
                .order_by(ResearchTask.order_index)
                .all()
            )
            evidence = session.query(Evidence).filter(Evidence.research_id == research_id).all()
            goal = research.goal if research else ""
            task_texts = [t.task for t in tasks]
            evidence_items = [_evidence_item(row) for row in evidence]
            # Tasks stopped after exhausting attempts must be surfaced in the
            # report as "Insufficient verified evidence", never silently dropped.
            insufficient = [
                t.task for t in tasks if t.status == TaskStatus.FAILED
            ]

        started = _now_ms()
        if not evidence_items:
            # Nothing was grounded in any attempt — a "report" here would be
            # fabrication. Fail loudly with a clear, actionable message.
            insufficient_count = len([t for t in tasks if t.status == TaskStatus.FAILED])
            raise RuntimeError(
                f"No verifiable evidence was collected from {research.searches_count} searches "
                f"across {len(tasks)} tasks ({insufficient_count} stopped as insufficient). "
                "The Synthesis Agent refuses to generate a report without evidence — "
                "try a more specific goal or check search provider health."
            )
        report_content = await self.synthesis.synthesize(goal, task_texts, evidence_items, insufficient_tasks=insufficient)
        if not report_content.strip():
            raise RuntimeError("Synthesis Agent returned an empty report.")

        with SessionLocal() as session:
            session.add(Report(research_id=research_id, content=report_content))
            session.commit()

        await self._log(
            research_id,
            agent_name="Synthesis Agent",
            action="Report generated",
            input=f"{len(task_texts)} tasks, {len(evidence_items)} evidence items",
            output=f"{len(report_content)} characters",
            duration_ms=_now_ms() - started,
        )
        await self._publish(research_id, "report_completed", {"research_id": research_id, "content": report_content})
        await self._set_state(
            research_id,
            status=ResearchStatus.SYNTHESIZING,
            progress=98,
            current_agent="synthesis",
            current_task="Finalizing",
        )

    async def _finalize(self, research_id: str, status: str) -> None:
        self._update_counts(research_id)
        with SessionLocal() as session:
            research = session.get(Research, research_id)
            if research is not None:
                research.status = status
                research.progress = 100 if status == ResearchStatus.COMPLETED else research.progress
                research.completed_at = _utcnow()
                research.current_agent = None
                research.current_task = None
                session.commit()
                progress = research.progress
        await self._log(
            research_id,
            agent_name="Orchestrator",
            action=f"Research {status.lower()}",
            output=f"status={status}, progress={progress}",
            status=LogStatus.OK if status == ResearchStatus.COMPLETED else LogStatus.WARNING,
        )
        await self._publish(
            research_id,
            "status",
            {"status": status, "progress": 100 if status == ResearchStatus.COMPLETED else progress},
        )

    async def _fail(self, research_id: str, exc: Exception) -> None:
        error = f"{type(exc).__name__}: {exc}"
        with SessionLocal() as session:
            research = session.get(Research, research_id)
            if research is not None:
                research.status = ResearchStatus.FAILED
                research.error = error[:2000]
                research.completed_at = _utcnow()
                session.commit()
        await self._log(
            research_id,
            agent_name="Orchestrator",
            action="Research failed",
            input=None,
            output=error,
            status=LogStatus.ERROR,
        )
        await self._publish(research_id, "error", {"message": error})

    # ------------------------------------------------------ LLM-safe wrappers

    async def _generate_queries_safe(self, research_id: str, task_text: str) -> list[str]:
        try:
            return await self.research_agent.generate_queries(task_text)
        except LLMError as exc:
            await self._log(
                research_id,
                agent_name="Research Agent",
                action="Query generation failed (LLM unavailable); using fallback queries",
                input=task_text,
                output=str(exc),
                status=LogStatus.WARNING,
            )
            return self.research_agent.fallback_queries(task_text)

    async def _evaluate_safe(self, research_id: str, task_text: str, query: str, results: list[SearchResult]) -> Evaluation:
        evaluation: Evaluation | None = None
        research_row = self._get_research(research_id)
        goal = research_row.goal if research_row else ""
        for eval_attempt in range(3):
            try:
                return await self.evaluator.evaluate(task_text, query, results, goal=goal)
            except LLMError as exc:
                if eval_attempt == 2:
                    await self._log(
                        research_id,
                        agent_name="Evaluator Agent",
                        action="Evaluation failed after retries (LLM unavailable)",
                        input=query,
                        output=str(exc),
                        status=LogStatus.ERROR,
                    )
                    break
                await asyncio.sleep(2 ** eval_attempt + 1)
        return Evaluation(
            score=0.0,
            status="REJECTED",
            reason="Evaluation unavailable due to LLM errors; query rejected.",
        )

    async def _refine_safe(self, research_id: str, query: str, evaluation: Evaluation, task_text: str, attempt: int = 1) -> str:
        try:
            return await self.correction.refine(query, evaluation, task_text, attempt=attempt)
        except LLMError as exc:
            await self._log(
                research_id,
                agent_name="Correction Agent",
                action="Correction failed (LLM unavailable); using fallback refinement",
                input=query,
                output=str(exc),
                status=LogStatus.WARNING,
            )
            return f"{query} official information"

    # ---------------------------------------------------------------- helpers

    def _check_cancelled(self, research_id: str) -> None:
        if cancellations.is_cancelled(research_id):
            raise ResearchCancelled()

    def _get_research(self, research_id: str) -> Research | None:
        with SessionLocal() as session:
            return session.get(Research, research_id)

    async def _set_state(self, research_id: str, **kwargs) -> None:
        with SessionLocal() as session:
            research = session.get(Research, research_id)
            if research is None:
                return
            for key, value in kwargs.items():
                setattr(research, key, value)
            session.commit()
        await self._publish(
            research_id,
            "status",
            {
                "status": kwargs.get("status"),
                "progress": kwargs.get("progress"),
                "current_agent": kwargs.get("current_agent"),
                "current_task": kwargs.get("current_task"),
            },
        )

    async def _publish(self, research_id: str, event_type: str, data: dict) -> None:
        await bus.publish(research_id, {"type": event_type, "data": data})

    async def _publish_counts(self, research_id: str) -> None:
        """Push authoritative counters so the UI never drifts from the DB."""
        counts = self._current_counts(research_id)
        await self._publish(research_id, "counters", counts)

    def _current_counts(self, research_id: str) -> dict:
        with SessionLocal() as session:
            research = session.get(Research, research_id)
            tasks = (
                session.query(ResearchTask)
                .filter(ResearchTask.research_id == research_id)
                .all()
            )
            completed = sum(1 for t in tasks if t.status in ("COMPLETED", "FAILED"))
            return {
                "searches_count": research.searches_count if research else 0,
                "corrections_count": research.corrections_count if research else 0,
                "sources_count": research.sources_count if research else 0,
                "tasks_total": len(tasks),
                "tasks_completed": completed,
                "progress": research.progress if research else 0,
            }

    async def _log(
        self,
        research_id: str,
        agent_name: str,
        action: str,
        input: str | None = None,
        output: str | None = None,
        status: str = LogStatus.OK,
        duration_ms: int | None = None,
    ) -> None:
        with SessionLocal() as session:
            log = AgentLog(
                research_id=research_id,
                agent_name=agent_name,
                action=action,
                input=input,
                output=output,
                status=status,
                duration_ms=duration_ms,
            )
            session.add(log)
            session.commit()
            session.refresh(log)
            log_out = AgentLogOut.model_validate(log)
        await self._publish(research_id, "agent_log", {"log": log_out.model_dump(mode="json")})

    def _mark_task_in_progress(self, research_id: str, task_text: str) -> ResearchTask | None:
        with SessionLocal() as session:
            row = (
                session.query(ResearchTask)
                .filter(ResearchTask.research_id == research_id, ResearchTask.task == task_text)
                .order_by(ResearchTask.order_index)
                .first()
            )
            if row is None:
                return None
            row.status = TaskStatus.IN_PROGRESS
            session.commit()
            session.refresh(row)
            return row

    def _record_search(
        self,
        research_id: str,
        task_id: int | None,
        query: str,
        attempt: int,
        result_count: int,
        relevance_score: float | None,
        status: str,
        was_correction: bool,
    ) -> SearchRecord:
        with SessionLocal() as session:
            row = SearchRecord(
                research_id=research_id,
                task_id=task_id,
                query=query,
                attempt_number=attempt,
                result_count=result_count,
                relevance_score=relevance_score,
                status=status,
                was_correction=1 if was_correction else 0,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            research = session.get(Research, research_id)
            if research is not None:
                research.searches_count += 1
                session.commit()
            return row

    def _update_search_score(self, search_id: int, score: float, status: str) -> None:
        with SessionLocal() as session:
            row = session.get(SearchRecord, search_id)
            if row is not None:
                row.relevance_score = round(score, 2)
                row.status = status
                session.commit()

    def _save_evidence(self, research_id: str, task_id: int | None, item) -> Evidence:
        with SessionLocal() as session:
            row = Evidence(
                research_id=research_id,
                task_id=task_id,
                claim=item.claim,
                supporting_content=getattr(item, "supporting_content", "") or "",
                source_title=item.source_title,
                source_url=item.source_url,
                source_domain=item.source_domain,
                source_tier=getattr(item, "source_tier", "medium") or "medium",
                freshness=float(getattr(item, "freshness", 0.5) or 0.5),
                confidence_score=item.confidence,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            research = session.get(Research, research_id)
            if research is not None:
                research.sources_count = (
                    session.query(Evidence).filter(Evidence.research_id == research_id).count()
                )
                session.commit()
            return row

    def _complete_task(self, research_id: str, task_id: int, result: str) -> ResearchTask:
        with SessionLocal() as session:
            row = session.get(ResearchTask, task_id)
            if row is not None:
                row.status = TaskStatus.COMPLETED
                row.result = result
                row.completed_at = _utcnow()
                session.commit()
                session.refresh(row)
                return row
            raise RuntimeError(f"Task {task_id} not found")

    def _fail_task(self, research_id: str, task_id: int, result: str) -> ResearchTask:
        with SessionLocal() as session:
            row = session.get(ResearchTask, task_id)
            if row is not None:
                row.status = TaskStatus.FAILED
                row.result = result
                row.completed_at = _utcnow()
                session.commit()
                session.refresh(row)
                return row
            raise RuntimeError(f"Task {task_id} not found")

    async def _publish_task(self, research_id: str, row: ResearchTask) -> None:
        """Stream a task row so the Plan tab updates live (status/result)."""
        out = ResearchTaskOut.model_validate(row).model_dump(mode="json")
        await self._publish(research_id, "task_updated", {"task": out})

    def _increment_corrections(self, research_id: str) -> None:
        with SessionLocal() as session:
            research = session.get(Research, research_id)
            if research is not None:
                research.corrections_count += 1
                session.commit()

    def _update_counts(self, research_id: str) -> None:
        with SessionLocal() as session:
            research = session.get(Research, research_id)
            if research is not None:
                research.sources_count = (
                    session.query(Evidence).filter(Evidence.research_id == research_id).count()
                )
                session.commit()


# --- small helpers -------------------------------------------------------------

def _norm_url(url: str) -> str:
    import re as _re

    return _re.sub(r"[#?].*$", "", (url or "").strip().rstrip("/")).lower()


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _evidence_out(row: Evidence) -> dict:
    return EvidenceOut.model_validate(row).model_dump(mode="json")


def _evidence_item(row: Evidence):
    from app.types import EvidenceItem

    return EvidenceItem(
        claim=row.claim,
        supporting_content=row.supporting_content or "",
        source_title=row.source_title,
        source_url=row.source_url,
        source_domain=row.source_domain,
        source_tier=row.source_tier or "medium",
        freshness=row.freshness if row.freshness is not None else 0.5,
        confidence=row.confidence_score,
    )


orchestrator = Orchestrator()
