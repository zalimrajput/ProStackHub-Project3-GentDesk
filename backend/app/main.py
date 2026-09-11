"""GentDesk API — FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers.research import router as research_router


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    init_db()
    yield


app = FastAPI(
    title="GentDesk API",
    description="Autonomous multi-agent research platform backend.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "gentdesk-api"}