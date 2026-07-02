"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  ApiError,
  apiFetch,
  deleteProject,
  getProjectJob,
  startAiStructureJob,
  startEducationalContentJob,
} from "@/lib/api";
import type { ProjectFile } from "@/types/file";
import type { ProcessingJob, StartProcessingResponse } from "@/types/processing";
import type { Project } from "@/types/project";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatingEducationalContent, setGeneratingEducationalContent] = useState(false);
  const [activeJob, setActiveJob] = useState<ProcessingJob | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<Project>(`/projects/${params.id}`),
      apiFetch<ProjectFile[]>(`/projects/${params.id}/files`),
    ])
      .then(([projectData, fileData]) => {
        setProject(projectData);
        setFiles(fileData);
      })
      .catch(() => setError("Nao foi possivel carregar este projeto."))
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
      setError("Nao foi possivel iniciar o processamento.");
    } finally {
      setProcessing(false);
    }
  }

  async function generateStructure(projectId: string) {
    setGenerating(true);
    setError("");
    try {
      const startedJob = await startAiStructureJob(projectId);
      pollJob(projectId, startedJob.job_id, "structure");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Nao foi possivel gerar a estrutura com IA.");
      }
    } finally {
      setGenerating(false);
    }
  }

  async function generateEducationalContent(projectId: string) {
    setGeneratingEducationalContent(true);
    setError("");
    try {
      const startedJob = await startEducationalContentJob(projectId);
      pollJob(projectId, startedJob.job_id, "educational-content");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Nao foi possivel gerar os conteudos educacionais.");
      }
    } finally {
      setGeneratingEducationalContent(false);
    }
  }

  async function pollJob(projectId: string, jobId: string, target: "structure" | "educational-content") {
    try {
      const job = await getProjectJob(projectId, jobId);
      setActiveJob(job);

      if (job.status === "completed") {
        if (target === "structure") {
          router.push(`/projects/${projectId}/review`);
        } else {
          router.push(`/projects/${projectId}/educational-content`);
        }
        return;
      }

      if (job.status === "failed") {
        setGenerating(false);
        setGeneratingEducationalContent(false);
        setError(job.error_message || "Nao foi possivel concluir o processamento.");
        return;
      }

      window.setTimeout(() => pollJob(projectId, jobId, target), 2000);
    } catch (err) {
      setGenerating(false);
      setGeneratingEducationalContent(false);
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessÃ£o expirou. FaÃ§a login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Nao foi possivel consultar o progresso do processamento.");
      }
    }
  }

  async function handleDeleteProject(projectId: string) {
    const confirmed = window.confirm("Tem certeza que deseja excluir este projeto? Ele será removido da sua lista.");
    if (!confirmed) {
      return;
    }

    setError("");
    try {
      await deleteProject(projectId);
      router.push("/projects");
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
      <div className="mx-auto max-w-4xl">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/projects" className="text-sm text-gold-400 hover:text-gold-500">
            Voltar para projetos
          </Link>
          {project ? (
            <button
              type="button"
              onClick={() => handleDeleteProject(project.id)}
              className="rounded-md border border-red-400/30 px-3 py-2 text-sm text-red-300 transition hover:border-red-300/60 hover:text-red-200"
            >
              Excluir projeto
            </button>
          ) : null}
        </div>

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
              <Info label="Publico-alvo" value={project.target_audience} />
              <Info label="Tom de voz" value={project.tone_of_voice} />
              <Info label="Duracao desejada" value={project.desired_duration} />
              <Info label="Atualizado em" value={new Date(project.updated_at).toLocaleDateString("pt-BR")} />
            </div>

            <div className="mt-6">
              <p className="text-sm text-slate-400">Descricao</p>
              <p className="mt-2 whitespace-pre-wrap text-slate-200">
                {project.description || "Nenhuma descricao informada."}
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

              {project.processing_status === "text_extracted" ? (
                <button
                  type="button"
                  onClick={() => generateStructure(project.id)}
                  disabled={generating}
                  className="inline-flex rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {generating ? "Gerando..." : "Gerar estrutura com IA"}
                </button>
              ) : null}

              {project.processing_status === "ai_structure_generated" ? (
                <button
                  type="button"
                  onClick={() => generateEducationalContent(project.id)}
                  disabled={generatingEducationalContent}
                  className="inline-flex rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {generatingEducationalContent ? "Gerando conteudos..." : "Gerar conteudos educacionais"}
                </button>
              ) : null}

              {project.processing_status === "educational_content_generated" ? (
                <Link
                  href={`/projects/${project.id}/educational-content`}
                  className="inline-flex rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400"
                >
                  Ver conteudos educacionais
                </Link>
              ) : null}

              {project.processing_status === "ai_structure_generated" || project.processing_status === "educational_content_generated" ? (
                <Link
                  href={`/projects/${project.id}/review`}
                  className="inline-flex rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                >
                  Revisar estrutura
                </Link>
              ) : null}

              {files.length && project.processing_status !== "text_extracted" && project.processing_status !== "failed" && project.processing_status !== "ai_structure_generated" && project.processing_status !== "educational_content_generated" ? (
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

            {activeJob ? <JobProgressCard job={activeJob} /> : null}
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}

function JobProgressCard({ job }: { job: ProcessingJob }) {
  return (
    <div className="mt-6 rounded-md border border-gold-500/20 bg-gold-500/10 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gold-200">Processamento em andamento</p>
          <p className="mt-1 text-sm text-slate-300">{job.current_step || "Preparando processamento"}</p>
        </div>
        <span className="text-xs uppercase tracking-wide text-gold-300">{job.status || "pending"}</span>
      </div>
      <div className="mt-4 h-2 rounded-full bg-white/10">
        <div className="h-2 rounded-full bg-gold-500 transition-all" style={{ width: `${job.progress || 0}%` }} />
      </div>
      <p className="mt-2 text-sm text-slate-400">{job.message || `${job.progress || 0}% concluido`}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-md border border-white/10 bg-navy-950/60 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-slate-100">{value || "Nao informado"}</p>
    </div>
  );
}
