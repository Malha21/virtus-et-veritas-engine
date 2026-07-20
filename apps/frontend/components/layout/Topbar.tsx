"use client";

import { useRouter } from "next/navigation";

import { logout } from "@/lib/auth";

export function Topbar() {
  const router = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="flex h-16 items-center justify-end border-b border-white/5 bg-navy-950/95 px-6">
      <button
        type="button"
        onClick={handleLogout}
        className="rounded-md border border-white/5 px-3 py-2 text-sm text-zinc-200 transition hover:border-accent-500/40 hover:text-accent-400"
      >
        Sair
      </button>
    </header>
  );
}
