"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE, researchApi } from "./api";
import type {
  AgentLog,
  EvidenceItem,
  ReportData,
  ResearchSnapshot,
  ResearchTask,
  SearchRecord,
} from "./types";

const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export interface LiveSearchInfo {
  query: string;
  result_count: number;
  score: number | null;
  status: string;
  was_correction: boolean;
}

export function useResearch(id: string) {
  const [snapshot, setSnapshot] = useState<ResearchSnapshot | null>(null);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [searches, setSearches] = useState<SearchRecord[]>([]);
  const [liveSearches, setLiveSearches] = useState<LiveSearchInfo[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [report, setReport] = useState<ReportData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  const esRef = useRef<EventSource | null>(null);
  const seenLogIds = useRef<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      researchApi.status(id),
      researchApi.logs(id),
      researchApi.searches(id),
      researchApi.evidence(id),
      researchApi.tasks(id),
    ])
      .then(([snap, ls, ss, ev, ts]) => {
        if (cancelled) return;
        setSnapshot(snap);
        setLogs(ls);
        setSearches(ss);
        setEvidence(ev);
        setTasks(ts);
        ls.forEach((l) => seenLogIds.current.add(l.id));
        setLoading(false);

        if (TERMINAL.has(snap.status)) {
          if (snap.status === "COMPLETED") {
            researchApi
              .report(id)
              .then(setReport)
              .catch(() => setReport(null));
          }
          return;
        }

        // Stream live events for active sessions.
        const es = new EventSource(`${API_BASE}/api/research/${id}/events`);
        esRef.current = es;
        es.onopen = () => setConnected(true);

        es.addEventListener("status", (e) => {
          const data = JSON.parse((e as MessageEvent).data);
          setSnapshot((prev) =>
            prev
              ? {
                  ...prev,
                  // Only merge defined fields so partial events never blank
                  // out counters or resurrect stale status messages.
                  ...Object.fromEntries(
                    Object.entries(data).filter(([, v]) => v != null),
                  ),
                }
              : prev,
          );
          if (data.status && TERMINAL.has(data.status)) {
            es.close();
            setConnected(false);
            if (data.status === "COMPLETED") {
              researchApi
                .report(id)
                .then(setReport)
                .catch(() => setReport(null));
            }
          }
        });

        // Authoritative counter sync pushed by the orchestrator after every
        // search / evaluation / correction / evidence event.
        es.addEventListener("counters", (e) => {
          const data = JSON.parse((e as MessageEvent).data) as Partial<ResearchSnapshot>;
          setSnapshot((prev) => (prev ? { ...prev, ...data } : prev));
        });

        // The plan just arrived (live session joined before planning finished).
        es.addEventListener("plan_created", () => {
          researchApi
            .tasks(id)
            .then(setTasks)
            .catch(() => {});
        });

        // A task's status/result changed → update it in place so the Plan
        // tab shows live progress (IN_PROGRESS → COMPLETED/FAILED per task)
        // instead of freezing on the first task forever.
        es.addEventListener("task_updated", (e) => {
          const { task } = JSON.parse((e as MessageEvent).data) as {
            task: ResearchTask;
          };
          setTasks((prev) => {
            const idx = prev.findIndex((t) => t.id === task.id);
            if (idx === -1) return [...prev, task];
            const next = [...prev];
            next[idx] = task;
            return next;
          });
        });

        // A new task may have been added by the gap-driven second pass.
        es.addEventListener("tasks_updated", () => {
          researchApi
            .tasks(id)
            .then(setTasks)
            .catch(() => {});
        });

        es.addEventListener("agent_log", (e) => {
          const { log } = JSON.parse((e as MessageEvent).data) as {
            log: AgentLog;
          };
          if (seenLogIds.current.has(log.id)) return;
          seenLogIds.current.add(log.id);
          setLogs((prev) => [...prev, log]);
        });

        es.addEventListener("search_completed", (e) => {
          const data = JSON.parse((e as MessageEvent).data) as {
            query: string;
            result_count: number;
          };
          setLiveSearches((prev) => [
            ...prev,
            {
              query: data.query,
              result_count: data.result_count,
              score: null,
              status: "COMPLETED",
              was_correction: false,
            },
          ]);
        });

        es.addEventListener("results_evaluated", (e) => {
          const data = JSON.parse((e as MessageEvent).data) as {
            query: string;
            score: number;
            status: string;
          };
          setLiveSearches((prev) => {
            const next = [...prev];
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].query === data.query && next[i].score === null) {
                next[i] = {
                  ...next[i],
                  score: data.score,
                  status: data.status,
                };
                break;
              }
            }
            return next;
          });
        });

        es.addEventListener("correction_completed", (e) => {
          const data = JSON.parse((e as MessageEvent).data) as {
            from: string;
            to: string;
          };
          setLiveSearches((prev) =>
            prev.map((s) =>
              s.query === data.from ? { ...s, was_correction: true } : s,
            ),
          );
        });

        es.addEventListener("evidence_collected", (e) => {
          const { evidence: item } = JSON.parse((e as MessageEvent).data) as {
            evidence: EvidenceItem;
          };
          setEvidence((prev) =>
            prev.some((x) => x.id === item.id) ? prev : [...prev, item],
          );
        });

        es.addEventListener("report_completed", (e) => {
          const data = JSON.parse((e as MessageEvent).data) as ReportData;
          setReport(data);
        });

        // NOTE: the browser also fires "error" for connection failures (no data);
        // only react to server-sent error events that carry a JSON payload.
        es.addEventListener("error", (e) => {
          const raw = (e as MessageEvent).data;
          if (!raw) return;
          try {
            const data = JSON.parse(raw) as { message: string };
            setError(data.message);
          } catch {
            /* not a server error event */
          }
        });

        // Reconnect never happens: onerror leaves EventSource in its
        // built-in retry loop; once the server closes the stream the
        // status event above terminates the session.
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      esRef.current?.close();
    };
  }, [id]);

  const refresh = useCallback(() => {
    researchApi
      .status(id)
      .then(setSnapshot)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
  }, [id]);

  return {
    snapshot,
    logs,
    searches,
    liveSearches,
    evidence,
    tasks,
    report,
    error,
    connected,
    loading,
    refresh,
  };
}