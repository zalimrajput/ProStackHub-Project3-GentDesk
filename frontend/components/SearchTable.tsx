"use client";

import type { SearchRecord } from "@/lib/types";
import type { LiveSearchInfo } from "@/lib/useResearch";

type Row = {
  key: string;
  query: string;
  attempt: number;
  results: number;
  score: number | null;
  status: string;
  correction: boolean;
};

function scoreColor(score: number | null) {
  if (score == null) return "text-slate-500";
  if (score >= 0.7) return "text-emerald-300";
  if (score >= 0.4) return "text-amber-300";
  return "text-rose-300";
}

function scoreBg(score: number | null) {
  if (score == null) return "border-white/10 bg-white/5 text-slate-400";
  if (score >= 0.7) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (score >= 0.4) return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  return "border-rose-500/30 bg-rose-500/10 text-rose-300";
}

export function SearchTable({
  searches,
  liveSearches,
}: {
  searches: SearchRecord[];
  liveSearches: LiveSearchInfo[];
}) {
  const rows: Row[] = [
    ...searches.map((s) => ({
      key: `db-${s.id}`,
      query: s.query,
      attempt: s.attempt_number,
      results: s.result_count,
      score: s.relevance_score,
      status: s.status,
      correction: s.was_correction,
    })),
    ...liveSearches.map((s, i) => ({
      key: `live-${i}-${s.query}`,
      query: s.query,
      attempt: 0,
      results: s.result_count,
      score: s.score,
      status: s.status,
      correction: s.was_correction,
    })),
  ];

  if (rows.length === 0) {
    return (
      <div className="py-10 text-center">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-lg">
          🔎
        </div>
        <p className="text-sm text-slate-500">
          No searches yet — the Research Agent hasn't run.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-white/10 text-[11px] uppercase tracking-wider text-slate-500">
            <th className="py-2.5 pr-3 font-medium">Query</th>
            <th className="py-2.5 pr-3 font-medium">Results</th>
            <th className="py-2.5 pr-3 font-medium">Relevance</th>
            <th className="py-2.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className={`group border-b border-white/5 transition hover:bg-white/[0.04] ${
                row.correction ? "bg-rose-500/[0.06]" : ""
              }`}
            >
              <td className="max-w-md py-2.5 pr-3">
                <span className="block truncate font-mono text-xs text-slate-200">
                  {row.query}
                </span>
                {row.correction && (
                  <span className="mt-0.5 inline-flex items-center gap-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-medium text-rose-300">
                    🔁 refined query
                  </span>
                )}
              </td>
              <td className="py-2.5 pr-3 tabular-nums text-slate-300">
                {row.results}
              </td>
              <td className="py-2.5 pr-3">
                <span
                  className={`inline-block rounded-md border px-1.5 py-0.5 font-semibold tabular-nums ${scoreBg(row.score)}`}
                >
                  {row.score != null ? row.score.toFixed(2) : "—"}
                </span>
              </td>
              <td className="py-2.5">
                <span
                  className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                    row.status === "ACCEPTED"
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                      : row.status === "REJECTED"
                        ? "border-rose-500/30 bg-rose-500/10 text-rose-300"
                        : "border-white/10 bg-white/5 text-slate-400"
                  }`}
                >
                  {row.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
