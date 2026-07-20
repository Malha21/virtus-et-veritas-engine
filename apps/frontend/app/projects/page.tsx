"use client";

import { useEffect, useState } from "react";
import { FolderOpen, Trash2 } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { KpiActionCard } from "@/components/ui/KpiActionCard";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch, deleteProject } from "@/lib/api";
import { translateProcessingStatus, translateProductType, translateProjectStatus } from "@/lib/status-labels";
import type { ProjectListResponse } from "@/types/project";

export default function ProjectsPage() {
  const [data, setData] = useState<ProjectListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<ProjectListResponse>("/projects")
      .then(setData)
      .catch(() => setError("Não foi possível carregar os projetos."))
      .finally(() => setLoading(false));
  }, []);

  async function handleDeleteProject(projectId: string) {
    const confirmed = window.confirm("Tem certeza que deseja excluir este projeto? Ele será removido da sua lista.");
    if (!confirmed) {
      return;
    }

    setError("");
    try {
      await deleteProject(projectId);
      setData((current) => {
        if (!current) return current;
        return {
          ...current,
          items: current.items.filter((project) => project.id !== projectId),
          total: Math.max(current.total - 1, 0),
        };
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Nao foi possivel excluir o projeto.");
      }
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Projetos</p>
          <h1 className="mt-2 text-3xl font-semibold">Produção intelectual</h1>
          <p className="mt-2 text-zinc-400">Acompanhe os projetos criados no VVE Engine.</p>
        </div>

        <div className="mt-8 rounded-lg border border-white/5 bg-white/[0.035]">
          {loading ? (
            <div className="p-6">
              <LoadingProgress label="Carregando projetos..." />
            </div>
          ) : error ? (
            <p className="p-6 text-red-300">{error}</p>
          ) : !data?.items.length ? (
            <div className="p-8 text-center">
              <p className="text-lg font-semibold text-white">Nenhum projeto criado ainda.</p>
              <p className="mt-2 text-sm text-zinc-400">Crie o primeiro projeto para iniciar a produção.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-white/5 text-zinc-400">
                  <tr>
                    <th className="px-5 py-4 font-medium">Título</th>
                    <th className="px-5 py-4 font-medium">Tipo</th>
                    <th className="px-5 py-4 font-medium">Status</th>
                    <th className="px-5 py-4 font-medium">Processamento</th>
                    <th className="px-5 py-4 font-medium">Atualizado em</th>
                    <th className="px-5 py-4 font-medium">Ação</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((project) => (
                    <tr key={project.id} className="border-b border-white/5">
                      <td className="px-5 py-4 font-medium text-white">{project.title}</td>
                      <td className="px-5 py-4 text-zinc-300">{translateProductType(project.product_type)}</td>
                      <td className="px-5 py-4">
                        <StatusBadge
                          label={translateProjectStatus(project.status)}
                          tone={project.status === "active" ? "success" : "neutral"}
                        />
                      </td>
                      <td className="px-5 py-4">
                        <StatusBadge label={translateProcessingStatus(project.processing_status)} tone="warning" />
                      </td>
                      <td className="px-5 py-4 text-zinc-400">
                        {new Date(project.updated_at).toLocaleDateString("pt-BR")}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <KpiActionCard
                            size="sm"
                            icon={FolderOpen}
                            label="Abrir"
                            href={`/projects/${project.id}`}
                          />
                          <KpiActionCard
                            size="sm"
                            tone="red"
                            icon={Trash2}
                            label="Excluir"
                            onClick={() => handleDeleteProject(project.id)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
