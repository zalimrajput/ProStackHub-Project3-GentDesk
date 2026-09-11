"""Agent 2 — Research Agent.

Receives a task from the planner, generates precise, diverse search queries,
and executes web searches via the SearchTool. Query generation biases toward
official documentation and specific factual dimensions instead of vague
restatement of the task.
"""

from __future__ import annotations

import re

from app.config import settings
from app.llm import LLMClient, parse_json_list
from app.mock import mock_queries
from app.search import SearchTool
from app.types import SearchResult

SYSTEM_PROMPT = (
    "You are the Research Agent of an autonomous research system. "
    "Given a research task, you generate precise web-search queries. "
    "Prefer specific, high-precision queries over vague ones (e.g. 'Figma official pricing' "
    "rather than 'Figma')."
)

STRICT_SYSTEM_PROMPT = (
    "You are the Research Agent of an autonomous research system. "
    "Given one research task, you generate 2-3 DIVERSE, precise web-search queries that together "
    "cover the task from different angles. Rules: "
    "(1) Each query targets a DIFFERENT aspect or phrasing — never near-duplicates. "
    "(2) At least one query should target official/primary documentation "
    "(e.g. include the vendor name, or 'official documentation', or 'site:' style specificity). "
    "(3) Queries must be self-contained (no pronouns), under 12 words, and web-searchable. "
    "(4) Include current-year recency terms when freshness matters. "
    "Return ONLY a JSON array of query strings."
)


def _query_year(task: str) -> str:
    """Best-effort year extraction; default to 2026 for current-year research goals."""
    m = re.search(r"(20\d\d)", task)
    return m.group(1) if m else "2026"


class ResearchAgent:
    def __init__(self, llm: LLMClient, search: SearchTool) -> None:
        self.llm = llm
        self.search_tool = search

    async def generate_queries(self, task: str) -> list[str]:
        """Produce up to max_queries_per_task diverse search queries for a task."""
        if self.llm.is_mock:
            return mock_queries(task)[: settings.max_queries_per_task]

        prompt = (
            f"Research task: {task}\n\n"
            f"Generate search queries as a JSON array of strings. Produce at most "
            f"{settings.max_queries_per_task} queries. The FIRST query must target official/primary "
            f"sources for the entities in the task. Make the remaining queries cover different "
            f"aspects (numbers/limits, comparisons, official announcements). "
            f"Queries must be mutually diverse — no near-duplicates.\n\n"
            f'Return strictly: ["query 1", "query 2", ...]'
        )
        text = await self.llm.complete(prompt, system=STRICT_SYSTEM_PROMPT, json_mode=True, temperature=0.4)
        queries = parse_json_list(text) or []
        queries = [str(q).strip() for q in queries if str(q).strip()]
        queries = self._dedupe(queries)
        return queries[: settings.max_queries_per_task] or [task]

    async def search(self, query: str, max_results: int | None = None) -> list[SearchResult]:
        """Execute a web search and return the raw results."""
        return await self.search_tool.search(query, max_results)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _dedupe(queries: list[str]) -> list[str]:
        """Drop near-duplicate queries (token-overlap > 0.8)."""
        kept: list[str] = []

        def tokens(q: str) -> set[str]:
            return {t for t in re.findall(r"[a-z0-9]{3,}", q.lower())}

        for q in queries:
            qt = tokens(q)
            duplicate = False
            for k in kept:
                kt = tokens(k)
                if not qt or not kt:
                    continue
                overlap = len(qt & kt) / min(len(qt), len(kt))
                if overlap > 0.8:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(q)
        return kept

    @staticmethod
    def fallback_queries(task: str) -> list[str]:
        """Deterministic queries used when the LLM is unavailable.

        Biases the first query toward official sources.
        """
        base = task.strip().rstrip(".")
        year = _query_year(base)
        return [
            f"{base} official documentation {year}",
            f"{base} {year}",
            f"{base} specifications limits {year}",
        ][: settings.max_queries_per_task]
