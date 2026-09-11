"""Agent 5 — Synthesis Agent.

Combines all collected evidence into a structured markdown report:
executive summary, methodology, key findings, comparison, detailed
analysis, conclusion, and sources.

The agent is evidence-gated: it must mark uncovered aspects explicitly
as gaps instead of asserting a "comprehensive comparison" without the
evidence to support it. If critical entities or dimensions have no
evidence at all, it returns them in a structured gaps block that the
orchestrator uses to trigger a targeted second research pass.
"""

from __future__ import annotations

import json
import re

from app.llm import LLMClient, parse_json_object
from app.mock import mock_synthesize
from app.types import EvidenceItem

SYSTEM_PROMPT = (
    "You are the Synthesis Agent of an autonomous research system. "
    "You write a final structured research report in Markdown from the collected evidence. "
    "Include: Executive Summary, Research Methodology, Key Findings, Comparison (if applicable), "
    "Detailed Analysis, Conclusion, and Sources. "
    "Only assert claims backed by the provided evidence; note gaps explicitly. "
    "Cite sources inline as markdown links."
)

GATED_SYSTEM_PROMPT = (
    "You are the Synthesis Agent of an autonomous research system. "
    "You write the final structured research report in Markdown from the collected evidence.\n"
    "Hard rules:\n"
    "(1) ONLY assert claims backed by the provided evidence. Never invent facts, numbers, or sources.\n"
    "(2) Prefer official/high-authority sources; when low-authority (forum) evidence is all you have "
    "for a point, mark it '(community-reported, unverified)'.\n"
    "(3) If an entity or dimension requested by the goal has NO evidence, do NOT skip it silently and "
    "do NOT claim a comprehensive comparison: list it under '## Coverage & Gaps' with exactly what is "
    "missing.\n"
    "(4) Structure: Executive Summary, Research Methodology, Key Findings, Comparison, Detailed "
    "Analysis, Coverage & Gaps, Conclusion, Sources.\n"
    "(5) Cite sources inline as markdown links."
)

# Response contract used for gap extraction (cheap JSON call before writing).
GAP_PROMPT_SYSTEM = (
    "You are the Synthesis Agent's coverage checker. Given a research goal and the collected "
    "evidence, identify entities or dimensions the goal asks about that have NO or clearly "
    "insufficient evidence. Respond with a single JSON object: "
    '{\"sufficient\": true|false, \"gaps\": [\"exact fact/entity+dimension missing\", ...], '
    '\"search_tasks\": [\"one concrete web-searchable research task per gap\"]}. '
    "Only include gaps that web search could plausibly fill."
)


class SynthesisAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def find_gaps(self, goal: str, tasks: list[str], evidence: list[EvidenceItem]) -> list[str]:
        """Return concrete search tasks for uncovered parts of the goal.

        Empty list ⇒ evidence coverage considered sufficient.
        """
        if self.llm.is_mock:
            return []
        if not goal:
            return []

        evidence_block = "\n".join(
            f"- [{item.source_tier}] {item.claim[:200]}" for item in evidence
        ) or "- (no evidence collected)"
        tasks_block = "\n".join(f"- {t}" for t in tasks) or "- (no tasks)"

        prompt = (
            f"Research goal: {goal}\n\n"
            f"Research tasks executed:\n{tasks_block}\n\n"
            f"Evidence collected (tier, claim):\n{evidence_block}\n\n"
            "Which requested entities/dimensions remain uncovered or insufficiently evidenced? "
            "Return the JSON object now."
        )
        try:
            text = await self.llm.complete(prompt, system=GAP_PROMPT_SYSTEM, json_mode=True, temperature=0.1)
            data = parse_json_object(text) or {}
            if not data.get("sufficient", True):
                return [str(g).strip() for g in (data.get("search_tasks") or []) if str(g).strip()][:4]
        except Exception:  # noqa: BLE001 - gap detection is best-effort
            return []
        return []

    async def synthesize(
        self,
        goal: str,
        tasks: list[str],
        evidence: list[EvidenceItem],
        insufficient_tasks: list[str] | None = None,
    ) -> str:
        """Produce the final markdown report (evidence-gated).

        Tasks listed in insufficient_tasks were stopped after exhausting the
        search/retry budget without sufficient evidence; they must be flagged
        as 'Insufficient verified evidence' in the report.
        """
        if self.llm.is_mock:
            base = mock_synthesize(goal, tasks, evidence)
            if insufficient_tasks:
                base += "\n\n## Insufficient Verified Evidence\n\n"
                base += "\n".join(f"- {t}" for t in insufficient_tasks)
            return base

        evidence_block = "\n".join(
            f"- Claim: {item.claim}\n"
            f"  Supporting: {item.supporting_content[:300]}\n"
            f"  Source: {item.source_title} ({item.source_domain}) [{item.source_tier}]\n"
            f"  URL: {item.source_url}\n"
            f"  Freshness: {item.freshness:.2f} | Confidence: {item.confidence:.2f}"
            for item in evidence
        ) or "- No evidence collected."
        tasks_block = "\n".join(f"- {t}" for t in tasks) or "- (no tasks)"
        insufficient_block = ""
        if insufficient_tasks:
            insufficient_block = (
                "\n\nResearch tasks stopped WITHOUT sufficient evidence "
                "(search retry budget exhausted):\n"
                + "\n".join(f"- {t}" for t in insufficient_tasks)
                + "\nEach of these MUST appear under 'Coverage & Gaps' as "
                "'Insufficient verified evidence' with the specific facts missing."
            )

        prompt = (
            f"Research goal: {goal}\n\n"
            f"Research tasks:\n{tasks_block}\n\n"
            f"Collected evidence:\n{evidence_block}"
            f"{insufficient_block}\n\n"
            "Write the final research report in Markdown following the required structure. "
            "Mark every uncovered aspect explicitly in 'Coverage & Gaps'; do not overstate coverage."
        )
        report = (await self.llm.complete(prompt, system=GATED_SYSTEM_PROMPT, temperature=0.4)).strip()
        if insufficient_tasks and "Insufficient verified evidence" not in report:
            # Enforce the flag even if the model omitted it.
            report += "\n\n## Insufficient Verified Evidence\n\n"
            report += "\n".join(f"- {t} — insufficient verified evidence after the search retry budget." for t in insufficient_tasks)
        return report or mock_synthesize(goal, tasks, evidence)
