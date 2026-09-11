"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ActivityFeed } from "@/components/ActivityFeed";
import { AgentPipeline } from "@/components/AgentPipeline";
import { EvidenceGrid } from "@/components/EvidenceGrid";
import { ProgressBar } from "@/components/ProgressBar";
import { ReportView } from "@/components/ReportView";
import { SearchTable } from "@/components/SearchTable";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { researchApi } from "@/lib/api";
import { useResearch } from "@/lib/useResearch";

const TABS = ["Activity", "Plan", "Searches", "Evidence", "Report"] as const;
type Tab = (typeof TABS)[number];

export default function ResearchPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const {
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
  } = useResearch(id);
  const [tab, setTab] = useState<Tab>("Activity");
  const [cancelling, setCancelling] = useState(false);

  const active =
    snapshot != null &&
    !["COMPLETED", "FAILED", "CANCELLED"].includes(snapshot.status);

  const plannedTasks = useMemo(
    () => [...tasks].sort((a, b) => a.order_index - b.order_index),
    [tasks],
  );

  async function cancel() {
    if (!snapshot || cancelling) return;
    setCancelling(true);
    try {
      await researchApi.cancel(id);
    } catch {
      setCancelling(false);
    }
  }

  if (loading || !snapshot) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-center">
        <div className="relative h-12 w-12">
          <div className="absolute inset-0 animate-spin rounded-full border-2 border-indigo-500/30 border-t-indigo-400" />
          <div className="absolute inset-2 animate-spin rounded-full border-2 border-fuchsia-500/30 border-b-fuchsia-400 [animation-direction:reverse] [animation-duration:1.4s]" />
        </div>
        <p className="mt-5 animate-pulse text-sm text-slate-400">
          Loading research session…
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl animate-fade-up">
      <div className="mb-4 flex items-center justify-between gap-3">
        <Link
          href="/"
          className="group inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-slate-300 transition hover:border-indigo-400/40 hover:text-indigo-200"
        >
          <span className="transition group-hover:-translate-x-0.5">←</span>
          New Research
        </Link>
        <div className="flex items-center gap-3">
          <span className="hidden rounded-md border border-white/5 bg-white/5 px-2 py-1 font-mono text-xs text-slate-500 sm:block">
            {id}
          </span>
          <StatusBadge status={snapshot.status} />
          {active && (
            <button
              onClick={cancel}
              disabled={cancelling}
              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 transition hover:border-rose-500/50 hover:bg-rose-500/10 hover:text-rose-300 disabled:opacity-50"
            >
              {cancelling ? "Cancelling…" : "Cancel"}
            </button>
          )}
        </div>
      </div>

      {/* Hero / status card */}
      <div className="glass-strong relative mb-6 overflow-hidden rounded-2xl p-6">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-indigo-500/15 blur-3xl"
        />
        <div className="flex items-start justify-between gap-4">
          <h1 className="max-w-3xl text-xl font-semibold leading-snug text-white">
            {snapshot.goal}
          </h1>
          {connected && (
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
              </span>
              live
            </span>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
          <span className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 capitalize">
            depth: {snapshot.depth}
          </span>
        </div>

        {active && (
          <AgentPipeline currentAgent={snapshot.current_agent} status={snapshot.status} />
        )}
        {active && snapshot.current_task && (
          <p
            className="mt-2 max-w-xl truncate text-xs text-slate-400"
            title={snapshot.current_task}
          >
            <span className="mr-1 text-slate-600">▸</span>
            {snapshot.current_task}
          </p>
        )}

        <div className="mt-5">
          <ProgressBar progress={snapshot.progress} />
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatCard label="Searches" value={snapshot.searches_count} icon="🔎" />
          <StatCard
            label="Corrections"
            value={snapshot.corrections_count}
            icon="🔁"
            accent={
              snapshot.corrections_count > 0 ? "text-rose-300" : undefined
            }
          />
          <StatCard label="Sources" value={snapshot.sources_count} icon="🔗" />
          <StatCard
            label="Tasks"
            value={`${snapshot.tasks_completed}/${snapshot.tasks_total}`}
            icon="📋"
          />
          <StatCard label="Evidence" value={evidence.length} icon="🗂️" />
        </div>

        {error && (
          <p className="mt-4 rounded-xl border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {error}
          </p>
        )}
      </div>

      {/* Tab bar */}
      <div className="glass mb-4 flex flex-wrap gap-1 rounded-xl p-1.5">
        {TABS.map((t) => {
          const disabled = t === "Report" && !report;
          const badge =
            t === "Evidence" && evidence.length > 0
              ? evidence.length
              : t === "Searches" && searches.length + liveSearches.length > 0
                ? searches.length + liveSearches.length
                : null;
          const isActive = tab === t;
          return (
            <button
              key={t}
              disabled={disabled}
              onClick={() => setTab(t)}
              className={`relative rounded-lg px-4 py-1.5 text-sm font-medium transition-all ${
                isActive
                  ? "bg-gradient-to-r from-indigo-500/25 to-fuchsia-500/20 text-white shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)] ring-1 ring-indigo-400/30"
                  : disabled
                    ? "cursor-not-allowed text-slate-600"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`}
            >
              {t}
              {badge != null && (
                <span
                  className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] tabular-nums ${
                    isActive
                      ? "bg-indigo-400/20 text-indigo-200"
                      : "bg-white/10 text-slate-300"
                  }`}
                >
                  {badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div className="glass rounded-2xl p-4 sm:p-6" key={tab}>
        <div className="animate-fade-in">
          {tab === "Activity" && <ActivityFeed logs={logs} />}
          {tab === "Plan" && (
            <ol className="space-y-2">
              {plannedTasks.map((t, i) => (
                <li
                  key={t.id}
                  className="group flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.03] px-3.5 py-3 transition hover:border-white/15 hover:bg-white/[0.06]"
                >
                  <span
                    className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition ${
                      t.status === "COMPLETED"
                        ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                        : t.status === "IN_PROGRESS"
                          ? "animate-pulse border-indigo-400/40 bg-indigo-500/15 text-indigo-300"
                          : "border-white/10 bg-white/5 text-slate-400"
                    }`}
                  >
                    {t.status === "COMPLETED" ? "✓" : i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm leading-relaxed text-slate-200">{t.task}</p>
                    {t.result && (
                      <p className="mt-1 border-l-2 border-white/10 pl-2 text-xs leading-relaxed text-slate-500">
                        {t.result}
                      </p>
                    )}
                  </div>
                  <span
                    className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                      t.status === "COMPLETED"
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                        : t.status === "FAILED"
                          ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                          : t.status === "IN_PROGRESS"
                            ? "border-indigo-500/30 bg-indigo-500/10 text-indigo-300"
                            : "border-white/10 bg-white/5 text-slate-400"
                    }`}
                  >
                    {t.status === "FAILED"
                      ? "Insufficient Evidence"
                      : t.status === "IN_PROGRESS"
                        ? "Running"
                        : t.status}
                  </span>
                </li>
              ))}
              {plannedTasks.length === 0 && (
                <div className="py-10 text-center">
                  <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-lg">
                    🧭
                  </div>
                  <p className="text-sm text-slate-500">
                    The Planner Agent hasn't created the plan yet.
                  </p>
                </div>
              )}
            </ol>
          )}
          {tab === "Searches" && (
            <SearchTable searches={searches} liveSearches={liveSearches} />
          )}
          {tab === "Evidence" && <EvidenceGrid evidence={evidence} />}
          {tab === "Report" &&
            (report ? (
              <ReportView content={report.content} />
            ) : (
              <div className="py-10 text-center">
                <div className="mx-auto mb-3 flex h-10 w-10 animate-pulse-slow items-center justify-center rounded-xl bg-white/5 text-lg">
                  ✍️
                </div>
                <p className="text-sm text-slate-500">
                  The report isn't ready yet — the Synthesis Agent is still
                  working.
                </p>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
