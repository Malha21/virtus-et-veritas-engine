type StatusBadgeProps = {
  label: string;
  tone?: "neutral" | "success" | "warning" | "progress";
};

const toneClasses = {
  neutral: "bg-white/[0.06] text-zinc-200",
  success: "bg-emerald-400/15 text-emerald-300",
  warning: "bg-accent-500/15 text-accent-400",
  progress: "bg-violet-400/15 text-violet-300",
};

export function StatusBadge({ label, tone = "neutral" }: StatusBadgeProps) {
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${toneClasses[tone]}`}>
      {label}
    </span>
  );
}
