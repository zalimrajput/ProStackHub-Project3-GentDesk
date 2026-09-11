export function StatCard({
  label,
  value,
  icon,
  accent = "text-white",
}: {
  label: string;
  value: string | number;
  icon?: string;
  accent?: string;
}) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 transition hover:border-white/20 hover:bg-white/[0.07]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-6 -top-6 h-16 w-16 rounded-full bg-indigo-500/10 blur-2xl transition group-hover:bg-indigo-500/20"
      />
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
        {icon && <span className="text-sm transition group-hover:scale-110">{icon}</span>}
        {label}
      </div>
      <div className={`mt-1 text-xl font-bold tabular-nums ${accent}`}>{value}</div>
    </div>
  );
}
