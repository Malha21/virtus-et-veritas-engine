"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { StatCard } from "@/components/ui/StatCard";
import { apiFetch } from "@/lib/api";
import type { CurrentUser } from "@/types/auth";
import type { ProjectListResponse } from "@/types/project";

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectListResponse | null>(null);

  useEffect(() => {
    apiFetch<ProjectListResponse>("/projects?page=1&page_size=100")
      .then(setProjects)
      .catch(() => setProjects(null));
  }, []);

  return (
    <AppShell>
      {(user: CurrentUser) => {
        const items = projects?.items || [];
        const completed = items.filter((item) => item.processing_status === "completed").length;
        const processing = items.filter((item) =>
          ["queued", "extracting_text", "analyzing", "generating_structure"].includes(item.processing_status),
        ).length;

        return (
          <div className="mx-auto max-w-6xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm text-gold-400">Dashboard</p>
                <h1 className="mt-2 text-3xl font-semibold">Olá, {user.name}</h1>
                <p className="mt-2 text-slate-400">{user.organization.name}</p>
              </div>

              <div className="flex gap-3">
                <Link
                  href="/projects"
                  className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 hover:border-gold-500/40"
                >
                  Ver Projetos
                </Link>
                <Link
                  href="/projects/new"
                  className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-gold-400"
                >
                  Novo Projeto
                </Link>
              </div>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Projetos criados" value={projects?.total ?? 0} />
              <StatCard label="Cursos concluídos" value={completed} />
              <StatCard label="Em processamento" value={processing} />
              <StatCard label="Exportações geradas" value={0} hint="Fase futura" />
            </div>
          </div>
        );
      }}
    </AppShell>
  );
}
