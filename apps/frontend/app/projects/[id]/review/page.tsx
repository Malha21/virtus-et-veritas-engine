"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch, generateEducationalContent as generateEducationalContentRequest } from "@/lib/api";
import type {
  CourseStructureContent,
  DocumentAnalysisContent,
  GeneratedContent,
  GeneratedContentListResponse,
} from "@/types/content";

export default function ReviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [contents, setContents] = useState<GeneratedContent[]>([]);
  const [activeTab, setActiveTab] = useState<"analysis" | "course">("analysis");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generatingEducationalContent, setGeneratingEducationalContent] = useState(false);

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
      await generateEducationalContentRequest(params.id);
      router.push(`/projects/${params.id}/educational-content`);
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

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link href={`/projects/${params.id}`} className="text-sm text-gold-400 hover:text-gold-500">
            Voltar ao projeto
          </Link>
          {courseStructure ? (
            <button
              type="button"
              onClick={generateEducationalContent}
              disabled={generatingEducationalContent}
              className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {generatingEducationalContent ? "Gerando roteiros, quizzes e materiais..." : "Gerar conteudos educacionais"}
            </button>
          ) : null}
        </div>

        <section className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm text-gold-400">Revisao humana</p>
              <h1 className="mt-2 text-3xl font-semibold">Estrutura gerada pela IA</h1>
              <p className="mt-2 max-w-3xl text-slate-400">
                Confira a analise do documento e a arquitetura inicial do curso antes das proximas etapas.
              </p>
            </div>
            {courseStructure ? <StatusBadge label={courseStructure.status} tone="success" /> : null}
          </div>

          <div className="mt-6 flex flex-wrap gap-2 border-b border-white/10 pb-4">
            <TabButton active={activeTab === "analysis"} onClick={() => setActiveTab("analysis")}>
              Analise do Documento
            </TabButton>
            <TabButton active={activeTab === "course"} onClick={() => setActiveTab("course")}>
              Estrutura do Curso
            </TabButton>
          </div>

          {loading ? (
            <p className="mt-8 text-slate-300">Carregando revisao...</p>
          ) : error ? (
            <p className="mt-8 text-red-300">{error}</p>
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
          ? "bg-gold-500 text-navy-950"
          : "border border-white/10 text-slate-300 hover:border-gold-500/40 hover:text-gold-400"
      }`}
    >
      {children}
    </button>
  );
}

function DocumentAnalysisView({ content }: { content?: GeneratedContent }) {
  if (!content?.content_json) {
    return <p className="mt-8 text-slate-400">Analise do documento ainda nao encontrada.</p>;
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
    return <p className="mt-8 text-slate-400">Estrutura do curso ainda nao encontrada.</p>;
  }

  const course = (content.content_json as CourseStructureContent).course;
  if (!course) {
    return <RawJsonView value={content.content_json} />;
  }

  return (
    <div className="mt-8 grid gap-6">
      <div>
        <p className="text-sm text-gold-400">Curso</p>
        <h2 className="mt-2 text-2xl font-semibold text-slate-50">{course.title || "Sem titulo"}</h2>
        <p className="mt-3 text-lg text-slate-200">{course.promise}</p>
        <p className="mt-3 leading-7 text-slate-400">{course.description}</p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <InfoBlock label="Publico-alvo" value={course.target_audience} />
        <ListBlock title="Objetivos de aprendizagem" items={course.learning_objectives} />
      </div>

      <div className="grid gap-4">
        <h3 className="text-lg font-semibold text-slate-100">Modulos</h3>
        {(course.modules || []).map((module) => (
          <div key={`${module.module_number}-${module.title}`} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
            <p className="text-xs font-medium text-gold-400">Modulo {module.module_number}</p>
            <h4 className="mt-2 text-xl font-semibold text-slate-50">{module.title}</h4>
            <p className="mt-2 text-sm leading-6 text-slate-400">{module.description}</p>
            <p className="mt-3 text-sm text-slate-300">Objetivo: {module.learning_goal || "Nao informado"}</p>

            <div className="mt-5 grid gap-3">
              {(module.lessons || []).map((lesson) => (
                <div
                  key={`${module.module_number}-${lesson.lesson_number}-${lesson.title}`}
                  className="rounded-md border border-white/10 bg-black/20 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-100">
                      Aula {lesson.lesson_number}: {lesson.title}
                    </p>
                    <span className="text-xs text-gold-400">{lesson.estimated_duration_minutes || 10} min</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-400">{lesson.summary}</p>
                  <p className="mt-2 text-xs text-slate-500">{lesson.learning_objective}</p>
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
    <div className="rounded-md border border-white/10 bg-navy-950/60 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 whitespace-pre-wrap text-slate-100">{value || "Nao informado"}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items?: string[] }) {
  return (
    <div className="rounded-md border border-white/10 bg-navy-950/60 p-4">
      <p className="text-sm text-slate-400">{title}</p>
      {items?.length ? (
        <ul className="mt-3 grid gap-2 text-sm text-slate-100">
          {items.map((item) => (
            <li key={item} className="rounded border border-white/10 bg-black/20 px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-slate-100">Nao informado</p>
      )}
    </div>
  );
}

function RawJsonView({ value }: { value: Record<string, unknown> }) {
  return (
    <pre className="mt-8 overflow-x-auto rounded-md border border-white/10 bg-navy-950/70 p-4 text-sm text-slate-200">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
