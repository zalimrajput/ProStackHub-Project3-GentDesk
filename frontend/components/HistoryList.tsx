"use client";

import Link from "next/link";

import type { HistoryItem } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function HistoryList({ items }: { items: HistoryItem[] }) {
  if (items.length === 0) {
    return (
      <div className="glass rounded-2xl px-6 py-10 text-center">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-white/5 text-xl">
          🧪
        </div>
        <p className="text-sm text-slate-400">
          No research sessions yet.
        </p>
        <p className="mt-1 text-xs text-slate-600">
          Start your first one above — the pipeline will show up here.
        </p>
      </div>
    );
  }
  return (
    <ul className="space-y-2.5">
      {items.map((item, i) => (
        <li key={item.id} className="animate-fade-up" style={{ animationDelay: `${Math.min(i * 40, 240)}ms` }}>
          <Link
            href={`/research/${item.id}`}
            className="glass glow-card group flex items-center justify-between gap-4 rounded-xl px-4 py-3.5 transition hover:-translate-y-0.5"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-100 transition group-hover:text-indigo-200">
                {item.goal}
              </p>
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-500">
                <span className="text-slate-600">·</span>
                {item.searches_count} searches
                <span className="text-slate-700">·</span>
                {item.corrections_count} corrections
                <span className="text-slate-700">·</span>
                {item.sources_count} sources
                <span className="text-slate-700">·</span>
                <span className="tabular-nums">
                  {item.tasks_completed}/{item.tasks_total} tasks
                </span>
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span className="hidden rounded-md border border-white/5 bg-white/5 px-2 py-0.5 font-mono text-[11px] text-slate-500 sm:block">
                {fmtDate(item.created_at)}
              </span>
              <StatusBadge status={item.status} />
              <span className="hidden text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-indigo-300 sm:block">
                →
              </span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
