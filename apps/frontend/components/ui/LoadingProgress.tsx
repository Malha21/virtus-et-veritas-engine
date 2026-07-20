"use client";

import { useEffect, useState } from "react";

type LoadingProgressProps = {
  label?: string;
  size?: "block" | "inline";
};

export function LoadingProgress({ label = "Carregando...", size = "block" }: LoadingProgressProps) {
  const [percent, setPercent] = useState(0);

  useEffect(() => {
    setPercent(0);
    const interval = window.setInterval(() => {
      setPercent((current) => {
        if (current >= 92) return current;
        const step = Math.max(1, Math.round((92 - current) * 0.12));
        return Math.min(92, current + step);
      });
    }, 220);
    return () => window.clearInterval(interval);
  }, []);

  if (size === "inline") {
    return (
      <span className="inline-flex items-center gap-2 text-sm text-zinc-400">
        {label}
        <span className="font-mono text-xs text-accent-400">{percent}%</span>
      </span>
    );
  }

  return (
    <div className="w-full max-w-sm">
      <div className="flex items-center justify-between text-sm text-zinc-300">
        <span>{label}</span>
        <span className="font-mono text-xs text-accent-400">{percent}%</span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-white/10">
        <div
          className="h-2 rounded-full bg-accent-500 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
