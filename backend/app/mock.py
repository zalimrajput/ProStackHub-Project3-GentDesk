"""Deterministic offline stand-ins for the LLM and web search.

Used when LLM_PROVIDER=mock / SEARCH_BACKEND=mock so the entire platform
runs end-to-end without any API keys. These implementations still follow
the real agent contracts (planning, evaluation, correction, synthesis).
"""

from __future__ import annotations

import re
from urllib.parse import quote

from app.types import Evaluation, EvidenceItem, SearchResult

STOPWORDS = {
    "the", "a", "an", "of", "to", "and", "or", "for", "with", "on", "in",
    "at", "by", "is", "are", "was", "were", "be", "their", "its", "it's",
    "top", "best", "most", "compare", "comparison", "research", "about",
    "vs", "versus", "list", "your", "you", "we", "i", "what", "how",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", text.lower()) if t not in STOPWORDS}


def _topic_words(goal: str) -> list[str]:
    tokens = _tokens(goal)
    ordered = sorted(tokens, key=len, reverse=True)
    return ordered[:6]


def mock_plan(goal: str, max_tasks: int = 10) -> list[str]:
    """Produce a plausible research plan from the goal."""
    topics = ", ".join(_topic_words(goal)[:3]) or "the topic"
    tasks = [
        f"Identify the key players / entities related to: {topics}",
        "Research the most relevant candidates in detail",
        f"Collect detailed information about: {topics}",
        "Gather pricing, features, and target-user information",
        "Verify important findings against authoritative sources",
        "Compare the findings side by side",
        "Generate the final structured report",
    ]
    return tasks[:max_tasks]


def mock_queries(task: str) -> list[str]:
    """Produce a few search queries for a task."""
    base = task.strip().rstrip(".")
    year = "2026"
    variants = [
        base,
        f"{base} {year}",
        f"{base} official information {year}",
    ]
    lower = base.lower()
    if "pricing" in lower or "plan" in lower or "cost" in lower:
        variants.append(f"{base} {year} official pricing")
    elif "feature" in lower or "capabilities" in lower:
        variants.append(f"{base} {year} key features")
    elif "competitor" in lower or "compare" in lower:
        variants.append(f"{base} {year} alternatives")
    return variants[:3]


def mock_search(query: str, limit: int = 8) -> list[SearchResult]:
    """Canned, on-topic search results derived from the query.

    Returns intentionally weak, low-information results so the mock evaluator
    is more likely to reject them and the Correction Agent gets exercised.
    """
    words = [w for w in _tokens(query) or ["topic"]][:4]
    parts = list(dict.fromkeys(words))
    results: list[SearchResult] = []
    for i in range(min(limit, 4)):
        title = f"{' '.join(w.capitalize() for w in parts)} — Placeholder #{i + 1}"
        domain = ["example.com", "placeholder.net", "demo-info.org", "sample-site.io"][i % 4]
        snippet = (
            f"Placeholder page about {' '.join(parts)}. "
            f"This mock result is intentionally thin and not a real authoritative source."
        )
        results.append(
            SearchResult(
                title=title,
                url=f"https://{domain}/page/{i + 1}?q={quote(query)}",
                snippet=snippet,
                domain=domain,
            )
        )
    return results


def mock_evaluate(task: str, query: str, results: list[SearchResult]) -> Evaluation:
    """Score results by keyword overlap with the task (mimics the Evaluator).

    Mock results are intentionally weak, so most evaluations should be REJECTED
    so the Correction Agent can be demonstrated.
    """
    if not results:
        return Evaluation(score=0.0, status="REJECTED", reason="No search results returned.")

    task_tokens = _tokens(task) | _tokens(query)
    if not task_tokens:
        task_tokens = {"information"}

    best: SearchResult | None = None
    best_ratio = 0.0
    for r in results:
        haystack = _tokens(r.title) | _tokens(r.snippet)
        if not haystack:
            continue
        overlap = len(task_tokens & haystack)
        ratio = overlap / len(task_tokens)
        if ratio > best_ratio:
            best_ratio, best = ratio, r

    # Threshold low enough to occasionally accept, but high enough that
    # thin mock results are commonly rejected.
    score = round(min(0.75, max(0.05, best_ratio * 0.85 + 0.1)), 2)

    if score >= 0.5 and best is not None and best_ratio > 0.25:
        return Evaluation(
            score=score,
            status="ACCEPTED",
            reason=f"Results partially match the task context (overlap {best_ratio:.0%}).",
            evidence=[
                EvidenceItem(
                    claim=(best.snippet or best.title)[:280],
                    source_title=best.title,
                    source_url=best.url,
                    source_domain=best.domain,
                    confidence=score,
                )
            ],
        )

    return Evaluation(
        score=score,
        status="REJECTED",
        reason="Insufficient contextual match between results and the research task.",
    )


def mock_refine(query: str, reason: str, task: str) -> str:
    """Produce a refined query after a rejected evaluation."""
    extra = _topic_words(task)[:2]
    additions = ["official", "2026"]
    suffix = " ".join(dict.fromkeys(extra + additions))
    refined = query.strip().rstrip(".")
    if suffix and suffix.lower() not in refined.lower():
        return f"{refined} {suffix}"
    return f"{refined} details"


def mock_synthesize(goal: str, tasks: list[str], evidence: list[EvidenceItem]) -> str:
    """Template-based report assembled from the collected evidence."""
    lines: list[str] = []
    lines.append("# Research Report")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(
        f"This report summarizes autonomous research performed for the goal: *{goal}*. "
        f"Findings were gathered from {len(evidence)} source(s) across {len(tasks)} research task(s)."
    )
    lines.append("")
    lines.append("## Research Methodology")
    lines.append("")
    lines.append(
        "A Planner Agent decomposed the goal into tasks; a Research Agent generated and executed "
        "search queries; an Evaluator Agent scored result relevance and rejected weak results; a "
        "Correction Agent refined unsuccessful queries; and a Synthesis Agent assembled this report "
        "from the collected evidence."
    )
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    if evidence:
        for i, item in enumerate(evidence, start=1):
            lines.append(f"{i}. **{item.claim}**")
            lines.append(f"   - Source: [{item.source_title}]({item.source_url}) ({item.source_domain})")
            lines.append(f"   - Confidence: {item.confidence:.2f}")
            lines.append("")

    lines.append("## Comparison")
    lines.append("")
    lines.append(
        "Where the evidence permits, the collected findings are compared side by side. "
        "Any gaps or low-confidence points are noted explicitly in the Detailed Analysis."
    )
    lines.append("")
    lines.append("## Detailed Analysis")
    lines.append("")
    if evidence:
        for item in evidence:
            verified = "verified" if item.confidence >= 0.7 else "unverified"
            lines.append(f"- **{item.source_domain}** — {item.claim} ({verified}, confidence {item.confidence:.2f})")
    else:
        lines.append("- Insufficient evidence for a detailed analysis.")
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append(
        "The autonomous research loop completed within the configured limits. "
        "Self-correction and evaluation steps were logged in the audit trail."
    )
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    if evidence:
        seen: set[str] = set()
        for item in evidence:
            if item.source_url in seen:
                continue
            seen.add(item.source_url)
            lines.append(f"- [{item.source_title}]({item.source_url}) — {item.source_domain}")
    else:
        lines.append("- No sources.")
    return "\n".join(lines)
