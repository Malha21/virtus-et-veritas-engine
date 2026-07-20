type StatCardProps = {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "neutral" | "accent" | "violet";
};

const toneClasses = {
  neutral: "border-white/5 bg-white/[0.035]",
  accent: "border-accent-500/20 bg-gradient-to-br from-accent-500/15 to-transparent",
  violet: "border-violet-400/20 bg-gradient-to-br from-violet-400/15 to-transparent",
};

export function StatCard({ label, value, hint, tone = "neutral" }: StatCardProps) {
  return (
    <div className={`rounded-lg border p-5 shadow-premium ${toneClasses[tone]}`}>
      <p className="text-sm text-zinc-400">{label}</p>
      <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
      {hint ? <p className="mt-2 text-sm text-zinc-500">{hint}</p> : null}
    </div>
  );
}
