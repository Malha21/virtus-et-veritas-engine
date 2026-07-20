"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  BookOpen,
  ListChecks,
  PlayCircle,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { KpiActionCard } from "@/components/ui/KpiActionCard";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  ApiError,
  apiFetch,
  deleteProject,
  getProjectJob,
  startAiStructureJob,
  startEducationalContentJob,
} from "@/lib/api";
import { translateJobStatus, translateProcessingStatus, translateProductType, translateProjectStatus } from "@/lib/status-labels";
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

  async function pollJob(
    projectId: string,
    jobId: string,
    target: "structure" | "educational-content",
  ) {
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
        <KpiActionCard size="sm" icon={ArrowLeft} label="Voltar para projetos" href="/projects" />

        {loading ? (
          <div className="mt-8">
            <LoadingProgress label="Carregando projeto..." />
          </div>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : project ? (
          <section className="mt-6 rounded-lg border border-white/5 bg-white/[0.035] p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="font-mono text-xs uppercase tracking-wider text-accent-400">
                  {translateProductType(project.product_type)}
                </p>
                <h1 className="mt-2 text-3xl font-semibold">{project.title}</h1>
                <p className="mt-2 text-sm text-zinc-400">Slug: {project.slug}</p>
              </div>
              <div className="flex gap-2">
                <StatusBadge label={translateProjectStatus(project.status)} tone="success" />
                <StatusBadge label={translateProcessingStatus(project.processing_status)} tone="warning" />
              </div>
            </div>

            <div className="mt-8 grid gap-5 md:grid-cols-2">
              <Info label="Publico-alvo" value={project.target_audience} />
              <Info label="Tom de voz" value={project.tone_of_voice} />
              <Info label="Duracao desejada" value={project.desired_duration} />
              <Info label="Atualizado em" value={new Date(project.updated_at).toLocaleDateString("pt-BR")} />
            </div>

            <div className="mt-6">
              <p className="text-sm text-zinc-400">Descricao</p>
              <p className="mt-2 whitespace-pre-wrap text-zinc-200">
                {project.description || "Nenhuma descricao informada."}
              </p>
            </div>

            <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <KpiActionCard
                icon={BookOpen}
                label="Conteúdos Educacionais"
                hint="Roteiros, narração, vídeo e export"
                tone="accent"
                href={`/projects/${project.id}/educational-content`}
              />
              <KpiActionCard
                icon={ListChecks}
                label="Revisar Estrutura"
                hint="Análise e estrutura do curso"
                href={`/projects/${project.id}/review`}
              />
              <KpiActionCard
                icon={Upload}
                label="Ver Documento"
                hint={files.length ? "Documento-base enviado" : "Nenhum documento ainda"}
                href={`/projects/${project.id}/upload`}
              />
              <KpiActionCard
                icon={Trash2}
                label="Excluir Projeto"
                hint="Remove o projeto da lista"
                tone="red"
                onClick={() => handleDeleteProject(project.id)}
              />
            </div>

            {files.length ? (
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {project.processing_status === "text_extracted" || project.processing_status === "failed" ? (
                  <KpiActionCard
                    size="sm"
                    icon={Activity}
                    label="Ver Processamento"
                    href={`/projects/${project.id}/processing`}
                  />
                ) : null}

                {project.processing_status === "text_extracted" ? (
                  <KpiActionCard
                    size="sm"
                    icon={Sparkles}
                    label={generating ? "Gerando..." : "Gerar Estrutura com IA"}
                    disabled={generating}
                    onClick={() => generateStructure(project.id)}
                  />
                ) : null}

                {project.processing_status === "ai_structure_generated" ? (
                  <KpiActionCard
                    size="sm"
                    icon={Sparkles}
                    label={generatingEducationalContent ? "Gerando..." : "Gerar Conteúdos Educacionais"}
                    disabled={generatingEducationalContent}
                    onClick={() => generateEducationalContent(project.id)}
                  />
                ) : null}

                {project.processing_status !== "text_extracted" &&
                project.processing_status !== "failed" &&
                project.processing_status !== "ai_structure_generated" &&
                project.processing_status !== "educational_content_generated" ? (
                  <KpiActionCard
                    size="sm"
                    icon={PlayCircle}
                    label={processing ? "Processando..." : "Iniciar Processamento"}
                    disabled={processing}
                    onClick={() => startProcessing(project.id)}
                  />
                ) : null}
              </div>
            ) : null}

            {activeJob ? <JobProgressCard job={activeJob} /> : null}
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}

function JobProgressCard({ job }: { job: ProcessingJob }) {
  return (
    <div className="mt-6 rounded-md border border-accent-500/20 bg-accent-500/10 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-accent-200">Processamento em andamento</p>
          <p className="mt-1 text-sm text-zinc-300">{job.current_step || "Preparando processamento"}</p>
        </div>
        <span className="flex items-center gap-2 text-xs uppercase tracking-wide text-accent-300">
          {translateJobStatus(job.status || "pending")}
          <span className="font-mono text-accent-200">{job.progress ?? 0}%</span>
        </span>
      </div>
      <div className="mt-4 h-2 rounded-full bg-white/10">
        <div className="h-2 rounded-full bg-accent-500 transition-all" style={{ width: `${job.progress || 0}%` }} />
      </div>
      <p className="mt-2 text-sm text-zinc-400">{job.message || `${job.progress || 0}% concluido`}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-md border border-white/5 bg-navy-950/60 p-4">
      <p className="text-sm text-zinc-400">{label}</p>
      <p className="mt-2 text-zinc-100">{value || "Nao informado"}</p>
    </div>
  );
}
