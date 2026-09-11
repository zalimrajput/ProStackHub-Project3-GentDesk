import type { ResearchStatus } from "@/lib/types";

const STYLES: Record<ResearchStatus, { label: string; dot: string; cls: string }> = {
  PLANNING: { label: "Planning", dot: "bg-sky-400", cls: "bg-sky-500/10 text-sky-300 border-sky-500/30" },
  RESEARCHING: { label: "Researching", dot: "bg-indigo-400", cls: "bg-indigo-500/10 text-indigo-300 border-indigo-500/30" },
  VERIFYING: { label: "Verifying", dot: "bg-amber-400", cls: "bg-amber-500/10 text-amber-300 border-amber-500/30" },
  SYNTHESIZING: { label: "Synthesizing", dot: "bg-fuchsia-400", cls: "bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/30" },
  COMPLETED: { label: "Completed", dot: "bg-emerald-400", cls: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30" },
  FAILED: { label: "Failed", dot: "bg-red-400", cls: "bg-red-500/10 text-red-300 border-red-500/30" },
  CANCELLED: { label: "Cancelled", dot: "bg-slate-400", cls: "bg-slate-500/10 text-slate-400 border-slate-500/30" },
};

export function StatusBadge({ status }: { status: ResearchStatus }) {
  const s = STYLES[status] ?? STYLES.FAILED;
  const active =
    status === "PLANNING" ||
    status === "RESEARCHING" ||
    status === "VERIFYING" ||
    status === "SYNTHESIZING";
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium backdrop-blur-sm ${s.cls}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {active && (
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${s.dot}`} />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${s.dot}`} />
      </span>
      {s.label}
    </span>
  );
}
