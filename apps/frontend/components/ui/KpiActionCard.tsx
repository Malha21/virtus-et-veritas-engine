import Link from "next/link";
import type { LucideIcon } from "lucide-react";

type Tone = "neutral" | "accent" | "violet" | "red";

const toneClasses: Record<Tone, string> = {
  neutral: "border-white/5 bg-white/[0.035] hover:border-accent-500/40",
  accent: "border-accent-500/20 bg-gradient-to-br from-accent-500/15 to-transparent hover:border-accent-500/40",
  violet: "border-violet-400/20 bg-gradient-to-br from-violet-400/15 to-transparent hover:border-violet-400/40",
  red: "border-red-400/30 bg-red-500/5 hover:border-red-300/60",
};

const iconToneClasses: Record<Tone, string> = {
  neutral: "text-accent-400",
  accent: "text-accent-400",
  violet: "text-violet-300",
  red: "text-red-300",
};

const activeClasses = "border-accent-500/60 bg-accent-500/15";

type BaseProps = {
  icon: LucideIcon;
  label: string;
  hint?: string;
  tone?: Tone;
  active?: boolean;
  disabled?: boolean;
  size?: "sm" | "md";
};

type KpiActionCardProps = BaseProps & ({ href: string; onClick?: undefined } | { href?: undefined; onClick: () => void });

export function KpiActionCard({
  icon: Icon,
  label,
  hint,
  tone = "neutral",
  active = false,
  disabled = false,
  size = "md",
  href,
  onClick,
}: KpiActionCardProps) {
  const isSmall = size === "sm";
  const layoutClasses = isSmall ? "flex-row items-center gap-2 px-3 py-2.5" : "flex-col gap-2 p-3.5";
  const className = `flex shrink-0 rounded-lg border text-left shadow-premium transition disabled:cursor-not-allowed disabled:opacity-60 ${layoutClasses} ${
    active ? activeClasses : toneClasses[tone]
  }`;

  const content = (
    <>
      <Icon
        className={`${isSmall ? "h-3.5 w-3.5" : "h-4 w-4"} shrink-0 ${active ? "text-accent-300" : iconToneClasses[tone]}`}
        strokeWidth={1.8}
        aria-hidden="true"
      />
      <span className={isSmall ? "text-xs font-medium text-white" : "text-sm font-semibold text-white"}>{label}</span>
      {hint && !isSmall ? <span className="text-xs text-zinc-500">{hint}</span> : null}
    </>
  );

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} disabled={disabled} className={className}>
      {content}
    </button>
  );
}
