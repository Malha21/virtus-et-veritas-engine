"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";

import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { apiFetch } from "@/lib/api";
import { getToken, removeToken } from "@/lib/auth";
import type { CurrentUser } from "@/types/auth";

type AppShellProps = {
  children: ReactNode | ((user: CurrentUser) => ReactNode);
};

export function AppShell({ children }: AppShellProps) {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    apiFetch<CurrentUser>("/auth/me", { token })
      .then(setUser)
      .catch(() => {
        removeToken();
        router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-navy-950 text-slate-200">
        Carregando área segura...
      </main>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <main className="flex min-h-screen bg-navy-950 text-white">
      <Sidebar role={user.role} />
      <section className="min-w-0 flex-1">
        <Topbar userName={user.name} organizationName={user.organization.name} />
        <div className="p-6">{typeof children === "function" ? children(user) : children}</div>
      </section>
    </main>
  );
}
