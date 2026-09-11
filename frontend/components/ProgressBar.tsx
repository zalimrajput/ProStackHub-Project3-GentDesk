export function ProgressBar({ progress }: { progress: number }) {
  const clamped = Math.max(0, Math.min(100, progress));
  return (
    <div className="w-full">
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="font-medium uppercase tracking-wider text-slate-500">
          Progress
        </span>
        <span className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 font-semibold tabular-nums text-slate-200">
          {clamped}%
        </span>
      </div>
      <div className="relative h-2.5 w-full overflow-hidden rounded-full border border-white/5 bg-black/40">
        {/* animated shimmer inside the filled portion */}
        <div
          className="relative h-full rounded-full bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 transition-all duration-700 ease-out"
          style={{ width: `${clamped}%` }}
        >
          {clamped > 0 && clamped < 100 && (
            <div
              className="absolute inset-0 rounded-full opacity-60"
              style={{
                backgroundImage:
                  "linear-gradient(90deg, transparent, rgba(255,255,255,0.35), transparent)",
                backgroundSize: "200% 100%",
                animation: "shimmer 1.8s linear infinite",
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
