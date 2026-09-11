"""Web search tool abstraction.

Backends:
  * duckduckgo — free, no API key required
  * serper     — Google results via Serper API, requires SERPER_API_KEY
  * tavily     — higher quality, requires TAVILY_API_KEY
  * mock       — deterministic offline results for development/demo

Chosen via SEARCH_BACKEND (auto | duckduckgo | serper | tavily | mock).
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.types import SearchResult


def _domain_of(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _resolve_backend() -> str:
    if settings.search_backend in ("duckduckgo", "serper", "tavily", "mock"):
        return settings.search_backend
    if settings.serper_api_key:
        return "serper"
    if settings.tavily_api_key:
        return "tavily"
    return "duckduckgo"


class SearchTool:
    """Async web-search tool used by the Research Agent."""

    def __init__(self) -> None:
        self._backend = _resolve_backend()
        self._ddgs_available = False
        if self._backend == "duckduckgo":
            try:
                import ddgs  # noqa: F401

                self._ddgs_available = True
            except ImportError:
                self._backend = "mock"

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def is_mock(self) -> bool:
        return self._backend == "mock"

    async def search(self, query: str, max_results: int | None = None) -> list[SearchResult]:
        limit = max_results or settings.search_results_per_query
        if self._backend == "duckduckgo":
            return await asyncio.to_thread(self._duckduckgo, query, limit)
        if self._backend == "serper":
            return await self._serper(query, limit)
        if self._backend == "tavily":
            return await self._tavily(query, limit)
        # mock
        from app.mock import mock_search

        return await asyncio.to_thread(mock_search, query, limit)

    def _duckduckgo(self, query: str, limit: int) -> list[SearchResult]:
        from ddgs import DDGS

        try:
            raw = list(DDGS().text(query, max_results=limit, region="wt-wt"))
        except Exception:
            return []
        results: list[SearchResult] = []
        for item in raw:
            title = (item.get("title") or "").strip()
            url = (item.get("href") or item.get("url") or "").strip()
            snippet = (item.get("body") or item.get("snippet") or "").strip()
            if not url:
                continue
            results.append(SearchResult(title=title, url=url, snippet=snippet, domain=_domain_of(url)))
        return results

    async def _serper(self, query: str, limit: int) -> list[SearchResult]:
        """Google search via the Serper API (https://serper.dev)."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": settings.serper_api_key,
                        "Content-Type": "application/json",
                    },
                    json={"q": query, "num": min(limit, 10)},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []
        results: list[SearchResult] = []
        for item in data.get("organic", []):
            url = (item.get("link") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=(item.get("title") or "").strip(),
                    url=url,
                    snippet=(item.get("snippet") or "").strip(),
                    domain=_domain_of(url),
                )
            )
        return results

    async def _tavily(self, query: str, limit: int) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "max_results": min(limit, 10),
                        "search_depth": "basic",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []
        results: list[SearchResult] = []
        for item in data.get("results", []):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=(item.get("title") or "").strip(),
                    url=url,
                    snippet=(item.get("content") or "").strip(),
                    domain=_domain_of(url),
                )
            )
        return results


def looks_like_pricing_claim(text: str) -> bool:
    """Heuristic used by the Verification step to flag claims worth cross-checking."""
    return bool(
        re.search(
            r"\b(price|pricing|plan|plans|cost|costs|fee|fees|free tier|per month|per year|subscription)\b",
            text,
            re.IGNORECASE,
        )
    )
