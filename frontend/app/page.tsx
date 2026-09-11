"use client";

import { useEffect, useState } from "react";

import { HistoryList } from "@/components/HistoryList";
import { ResearchForm } from "@/components/ResearchForm";
import { researchApi } from "@/lib/api";
import type { HistoryItem } from "@/lib/types";

export default function HomePage() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    researchApi
      .history()
      .then(setHistory)
      .catch((err: unknown) =>
        setHistoryError(err instanceof Error ? err.message : String(err)),
      );
  }, []);

  return (
    <div className="mx-auto max-w-3xl">
      <section className="mb-10 animate-fade-up text-center">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-indigo-500/25 bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-300">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-indigo-400" />
          </span>
          Multi-agent pipeline · live audit trail
        </div>
        <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
          Autonomous{" "}
          <span className="text-gradient">Research</span>{" "}
          Agent
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-slate-400 sm:text-[15px]">
          Describe a research goal in plain language. GentDesk plans the
          research, runs web searches, evaluates results, self-corrects poor
          queries, collects evidence, and writes a structured report — all with
          a transparent audit trail.
        </p>
      </section>

      <section className="animate-fade-up [animation-delay:80ms]">
        <ResearchForm />
      </section>

      {historyError && (
        <p className="mt-6 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-xs text-red-300 backdrop-blur">
          Could not load history: {historyError}
        </p>
      )}

      <section id="history" className="mt-14 animate-fade-up [animation-delay:160ms]">
        <div className="mb-4 flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Research History</h2>
          <div className="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent" />
          {history.length > 0 && (
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] tabular-nums text-slate-400">
              {history.length}
            </span>
          )}
        </div>
        <HistoryList items={history} />
      </section>
    </div>
  );
}
