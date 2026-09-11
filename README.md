<div align="center">

# 🔬 GentDesk

### Autonomous Multi-Agent AI Research Platform

**Plan → Search → Evaluate → Self-Correct → Verify → Synthesize**

*One goal in, an evidence-backed report out — with a complete, live audit trail.*

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Gemini](https://img.shields.io/badge/LLM-Gemini-8E75B2?logo=google%20gemini&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-green)](#license)

</div>

---

GentDesk is a full-stack **agentic AI** platform. You give it a research goal in plain language —
*"Compare the top 3 competitors of Canva, including pricing and features"* — and a team of five
specialized AI agents autonomously plans the research, searches the web, scores and evaluates every
result, **self-corrects poor queries**, verifies claims, and writes a structured, source-backed report.

It is not a single AI call. It is a **closed-loop pipeline with full observability**: every search,
score, correction, and agent action is persisted to PostgreSQL and streamed live to the dashboard
over Server-Sent Events.

---

## ✨ Features

- 🧠 **Five specialized agents** — Planner, Research, Evaluator, Correction, Synthesis — coordinated by an async Orchestrator
- 🔁 **Self-correction loop** — rejected searches are diagnosed and retried with refined queries (up to `MAX_ATTEMPTS_PER_TASK`)
- 🏦 **Evidence banking** — grounded facts from authoritative sources are retained even when overall results are rejected
- 🧭 **Gap-driven second pass** — detects uncovered aspects of the goal and runs targeted follow-up research
- ✅ **Verification pass** — low-confidence and pricing claims are cross-checked against official sources
- 🚫 **Anti-fabrication** — with zero verifiable evidence, the Synthesis Agent refuses to generate a report and fails loudly
- 📡 **Live SSE dashboard** — watch agents work in real time: pipeline strip, audit feed, searches, evidence, report tabs
- 🗄️ **Full audit trail** — 6 PostgreSQL tables capture every action, score, and source
- 🎨 **Aurora-glass UI** — glassmorphism design system with per-agent accent colors and micro-animations
- 🔌 **Provider-agnostic** — LLM: Gemini / OpenAI / deterministic mock · Search: Serper / Tavily / DuckDuckGo / mock
- 🧪 **Offline-capable** — runs the entire pipeline with zero API keys via mock providers

---

## 🏗️ Architecture

```
┌────────────────────────────── FRONTEND (Next.js @ :3000) ──────────────────────────────┐
│  /                     Home — research form + session history                          │
│  /research/[id]        Live dashboard — Activity · Plan · Searches · Evidence · Report │
└──────────────▲─────────────────────────────────────────────────────────▲───────────────┘
               │ REST (fetch)                                             │ EventSource (SSE)
┌──────────────┴─────────────────────────────────────────────────────────┴───────────────┐
│                             BACKEND (FastAPI @ :8000)                                  │
│                                                                                       │
│  routers/research.py ──► orchestrator.py ──► agents/ (planner, research,              │
│       (REST API)             │                evaluator, correction, synthesis)        │
│                              │                │                                       │
│                        event_bus.py      llm.py (Gemini/OpenAI/mock)                  │
│                        (SSE pub/sub)     search.py (Serper/Tavily/DDG/mock)           │
│                              │                │                                       │
└──────────────────────────────┼────────────────┼───────────────────────────────────────┘
                               ▼                ▼
                   ┌────────────────────────────────────┐
                   │      PostgreSQL (Supabase)         │  researches · research_tasks
                   │  6 tables — full audit trail       │  searches · evidence
                   │                                    │  agent_logs · reports
                   └────────────────────────────────────┘
```

## 🤖 The Agent Pipeline

```
              User Goal
                 │
                 ▼
         ┌──────────────┐
         │    Planner   │  decomposes the goal into ordered research tasks
         └──────┬───────┘
                ▼
         ┌──────────────┐
         │   Research   │  generates precise web-search queries   ◄──┐
         └──────┬───────┘                                            │
                ▼                                                    │
           Web Search (Serper / Tavily / DDG)                        │ refined
                │                                                    │ query
                ▼                                                    │
         ┌──────────────┐   score < threshold                        │
         │  Evaluator   │─────────────────────┐                      │
         └──────┬───────┘                     ▼                      │
                │ score ≥ threshold         ┌──────────────┐        │
                │                           │  Correction  ├────────┘
                ▼                           └──────────────┘
       Evidence extracted
   (claims + sources → DB)
                │
                ▼
         Verification pass  — cross-checks pricing / low-confidence claims
                │
                ▼
         ┌──────────────┐
         │  Synthesis   │  structured Markdown report, gaps flagged
         └──────┬───────┘
                ▼
          Final Report + Audit Log  (every action streamed live to the UI)
```

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | 🧭 **Planner** | Decomposes the goal into an ordered list of concrete research tasks |
| 2 | 🔎 **Research** | Turns tasks into precise search queries and executes web searches |
| 3 | ⚖️ **Evaluator** | Scores results 0.0–1.0 → ACCEPTED / REJECTED, extracts evidence claims |
| 4 | 🔁 **Correction** | Diagnoses rejected searches and refines the query — the feedback loop |
| 5 | ✍️ **Synthesis** | Combines verified evidence into the structured final report |

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+
- A PostgreSQL database (e.g. free [Supabase](https://supabase.com)) — or nothing: SQLite works with zero config

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
# .venv/bin/pip install -r requirements.txt        # macOS/Linux

cp .env.example .env                               # then edit with your keys

.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

> All 6 tables are created automatically at startup (`init_db()`).
> Swagger docs: http://localhost:8000/docs

**Minimum viable `.env`** (runs fully offline with mocks — no keys required):

```env
DATABASE_URL=sqlite:///./gentdesk.db
LLM_PROVIDER=mock
SEARCH_BACKEND=mock
```

For real research, set `LLM_PROVIDER=auto` + `GEMINI_API_KEY` and
`SEARCH_BACKEND=auto` + `SERPER_API_KEY` ([serper.dev](https://serper.dev) has a free tier).

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                 # http://localhost:3000
```

### 3. Smoke test (end-to-end, works offline)

```bash
cd backend
.venv/Scripts/python smoke_test.py
```

Runs the complete plan → search → evaluate → correct → synthesize loop against a
throwaway SQLite database. Uses real providers when keys are present, deterministic
mocks otherwise.

---

## 📡 API Reference

Base URL: `http://localhost:8000`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/research` | Start a session — body: `{ "goal": "...", "depth": "standard" \| "deep" }` |
| `GET` | `/api/research/history` | Last 50 sessions |
| `GET` | `/api/research/{id}` | Session snapshot — status, progress, live counters |
| `GET` | `/api/research/{id}/tasks` | Planned tasks with status |
| `GET` | `/api/research/{id}/searches` | All search records with relevance scores |
| `GET` | `/api/research/{id}/logs` | Full agent audit trail |
| `GET` | `/api/research/{id}/evidence` | Collected evidence, sorted by confidence |
| `GET` | `/api/research/{id}/report` | Final Markdown report (404 until ready) |
| `POST` | `/api/research/{id}/cancel` | Cancel a running session |
| `GET` | `/api/research/{id}/events` | 🔴 SSE live progress stream |
| `GET` | `/api/health` | Health check |

**Start a session:**

```bash
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"goal": "Compare the top 3 Python web frameworks in 2025", "depth": "standard"}'
```

**Watch it live:**

```bash
curl -N http://localhost:8000/api/research/<research_id>/events
```

<details>
<summary><strong>SSE event types</strong></summary>

| Event | Payload |
|-------|---------|
| `status` | `{status, progress, current_agent, current_task}` |
| `counters` | Authoritative counts pushed after every mutation |
| `plan_created` / `tasks_updated` / `task_updated` | Plan and per-task updates |
| `task_insufficient` | Task stopped — not enough evidence after all attempts |
| `search_started` / `search_completed` | Query, result count, top results |
| `results_evaluated` | `{query, score, status, reason}` |
| `correction_started` / `correction_completed` | `{query, reason}` / `{from, to}` |
| `evidence_collected` | Extracted claim + source |
| `report_completed` | `{research_id, content}` |
| `agent_log` | Audit entry (agent, action, input, output, duration) |
| `error` | `{message}` |

</details>

---

## 🗄️ Database Schema (6 tables)

| Table | Purpose |
|-------|---------|
| `researches` | One row per session — goal, depth, status, progress, live counters |
| `research_tasks` | Planner output — ordered tasks with per-task status/result |
| `searches` | Every search — query, attempt number, result count, relevance score, correction flag |
| `evidence` | Extracted facts — claim, source title/URL/domain, tier, confidence, verified flag |
| `agent_logs` | Complete audit trail — agent, action, input, output, status, duration |
| `reports` | Final Markdown reports (one per session) |

---

## ⚙️ Configuration

See [`backend/.env.example`](backend/.env.example) for the annotated template.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///./gentdesk.db` | PostgreSQL or SQLite connection string |
| `LLM_PROVIDER` | `auto` | `auto` / `gemini` / `openai` / `mock` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | — / `gemini-3.5-flash` | Gemini credentials |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | — / `gpt-4o-mini` | OpenAI fallback |
| `SEARCH_BACKEND` | `auto` | `auto` / `serper` / `tavily` / `duckduckgo` / `mock` |
| `SERPER_API_KEY` / `TAVILY_API_KEY` | — | Search provider keys |
| `RELEVANCE_THRESHOLD` | `0.5` | Minimum score for ACCEPTED |
| `MAX_RETRIES` / `MAX_ATTEMPTS_PER_TASK` | `3` / `3` | Retry limits |
| `MAX_QUERIES_PER_TASK` / `MAX_TASKS` | `3` / `10` | Plan size limits |
| `MAX_TOTAL_SEARCHES` / `MAX_EVIDENCE` | `40` / `30` | Session budgets |
| `GAP_RESEARCH_ENABLED` | `true` | Gap-driven second research pass |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins |
| `LLM_TIMEOUT` | `60` | LLM request timeout (seconds) |

---

## 📁 Project Structure

```
GentDesk/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entrypoint
│   │   ├── config.py         # Env-driven settings
│   │   ├── database.py       # SQLAlchemy engine + init_db()
│   │   ├── models.py         # 6 ORM tables
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── orchestrator.py   # Multi-agent coordination + limits
│   │   ├── event_bus.py      # In-memory SSE pub/sub
│   │   ├── llm.py            # Gemini / OpenAI / mock
│   │   ├── search.py         # Serper / Tavily / DDG / mock
│   │   ├── routers/research.py
│   │   └── agents/           # planner · research · evaluator · correction · synthesis
│   ├── smoke_test.py         # Offline end-to-end test
│   └── requirements.txt
├── frontend/
│   ├── app/                  # layout · home · research/[id]
│   ├── components/           # ResearchForm · ActivityFeed · EvidenceGrid · ReportView · …
│   ├── lib/                  # api.ts · types.ts · useResearch.ts (SSE hook)
│   └── package.json
├── FINAL_DOCUMENT.md         # In-depth technical documentation
└── README.md
```

---

## 📊 Example Session

> **Goal:** *"Research the top 3 competitors of Zoom and compare their pricing and major features."*

```
Planner      → 7 tasks: find competitors → verify → research each → verify pricing → report
Research     → "Zoom competitors pricing comparison 2026" → 8 results
Evaluator    → score 0.35 → REJECTED ("missing official pricing pages")
Correction   → refines query: adds competitor names + "official pricing"
Research     → re-search → Evaluator → score 0.89 → ACCEPTED ✓
Evidence     → 24 grounded claims from official domains (de-duplicated by URL)
Verification → pricing claims cross-checked against official sources ✓
Synthesis    → Executive Summary · Methodology · Key Findings · Comparison · Sources
─────────────────────────────────────────────────────────────
Searches: 11   Corrections: 2   Sources: 24   Tasks: 7/7   Status: COMPLETED ✓
```

Every step above is visible live in the dashboard and permanently queryable via the API.

---

## 🧪 Design Notes

- **Graceful LLM degradation** — every LLM call is wrapped with retries + exponential backoff + deterministic fallbacks, so a flaky provider degrades quality instead of crashing the session.
- **Cooperative cancellation** — checked at every phase boundary; the session stops cleanly between steps.
- **URL de-duplication** — evidence is de-duplicated by normalized URL; `MAX_EVIDENCE` caps the session.
- **UI never drifts** — the orchestrator pushes authoritative `counters` events so the dashboard always matches the database.
- **No fabricated reports** — zero evidence ⇒ hard failure with an actionable message.

---

## 🗺️ Roadmap

- [ ] Redis pub/sub for the event bus (multi-worker deployments)
- [ ] API authentication (JWT / API keys)
- [ ] PDF / DOCX report export
- [ ] Per-user session isolation and sharing
- [ ] Unit + contract test suite

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Built with FastAPI · Next.js · PostgreSQL · Gemini**

⭐ Star this repo if you find it useful!

</div>
