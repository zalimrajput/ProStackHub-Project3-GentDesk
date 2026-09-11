"""Agent 1 — Planner Agent.

Understands the user's research goal and produces an ordered list of
concrete, targeted research tasks. Tasks must each target a *specific
dimension* (competitors, pricing, features, limits, security, ...)
rather than restating the goal generically.
"""

from __future__ import annotations

import re

from app.config import settings
from app.llm import LLMClient, parse_json_list
from app.mock import mock_plan

SYSTEM_PROMPT = (
    "You are the Planner Agent of an autonomous research system. "
    "You decompose a user's research goal into a concise, ordered list of concrete research tasks. "
    "Tasks must be actionable and each one must be answerable through web search."
)

STRICT_SYSTEM_PROMPT = (
    "You are the Planner Agent of an autonomous research system. "
    "You decompose a research goal into concrete, TARGETED research tasks. "
    "Rules: "
    "(1) Each task must investigate ONE specific dimension of the goal "
    "(e.g. for a product comparison: one task per product per dimension, or one task per dimension "
    "covering all products explicitly by name). "
    "(2) Never write generic tasks like 'research the topic' or 'gather information' — always name "
    "the exact entities and the exact dimension. "
    "(3) A task asking for quantitative facts (pricing, limits, specifications) must cover AT MOST "
    "ONE product. Comparing numbers for several products in one task makes a single web search "
    "impossible to satisfy — never do it. Split into per-product tasks. "
    "(4) Cover every dimension the user explicitly requested, plus: official capabilities documentation, "
    "pricing/plans, key features, security/compliance, and enterprise capabilities where relevant. "
    "(5) Each task must be self-contained and answerable via web search. "
    "Return ONLY a JSON array of task strings."
)

# Fallback research dimensions used for goal-driven planning when the LLM
# output is too generic. {subject} is substituted with the goal's key entities.
_DIMENSION_TEMPLATES = [
    "Find the official product/capability documentation for {subject}",
    "Research pricing plans and tier limits for {subject}",
    "Research core features and capabilities of {subject}",
    "Research participant/user limits and scale constraints for {subject}",
    "Research session/duration constraints and technical requirements for {subject}",
    "Research AI features and recent product updates for {subject}",
    "Research security, privacy, and compliance certifications of {subject}",
    "Research enterprise/admin capabilities of {subject}",
    "Compare {subject} side by side on the collected evidence",
]


def _extract_subjects(goal: str, max_subjects: int = 4) -> list[str]:
    """Extract likely entity names (product names) from the goal.

    Uses capitalized multi-word sequences and known product hints; falls back
    to the longest informative tokens.
    """
    stop = {
        "research", "compare", "comparison", "and", "or", "the", "for", "with",
        "their", "best", "top", "alternatives", "competitors", "building",
        "production", "about", "current", "using", "include", "including",
    }
    # Capitalized sequences like "Microsoft Teams", "Google Meet", "Cisco Webex".
    seqs = re.findall(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*)\b", goal)
    seqs = [s for s in seqs if s.split()[0].lower() not in stop and s.lower() not in stop]
    subjects: list[str] = []
    for s in seqs:
        # Drop leading stop words from a captured sequence so
        # "Compare Google Drive" → "Google Drive" instead of being discarded.
        words = s.split()
        while words and words[0].lower() in stop:
            words.pop(0)
        if not words:
            continue
        s = " ".join(words)
        if len(s.split()) >= 2 or s not in " ".join(subjects):
            if s.lower() not in {x.lower() for x in subjects}:
                subjects.append(s)
    if not subjects:
        tokens = [t for t in re.findall(r"[A-Za-z0-9]{4,}", goal) if t.lower() not in stop]
        subjects = sorted(set(tokens), key=len, reverse=True)[:max_subjects]
    return subjects[:max_subjects]


def _goal_dimensions(goal: str) -> list[str]:
    """Dimensions the user explicitly asked about, as lowercase keyword hints."""
    dimension_hints = {
        "pricing": "pricing",
        "price": "pricing",
        "plan": "pricing",
        "cost": "pricing",
        "participant": "participant limits",
        "limit": "limits",
        "duration": "duration limits",
        "ai": "AI features",
        "security": "security",
        "privacy": "security",
        "encryption": "security",
        "enterprise": "enterprise capabilities",
        "integration": "integrations",
        "performance": "performance",
        "scalab": "scalability",
        "documentation": "documentation",
        "auth": "authentication",
        "ecosystem": "ecosystem",
        "async": "async support",
        "feature": "features",
        "compliance": "security",
    }
    lower = goal.lower()
    dims: list[str] = []
    for keyword, dim in dimension_hints.items():
        if keyword in lower and dim not in dims:
            dims.append(dim)
    return dims


_QUANT_HINTS = (
    "pricing", "price", "cost", "plans", "limits", "limit", "storage", "caps",
    "participant", "duration", "specifications", "quota", "slas", "sla",
    "uptime", "tier", "tiers", "free tier",
)

_COORDINATORS = {"and", "or", ",", "vs", "versus", "+"}


def _split_multi_product_task(task: str, subjects: list[str]) -> list[str]:
    """Split quantitative mega-tasks into per-product tasks.

    'Compare pricing and storage limits for Google Drive, OneDrive, Dropbox, Box, and Egnyte'
    asks for 5 products × 2 numbers — no single search can satisfy a strict
    evaluator, so every attempt gets rejected and the task dies as
    'insufficient evidence'. Rewriting per-product keeps each task answerable.
    """
    lowered = task.lower()
    if not any(hint in lowered for hint in _QUANT_HINTS):
        return [task]

    # Find which known subjects the task mentions.
    mentioned = [s for s in subjects if re.search(r"\b" + re.escape(s).replace("\\ ", r"\s+") + r"\b", task, re.IGNORECASE)]
    if len(mentioned) < 2:
        return [task]

    # Reuse the task's own dimension wording (text before the entity list).
    m = re.search(r"\b(?:for|of|across|among)\b", lowered)
    prefix = task[: m.start()].strip() if m else f"Research {next((h for h in _QUANT_HINTS if h in lowered), 'the details')} of"
    prefix = prefix.rstrip(",;:")
    if len(prefix) < 10:
        prefix = f"Research official pricing and limits of"

    return [f"{prefix} for {name}" for name in mentioned]


class PlannerAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def plan(self, goal: str) -> list[str]:
        """Return an ordered list of research tasks for the goal."""
        if self.llm.is_mock:
            return mock_plan(goal, settings.max_tasks)

        prompt = (
            f"Research goal: {goal}\n\n"
            "Create a research plan as a JSON array of task strings. "
            f"Produce {settings.max_tasks} tasks at most, but prefer precision over count. "
            "Each task must name the exact entities AND the exact dimension being investigated, "
            "and must be verifiable via official documentation where possible.\n\n"
            "CRITICAL: a task requesting quantitative facts (pricing, storage limits, participant "
            "caps, specifications) must ask about AT MOST ONE product, so one web search can "
            "actually answer it. Split multi-product questions into separate per-product tasks.\n\n"
            'Return strictly: ["task 1", "task 2", ...]'
        )
        text = await self.llm.complete(prompt, system=STRICT_SYSTEM_PROMPT, json_mode=True, temperature=0.3)
        tasks = parse_json_list(text) or []
        tasks = [str(t).strip() for t in tasks if str(t).strip()]

        tasks = self._ensure_targeted(goal, tasks)
        return tasks[: settings.max_tasks] or [f"Research: {goal}"]

    def _ensure_targeted(self, goal: str, tasks: list[str]) -> list[str]:
        """Post-process LLM plans: drop generic tasks, ensure dimension coverage.

        If the LLM produced vague tasks or missed requested dimensions, fill in
        targeted fallback tasks derived from the goal's entities/dimensions.
        """
        generic_markers = (
            "key players", "most relevant candidates", "collect detailed information",
            "gather information", "research the topic", "identify the main entities",
            "relevant information", "detailed information about:",
        )
        cleaned: list[str] = []
        for t in tasks:
            lowered = t.lower()
            if any(marker in lowered for marker in generic_markers):
                continue
            if t not in cleaned:
                cleaned.append(t)

        dims = _goal_dimensions(goal)
        subjects = _extract_subjects(goal)

        # Split mega-tasks: quantitative questions spanning >2 products can
        # never be answered by a single search (the strict evaluator then
        # rejects every attempt). Rewrite them as per-product tasks.
        split_tasks: list[str] = []
        for t in cleaned:
            replaced = _split_multi_product_task(t, subjects)
            split_tasks.extend(replaced)
        cleaned = split_tasks

        # Ensure explicitly requested dimensions appear in at least one task.
        for dim in dims:
            if not any(dim.split()[0] in t.lower() for t in cleaned):
                target = " and ".join(subjects[:3]) if subjects else "the subject"
                cleaned.append(f"Research {dim} of {target}")

        # If nothing survived filtering, fall back to dimension templates.
        if not cleaned:
            target = " and ".join(subjects[:3]) if subjects else "the subject"
            cleaned = [tpl.format(subject=target) for tpl in _DIMENSION_TEMPLATES]

        return cleaned
