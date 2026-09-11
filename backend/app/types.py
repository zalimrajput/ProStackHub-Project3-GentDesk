"""Small shared dataclasses used across agents and the orchestrator."""

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    domain: str = ""


@dataclass
class EvidenceItem:
    claim: str
    supporting_content: str = ""
    source_title: str = ""
    source_url: str = ""
    source_domain: str = ""
    source_tier: str = "medium"  # official | high | medium | low
    freshness: float = 0.5
    confidence: float = 0.5


@dataclass
class Evaluation:
    score: float
    status: str  # "ACCEPTED" | "REJECTED"
    reason: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    missing: str = ""  # facts still needed when REJECTED (drives correction)
