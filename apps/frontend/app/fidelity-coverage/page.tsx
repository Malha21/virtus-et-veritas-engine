"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import type { ProjectListItem, ProjectListResponse } from "@/types/project";

const NOT_AVAILABLE = "—";

export default function FidelityCoveragePage() {
  const [data, setData] = useState<ProjectListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    apiFetch<ProjectListResponse>("/projects?page=1&page_size=100")
      .then(setData)
      .catch(() => setError("Não foi possível carregar os projetos."))
      .finally(() => setLoading(false));
  }, []);

  const projects = useMemo(() => data?.items || [], [data]);

  const statusOptions = useMemo(() => {
    const unique = new Set(projects.map((project) => project.status));
    return Array.from(unique);
  }, [projects]);

  const filteredProjects = useMemo(() => {
    return projects.filter((project) => {
      const matchesSearch = project.title.toLowerCase().includes(search.trim().toLowerCase());
      const matchesStatus = statusFilter === "all" || project.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [projects, search, statusFilter]);

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <div>
          <p className="text-sm text-gold-400">Fidelidade e Cobertura</p>
          <h1 className="mt-2 text-3xl font-semibold">Fidelidade e Cobertura</h1>
          <p className="mt-2 max-w-3xl text-slate-400">
            Gerencie a rastreabilidade entre os documentos originais, os conteúdos identificados, os
            módulos, as aulas e as validações de fidelidade de todos os projetos.
          </p>
        </div>

        <GlobalMetrics />

        {loading ? (
          <p className="mt-8 text-slate-300">Carregando projetos...</p>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : !projects.length ? (
          <div className="mt-8">
            <EmptyState
              title="Nenhuma análise de fidelidade disponível"
              description="As análises aparecerão aqui após o processamento dos documentos dos projetos."
              action={
                <>
                  <Link
                    href="/projects/new"
                    className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-gold-400"
                  >
                    Criar novo projeto
                  </Link>
                  <Link
                    href="/projects"
                    className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 hover:border-gold-500/40"
                  >
                    Abrir projetos
                  </Link>
                </>
              }
            />
          </div>
        ) : (
          <>
            <div className="mt-8 rounded-md border border-gold-500/20 bg-gold-500/10 p-4 text-sm text-gold-200">
              Nenhuma análise de fidelidade disponível ainda. As análises aparecerão aqui após o
              processamento e a auditoria dos documentos de cada projeto.
            </div>

            <Filters
              search={search}
              onSearchChange={setSearch}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
              statusOptions={statusOptions}
            />

            <ProjectsTable projects={filteredProjects} />
          </>
        )}
      </div>
    </AppShell>
  );
}

function GlobalMetrics() {
  const metrics: { label: string; hint: string }[] = [
    { label: "Projetos analisados", hint: "Aguardando integração com a auditoria" },
    { label: "Inventário concluído", hint: "Aguardando integração com a auditoria" },
    { label: "Aguardando auditoria", hint: "Aguardando integração com a auditoria" },
    { label: "Com pendências", hint: "Aguardando integração com a auditoria" },
    { label: "Aprovados", hint: "Aguardando integração com a auditoria" },
    { label: "Cobertura média", hint: "Aguardando integração com a auditoria" },
    { label: "Itens sem cobertura", hint: "Aguardando integração com a auditoria" },
    { label: "Afirmações sem fonte", hint: "Aguardando integração com a auditoria" },
    { label: "Aulas acima de 10 min", hint: "Aguardando integração com a auditoria" },
  ];

  return (
    <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {metrics.map((metric) => (
        <StatCard key={metric.label} label={metric.label} value={NOT_AVAILABLE} hint={metric.hint} />
      ))}
    </div>
  );
}

type FiltersProps = {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  statusOptions: string[];
};

function Filters({ search, onSearchChange, statusFilter, onStatusFilterChange, statusOptions }: FiltersProps) {
  const disabledFilters = ["Com pendências", "Aprovados", "Ainda não analisados", "Data da última análise"];

  return (
    <div className="mt-6 flex flex-wrap items-center gap-3">
      <input
        type="text"
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        placeholder="Buscar por nome do projeto"
        className="w-full max-w-xs rounded-md border border-white/10 bg-navy-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-gold-500/40 focus:outline-none"
      />
      <select
        value={statusFilter}
        onChange={(event) => onStatusFilterChange(event.target.value)}
        className="rounded-md border border-white/10 bg-navy-950/60 px-3 py-2 text-sm text-slate-100 focus:border-gold-500/40 focus:outline-none"
      >
        <option value="all">Todos os status</option>
        {statusOptions.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>

      {disabledFilters.map((label) => (
        <button
          key={label}
          type="button"
          disabled
          title="Disponível em breve, após a auditoria de fidelidade"
          className="cursor-not-allowed rounded-md border border-white/5 px-3 py-2 text-sm text-slate-500"
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function ProjectsTable({ projects }: { projects: ProjectListItem[] }) {
  if (!projects.length) {
    return (
      <div className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-8 text-center">
        <p className="text-slate-300">Nenhum projeto encontrado para os filtros selecionados.</p>
      </div>
    );
  }

  return (
    <div className="mt-6 overflow-x-auto rounded-lg border border-white/10 bg-white/[0.035]">
      <table className="w-full min-w-[920px] text-left text-sm">
        <thead className="border-b border-white/10 text-slate-400">
          <tr>
            <th className="px-5 py-4 font-medium">Projeto</th>
            <th className="px-5 py-4 font-medium">Documento principal</th>
            <th className="px-5 py-4 font-medium">Última atualização</th>
            <th className="px-5 py-4 font-medium">Itens identificados</th>
            <th className="px-5 py-4 font-medium">Cobertura</th>
            <th className="px-5 py-4 font-medium">Fidelidade</th>
            <th className="px-5 py-4 font-medium">Pendências</th>
            <th className="px-5 py-4 font-medium">Status</th>
            <th className="px-5 py-4 font-medium">Ação</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id} className="border-b border-white/5">
              <td className="px-5 py-4 font-medium text-white">{project.title}</td>
              <td className="px-5 py-4 text-slate-500">{NOT_AVAILABLE}</td>
              <td className="px-5 py-4 text-slate-400">
                {new Date(project.updated_at).toLocaleDateString("pt-BR")}
              </td>
              <td className="px-5 py-4 text-slate-500">{NOT_AVAILABLE}</td>
              <td className="px-5 py-4 text-slate-500">{NOT_AVAILABLE}</td>
              <td className="px-5 py-4 text-slate-500">{NOT_AVAILABLE}</td>
              <td className="px-5 py-4 text-slate-500">{NOT_AVAILABLE}</td>
              <td className="px-5 py-4">
                <StatusBadge label={project.status} tone={project.status === "active" ? "success" : "neutral"} />
              </td>
              <td className="px-5 py-4">
                <Link href={`/fidelity-coverage/${project.id}`} className="text-gold-400 hover:text-gold-500">
                  Ver detalhes
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
