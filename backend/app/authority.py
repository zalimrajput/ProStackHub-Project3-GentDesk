"""Source-authority and freshness heuristics.

Used by the Evaluator to prioritize official/authoritative sources over
user-generated content, and to estimate how fresh a result is.

Tiers:
  official — vendor documentation / primary source for the researched subject
  high     — highly reputable technical/reference domains
  medium   — well-known blogging/community engineering platforms
  low      — general user-generated content (Reddit, Quora, forums, ...)
"""

from __future__ import annotations

import re
from datetime import datetime

OFFICIAL = "official"
HIGH = "high"
MEDIUM = "medium"
LOW = "low"

TIER_SCORE: dict[str, float] = {
    OFFICIAL: 1.0,
    HIGH: 0.9,
    MEDIUM: 0.7,
    LOW: 0.4,
}

# Domains that are primary documentation / vendor sources.
_OFFICIAL_DOMAIN_PARTS = (
    "docs.", "documentation", "developer.", "developers.", "learn.",
    "support.", "help.", "www.docs",
)

_KNOWN_OFFICIAL_DOMAINS = {
    "tiangolo.com",            # FastAPI author's site
    "fastapi.tiangolo.com",
    "djangoproject.com", "docs.djangoproject.com",
    "flask.palletsprojects.com",
    "microsoft.com", "learn.microsoft.com", "azure.microsoft.com",
    "google.com", "cloud.google.com", "developers.google.com",
    "cisco.com", "developer.cisco.com",
    "zoom.com", "support.zoom.com", "explore.zoom.us",
    "python.org", "peps.python.org",
    "postgrespro.com", "postgresql.org",
    "aws.amazon.com", "docs.aws.amazon.com",
    "pydantic.dev", "sqlalchemy.org", "docs.sqlalchemy.org",
    "react.dev", "nextjs.org", "tailwindcss.com",
    "github.com",              # primary source code / official repos
    "gitlab.com",
    "stripe.com", "docs.stripe.com",
    "openai.com", "platform.openai.com", "anthropic.com", "docs.anthropic.com",
    "gemini.google.com", "ai.google.dev",
}

# Reputable engineering/reference outlets (not vendor-official, but reliable).
_HIGH_DOMAINS = {
    "developer.mozilla.org", "mdn.mozilla.org",
    "stackoverflow.com",
    "arxiv.org", "acm.org", "ieee.org",
    "infoq.com", "thoughtworks.com",
    "oreilly.com", "packt.com", "manning.com",
    "techradar.com", "zdnet.com", "theregister.com",
    "engineering.fb.com", "netflixtechblog.com", "uber.com",
    "blog.jetbrains.com", "pycon.org",
    "npmjs.com", "pypi.org",
}

# Blogging platforms — real engineers, but third-party and often stale.
_MEDIUM_DOMAINS = {
    "medium.com", "dev.to", "hashnode.com", "devblogs.microsoft.com",
    "logrocket.com", "smashingmagazine.com", "realpython.com",
    "testdriven.io", "morioh.com", "towardsdatascience.com",
    "levelup.gitconnected.com", "betterprogramming.pub",
    "blog.quantumly.dev", "substack.com",
}

# User-generated discussion — weak evidence.
_LOW_DOMAINS = {
    "reddit.com", "quora.com", "news.ycombinator.com",
    "medium.com/@",
    "discord.com", "t.me", "x.com", "twitter.com", "facebook.com",
    "answers.microsoft.com", "superuser.com", "askubuntu.com",
    "cpanel.net", "w3schools.com",
    "g2.com", "capterra.com", "trustpilot.com", "trustradius.com",
    "glassdoor.com", "indeed.com",
}

_SUBSTACK_PARTS = ("substack.com",)


def _registrable(domain: str) -> str:
    """Rough registrable-domain extraction (last two labels)."""
    parts = domain.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


def is_ugc(domain: str) -> bool:
    d = domain.lower()
    if any(d == low or d.endswith("." + low) for low in _LOW_DOMAINS):
        return True
    if any(part in d for part in _SUBSTACK_PARTS):
        return True
    return _authority_tier_for_known(d) == LOW


def _authority_tier_for_known(d: str) -> str | None:
    if d in _KNOWN_OFFICIAL_DOMAINS or _registrable(d) in {_registrable(x) for x in _KNOWN_OFFICIAL_DOMAINS}:
        return OFFICIAL
    if d in _HIGH_DOMAINS or d.endswith(".ieee.org"):
        return HIGH
    if d in _MEDIUM_DOMAINS or _registrable(d) in {_registrable(x) for x in _MEDIUM_DOMAINS}:
        return MEDIUM
    if d in _LOW_DOMAINS:
        return LOW
    return None


def authority_tier(domain: str, task: str = "", goal: str = "") -> str:
    """Classify a result domain's authority for the researched subject."""
    d = (domain or "").lower().strip()

    known = _authority_tier_for_known(d)
    if known:
        return known

    # Vendor documentation subdomains: docs.stripe.com, learn.microsoft.com ...
    if any(part in d for part in _OFFICIAL_DOMAIN_PARTS):
        return OFFICIAL

    # If the domain contains a subject keyword (e.g. "zoom" when researching
    # Zoom competitors), treat it as the vendor's official site.
    subject_tokens = _subject_tokens(task or goal)
    base = _registrable(d).split(".")[0]
    if subject_tokens and base in subject_tokens:
        return OFFICIAL

    return MEDIUM


def _subject_tokens(text: str) -> set[str]:
    stop = {
        "the", "and", "for", "with", "compare", "comparison", "research",
        "best", "top", "alternatives", "competitors", "competitor", "official",
        "documentation", "pricing", "features", "review", "reviews", "vs",
        "their", "using", "build", "building", "production", "about",
    }
    return {
        t for t in re.findall(r"[a-z0-9]{3,}", text.lower()) if t not in stop
    }


def authority_score(domain: str, task: str = "", goal: str = "") -> float:
    return TIER_SCORE[authority_tier(domain, task=task, goal=goal)]


_CURRENT_YEAR = datetime.utcnow().year
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def freshness_from_text(*texts: str) -> float:
    """Estimate 0–1 freshness from mentions of years in titles/snippets.

    Current year → 1.0; −0.2 per year of age, floored at 0.3 (undated
    documentation is often still maintained).
    """
    years: list[int] = []
    for text in texts:
        if not text:
            continue
        for m in _YEAR_RE.finditer(text):
            year = int(m.group(1))
            if 2015 <= year <= _CURRENT_YEAR + 1:
                years.append(year)
    if not years:
        return 0.5
    newest = max(years)
    age = max(0, _CURRENT_YEAR - newest)
    return max(0.3, 1.0 - 0.2 * age)


def tier_rank(tier: str) -> int:
    return {OFFICIAL: 3, HIGH: 2, MEDIUM: 1, LOW: 0}.get(tier, 1)
