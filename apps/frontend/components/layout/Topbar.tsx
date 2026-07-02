"use client";

import { useRouter } from "next/navigation";

import { logout } from "@/lib/auth";

type TopbarProps = {
  userName?: string;
  organizationName?: string;
};

export function Topbar({ userName, organizationName }: TopbarProps) {
  const router = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="flex h-16 items-center justify-between border-b border-white/10 bg-navy-950/95 px-6">
      <div>
        <p className="text-sm font-medium text-white">{userName || "VVE Engine"}</p>
        <p className="text-xs text-slate-400">{organizationName || "Área autenticada"}</p>
      </div>
      <button
        type="button"
        onClick={handleLogout}
        className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
      >
        Sair
      </button>
    </header>
  );
}
