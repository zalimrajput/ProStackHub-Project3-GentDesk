"use client";

import type { EvidenceItem, SourceTier } from "@/lib/types";

const TIER_META: Record<SourceTier, { label: string; className: string }> = {
  official: {
    label: "Official",
    className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  },
  high: {
    label: "Authoritative",
    className: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  },
  medium: {
    label: "Secondary",
    className: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  },
  low: {
    label: "Community/UGC",
    className: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  },
};

function tierMeta(tier: string) {
  return TIER_META[(tier as SourceTier) in TIER_META ? (tier as SourceTier) : "medium"];
}

function confidenceColor(score: number) {
  if (score >= 0.7) return "bg-gradient-to-r from-emerald-500 to-emerald-400";
  if (score >= 0.4) return "bg-gradient-to-r from-amber-500 to-amber-400";
  return "bg-gradient-to-r from-rose-500 to-rose-400";
}

function freshnessLabel(freshness: number) {
  if (freshness >= 0.9) return "current";
  if (freshness >= 0.7) return "recent";
  if (freshness >= 0.5) return "undated";
  return "older";
}

export function EvidenceGrid({ evidence }: { evidence: EvidenceItem[] }) {
  if (evidence.length === 0) {
    return (
      <div className="py-10 text-center">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-lg">
          🗂️
        </div>
        <p className="text-sm text-slate-500">No evidence collected yet.</p>
      </div>
    );
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {evidence.map((item) => {
        const meta = tierMeta(item.source_tier ?? "medium");
        return (
          <div
            key={item.id}
            className="glass glow-card group flex flex-col rounded-xl p-4 transition hover:-translate-y-0.5"
          >
            <p className="text-sm leading-relaxed text-slate-200">{item.claim}</p>

            {item.supporting_content &&
              item.supporting_content !== item.claim && (
                <p
                  className="mt-2 line-clamp-3 border-l-2 border-indigo-500/40 pl-2.5 text-xs italic leading-relaxed text-slate-400"
                  title={item.supporting_content}
                >
                  “{item.supporting_content}”
                </p>
              )}

            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span
                className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${meta.className}`}
                title={`Source authority: ${item.source_tier}`}
              >
                {meta.label}
              </span>
              {item.freshness != null && (
                <span
                  className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400"
                  title={`Estimated freshness: ${item.freshness.toFixed(2)}`}
                >
                  🕒 {freshnessLabel(item.freshness)}
                </span>
              )}
              <span className="max-w-[180px] truncate rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400">
                {item.source_domain}
              </span>
            </div>

            <div className="mt-2.5 flex items-center justify-between gap-2">
              <a
                href={item.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="min-w-0 truncate text-xs font-medium text-indigo-300 transition hover:text-indigo-200 hover:underline"
                title={item.source_url}
              >
                {item.source_title || item.source_domain}
              </a>
              <span className="shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-indigo-300">↗</span>
            </div>

            <div className="mt-3 border-t border-white/5 pt-2.5">
              <div className="mb-1 flex justify-between text-[10px] uppercase tracking-wide text-slate-500">
                <span>Confidence</span>
                <span className="font-semibold tabular-nums normal-case text-slate-300">
                  {item.confidence_score.toFixed(2)}
                  {item.verified && (
                    <span className="ml-1 text-emerald-400">· verified ✓</span>
                  )}
                </span>
              </div>
              <div className="h-1 w-full overflow-hidden rounded-full bg-black/40">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${confidenceColor(item.confidence_score)}`}
                  style={{
                    width: `${Math.round(item.confidence_score * 100)}%`,
                  }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
