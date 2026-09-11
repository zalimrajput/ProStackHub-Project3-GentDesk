import type {
  AgentLog,
  EvidenceItem,
  HistoryItem,
  ReportData,
  ResearchSnapshot,
  ResearchTask,
  SearchRecord,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      detail = await res.text();
    }
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    }),
};

export const researchApi = {
  start: (goal: string, depth: string) =>
    api.post<{ research_id: string; status: string }>("/api/research", {
      goal,
      depth,
    }),
  status: (id: string) => api.get<ResearchSnapshot>(`/api/research/${id}`),
  tasks: (id: string) => api.get<ResearchTask[]>(`/api/research/${id}/tasks`),
  searches: (id: string) =>
    api.get<SearchRecord[]>(`/api/research/${id}/searches`),
  logs: (id: string) => api.get<AgentLog[]>(`/api/research/${id}/logs`),
  evidence: (id: string) =>
    api.get<EvidenceItem[]>(`/api/research/${id}/evidence`),
  report: (id: string) => api.get<ReportData>(`/api/research/${id}/report`),
  history: () => api.get<HistoryItem[]>("/api/research/history"),
  cancel: (id: string) =>
    api.post<{ research_id: string; status: string }>(
      `/api/research/${id}/cancel`,
    ),
};