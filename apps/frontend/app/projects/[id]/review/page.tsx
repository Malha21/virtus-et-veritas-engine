"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch, getProjectJob, startEducationalContentJob } from "@/lib/api";
import type { GenerationLanguage } from "@/lib/api";
import { translateContentStatus, translateJobStatus } from "@/lib/status-labels";
import type {
  CourseStructureContent,
  DocumentAnalysisContent,
  GeneratedContent,
  GeneratedContentListResponse,
} from "@/types/content";
import type { ProcessingJob } from "@/types/processing";

export default function ReviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [contents, setContents] = useState<GeneratedContent[]>([]);
  const [activeTab, setActiveTab] = useState<"analysis" | "course">("analysis");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generatingEducationalContent, setGeneratingEducationalContent] = useState(false);
  const [generationLanguage, setGenerationLanguage] = useState<GenerationLanguage>("pt-BR");
  const [activeJob, setActiveJob] = useState<ProcessingJob | null>(null);

  useEffect(() => {
    apiFetch<GeneratedContentListResponse>(`/projects/${params.id}/contents`)
      .then((data) => setContents(data.items))
      .catch(() => setError("Nao foi possivel carregar os conteudos gerados."))
      .finally(() => setLoading(false));
  }, [params.id]);

  const analysis = useMemo(
    () => contents.find((content) => content.content_type === "document_analysis"),
    [contents],
  );
  const courseStructure = useMemo(
    () => contents.find((content) => content.content_type === "course_structure"),
    [contents],
  );

  async function generateEducationalContent() {
    setGeneratingEducationalContent(true);
    setError("");
    try {
      const startedJob = await startEducationalContentJob(params.id, generationLanguage);
      pollJob(startedJob.job_id);
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

  async function pollJob(jobId: string) {
    try {
      const job = await getProjectJob(params.id, jobId);
      setActiveJob(job);

      if (job.status === "completed") {
        if (typeof window !== "undefined") {
          window.sessionStorage.setItem(
            `vve_educational_generation_message_${params.id}`,
            job.message || "Conteudos educacionais gerados com sucesso.",
          );
        }
        router.push(`/projects/${params.id}/educational-content`);
        return;
      }

      if (job.status === "failed") {
        setGeneratingEducationalContent(false);
        setError(job.error_message || "Nao foi possivel gerar os conteudos educacionais.");
        return;
      }

      window.setTimeout(() => pollJob(jobId), 2000);
    } catch (err) {
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

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link href={`/projects/${params.id}`} className="text-sm text-accent-400 hover:text-accent-500">
            Voltar ao projeto
          </Link>
          {courseStructure ? (
            <div className="flex flex-wrap items-end gap-3">
              <label className="grid gap-2 text-sm text-zinc-300">
                Idioma dos conteúdos
                <select
                  value={generationLanguage}
                  onChange={(event) => setGenerationLanguage(event.target.value as GenerationLanguage)}
                  className="rounded-md border border-white/5 bg-navy-950 px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-accent-500/60"
                >
                  <option value="pt-BR">Português do Brasil</option>
                  <option value="en-US">English</option>
                </select>
              </label>
              <button
                type="button"
                onClick={generateEducationalContent}
                disabled={generatingEducationalContent}
                className="rounded-md bg-accent-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:cursor-not-allowed disabled:opacity-60"
              >
                {generatingEducationalContent ? "Gerando roteiros, quizzes e materiais..." : "Gerar conteúdos educacionais"}
              </button>
            </div>
          ) : null}
        </div>

        <section className="mt-6 rounded-lg border border-white/5 bg-white/[0.035] p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Revisao humana</p>
              <h1 className="mt-2 text-3xl font-semibold">Estrutura gerada pela IA</h1>
              <p className="mt-2 max-w-3xl text-zinc-400">
                Confira a analise do documento e a arquitetura inicial do curso antes das proximas etapas.
              </p>
            </div>
            {courseStructure ? <StatusBadge label={translateContentStatus(courseStructure.status)} tone="success" /> : null}
          </div>

          <div className="mt-6 flex flex-wrap gap-2 border-b border-white/5 pb-4">
            <TabButton active={activeTab === "analysis"} onClick={() => setActiveTab("analysis")}>
              Analise do Documento
            </TabButton>
            <TabButton active={activeTab === "course"} onClick={() => setActiveTab("course")}>
              Estrutura do Curso
            </TabButton>
          </div>

          {loading ? (
            <div className="mt-8">
              <LoadingProgress label="Carregando revisão..." />
            </div>
          ) : error ? (
            <p className="mt-8 text-red-300">{error}</p>
          ) : activeJob ? (
            <JobProgressCard job={activeJob} />
          ) : activeTab === "analysis" ? (
            <DocumentAnalysisView content={analysis} />
          ) : (
            <CourseStructureView content={courseStructure} />
          )}
        </section>
      </div>
    </AppShell>
  );
}

function JobProgressCard({ job }: { job: ProcessingJob }) {
  return (
    <div className="mt-8 rounded-md border border-accent-500/20 bg-accent-500/10 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-accent-100">Processamento em andamento</p>
          <p className="mt-2 text-sm text-zinc-300">{job.current_step || "Preparando conteudos educacionais"}</p>
        </div>
        <StatusBadge
          label={`${translateJobStatus(job.status || "pending")} · ${job.progress ?? 0}%`}
          tone={job.status === "failed" ? "neutral" : "warning"}
        />
      </div>
      <div className="mt-5 h-2 rounded-full bg-white/10">
        <div className="h-2 rounded-full bg-accent-500 transition-all" style={{ width: `${job.progress || 0}%` }} />
      </div>
      <p className="mt-2 text-sm text-zinc-400">{job.message || `${job.progress || 0}% concluido`}</p>
    </div>
  );
}

function TabButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-4 py-2 text-sm transition ${
        active
          ? "bg-accent-500 text-navy-950"
          : "border border-white/5 text-zinc-300 hover:border-accent-500/40 hover:text-accent-400"
      }`}
    >
      {children}
    </button>
  );
}

function DocumentAnalysisView({ content }: { content?: GeneratedContent }) {
  if (!content?.content_json) {
    return <p className="mt-8 text-zinc-400">Analise do documento ainda nao encontrada.</p>;
  }

  const analysis = (content.content_json as DocumentAnalysisContent).document_analysis;
  if (!analysis) {
    return <RawJsonView value={content.content_json} />;
  }

  return (
    <div className="mt-8 grid gap-5">
      <InfoBlock label="Tema principal" value={analysis.main_theme} />
      <div className="grid gap-5 md:grid-cols-2">
        <InfoBlock label="Nivel de complexidade" value={analysis.complexity_level} />
        <InfoBlock label="Publico recomendado" value={analysis.recommended_audience} />
      </div>
      <InfoBlock label="Abordagem sugerida" value={analysis.suggested_approach} />
      <ListBlock title="Subtemas" items={analysis.subthemes} />
      <ListBlock title="Riscos didaticos" items={analysis.didactic_risks} />
      <ListBlock title="Oportunidades" items={analysis.opportunities} />
    </div>
  );
}

function CourseStructureView({ content }: { content?: GeneratedContent }) {
  if (!content?.content_json) {
    return <p className="mt-8 text-zinc-400">Estrutura do curso ainda nao encontrada.</p>;
  }

  const course = (content.content_json as CourseStructureContent).course;
  if (!course) {
    return <RawJsonView value={content.content_json} />;
  }

  return (
    <div className="mt-8 grid gap-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Curso</p>
        <h2 className="mt-2 text-2xl font-semibold text-zinc-50">{course.title || "Sem titulo"}</h2>
        <p className="mt-3 text-lg text-zinc-200">{course.promise}</p>
        <p className="mt-3 leading-7 text-zinc-400">{course.description}</p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <InfoBlock label="Publico-alvo" value={course.target_audience} />
        <ListBlock title="Objetivos de aprendizagem" items={course.learning_objectives} />
      </div>

      <div className="grid gap-4">
        <h3 className="text-lg font-semibold text-zinc-100">Modulos</h3>
        {(course.modules || []).map((module) => (
          <div key={`${module.module_number}-${module.title}`} className="rounded-lg border border-white/5 bg-navy-950/60 p-5">
            <p className="text-xs font-medium text-accent-400">Modulo {module.module_number}</p>
            <h4 className="mt-2 text-xl font-semibold text-zinc-50">{module.title}</h4>
            <p className="mt-2 text-sm leading-6 text-zinc-400">{module.description}</p>
            <p className="mt-3 text-sm text-zinc-300">Objetivo: {module.learning_goal || "Nao informado"}</p>

            <div className="mt-5 grid gap-3">
              {(module.lessons || []).map((lesson) => (
                <div
                  key={`${module.module_number}-${lesson.lesson_number}-${lesson.title}`}
                  className="rounded-md border border-white/5 bg-black/20 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-zinc-100">
                      Aula {lesson.lesson_number}: {lesson.title}
                    </p>
                    <span className="text-xs text-accent-400">{lesson.estimated_duration_minutes || 10} min</span>
                  </div>
                  <p className="mt-2 text-sm text-zinc-400">{lesson.summary}</p>
                  <p className="mt-2 text-xs text-zinc-500">{lesson.learning_objective}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value?: string }) {
  return (
    <div className="rounded-md border border-white/5 bg-navy-950/60 p-4">
      <p className="text-sm text-zinc-400">{label}</p>
      <p className="mt-2 whitespace-pre-wrap text-zinc-100">{value || "Nao informado"}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items?: string[] }) {
  return (
    <div className="rounded-md border border-white/5 bg-navy-950/60 p-4">
      <p className="text-sm text-zinc-400">{title}</p>
      {items?.length ? (
        <ul className="mt-3 grid gap-2 text-sm text-zinc-100">
          {items.map((item) => (
            <li key={item} className="rounded border border-white/5 bg-black/20 px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-zinc-100">Nao informado</p>
      )}
    </div>
  );
}

function RawJsonView({ value }: { value: Record<string, unknown> }) {
  return (
    <pre className="mt-8 overflow-x-auto rounded-md border border-white/5 bg-navy-950/70 p-4 text-sm text-zinc-200">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
