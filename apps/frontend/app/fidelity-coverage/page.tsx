"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  apiFetch,
  getCoveragePlanSummary,
  getDocumentExtractionSummary,
  getSourceInventorySummary,
} from "@/lib/api";
import type { CoveragePlanSummary } from "@/types/coverage-plan";
import type { DocumentExtractionSummary } from "@/types/document-extraction";
import type { ProjectFile } from "@/types/file";
import type { ProjectListItem, ProjectListResponse } from "@/types/project";
import type { SourceInventorySummary } from "@/types/source-inventory";

const NOT_AVAILABLE = "—";

type ProjectFidelityRow = {
  project: ProjectListItem;
  file: ProjectFile | null;
  extraction: DocumentExtractionSummary | null;
  inventory: SourceInventorySummary | null;
  coverage: CoveragePlanSummary | null;
};

async function loadProjectFidelity(project: ProjectListItem): Promise<ProjectFidelityRow> {
  const files = await apiFetch<ProjectFile[]>(`/projects/${project.id}/files`).catch(() => []);
  const file = files[0] || null;

  if (!file) {
    return { project, file: null, extraction: null, inventory: null, coverage: null };
  }

  const [extraction, inventory, coverage] = await Promise.all([
    getDocumentExtractionSummary(project.id, file.id).catch(() => null),
    getSourceInventorySummary(project.id, file.id).catch(() => null),
    getCoveragePlanSummary(project.id, file.id).catch(() => null),
  ]);

  return { project, file, extraction, inventory, coverage };
}

export default function FidelityCoveragePage() {
  const [rows, setRows] = useState<ProjectFidelityRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    apiFetch<ProjectListResponse>("/projects?page=1&page_size=100")
      .then(async (data) => {
        const loaded = await Promise.all(data.items.map(loadProjectFidelity));
        setRows(loaded);
      })
      .catch(() => setError("Não foi possível carregar os projetos."))
      .finally(() => setLoading(false));
  }, []);

  const allRows = useMemo(() => rows || [], [rows]);

  const statusOptions = useMemo(() => {
    const unique = new Set(allRows.map((row) => row.project.status));
    return Array.from(unique);
  }, [allRows]);

  const filteredRows = useMemo(() => {
    return allRows.filter((row) => {
      const matchesSearch = row.project.title.toLowerCase().includes(search.trim().toLowerCase());
      const matchesStatus = statusFilter === "all" || row.project.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [allRows, search, statusFilter]);

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Fidelidade e Cobertura</p>
          <h1 className="mt-2 text-3xl font-semibold">Fidelidade e Cobertura</h1>
          <p className="mt-2 max-w-3xl text-zinc-400">
            Gerencie a rastreabilidade entre os documentos originais, os conteúdos identificados, os
            módulos, as aulas e as validações de fidelidade de todos os projetos.
          </p>
        </div>

        <GlobalMetrics rows={allRows} loading={loading} />

        {loading ? (
          <div className="mt-8">
            <LoadingProgress label="Carregando projetos..." />
          </div>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : !allRows.length ? (
          <div className="mt-8">
            <EmptyState
              title="Nenhuma análise de fidelidade disponível"
              description="As análises aparecerão aqui após o processamento dos documentos dos projetos."
              action={
                <>
                  <Link
                    href="/projects/new"
                    className="rounded-md bg-accent-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow"
                  >
                    Criar novo projeto
                  </Link>
                  <Link
                    href="/projects"
                    className="rounded-md border border-white/5 px-4 py-2 text-sm text-zinc-200 hover:border-accent-500/40"
                  >
                    Abrir projetos
                  </Link>
                </>
              }
            />
          </div>
        ) : (
          <>
            <Filters
              search={search}
              onSearchChange={setSearch}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
              statusOptions={statusOptions}
            />

            <ProjectsTable rows={filteredRows} />
          </>
        )}
      </div>
    </AppShell>
  );
}

function average(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function GlobalMetrics({ rows, loading }: { rows: ProjectFidelityRow[]; loading: boolean }) {
  const analyzed = rows.filter((row) => row.extraction && row.extraction.status !== "not_started").length;
  const inventoryDone = rows.filter(
    (row) => row.inventory && ["completed", "partially_completed"].includes(row.inventory.status),
  ).length;
  const awaitingAudit = rows.filter(
    (row) => row.inventory && row.inventory.status !== "not_started" && (!row.coverage || row.coverage.status === "not_started"),
  ).length;
  const withPendencies = rows.filter(
    (row) => (row.inventory?.requires_review_items || 0) > 0 || (row.coverage?.unmapped_items || 0) > 0,
  ).length;
  const approved = rows.filter((row) => row.coverage?.status === "approved").length;
  const coveragePercentages = rows
    .map((row) => row.inventory?.page_coverage_percentage)
    .filter((value): value is number => typeof value === "number");
  const avgCoverage = average(coveragePercentages);
  const itemsWithoutCoverage = rows.reduce((sum, row) => sum + (row.coverage?.unmapped_items || 0), 0);

  const metrics: { label: string; value: string; hint?: string }[] = [
    { label: "Projetos analisados", value: loading ? NOT_AVAILABLE : String(analyzed) },
    { label: "Inventário concluído", value: loading ? NOT_AVAILABLE : String(inventoryDone) },
    { label: "Aguardando auditoria", value: loading ? NOT_AVAILABLE : String(awaitingAudit) },
    { label: "Com pendências", value: loading ? NOT_AVAILABLE : String(withPendencies) },
    { label: "Aprovados", value: loading ? NOT_AVAILABLE : String(approved) },
    {
      label: "Cobertura média",
      value: loading || avgCoverage === null ? NOT_AVAILABLE : `${avgCoverage.toFixed(1)}%`,
    },
    { label: "Itens sem cobertura", value: loading ? NOT_AVAILABLE : String(itemsWithoutCoverage) },
    { label: "Afirmações sem fonte", value: NOT_AVAILABLE, hint: "Aguardando integração com a auditoria" },
    { label: "Aulas acima de 10 min", value: NOT_AVAILABLE, hint: "Aguardando integração com a auditoria" },
  ];

  return (
    <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {metrics.map((metric) => (
        <StatCard key={metric.label} label={metric.label} value={metric.value} hint={metric.hint} />
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
  return (
    <div className="mt-6 flex flex-wrap items-center gap-3">
      <input
        type="text"
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        placeholder="Buscar por nome do projeto"
        className="w-full max-w-xs rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-accent-500/40 focus:outline-none"
      />
      <select
        value={statusFilter}
        onChange={(event) => onStatusFilterChange(event.target.value)}
        className="rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
      >
        <option value="all">Todos os status</option>
        {statusOptions.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>
    </div>
  );
}

const COVERAGE_STATUS_LABEL: Record<string, string> = {
  not_started: "Não iniciado",
  pending: "Na fila",
  processing: "Processando",
  generated: "Gerado",
  requires_review: "Requer revisão",
  invalid: "Inválido",
  ready_for_review: "Pronto para revisão",
  approved: "Aprovado",
  stale: "Desatualizado",
  failed: "Falhou",
};

function fidelityTone(status: string | undefined): "neutral" | "success" | "warning" {
  if (status === "approved") return "success";
  if (!status || status === "not_started") return "neutral";
  if (["invalid", "failed", "requires_review", "stale"].includes(status)) return "warning";
  return "neutral";
}

function ProjectsTable({ rows }: { rows: ProjectFidelityRow[] }) {
  if (!rows.length) {
    return (
      <div className="mt-6 rounded-lg border border-white/5 bg-white/[0.035] p-8 text-center">
        <p className="text-zinc-300">Nenhum projeto encontrado para os filtros selecionados.</p>
      </div>
    );
  }

  return (
    <div className="mt-6 overflow-x-auto rounded-lg border border-white/5 bg-white/[0.035]">
      <table className="w-full min-w-[920px] text-left text-sm">
        <thead className="border-b border-white/5 text-zinc-400">
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
          {rows.map(({ project, file, inventory, coverage }) => {
            const pendencies = (inventory?.requires_review_items || 0) + (coverage?.unmapped_items || 0);
            return (
              <tr key={project.id} className="border-b border-white/5">
                <td className="px-5 py-4 font-medium text-white">{project.title}</td>
                <td className="max-w-[220px] truncate px-5 py-4 text-zinc-400" title={file?.original_filename}>
                  {file?.original_filename || NOT_AVAILABLE}
                </td>
                <td className="px-5 py-4 text-zinc-400">
                  {new Date(project.updated_at).toLocaleDateString("pt-BR")}
                </td>
                <td className="px-5 py-4 text-zinc-300">{inventory?.total_items ?? NOT_AVAILABLE}</td>
                <td className="px-5 py-4 text-zinc-300">
                  {inventory ? `${inventory.page_coverage_percentage.toFixed(0)}%` : NOT_AVAILABLE}
                </td>
                <td className="px-5 py-4">
                  <StatusBadge
                    label={coverage ? COVERAGE_STATUS_LABEL[coverage.status] || coverage.status : NOT_AVAILABLE}
                    tone={fidelityTone(coverage?.status)}
                  />
                </td>
                <td className="px-5 py-4 text-zinc-300">{file ? pendencies : NOT_AVAILABLE}</td>
                <td className="px-5 py-4">
                  <StatusBadge label={project.status} tone={project.status === "active" ? "success" : "neutral"} />
                </td>
                <td className="px-5 py-4">
                  <Link href={`/fidelity-coverage/${project.id}`} className="text-accent-400 hover:text-accent-500">
                    Ver detalhes
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
