# GentDesk — Final Project Document

**Version 1.0 · September 2026**

**GentDesk** is a full-stack, multi-agent, autonomous AI research platform. A user describes a high-level research goal in plain language (e.g. *"Compare the top 3 competitors of Canva, including pricing and features"*), and GentDesk autonomously transforms that goal into an evidence-backed, structured report.

The defining capability of GentDesk is its **closed-loop autonomous research process**:

```
Plan → Search → Evaluate → Detect failure → Self-correct → Retry
     → Verify → Synthesize findings → Final report
```

Every step of that chain is transparently logged — searches, scores, corrections, evidence and agent actions are all persisted and streamed live to the UI for auditing and debugging.

---

## 1. The Five Agents

GentDesk is not a single AI call. It is a **pipeline of five specialized agents**, each handing its output to the next, with rejected work looping back for self-correction.

| # | Agent | Responsibility | Code |
|---|-------|----------------|------|
| 1 | **Planner Agent** | Decomposes the user's objective into an ordered list of concrete research tasks | `backend/app/agents/planner.py` |
| 2 | **Research Agent** | Turns each task into precise web-search queries and executes them through the search tool | `backend/app/agents/research.py` |
| 3 | **Evaluator Agent** | Scores search results 0.0–1.0, decides ACCEPTED / REJECTED, explains why, and extracts evidence claims | `backend/app/agents/evaluator.py` |
| 4 | **Correction Agent** | When a search is rejected, diagnoses the failure and produces a refined query for another attempt — the feedback loop | `backend/app/agents/correction.py` |
| 5 | **Synthesis Agent** | Combines all verified evidence into a structured Markdown final report; also runs the coverage/gap analysis | `backend/app/agents/synthesis.py` |

A sixth implicit actor, the **Orchestrator** (`backend/app/orchestrator.py`), coordinates the phases, enforces all execution limits, retries LLM calls safely, records the audit trail, and publishes every state change to the SSE event bus.

### Workflow

```
                        User Goal
                           │
                           ▼
                   ┌───────────────┐
                   │ Planner Agent │  decomposes the goal into research tasks
                   └───────┬───────┘
                           ▼
                   ┌───────────────┐
                   │ Research Agent│  generates precise search queries
                   └───────┬───────┘
                           ▼
                       Web Search
                  (Serper / Tavily / DDG)
                           ▼
                  ┌─────────────────┐
                  │ Evaluator Agent │  scores relevance 0.0–1.0
                  └───────┬─────────┘
              ACCEPTED?   │
        ┌────── NO ───────┴────── YES ──────┐
        ▼                                   ▼
┌────────────────┐                  Evidence stored
│ Correction     │                  (claims + sources in DB)
│ Agent: refine  │                        │
│ query & retry  │                  Verification pass
└───────┬────────┘                  (cross-checks pricing /
        │  loop back                low-confidence claims)
        ▼                                 │
   Research Agent                         ▼
                              ┌──────────────────┐
                              │ Synthesis Agent  │  writes the structured report
                              └───────┬──────────┘
                                      ▼
                                 Final Report + Audit Log
                     (every action recorded & streamed live to the UI)
```

### Agentic AI capabilities demonstrated

| Capability | How GentDesk does it |
|------------|----------------------|
| **Autonomy** | The system itself determines which research steps are needed after receiving only a goal. |
| **Planning** | The Planner Agent decomposes complex goals into ordered, web-searchable tasks. |
| **Tool Calling** | The Research Agent autonomously uses the web-search tool (Serper/Tavily/DuckDuckGo). |
| **Evaluation** | The Evaluator Agent scores and judges every batch of intermediate search results. |
| **Self-Correction** | The Correction Agent changes the search strategy whenever results are poor; the loop retries up to `MAX_ATTEMPTS_PER_TASK`. |
| **Evidence Banking** | Even when results are rejected overall, grounded facts from authoritative sources (score ≥ 0.3, non-UGC) are retained instead of discarded. |
| **Gap-Driven Second Pass** | After the main plan, the Synthesis Agent's `find_gaps` detects uncovered aspects of the goal and runs targeted follow-up tasks. |
| **Evidence-Based Generation** | The final report is built **only** from collected, verified evidence with source links — with zero evidence the Synthesis Agent refuses to fabricate and fails loudly. Gaps are flagged explicitly. |
| **Multi-Agent Collaboration** | Five specialized agents work together in a pipeline instead of a single monolithic AI call. |
| **Observability** | The complete chain of actions (agent, action, input, output, status, duration) is recorded to `agent_logs` and streamed live to the UI. |

---

## 2. System Architecture

```
┌─────────────────────────────── FRONTEND (Next.js @ :3000) ───────────────────────────────┐
│  /                       Home — research form + session history                          │
│  /research/[id]          Live session dashboard (Activity / Plan / Searches /            │
│                          Evidence / Report tabs) via SSE                                 │
└───────────────▲──────────────────────────────────────────────────────────▲──────────────┘
                │ REST (fetch)                                              │ EventSource (SSE)
┌───────────────┴──────────────────────────────────────────────────────────┴──────────────┐
│                                BACKEND (FastAPI @ :8000)                                 │
│                                                                                          │
│   routers/research.py ───► orchestrator.py ──► agents/ (planner, research,               │
│        (REST API)              │                  evaluator, correction, synthesis)      │
│                                │                 │                                      │
│                          event_bus.py          llm.py (Gemini / OpenAI / mock)          │
│                          (SSE pub/sub)         search.py (Serper / Tavily / DDG / mock)  │
│                                │                 │                                      │
└───────────────────────────────┼─────────────────┼──────────────────────────────────────┘
                                ▼                 ▼
                    ┌─────────────────────────────────────┐
                    │        PostgreSQL (Supabase)        │   researches · research_tasks
                    │   6 tables — full audit trail       │   searches · evidence
                    │                                     │   agent_logs · reports
                    └─────────────────────────────────────┘
```

### Technology stack

| Layer | Technology |
|-------|-----------|
| Backend API | **FastAPI (Python 3.11)** + SQLAlchemy 2.0 ORM |
| Orchestration | Custom async **Orchestrator** with an in-memory **event bus** (SSE) |
| LLM | **Google Gemini** (REST via httpx, no SDK) · OpenAI-compatible · deterministic mock |
| Web search | **Serper** (Google) · Tavily · DuckDuckGo (`ddgs`) · mock |
| Database | **PostgreSQL** (production, e.g. Supabase) — SQLite supported for zero-config dev |
| Frontend | **Next.js 14 (App Router)** + React 18 + TypeScript + Tailwind CSS |
| Real-time | Server-Sent Events (SSE) live progress stream with 15s keep-alive pings |

---

## 3. How a Session Runs — Request Flow in Code

1. `POST /api/research` — creates a `Research` row (status `PLANNING`), registers the SSE bus topic + cancellation flag, and fires the orchestrator as an async task.
2. **Phase 1 — Planning:** the Planner Agent decomposes the goal → `ResearchTask` rows; `plan_created` and `tasks_updated` events published; audit log written.
3. **Phase 2 — Research tasks:** for each task, the Research Agent generates up to `MAX_QUERIES_PER_TASK` queries. Each query is searched; the Evaluator scores the results:
   - **ACCEPTED** → evidence claims are extracted (`Evidence` rows, de-duplicated by normalized URL), the task is marked COMPLETED.
   - **REJECTED** → grounded facts from authoritative sources are still *banked* (partial-evidence retention), then the Correction Agent refines the query and the loop retries — up to `MAX_ATTEMPTS_PER_TASK` per task and `MAX_RETRIES` overall. If evidence remains insufficient, the task is marked **Insufficient Evidence** and surfaced in the report rather than silently dropped.
   - Authoritative counters are pushed to the UI after every search/evaluation/correction/evidence event (`counters` event) so the UI never drifts from the database.
4. **Phase 3 — Coverage pass (gap research):** `find_gaps` compares collected evidence against the goal; up to 3 follow-up tasks are executed in a second pass (`GAP_RESEARCH_ENABLED`).
5. **Phase 4 — Synthesis:** the Synthesis Agent writes the structured Markdown report (Executive Summary, Methodology, Key Findings, Comparison, Analysis, Conclusion, Sources), explicitly flagging insufficient-evidence topics → stored in `reports`. If **no** verifiable evidence was collected, the orchestrator raises a clear error instead of fabricating a report.
6. **Finalize:** session ends `COMPLETED` / `FAILED` / `CANCELLED`; progress (0–100), state transitions and agent activity are broadcast over SSE and persisted.

**Resilience built into the orchestrator:**
- Every LLM call is wrapped (`_generate_queries_safe`, `_evaluate_safe`, `_refine_safe`) with retries, exponential backoff, and deterministic fallbacks when the LLM is unavailable.
- Evaluation itself retries up to 3 times before degrading to a REJECTED verdict.
- Cancellation is checked at every phase boundary and cooperative checkpoint.

---

## 4. Complete Worked Example

> **User submits:** *"Research the top 3 competitors of Zoom and compare their pricing and major features."*

| Step | Actor | What happens |
|------|-------|--------------|
| 1 | Frontend | Goal submitted from `/` via `POST /api/research` → redirected to `/research/{id}` |
| 2 | API + DB | Session created: `res_ab12cd34ef`, status `PLANNING` |
| 3 | Planner Agent | Produces tasks: 1) find Zoom's main competitors → 2) verify list → 3–5) research each competitor (features + pricing) → 6) verify pricing → 7) generate comparison report |
| 4 | Research Agent | Generates and executes precise queries (e.g. *"Zoom competitors pricing comparison 2026"*) via Serper |
| 5 | Evaluator Agent | First attempt scores weakly: `score=0.35 → REJECTED` |
| 6 | Correction Agent | Diagnoses the failure ("missing competitor name / official pricing pages") and refines the query |
| 7 | Research Agent | Re-searches with the refined query |
| 8 | Evaluator Agent | `score=0.89 → ACCEPTED` |
| 9 | Evaluator Agent | Extracts evidence claims with sources → stored in `evidence` (claim, title, URL, domain, confidence, tier) |
| 10 | Orchestrator | Verification pass cross-checks pricing claims with targeted "official source" searches; confidence and `verified` flags updated |
| 11 | Synthesis Agent | Writes the final structured Markdown report |
| 12 | DB | Report + complete history (tasks, searches, evidence, `agent_logs`) persisted |
| 13 | Frontend | Dashboard shows: `Searches: 11 · Self-Corrections: 2 · Sources: 24 · Tasks 7/7` — plus the full report and audit trail |

---

## 5. Backend — FastAPI

### 5.1 Layout

```
backend/
├── .env / .env.example   # Configuration (see §8)
├── requirements.txt      # fastapi, uvicorn, sqlalchemy, psycopg2-binary,
│                         # pydantic, httpx, ddgs, python-dotenv
├── smoke_test.py         # End-to-end smoke test (throwaway SQLite DB)
└── app/
    ├── main.py           # FastAPI app entrypoint — lifespan runs init_db()
    ├── config.py         # Central settings (env vars + .env loading)
    ├── database.py       # SQLAlchemy engine, session factory, init_db()
    ├── models.py         # ORM models (6 tables)
    ├── schemas.py        # Pydantic request/response models
    ├── types.py          # Shared dataclasses (SearchResult, EvidenceItem, Evaluation)
    ├── orchestrator.py   # Agent coordination, limits, audit trail, SSE publishing
    ├── event_bus.py      # In-memory pub/sub queues for SSE
    ├── llm.py            # LLM client: Gemini / OpenAI / mock
    ├── search.py         # Web search tool: Serper / Tavily / DuckDuckGo / mock
    ├── mock.py           # Deterministic offline responses for LLM + search
    ├── routers/
    │   └── research.py   # REST + SSE endpoints
    └── agents/
        ├── planner.py    # Agent 1
        ├── research.py   # Agent 2
        ├── evaluator.py  # Agent 3
        ├── correction.py # Agent 4
        └── synthesis.py  # Agent 5
```

### 5.2 REST API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/research` | Start a session (body: `goal`, `depth` standard/deep, optional `user_id`) → `201 {research_id, status}` |
| `GET` | `/api/research/history` | List up to 50 past sessions (newest first) |
| `GET` | `/api/research/{id}` | Session snapshot (progress, counts, current agent & task) |
| `GET` | `/api/research/{id}/tasks` | Planned tasks with status and result |
| `GET` | `/api/research/{id}/searches` | All search records (query, attempt, score, correction flag) |
| `GET` | `/api/research/{id}/logs` | Full agent audit trail |
| `GET` | `/api/research/{id}/evidence` | Collected evidence, sorted by confidence (desc) |
| `GET` | `/api/research/{id}/report` | Final Markdown report (`404` until ready) |
| `POST` | `/api/research/{id}/cancel` | Request cancellation (400 if already terminal); logs a WARNING entry |
| `GET` | `/api/research/{id}/events` | SSE stream of live progress events |
| `GET` | `/api/health` | Health check → `{status: "ok", service: "gentdesk-api"}` |

### 5.3 SSE event types

| Event | Payload (data) |
|-------|----------------|
| `status` | `{status, progress, current_agent, current_task}` |
| `counters` | Authoritative counts (searches, corrections, sources, tasks) pushed after every mutation |
| `plan_created` | `{tasks: [...]}` |
| `tasks_updated` | `{tasks_total, tasks_completed}` (also fired when the gap pass adds tasks) |
| `task_updated` | `{task: {...}}` — one task's status/result changed (live Plan tab updates) |
| `task_insufficient` | `{task, attempts, max_attempts, reason}` |
| `search_started` | `{task, query, attempt, max_attempts}` |
| `search_completed` | `{task, query, result_count, attempt, max_attempts, top_results[≤5]}` |
| `results_evaluated` | `{query, score, status, reason, attempt, max_attempts}` |
| `correction_started` / `correction_completed` | `{query, reason, attempt, max_attempts}` / `{from, to, attempt, max_attempts}` |
| `evidence_collected` | `{evidence: {...}}` |
| `report_completed` | `{research_id, content}` |
| `agent_log` | `{log: {...}}` |
| `error` | `{message}` |

The SSE endpoint sends `: ping` comments every 15s to keep connections alive and unsubscribes cleanly on disconnect.

### 5.4 Execution limits (env-configurable — prevent infinite runs)

| Setting | Default | Meaning |
|---------|---------|---------|
| `RELEVANCE_THRESHOLD` | 0.7 in code (`.env.example` shows 0.5) | Minimum score for ACCEPTED |
| `MAX_RETRIES` | 3 | Max search→evaluate→correct retries |
| `MAX_ATTEMPTS_PER_TASK` | 3 | Hard cap on search/evaluate/correct cycles per task |
| `MAX_QUERIES_PER_TASK` | 3 | Queries generated per task |
| `MAX_TASKS` | 10 | Max tasks in a plan |
| `MAX_TOTAL_SEARCHES` | 40 | Global search budget per session |
| `MAX_EVIDENCE` | 30 | Max evidence items per session (de-duplicated by URL) |
| `SEARCH_RESULTS_PER_QUERY` | 8 | Results requested per search |
| `GAP_RESEARCH_ENABLED` | true | Gap-driven second research pass |

### 5.5 LLM client (`llm.py`)

`LLM_PROVIDER = auto | gemini | openai | mock`

- **auto** resolves to whichever key is set: Gemini first, then OpenAI, else mock.
- **Gemini** is called over REST (`generativelanguage.googleapis.com …/generateContent`) with `httpx` — no SDK dependency.
- Tolerant JSON extraction (`extract_json` / `parse_json_object` / `parse_json_list`) handles code fences and surrounding prose.
- Timeout: `LLM_TIMEOUT` (default 60s).

### 5.6 Web search (`search.py`)

`SEARCH_BACKEND = auto | serper | tavily | duckduckgo | mock`

- **Serper** — `POST https://google.serper.dev/search` with `X-API-KEY: SERPER_API_KEY`; maps `organic` results to `SearchResult`.
- **Tavily** — `api.tavily.com/search` with `TAVILY_API_KEY`.
- **DuckDuckGo** — free, via the `ddgs` library.
- **mock** — deterministic offline results so the whole platform runs with zero keys.
- **auto** picks Serper if its key is set, then Tavily, then DuckDuckGo.

---

## 6. Database — PostgreSQL

### 6.1 Connection & setup

- Production: **PostgreSQL** via `DATABASE_URL` (e.g. Supabase pooler), driver `psycopg2-binary`.
- Local dev fallback: **SQLite** (`sqlite:///./gentdesk.db`) — enabled transparently, with WAL mode.
- `database.py` builds the engine with `pool_pre_ping`; `init_db()` (called from the FastAPI lifespan in `main.py`) runs `Base.metadata.create_all()` so **all tables are created automatically at startup**.
- Sessions (`SessionLocal`) and the `get_db()` FastAPI dependency live in `database.py`. Orchestrator code uses short-lived `SessionLocal()` blocks to avoid holding connections across `await` points.

### 6.2 Schema — 6 tables (`models.py`)

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `researches` | One row per session | `id` (PK, `res_…`) · `user_id` · `goal` · `depth` · `status` (PLANNING/RESEARCHING/VERIFYING/SYNTHESIZING/COMPLETED/FAILED/CANCELLED) · `progress` (0–100) · `current_agent` · `current_task` · `searches_count` · `corrections_count` · `sources_count` · `error` · `created_at` · `completed_at` |
| `research_tasks` | Planned tasks (Planner output) | `research_id` (FK) · `task` · `status` (PENDING/IN_PROGRESS/COMPLETED/FAILED) · `order_index` · `result` · timestamps |
| `searches` | Every search executed | `research_id` (FK) · `task_id` (FK) · `query` · `attempt_number` · `result_count` · `relevance_score` · `status` (COMPLETED/FAILED/REJECTED/ACCEPTED) · `was_correction` · `created_at` |
| `evidence` | Extracted, verified facts | `research_id` (FK) · `task_id` (FK) · `claim` · `source_title` · `source_url` · `source_domain` · `source_tier` (official/high/medium/low) · `supporting_content` · `freshness` · `confidence_score` (0–1) · `verified` · `created_at` |
| `agent_logs` | Complete audit trail | `research_id` (FK) · `agent_name` · `action` · `input` · `output` · `status` (OK/WARNING/ERROR) · `timestamp` · `duration_ms` |
| `reports` | Final reports | `research_id` (FK, unique — one per session) · `content` (Markdown) · `created_at` |

A `research` **has many** tasks / searches / evidence / logs and **has one** report; children cascade-delete with the parent.

---

## 7. Frontend — Next.js

### 7.1 Pages & structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout — aurora background, glass header/footer,
│   │                           #   Inter + JetBrains Mono via next/font
│   ├── page.tsx                # Home — hero, research form, session history
│   ├── research/[id]/page.tsx  # Live session dashboard (5 tabs, SSE-driven)
│   └── globals.css             # Design system: aurora blobs, glass utilities,
│                               #   glow cards, gradient text, shimmer, keyframes
├── components/
│   ├── ResearchForm.tsx        # Goal input + depth selector + example chips
│   ├── HistoryList.tsx         # Past sessions (click to reopen, staggered fade-in)
│   ├── AgentPipeline.tsx       # Live workflow strip: Planner → Research → …
│   ├── ProgressBar.tsx         # 0–100 progress with shimmering gradient fill
│   ├── StatusBadge.tsx         # Status pill with colored ping dot
│   ├── StatCard.tsx            # Search/correction/source/task/evidence counters
│   ├── ActivityFeed.tsx        # Live agent audit log with timeline spine
│   ├── SearchTable.tsx         # Queries + relevance chips + correction marks
│   ├── EvidenceGrid.tsx        # Claims grid: tier badges, confidence bars, sources
│   ├── ReportView.tsx          # Rendered Markdown (typography plugin, polished)
│   └── WorkflowDiagram.tsx     # no-op placeholder
├── lib/
│   ├── api.ts                  # API base URL + typed REST client
│   ├── types.ts                # Shared TS types (mirror of Pydantic schemas)
│   └── useResearch.ts          # Data hook — REST bootstrap + SSE live merge
├── .env                        # NEXT_PUBLIC_API_URL=http://localhost:8000
├── tailwind.config.ts          # Design tokens: fonts, shadows, animations, keyframes
└── package.json                # Next.js 14.2 · React 18.3 · TypeScript 5.5 · Tailwind 3.4
```

### 7.2 Design system

The UI uses a **dark "aurora glassmorphism"** theme:

- **Aurora background** — three fixed, slowly drifting gradient blobs (indigo / fuchsia / emerald) behind a dot grid and vignette (`.aurora-*` utilities in `globals.css`).
- **Glass surfaces** — `.glass` / `.glass-strong` (translucent gradient + backdrop blur + inner highlight), `.glow-card` gradient hairline border that lights up on hover.
- **Typography** — Inter for UI, JetBrains Mono for IDs/queries/timestamps (`next/font`, exposed as `--font-sans` / `--font-mono`).
- **Motion** — `fade-up` entrance animations (staggered on lists), `shimmer` accent lines and progress fill, `bounce-soft` active pipeline icons, ping dots for live status.
- **Accents** — per-agent colors are consistent everywhere: Planner = sky, Research = indigo, Evaluator = amber, Correction = rose, Synthesis = fuchsia, Verification = emerald.

### 7.3 Key behavior

- **Home (`/`)** — submits a goal via `POST /api/research`, then routes to `/research/{id}`; shows recent history from `GET /api/research/history`.
- **Session page (`/research/[id]`)** — the `useResearch` hook loads snapshot/tasks/searches/evidence/logs via REST, then opens an `EventSource` to `/api/research/{id}/events` and merges live events: status & counters update the hero, `task_updated` mutates plan rows in place, `agent_log` appends (de-duplicated by ID), `search_completed` + `results_evaluated` build live search rows, `evidence_collected` appends cards, `report_completed` fills the Report tab. Partial `status` events only merge non-null fields so counters never blank out. On terminal status the stream closes and the report is fetched.
- **Tabs** — Activity (audit feed), Plan (task checklist with per-status styling and ✓ markers), Searches (queries + relevance chips, flagged corrections), Evidence (claims grid with tier badges + confidence bars), Report (Markdown, enabled once available).
- **Cancellation** — a running session can be cancelled from the header; the orchestrator stops at its next checkpoint.
- The frontend is fully typed against `lib/types.ts`, mirroring the backend's Pydantic response models, and talks to the backend through `NEXT_PUBLIC_API_URL`.
- `npm run build` passes cleanly (type-check + lint + static generation).

---

## 8. Configuration (`.env`)

The backend reads settings from `backend/.env` (loaded by `python-dotenv` in `config.py`; real shell environment variables take precedence). See `backend/.env.example` for the template.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (or `sqlite:///./gentdesk.db` for dev) |
| `LLM_PROVIDER` | `auto` / `gemini` / `openai` / `mock` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini API key and model (e.g. `gemini-3.5-flash`) |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Optional OpenAI fallback |
| `SEARCH_BACKEND` | `auto` / `serper` / `tavily` / `duckduckgo` / `mock` |
| `SERPER_API_KEY` / `TAVILY_API_KEY` | Search provider keys |
| `RELEVANCE_THRESHOLD`, `MAX_RETRIES`, `MAX_ATTEMPTS_PER_TASK`, `MAX_QUERIES_PER_TASK`, `MAX_TASKS`, `MAX_TOTAL_SEARCHES`, `MAX_EVIDENCE`, `SEARCH_RESULTS_PER_QUERY`, `GAP_RESEARCH_ENABLED` | Orchestrator execution limits |
| `CORS_ORIGINS` | Allowed frontend origin(s), comma-separated (default `http://localhost:3000`) |
| `LLM_TIMEOUT` | LLM request timeout in seconds |

Frontend config: `frontend/.env` → `NEXT_PUBLIC_API_URL=http://localhost:8000` (default when unset).

> 🔒 **Security note:** real credentials (a Supabase database URL and what appears to be a Gemini API key) were found committed in `backend/.env.example`. Templates must contain placeholders only — rotate both credentials and sanitize the file (see §11).

---

## 9. Running the Project

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt    # Windows
# .venv/bin/pip install -r requirements.txt      # macOS/Linux
# ensure backend/.env has DATABASE_URL + API keys (see .env.example)
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

Startup runs `init_db()`, creating all 6 tables in the configured database if missing. Swagger docs: `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
# or production:
npm run build && npm start
```

### Smoke test (end-to-end, throwaway SQLite DB)

```bash
cd backend
.venv/Scripts/python smoke_test.py
```

Runs the full planner → research → evaluate → correct → synthesis loop against a `smoke_…` session ID; uses real providers when keys are present, deterministic mocks otherwise — so it works fully offline with no configuration.

---

## 10. Current Live Configuration

| Component | Status |
|-----------|--------|
| Database | **PostgreSQL 17.6** (Supabase, ap-southeast-2) — connected; all **6 tables created** and verified |
| Web search | **Serper** — key configured; verified live (returns real Google results) |
| LLM | **Gemini** (`LLM_PROVIDER=auto` + `GEMINI_API_KEY`, model `gemini-3.5-flash`) |
| Backend | Boots cleanly; `/api/health` → `200 {status: ok}`; `init_db()` runs against Postgres at startup |
| Frontend | `npm run build` passes (type-check + lint); restyled "aurora glass" UI; `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| Observability | Full audit trail persisted per session and streamed live over SSE |

---

## 11. Known Limitations & Recommended Next Steps

| Area | Current state | Recommendation |
|------|---------------|----------------|
| **Secrets hygiene** | ✅ Resolved — `.env.example` now uses placeholders; real `.env` files and DB/log artifacts are excluded via `.gitignore`. **Note:** the credentials were previously exposed in an earlier working state — rotate the Supabase password and Gemini key if they were ever shared |
| **Stray artifacts** | ✅ Resolved — dev SQLite files (`debug*.db`, `loop_check.db`, `res_check.json`, `uvicorn.log`, `.bak`) are gitignored; optionally delete them from disk |
| **Event bus scope** | In-memory per-process pub/sub | For multi-worker deployments, move to Redis pub/sub or a Postgres LISTEN/NOTIFY channel |
| **Auth** | `user_id` is accepted but not authenticated | Add API-key or JWT auth before exposing publicly |
| **SSE fan-out** | One EventSource per session page | Fine at current scale; consider pagination for very long audit trails |
| **Testing** | Single end-to-end smoke script | Add unit tests for agents (mock LLM) and API contract tests |
