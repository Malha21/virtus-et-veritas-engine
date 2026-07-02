"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import type { ProjectFile } from "@/types/file";
import type { StartProcessingResponse } from "@/types/processing";
import type { Project } from "@/types/project";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch<Project>(`/projects/${params.id}`),
      apiFetch<ProjectFile[]>(`/projects/${params.id}/files`),
    ])
      .then(([projectData, fileData]) => {
        setProject(projectData);
        setFiles(fileData);
      })
      .catch(() => setError("Não foi possível carregar este projeto."))
      .finally(() => setLoading(false));
  }, [params.id]);

  async function startProcessing(projectId: string) {
    setProcessing(true);
    setError("");
    try {
      await apiFetch<StartProcessingResponse>(`/projects/${projectId}/process`, {
        method: "POST",
      });
      router.push(`/projects/${projectId}/processing`);
    } catch {
      setError("Não foi possível iniciar o processamento.");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <Link href="/projects" className="text-sm text-gold-400 hover:text-gold-500">
          Voltar para projetos
        </Link>

        {loading ? (
          <p className="mt-8 text-slate-300">Carregando projeto...</p>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : project ? (
          <section className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm text-gold-400">{project.product_type}</p>
                <h1 className="mt-2 text-3xl font-semibold">{project.title}</h1>
                <p className="mt-2 text-sm text-slate-400">Slug: {project.slug}</p>
              </div>
              <div className="flex gap-2">
                <StatusBadge label={project.status} tone="success" />
                <StatusBadge label={project.processing_status} tone="warning" />
              </div>
            </div>

            <div className="mt-8 grid gap-5 md:grid-cols-2">
              <Info label="Público-alvo" value={project.target_audience} />
              <Info label="Tom de voz" value={project.tone_of_voice} />
              <Info label="Duração desejada" value={project.desired_duration} />
              <Info label="Atualizado em" value={new Date(project.updated_at).toLocaleDateString("pt-BR")} />
            </div>

            <div className="mt-6">
              <p className="text-sm text-slate-400">Descrição</p>
              <p className="mt-2 whitespace-pre-wrap text-slate-200">
                {project.description || "Nenhuma descrição informada."}
              </p>
            </div>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href={`/projects/${project.id}/upload`}
                className="inline-flex rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400"
              >
                {files.length ? "Gerenciar PDF" : "Enviar PDF"}
              </Link>

              {files.length && (project.processing_status === "text_extracted" || project.processing_status === "failed") ? (
                <Link
                  href={`/projects/${project.id}/processing`}
                  className="inline-flex rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                >
                  Ver processamento
                </Link>
              ) : null}

              {files.length && project.processing_status !== "text_extracted" && project.processing_status !== "failed" ? (
                <button
                  type="button"
                  onClick={() => startProcessing(project.id)}
                  disabled={processing}
                  className="inline-flex rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {processing ? "Processando..." : "Iniciar processamento"}
                </button>
              ) : null}
            </div>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-md border border-white/10 bg-navy-950/60 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-slate-100">{value || "Não informado"}</p>
    </div>
  );
}
