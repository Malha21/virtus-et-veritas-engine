"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import type { GeneratedContent } from "@/types/content";
import type {
  ComplementaryMaterialContent,
  CourseSummaryContent,
  EducationalContentSummaryResponse,
  LessonScriptContent,
  ModuleQuizContent,
} from "@/types/educational-content";

type Tab = "summary" | "scripts" | "quizzes" | "materials";

export default function EducationalContentPage() {
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<EducationalContentSummaryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("summary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<EducationalContentSummaryResponse>(`/projects/${params.id}/educational-content`)
      .then(setData)
      .catch(() => setError("Nao foi possivel carregar os conteudos educacionais."))
      .finally(() => setLoading(false));
  }, [params.id]);

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link href={`/projects/${params.id}`} className="text-sm text-gold-400 hover:text-gold-500">
            Voltar ao projeto
          </Link>
          <button
            type="button"
            disabled
            className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-500"
          >
            Exportar - Disponivel na proxima fase
          </button>
        </div>

        <section className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-6">
          <p className="text-sm text-gold-400">Conteudos educacionais</p>
          <h1 className="mt-2 text-3xl font-semibold">Roteiros, quizzes e materiais</h1>
          <p className="mt-2 max-w-3xl text-slate-400">
            Revise os conteudos gerados para transformar a estrutura do curso em experiencia educacional.
          </p>

          <div className="mt-6 flex flex-wrap gap-2 border-b border-white/10 pb-4">
            <TabButton active={activeTab === "summary"} onClick={() => setActiveTab("summary")}>
              Resumo do Curso
            </TabButton>
            <TabButton active={activeTab === "scripts"} onClick={() => setActiveTab("scripts")}>
              Roteiros de Aula
            </TabButton>
            <TabButton active={activeTab === "quizzes"} onClick={() => setActiveTab("quizzes")}>
              Quizzes
            </TabButton>
            <TabButton active={activeTab === "materials"} onClick={() => setActiveTab("materials")}>
              Materiais Complementares
            </TabButton>
          </div>

          {loading ? (
            <p className="mt-8 text-slate-300">Carregando conteudos...</p>
          ) : error ? (
            <p className="mt-8 text-red-300">{error}</p>
          ) : data ? (
            <div className="mt-8">
              {activeTab === "summary" ? <SummaryView contents={data.course_summaries} /> : null}
              {activeTab === "scripts" ? <ScriptsView contents={data.lesson_scripts} /> : null}
              {activeTab === "quizzes" ? <QuizzesView contents={data.module_quizzes} /> : null}
              {activeTab === "materials" ? <MaterialsView contents={data.complementary_materials} /> : null}
            </div>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}

function TabButton({ active, children, onClick }: { active: boolean; children: ReactNode; onClick: () => void }) {
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

function SummaryView({ contents }: { contents: GeneratedContent[] }) {
  const summary = contents[0]?.content_json as CourseSummaryContent | undefined;
  const item = summary?.course_summary;

  if (!item) {
    return <EmptyState text="Resumo do curso ainda nao encontrado." />;
  }

  return (
    <div className="grid gap-5">
      <div>
        <p className="text-sm text-gold-400">Resumo executivo</p>
        <h2 className="mt-2 text-2xl font-semibold text-slate-50">{item.title}</h2>
        <p className="mt-3 text-lg text-slate-200">{item.promise}</p>
        <p className="mt-3 leading-7 text-slate-400">{item.long_description || item.short_description}</p>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <InfoBlock label="Publico-alvo" value={item.target_audience} />
        <InfoBlock label="Transformacao" value={item.transformation_statement} />
      </div>
      <ListBlock title="O que o aluno vai aprender" items={item.what_student_will_learn} />
      <ListBlock title="Diferenciais do curso" items={item.course_differentials} />
      <InfoBlock label="Copy de vendas" value={item.suggested_sales_copy} />
      <InfoBlock label="Legenda Instagram" value={item.suggested_instagram_caption} />
      <InfoBlock label="Mensagem WhatsApp" value={item.suggested_whatsapp_message} />
    </div>
  );
}

function ScriptsView({ contents }: { contents: GeneratedContent[] }) {
  if (!contents.length) {
    return <EmptyState text="Roteiros de aula ainda nao encontrados." />;
  }

  return (
    <div className="grid gap-5">
      {contents.map((content) => {
        const script = (content.content_json as LessonScriptContent | null)?.lesson_script;
        if (!script) return null;

        return (
          <article key={content.id} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-gold-400">
                  Modulo {script.module_number} - Aula {script.lesson_number}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-50">{script.lesson_title}</h3>
              </div>
              <span className="text-xs text-gold-400">{script.estimated_duration_minutes || 10} min</span>
            </div>
            <InfoBlock label="Abertura" value={script.opening} />
            <InfoBlock label="Objetivo" value={script.learning_objective} />
            <div className="mt-4 grid gap-3">
              {(script.main_script || []).map((section) => (
                <div key={`${content.id}-${section.section_title}`} className="rounded-md border border-white/10 bg-black/20 p-4">
                  <h4 className="font-semibold text-slate-100">{section.section_title}</h4>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{section.narration}</p>
                  <p className="mt-3 text-xs text-slate-500">{section.teaching_notes}</p>
                  <p className="mt-2 text-xs text-gold-400">{section.visual_suggestion}</p>
                </div>
              ))}
            </div>
            <InfoBlock label="Exemplo pratico" value={script.practical_example} />
            <InfoBlock label="Pergunta reflexiva" value={script.reflection_question} />
            <InfoBlock label="Fechamento" value={script.closing} />
          </article>
        );
      })}
    </div>
  );
}

function QuizzesView({ contents }: { contents: GeneratedContent[] }) {
  if (!contents.length) {
    return <EmptyState text="Quizzes ainda nao encontrados." />;
  }

  return (
    <div className="grid gap-5">
      {contents.map((content) => {
        const quiz = (content.content_json as ModuleQuizContent | null)?.module_quiz;
        if (!quiz) return null;

        return (
          <article key={content.id} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
            <p className="text-xs font-medium text-gold-400">Modulo {quiz.module_number}</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">{quiz.module_title}</h3>
            <div className="mt-5 grid gap-4">
              {(quiz.questions || []).map((question) => (
                <div key={`${content.id}-${question.question_number}`} className="rounded-md border border-white/10 bg-black/20 p-4">
                  <p className="font-semibold text-slate-100">
                    {question.question_number}. {question.question}
                  </p>
                  <div className="mt-3 grid gap-2">
                    {(question.options || []).map((option) => (
                      <p key={`${question.question_number}-${option.letter}`} className="rounded border border-white/10 px-3 py-2 text-sm text-slate-300">
                        {option.letter}. {option.text}
                      </p>
                    ))}
                  </div>
                  <p className="mt-3 text-sm text-gold-400">Resposta correta: {question.correct_answer}</p>
                  <p className="mt-2 text-sm text-slate-400">{question.explanation}</p>
                </div>
              ))}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function MaterialsView({ contents }: { contents: GeneratedContent[] }) {
  if (!contents.length) {
    return <EmptyState text="Materiais complementares ainda nao encontrados." />;
  }

  return (
    <div className="grid gap-5">
      {contents.map((content) => {
        const material = (content.content_json as ComplementaryMaterialContent | null)?.complementary_material;
        if (!material) return null;

        return (
          <article key={content.id} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
            <p className="text-xs font-medium text-gold-400">{material.material_type}</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">{material.material_title}</h3>
            <p className="mt-3 leading-7 text-slate-400">{material.overview}</p>
            <div className="mt-5 grid gap-5 md:grid-cols-2">
              <ConceptBlock items={material.key_concepts} />
              <ListBlock title="Aplicacoes praticas" items={material.practical_applications} />
              <ListBlock title="Exercicios reflexivos" items={material.reflection_exercises} />
              <ListBlock title="Proximos passos" items={material.recommended_next_steps} />
            </div>
          </article>
        );
      })}
    </div>
  );
}

function ConceptBlock({ items }: { items?: Array<{ concept?: string; explanation?: string }> }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm text-slate-400">Conceitos-chave</p>
      <div className="mt-3 grid gap-3">
        {items?.length ? (
          items.map((item) => (
            <div key={item.concept} className="rounded border border-white/10 px-3 py-2">
              <p className="font-medium text-slate-100">{item.concept}</p>
              <p className="mt-1 text-sm text-slate-400">{item.explanation}</p>
            </div>
          ))
        ) : (
          <p className="text-slate-100">Nao informado</p>
        )}
      </div>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value?: string }) {
  return (
    <div className="mt-4 rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 whitespace-pre-wrap text-slate-100">{value || "Nao informado"}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items?: string[] }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm text-slate-400">{title}</p>
      {items?.length ? (
        <ul className="mt-3 grid gap-2 text-sm text-slate-100">
          {items.map((item) => (
            <li key={item} className="rounded border border-white/10 bg-navy-950/60 px-3 py-2">
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

function EmptyState({ text }: { text: string }) {
  return <p className="rounded-md border border-white/10 bg-navy-950/60 p-4 text-slate-400">{text}</p>;
}
