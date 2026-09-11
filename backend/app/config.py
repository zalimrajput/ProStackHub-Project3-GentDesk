"""Central configuration for the GentDesk backend.

All settings are read from environment variables (see .env.example)
so the service can run identically in local dev, Docker, or the cloud.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env (shell env vars still take precedence).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass
class Settings:
    # --- Database ---
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./gentdesk.db")
    )

    # --- LLM ---
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "auto"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # --- Web search ---
    search_backend: str = field(default_factory=lambda: os.getenv("SEARCH_BACKEND", "auto"))
    serper_api_key: str = field(default_factory=lambda: os.getenv("SERPER_API_KEY", ""))
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    search_results_per_query: int = _env_int("SEARCH_RESULTS_PER_QUERY", 8)

    # --- Orchestrator limits (prevent infinite execution) ---
    relevance_threshold: float = _env_float("RELEVANCE_THRESHOLD", 0.7)
    max_retries: int = _env_int("MAX_RETRIES", 3)
    # Hard cap on search→evaluate→correct cycles per task (the visible
    # Research → Evaluator → Correction loop). One task never exceeds this.
    max_attempts_per_task: int = _env_int("MAX_ATTEMPTS_PER_TASK", 3)
    max_queries_per_task: int = _env_int("MAX_QUERIES_PER_TASK", 3)
    max_tasks: int = _env_int("MAX_TASKS", 10)
    max_total_searches: int = _env_int("MAX_TOTAL_SEARCHES", 40)
    max_evidence: int = _env_int("MAX_EVIDENCE", 30)
    # Gap-driven second research pass when coverage of the goal is incomplete.
    gap_research_enabled: bool = os.getenv("GAP_RESEARCH_ENABLED", "true").lower() in ("1", "true", "yes")

    # --- Server ---
    cors_origins: str = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000"))

    # --- Timeouts (seconds) ---
    llm_timeout: float = _env_float("LLM_TIMEOUT", 60.0)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()