type StatusBadgeProps = {
  label: string;
  tone?: "neutral" | "success" | "warning";
};

const toneClasses = {
  neutral: "border-white/10 bg-white/[0.04] text-slate-200",
  success: "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
  warning: "border-gold-500/20 bg-gold-500/10 text-gold-400",
};

export function StatusBadge({ label, tone = "neutral" }: StatusBadgeProps) {
  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${toneClasses[tone]}`}>
      {label}
    </span>
  );
}
