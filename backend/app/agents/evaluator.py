"""Agent 3 — Evaluator Agent.

Determines whether search results are relevant and useful for the current
research task. Scoring combines LLM relevance judgment with deterministic
source-authority and freshness signals:

  * official/primary sources are preferred over blogs and UGC
  * Reddit/Quora/forum answers are downweighted (weak evidence)
  * claims must be grounded in an actual returned result (anti-hallucination)
  * results missing key information for the task are rejected, triggering
    the Correction Agent (self-correction loop)

Verification is folded into this agent by design: there is no separate
Verification Agent in the architecture.
"""

from __future__ import annotations

import re

from app.authority import (
    authority_score,
    authority_tier,
    freshness_from_text,
    is_ugc,
)
from app.config import settings
from app.llm import LLMClient, parse_json_object
from app.mock import mock_evaluate
from app.types import Evaluation, EvidenceItem, SearchResult

SYSTEM_PROMPT = (
    "You are the Evaluator Agent of an autonomous research system. "
    "You assess whether web-search results are relevant to a research task. "
    "You score relevance 0.0–1.0, decide ACCEPTED or REJECTED, explain why, "
    "and extract concise evidence claims from the best results. "
    "Prefer authoritative sources (official sites, docs, reputable outlets) and penalize "
    "off-topic, duplicate, or thin results."
)

STRICT_SYSTEM_PROMPT = (
    "You are the strict Evaluator Agent of an autonomous research system. "
    "You judge whether the search results ANSWER the research task with concrete, specific facts.\n"
    "Scoring guide:\n"
    "- 0.9-1.0: results contain the specific facts the task asks for (numbers, limits, dates, "
    "official capabilities), preferably from official documentation\n"
    "- 0.7-0.89: results are clearly relevant and fact-rich but from secondary sources\n"
    "- 0.4-0.69: results are on-topic but generic, thin, or missing key details\n"
    "- 0.0-0.39: results are off-topic, marketing fluff, or do not answer the task\n"
    "Rules:\n"
    "(1) ACCEPT only if the results actually answer the task's specific question. Missing key "
    "information ⇒ REJECT with a reason stating exactly what is missing. "
    "(2) Extract each evidence claim VERBATIM-anchored to one result: every claim must be directly "
    "supported by that result's title/snippet — never invent facts, numbers, or sources. "
    "(3) In 'missing', list the concrete facts still needed (e.g. 'exact participant limit for "
    "Pro plan'). "
    "(4) Downweight forum/social discussion (Reddit, Quora, Hacker News) — usable only if nothing "
    "better exists, and say so in the reason."
)


def _norm_url(url: str) -> str:
    return re.sub(r"[#?].*$", "", (url or "").strip().rstrip("/")).lower()


def _llm_confidence_penalty(domain_tier: str) -> float:
    """Authority multiplier applied to LLM-provided confidence."""
    return {
        "official": 1.0,
        "high": 0.95,
        "medium": 0.8,
        "low": 0.6,
    }[domain_tier]


class EvaluatorAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def evaluate(
        self,
        task: str,
        query: str,
        results: list[SearchResult],
        goal: str = "",
    ) -> Evaluation:
        """Score the results and extract evidence for accepted searches."""
        if self.llm.is_mock:
            return mock_evaluate(task, query, results)

        if not results:
            return Evaluation(score=0.0, status="REJECTED", reason="No search results returned.")

        # Deterministic pre-scoring: authority + freshness per result.
        tiers = [authority_tier(r.domain, task=task, goal=goal) for r in results]
        freshness = [freshness_from_text(r.title, r.snippet) for r in results]

        listing_parts = []
        for i, r in enumerate(results):
            tier_tag = {"official": "[OFFICIAL]", "high": "[AUTHORITATIVE]", "medium": "", "low": "[FORUM/UGC]"}[tiers[i]]
            listing_parts.append(
                f"[{i + 1}]{tier_tag} title: {r.title}\n"
                f"    url: {r.url}\n"
                f"    domain: {r.domain}\n"
                f"    snippet: {r.snippet[:400]}"
            )
        listing = "\n".join(listing_parts)

        prompt = (
            f"Research task: {task}\n"
            f"Search query used: {query}\n\n"
            f"Search results:\n{listing}\n\n"
            "Respond with a single JSON object:\n"
            '{"score": <0.0-1.0>, "status": "ACCEPTED"|"REJECTED", '
            '"reason": "<brief explanation>", '
            '"missing": "<facts still needed if rejected>", '
            '"evidence": [{"result_index": <1-based result number>, '
            '"claim": "<one factual claim ONLY from that result>", '
            '"supporting_content": "<the snippet text that supports the claim>", '
            '"confidence": <0.0-1.0>}]}\n'
            "Include at most 3 evidence items. Each claim MUST cite the result_index of the result "
            "it comes from and must be directly supported by that result's snippet."
        )
        text = await self.llm.complete(prompt, system=STRICT_SYSTEM_PROMPT, json_mode=True, temperature=0.2)
        data = parse_json_object(text)
        if data is None:
            fallback = _parse_fallback_response(text, results, tiers, freshness, task=task, goal=goal)
            if fallback is not None:
                # Apply the same deterministic authority caps to recovered
                # responses so UGC-only sets can never sneak through as high
                # confidence.
                return _apply_authority_caps(fallback, tiers)
            # Genuinely unparseable response — do not silently accept or reject.
            return Evaluation(
                score=0.0,
                status="REJECTED",
                reason="Evaluator LLM returned an unparseable response; treating as no useful signal.",
            )

        raw_score = _clamp(float(data.get("score", 0.0)), 0.0, 1.0)
        status = "ACCEPTED" if (data.get("status") or "").upper() == "ACCEPTED" else "REJECTED"
        reason = str(data.get("reason") or "").strip()
        missing = str(data.get("missing") or "").strip()

        # Deterministic authority adjustment: UGC-heavy result sets and
        # missing official confirmation cap the score.
        draft = Evaluation(score=raw_score, status=status, reason=reason, evidence=[])
        adjusted = _apply_authority_caps(draft, tiers)
        if adjusted.status == "REJECTED":
            reject_reason = adjusted.reason
            if missing and missing.lower() not in reject_reason.lower():
                reject_reason = f"{reject_reason} Missing: {missing}".strip()
            partial_score = round(min(raw_score, 0.6), 2)
            # Bank whatever real facts ARE grounded in the results. A search
            # that only partially answers the task (e.g. an official pricing
            # page among mixed results) still yields usable evidence instead
            # of being discarded wholesale (all-or-nothing rejection).
            partial = _extract_evidence(
                data, results, tiers, freshness, fallback_score=partial_score, task=task, goal=goal
            )
            return Evaluation(
                score=partial_score,
                status="REJECTED",
                reason=reject_reason or "Results insufficiently relevant or missing key facts for the task.",
                missing=missing,
                evidence=partial[:2],
            )
        score = adjusted.score

        # --- Evidence extraction (grounded to actual results) ---------------
        items = _extract_evidence(data, results, tiers, freshness, fallback_score=score)
        if not items:
            # LLM accepted but produced no usable grounded evidence — reject
            # rather than fabricate evidence from nothing.
            return Evaluation(
                score=round(score, 2),
                status="REJECTED",
                reason=(reason or "Accepted but no evidence could be grounded in the actual results."),
            )

        return Evaluation(
            score=round(score, 2),
            status="ACCEPTED",
            reason=reason or "Results answer the task with sufficient specificity.",
            evidence=items,
        )


def _apply_authority_caps(evaluation: Evaluation, tiers: list[str]) -> Evaluation:
    """Deterministic authority downgrades applied to any ACCEPTED evaluation.

    UGC-only result sets are rejected outright (forum consensus is not
    evidence); sets lacking official/authoritative sources are capped.
    """
    if evaluation.status != "ACCEPTED":
        return evaluation
    best_tier_rank = max({"official": 3, "high": 2, "medium": 1, "low": 0}[t] for t in tiers)
    score = evaluation.score
    reason = evaluation.reason
    if best_tier_rank == 0:
        return Evaluation(
            score=round(min(score, 0.55), 2),
            status="REJECTED",
            reason=(reason + " — rejected: only forum/UGC sources in results; official confirmation required.").strip(" —"),
            evidence=evaluation.evidence,
        )
    if best_tier_rank < 2:
        score = min(score, 0.85)
    if score < settings.relevance_threshold:
        return Evaluation(
            score=round(score, 2),
            status="REJECTED",
            reason=(reason + " (downgraded: no authoritative source in results)").strip(),
            evidence=evaluation.evidence,
        )
    return Evaluation(score=round(score, 2), status="ACCEPTED", reason=reason, evidence=evaluation.evidence)


def _extract_evidence(
    data: dict,
    results: list[SearchResult],
    tiers: list[str],
    freshness: list[float],
    fallback_score: float,
    task: str = "",
    goal: str = "",
) -> list[EvidenceItem]:
    """Convert LLM evidence entries into EvidenceItems, strictly grounded."""
    items: list[EvidenceItem] = []
    seen_urls: set[str] = set()

    raw_entries = data.get("evidence") or []
    for raw in raw_entries[:3]:
        if not isinstance(raw, dict):
            continue
        claim = str(raw.get("claim") or "").strip()
        if not claim:
            continue

        # Ground the claim to a real result via result_index (1-based),
        # falling back to URL/title matching.
        idx: int | None = None
        try:
            raw_idx = int(raw.get("result_index", 0))
            if 1 <= raw_idx <= len(results):
                idx = raw_idx - 1
        except (TypeError, ValueError):
            pass
        if idx is None:
            idx = _match_result_by_content(raw, results)

        if idx is None:
            continue  # cannot ground → skip (anti-hallucination)

        source = results[idx]
        url_key = _norm_url(source.url)
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)

        tier = tiers[idx] if idx < len(tiers) else authority_tier(source.domain, task=task, goal=goal)
        fresh = freshness[idx] if idx < len(freshness) else 0.5

        llm_conf = raw.get("confidence")
        try:
            conf = float(llm_conf) if llm_conf is not None else fallback_score
        except (TypeError, ValueError):
            conf = fallback_score
        # Evidence confidence reflects source authority + freshness. This is
        # deliberately decoupled from the accept/reject score so a genuinely
        # relevant secondary source still passes the threshold but carries a
        # visibly lower evidence confidence.
        conf = _clamp(
            min(conf, fallback_score) * (0.6 + 0.3 * _llm_confidence_penalty(tier)) * (0.9 + 0.1 * fresh),
            0.0,
            1.0,
        )

        supporting = str(raw.get("supporting_content") or "").strip() or source.snippet[:500]

        items.append(
            EvidenceItem(
                claim=claim[:500],
                supporting_content=supporting[:1000],
                source_title=source.title,
                source_url=source.url,
                source_domain=source.domain,
                source_tier=tier,
                freshness=round(fresh, 2),
                confidence=_clamp(conf, 0.0, 1.0),
            )
        )

    # Deterministic fallback: if the LLM listed no evidence, ground the best
    # official/authoritative result snippet directly.
    if not items:
        ranked = sorted(
            range(len(results)),
            key=lambda i: ({"official": 3, "high": 2, "medium": 1, "low": 0}[tiers[i]], freshness[i]),
            reverse=True,
        )
        for i in ranked[:1]:
            source = results[i]
            if len(source.snippet) < 60:
                break
            url_key = _norm_url(source.url)
            if url_key in seen_urls:
                break
            conf = _clamp(
                fallback_score * _llm_confidence_penalty(tiers[i]) * (0.85 + 0.15 * freshness[i]),
                0.0,
                1.0,
            )
            items.append(
                EvidenceItem(
                    claim=source.snippet[:280],
                    supporting_content=source.snippet[:1000],
                    source_title=source.title,
                    source_url=source.url,
                    source_domain=source.domain,
                    source_tier=tiers[i],
                    freshness=round(freshness[i], 2),
                    confidence=round(conf, 2),
                )
            )
    return items


def _match_result_by_content(raw: dict, results: list[SearchResult]) -> int | None:
    """Match an evidence entry to a result by URL/domain/title fragments."""
    url_hint = _norm_url(str(raw.get("source_url") or ""))
    domain_hint = str(raw.get("source_domain") or "").lower()
    title_hint = str(raw.get("source_title") or "").lower()

    for i, r in enumerate(results):
        if url_hint and _norm_url(r.url) == url_hint:
            return i
    for i, r in enumerate(results):
        if domain_hint and (r.domain == domain_hint or r.domain.endswith("." + domain_hint)):
            return i
    if title_hint and len(title_hint) > 8:
        for i, r in enumerate(results):
            if title_hint in r.title.lower() or r.title.lower() in title_hint:
                return i
    return None


def _parse_fallback_response(
    text: str,
    results: list[SearchResult],
    tiers: list[str],
    freshness: list[float],
    task: str = "",
    goal: str = "",
) -> Evaluation | None:
    """Recover an Evaluation from a model response that is valid JSON but not
    the requested {score, status, ...} object.

    Handles two observed model behaviors:
      * a bare evidence array: [{"claim": ..., "confidence": ...}, ...]
      * the evaluation object wrapped in an array: [{"score": ..., ...}]
    """
    from app.llm import parse_json_list

    raw = parse_json_list(text)
    if not raw:
        return None

    # Case: evaluation object wrapped in an array.
    for entry in raw:
        if isinstance(entry, dict) and "score" in entry:
            score = _clamp(float(entry.get("score", 0.0)), 0.0, 1.0)
            status = "ACCEPTED" if (entry.get("status") or "").upper() == "ACCEPTED" else "REJECTED"
            items = _extract_evidence(
                {"evidence": entry.get("evidence") or []},
                results,
                tiers,
                freshness,
                fallback_score=score,
                task=task,
                goal=goal,
            )
            return Evaluation(
                score=score,
                status=status,
                reason=str(entry.get("reason") or "Recovered from wrapped evaluation response."),
                evidence=items if status == "ACCEPTED" else [],
            )

    # Case: bare evidence list — implicit acceptance with extracted evidence.
    items = _extract_evidence(
        {"evidence": raw},
        results,
        tiers,
        freshness,
        fallback_score=0.75,
        task=task,
        goal=goal,
    )
    if not items:
        return None
    return Evaluation(
        score=round(max(item.confidence for item in items), 2),
        status="ACCEPTED",
        reason="Model returned evidence list directly; accepted with extracted evidence.",
        evidence=items,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
