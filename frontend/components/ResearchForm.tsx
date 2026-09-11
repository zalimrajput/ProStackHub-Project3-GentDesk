"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { researchApi } from "@/lib/api";

const EXAMPLES = [
  "Research the top 3 competitors of Canva and compare their pricing, key features, and target users.",
  "Compare the top 3 Python web frameworks in 2025 and their performance characteristics.",
  "Research the leading AI meeting assistants and their core capabilities.",
];

export function ResearchForm() {
  const router = useRouter();
  const [goal, setGoal] = useState("");
  const [depth, setDepth] = useState("standard");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = goal.trim();
    if (trimmed.length < 3 || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await researchApi.start(trimmed, depth);
      router.push(`/research/${res.research_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  const ready = goal.trim().length >= 3;

  return (
    <form
      onSubmit={start}
      className="glass-strong glow-card relative overflow-hidden rounded-2xl p-6 sm:p-7"
    >
      {/* Corner accent glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-indigo-500/15 blur-3xl"
      />

      <label
        htmlFor="goal"
        className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200"
      >
        What would you like me to research?
      </label>
      <textarea
        id="goal"
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        placeholder="Research the top 3 competitors of Canva and compare their pricing and features…"
        rows={4}
        className="w-full resize-none rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm leading-relaxed text-slate-100 shadow-inner outline-none transition placeholder:text-slate-600 focus:border-indigo-400/60 focus:bg-black/40 focus:ring-4 focus:ring-indigo-500/15"
      />

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/30 px-3 py-1.5 text-sm transition focus-within:border-indigo-400/60">
          <span className="text-slate-500">Depth</span>
          <select
            value={depth}
            onChange={(e) => setDepth(e.target.value)}
            className="cursor-pointer rounded-lg bg-transparent py-0.5 text-sm font-medium text-slate-200 outline-none focus:ring-0 [&>option]:bg-slate-900"
          >
            <option value="standard">Standard</option>
            <option value="deep">Deep</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={submitting || !ready}
          className="group relative overflow-hidden rounded-xl bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-600 px-6 py-2.5 text-sm font-semibold text-white shadow-glow transition-all hover:shadow-glow-lg hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none disabled:hover:brightness-100 disabled:active:scale-100"
        >
          <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
          <span className="relative flex items-center gap-2">
            {submitting ? (
              <>
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                Starting…
              </>
            ) : (
              <>
                Start Research
                <span className="transition-transform group-hover:translate-x-0.5">→</span>
              </>
            )}
          </span>
        </button>
      </div>

      {error && (
        <p className="mt-3 rounded-xl border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </p>
      )}

      <div className="mt-5 border-t border-white/5 pt-4">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-slate-500">
          Try an example
        </p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex, i) => (
            <button
              key={ex}
              type="button"
              onClick={() => setGoal(ex)}
              className="max-w-full truncate rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 transition-all hover:scale-[1.03] hover:border-indigo-400/50 hover:bg-indigo-500/10 hover:text-indigo-200 active:scale-95"
              title={ex}
            >
              <span className="mr-1.5 text-slate-500">{i + 1}.</span>
              {ex.slice(0, 48)}…
            </button>
          ))}
        </div>
      </div>
    </form>
  );
}
