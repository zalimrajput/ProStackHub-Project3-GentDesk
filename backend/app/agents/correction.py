"""Agent 4 — Correction Agent.

When the Evaluator rejects a search, this agent analyzes the failure and
produces a refined query that is sent back to the Research Agent,
creating the closed feedback loop.
"""

from __future__ import annotations

import re

from app.llm import LLMClient
from app.mock import mock_refine
from app.types import Evaluation

SYSTEM_PROMPT = (
    "You are the Correction Agent of an autonomous research system. "
    "When a web search fails to return relevant results, you diagnose why "
    "(e.g. ambiguous terms, wrong context, too broad) and produce one refined, "
    "more precise query. Keep the refined query a single search-engine query string."
)


def _sanitize_refined_query(original: str, refined: str, attempt: int) -> str:
    """Deterministic sanitation of refined queries.

    Guards against observed degradation patterns:
      * wrapping every term in quotes ("Google" "Drive" "pricing") which
        shrinks result counts from 8 to 0
      * returning the same query again (wasting the retry budget)
      * overly long queries that search engines truncate
    """
    refined = re.sub(r'"([^"]*)"', r"\1", refined or "").strip()
    refined = re.sub(r"\s+", " ", refined)
    if len(refined) > 200:
        refined = refined[:200]

    def _tokens(q: str) -> set[str]:
        return {t for t in re.findall(r"[a-z0-9]{3,}", q.lower())}

    # Same (or near-same) query as the original → force a different angle.
    orig_tokens = _tokens(original)
    refined_tokens = _tokens(refined)
    if not refined_tokens or not refined or (
        orig_tokens and refined_tokens
        and len(orig_tokens & refined_tokens) / max(len(orig_tokens | refined_tokens), 1) > 0.85
    ):
        base = re.sub(r'"', "", original).strip()
        if attempt >= 2:
            refined = f"{base} official documentation specifications"
        else:
            refined = f"{base} official site information"
    return refined


class CorrectionAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def refine(self, query: str, evaluation: Evaluation, task: str, attempt: int = 1) -> str:
        """Return a refined query for another search attempt."""
        if self.llm.is_mock:
            return mock_refine(query, evaluation.reason, task)

        missing_hint = f" Facts still missing: {evaluation.missing}" if evaluation.missing else ""
        prompt = (
            f"Original query: {query}\n"
            f"Research task: {task}\n"
            f"Evaluation score: {evaluation.score:.2f}\n"
            f"Evaluation reason: {evaluation.reason}{missing_hint}\n\n"
            "Produce exactly one refined search query that fixes the problem "
            "and returns more relevant results. Rules: "
            "(1) Do NOT wrap terms in quotes — plain keywords search better. "
            "(2) Change the angle or wording from the original query, and drop parts that caused noise. "
            "(3) Keep it under 12 words, plain keyword style. "
            "Respond with the query text only."
        )
        refined = (await self.llm.complete(prompt, system=SYSTEM_PROMPT, temperature=0.4)).strip()
        return _sanitize_refined_query(query, refined, attempt)


def sanitize_refined_query(original: str, refined: str, attempt: int = 1) -> str:
    """Public wrapper used by tests and the orchestrator."""
    return _sanitize_refined_query(original, refined, attempt)
