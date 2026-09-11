"use client";

const PIPELINE = [
  { key: "planner", label: "Planner", icon: "🧭" },
  { key: "research", label: "Research", icon: "🔎" },
  { key: "evaluator", label: "Evaluator", icon: "⚖️" },
  { key: "correction", label: "Correction", icon: "🔁" },
  { key: "synthesis", label: "Synthesis", icon: "✍️" },
] as const;

type AgentKey = (typeof PIPELINE)[number]["key"];

const ACCENT: Record<AgentKey, string> = {
  planner: "border-sky-400/40 bg-sky-500/10 text-sky-200 shadow-[0_0_16px_-4px_rgba(56,189,248,0.5)]",
  research: "border-indigo-400/40 bg-indigo-500/10 text-indigo-200 shadow-[0_0_16px_-4px_rgba(129,140,248,0.5)]",
  evaluator: "border-amber-400/40 bg-amber-500/10 text-amber-200 shadow-[0_0_16px_-4px_rgba(251,191,36,0.4)]",
  correction: "border-rose-400/40 bg-rose-500/10 text-rose-200 shadow-[0_0_16px_-4px_rgba(251,113,133,0.4)]",
  synthesis: "border-fuchsia-400/40 bg-fuchsia-500/10 text-fuchsia-200 shadow-[0_0_16px_-4px_rgba(232,121,249,0.4)]",
};

/**
 * Workflow strip: Planner → Research → Evaluator → (Correction → Research →
 * Evaluator on rejection) → Synthesis.
 *
 * The active agent is driven by the backend's per-step `current_agent` state;
 * the Correction → Research loop renders naturally because the backend flips
 * current_agent back to "research" on every retry attempt.
 */
export function AgentPipeline({
  currentAgent,
  status,
}: {
  currentAgent: string | null;
  status: string;
}) {
  if (["COMPLETED", "FAILED", "CANCELLED"].includes(status)) return null;

  const activeKey = (currentAgent ?? "").toLowerCase() as AgentKey;
  const plannerDone = activeKey !== "planner";
  const synthesisActive = activeKey === "synthesis";

  return (
    <div className="mt-4 flex flex-wrap items-center gap-1.5 text-xs">
      {PIPELINE.map((step, i) => {
        const isActive = step.key === activeKey;
        const isCorrection = step.key === "correction";
        const done =
          (step.key === "planner" && plannerDone) ||
          (isCorrection && synthesisActive) ||
          (step.key === "synthesis" && false);
        return (
          <span key={step.key} className="flex items-center gap-1.5">
            {i > 0 && (
              <span
                className={`transition ${done || isActive ? "text-indigo-400/70" : "text-slate-700"}`}
              >
                →
              </span>
            )}
            <span
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium backdrop-blur-sm transition-all duration-300 ${
                isActive
                  ? ACCENT[step.key]
                  : done
                    ? "border-white/10 bg-white/5 text-slate-400"
                    : "border-white/5 bg-transparent text-slate-600"
              } ${isActive ? "animate-pulse scale-105" : ""}`}
              title={
                isActive
                  ? "Currently running"
                  : isCorrection
                    ? "Runs only when the Evaluator rejects results, then Research runs again"
                    : undefined
              }
            >
              <span className={isActive ? "animate-bounce-soft" : ""}>{step.icon}</span>
              {step.label}
            </span>
          </span>
        );
      })}
    </div>
  );
}
