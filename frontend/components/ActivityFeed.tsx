"use client";

import type { AgentLog } from "@/lib/types";

const AGENT_META: Record<string, { icon: string; color: string; ring: string }> = {
  "Planner Agent": { icon: "🧭", color: "text-sky-300", ring: "bg-sky-500/15" },
  "Research Agent": { icon: "🔎", color: "text-indigo-300", ring: "bg-indigo-500/15" },
  "Evaluator Agent": { icon: "⚖️", color: "text-amber-300", ring: "bg-amber-500/15" },
  "Correction Agent": { icon: "🔁", color: "text-rose-300", ring: "bg-rose-500/15" },
  "Synthesis Agent": { icon: "✍️", color: "text-fuchsia-300", ring: "bg-fuchsia-500/15" },
  "Verification Agent": { icon: "✔️", color: "text-emerald-300", ring: "bg-emerald-500/15" },
  Orchestrator: { icon: "🎛️", color: "text-slate-300", ring: "bg-white/10" },
};

function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

export function ActivityFeed({ logs }: { logs: AgentLog[] }) {
  if (logs.length === 0) {
    return (
      <div className="py-10 text-center">
        <div className="mx-auto mb-3 flex h-10 w-10 animate-pulse-slow items-center justify-center rounded-xl bg-white/5 text-lg">
          🎛️
        </div>
        <p className="text-sm text-slate-500">
          No agent activity yet — the orchestrator is starting…
        </p>
      </div>
    );
  }
  return (
    <ol className="relative space-y-0.5">
      {/* vertical timeline spine */}
      <span
        aria-hidden="true"
        className="absolute bottom-3 left-[17px] top-3 w-px bg-gradient-to-b from-indigo-500/40 via-white/10 to-transparent"
      />
      {logs.map((log) => {
        const meta = AGENT_META[log.agent_name] ?? {
          icon: "🤖",
          color: "text-slate-300",
          ring: "bg-white/10",
        };
        const isWarning = log.status === "WARNING";
        const isError = log.status === "ERROR";
        return (
          <li
            key={log.id}
            className="group relative flex gap-3 rounded-xl px-2 py-2 transition hover:bg-white/[0.04]"
            title={
              log.input || log.output
                ? `Input: ${log.input ?? "—"}\nOutput: ${log.output ?? "—"}`
                : undefined
            }
          >
            <span
              className={`relative z-10 mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/10 text-sm shadow-md ${meta.ring} ${meta.color} transition group-hover:scale-110`}
            >
              {meta.icon}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className={`text-sm font-medium ${meta.color}`}>
                  {log.agent_name}
                </span>
                <span className="shrink-0 rounded-md border border-white/5 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                  {fmtTime(log.timestamp)}
                </span>
              </div>
              <div className="text-sm leading-relaxed text-slate-300">{log.action}</div>
              {log.duration_ms != null && log.duration_ms > 0 && (
                <div className="mt-0.5 inline-flex items-center gap-1 rounded-md bg-white/5 px-1.5 py-0.5 text-[11px] tabular-nums text-slate-500">
                  ⏱ {(log.duration_ms / 1000).toFixed(1)}s
                </div>
              )}
            </div>
            {(isWarning || isError) && (
              <span
                className={`self-start rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                  isError
                    ? "border-red-500/30 bg-red-500/15 text-red-300"
                    : "border-amber-500/30 bg-amber-500/15 text-amber-300"
                }`}
              >
                {isError ? "Error" : "⚠"}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
