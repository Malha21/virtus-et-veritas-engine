"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { ApiError, apiFetch, downloadPresentationPdf } from "@/lib/api";
import type { GeneratedContent } from "@/types/content";
import type {
  ComplementaryMaterialContent,
  CourseSummaryContent,
  EducationalContentSummaryResponse,
  LessonScriptContent,
  ModuleQuizContent,
  PresentationDeckContent,
} from "@/types/educational-content";

type Tab = "summary" | "scripts" | "quizzes" | "materials" | "presentation";

function getGenerationLanguage(content?: GeneratedContent): string | undefined {
  return content?.language || (content?.content_json?.generation_language as string | undefined);
}

function getLanguageLabel(language?: string): string {
  if (language === "en-US") return "English";
  if (language === "pt-BR") return "Português do Brasil";
  return "Idioma não informado";
}

function getContentNumber(content: GeneratedContent, section: string, field: string): number {
  const contentJson = content.content_json || {};
  const metadata = contentJson.metadata as Record<string, unknown> | undefined;
  const nested = contentJson[section] as Record<string, unknown> | undefined;
  const value = nested?.[field] ?? metadata?.[field];
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 9999;
}

function sortLessonScripts(contents: GeneratedContent[]): GeneratedContent[] {
  return [...contents].sort(
    (a, b) =>
      getContentNumber(a, "lesson_script", "module_number") - getContentNumber(b, "lesson_script", "module_number") ||
      getContentNumber(a, "lesson_script", "lesson_number") - getContentNumber(b, "lesson_script", "lesson_number") ||
      new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );
}

function sortModuleQuizzes(contents: GeneratedContent[]): GeneratedContent[] {
  return [...contents].sort(
    (a, b) =>
      getContentNumber(a, "module_quiz", "module_number") - getContentNumber(b, "module_quiz", "module_number") ||
      new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );
}

function sortByCreatedAt(contents: GeneratedContent[]): GeneratedContent[] {
  return [...contents].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
}

function sortSummaries(contents: GeneratedContent[]): GeneratedContent[] {
  return [...contents].sort(
    (a, b) => a.version - b.version || new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );
}

export default function EducationalContentPage() {
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<EducationalContentSummaryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("summary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generationMessage, setGenerationMessage] = useState("");
  const [exportingPresentation, setExportingPresentation] = useState(false);
  const [exportError, setExportError] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const messageKey = `vve_educational_generation_message_${params.id}`;
      const storedMessage = window.sessionStorage.getItem(messageKey);
      if (storedMessage) {
        setGenerationMessage(storedMessage);
        window.sessionStorage.removeItem(messageKey);
      }
    }

    apiFetch<EducationalContentSummaryResponse>(`/projects/${params.id}/educational-content`)
      .then((payload) =>
        setData({
          lesson_scripts: sortLessonScripts(payload.lesson_scripts),
          module_quizzes: sortModuleQuizzes(payload.module_quizzes),
          complementary_materials: sortByCreatedAt(payload.complementary_materials),
          course_summaries: sortSummaries(payload.course_summaries),
          presentation_decks: sortSummaries(payload.presentation_decks || []),
        }),
      )
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
          {generationMessage ? (
            <p className="mt-4 rounded-md border border-gold-500/20 bg-gold-500/10 px-4 py-3 text-sm text-gold-200">
              {generationMessage}
            </p>
          ) : null}

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
            <TabButton active={activeTab === "presentation"} onClick={() => setActiveTab("presentation")}>
              Apresentacao
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
              {activeTab === "presentation" ? (
                <PresentationView
                  contents={data.presentation_decks}
                  projectId={params.id}
                  exporting={exportingPresentation}
                  exportError={exportError}
                  onExport={async () => {
                    setExportingPresentation(true);
                    setExportError("");
                    try {
                      await downloadPresentationPdf(params.id);
                    } catch (err) {
                      if (err instanceof ApiError && err.status === 401) {
                        setExportError("Sua sessao expirou. Faca login novamente.");
                      } else if (err instanceof Error && err.message) {
                        setExportError(err.message);
                      } else {
                        setExportError("Nao foi possivel baixar a apresentacao.");
                      }
                    } finally {
                      setExportingPresentation(false);
                    }
                  }}
                />
              ) : null}
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
  const content = sortSummaries(contents)[0];
  const summary = content?.content_json as CourseSummaryContent | undefined;
  const item = summary?.course_summary;

  if (!item) {
    return <EmptyState text="Resumo do curso ainda nao encontrado." />;
  }

  return (
    <div className="grid gap-5">
      <div>
        <p className="text-sm text-gold-400">Resumo executivo</p>
        <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
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

  const grouped = sortLessonScripts(contents).reduce<Record<string, GeneratedContent[]>>((acc, content) => {
    const moduleNumber = getContentNumber(content, "lesson_script", "module_number");
    const key = String(moduleNumber || "sem-modulo");
    acc[key] = acc[key] || [];
    acc[key].push(content);
    return acc;
  }, {});

  return (
    <div className="grid gap-5">
      {Object.entries(grouped).map(([moduleKey, moduleContents]) => {
        const firstScript = (moduleContents[0]?.content_json as LessonScriptContent | null)?.lesson_script;
        return (
          <section key={moduleKey} className="grid gap-4">
            <div>
              <p className="text-xs font-medium text-gold-400">Modulo {firstScript?.module_number || moduleKey}</p>
              <h3 className="mt-1 text-xl font-semibold text-slate-50">{firstScript?.module_title || "Modulo"}</h3>
            </div>
            {moduleContents.map((content) => {
              const script = (content.content_json as LessonScriptContent | null)?.lesson_script;
              if (!script) return null;

              return (
                <article key={content.id} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-gold-400">
                  Modulo {script.module_number} - Aula {script.lesson_number}
                </p>
                <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
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
          </section>
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
      {sortModuleQuizzes(contents).map((content) => {
        const quiz = (content.content_json as ModuleQuizContent | null)?.module_quiz;
        if (!quiz) return null;

        return (
          <article key={content.id} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
            <p className="text-xs font-medium text-gold-400">Modulo {quiz.module_number}</p>
            <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
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
      {sortByCreatedAt(contents).map((content) => {
        const raw = content.content_json || {};
        const material = (raw as ComplementaryMaterialContent | null)?.complementary_material;

        if (!material) {
          return (
            <article key={content.id} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
              <p className="text-xs font-medium text-gold-400">Material complementar</p>
              <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
              <pre className="mt-5 max-h-[720px] overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/30 p-4 text-sm leading-6 text-slate-200">
                {JSON.stringify(raw, null, 2)}
              </pre>
            </article>
          );
        }

        return (
          <article key={content.id} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
            <p className="text-xs font-medium text-gold-400">{safeText(material.material_type || "Material complementar")}</p>
            <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">{safeText(material.material_title || "Material complementar")}</h3>
            <p className="mt-3 whitespace-pre-wrap leading-7 text-slate-400">{safeText(material.overview)}</p>

            <div className="mt-5 grid gap-5 md:grid-cols-2">
              <ConceptBlock items={Array.isArray(material.key_concepts) ? material.key_concepts : []} />
              <ListBlock title="Aplicacoes praticas" items={Array.isArray(material.practical_applications) ? material.practical_applications : []} />
              <ListBlock title="Exercicios reflexivos" items={Array.isArray(material.reflection_exercises) ? material.reflection_exercises : []} />
              <ListBlock title="Proximos passos" items={Array.isArray(material.recommended_next_steps) ? material.recommended_next_steps : []} />
            </div>
          </article>
        );
      })}
    </div>
  );
}

function PresentationView({
  contents,
  exporting,
  exportError,
  onExport,
}: {
  contents: GeneratedContent[];
  projectId: string;
  exporting: boolean;
  exportError: string;
  onExport: () => Promise<void>;
}) {
  const content = sortSummaries(contents)[0];
  const deck = content?.content_json as PresentationDeckContent | undefined;

  if (!deck) {
    return (
      <EmptyState text="A apresentacao ainda nao foi gerada. Gere os conteudos educacionais para criar a apresentacao." />
    );
  }

  const slides = Array.isArray(deck.slides) ? deck.slides : [];

  return (
    <div className="grid gap-6">
      <section className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-gold-400">Apresentacao</p>
            <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">{safeText(deck.presentation_title)}</h2>
          </div>
          <button
            type="button"
            onClick={onExport}
            disabled={exporting}
            className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exporting ? "Gerando PDF..." : "Baixar apresentacao em PDF"}
          </button>
        </div>
        {exportError ? <p className="mt-4 text-sm text-red-300">{exportError}</p> : null}
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <InfoBlock label="Publico-alvo" value={deck.target_audience} />
          <InfoBlock label="Duracao estimada" value={deck.estimated_duration} />
          <InfoBlock label="Estilo visual sugerido" value={deck.visual_style} />
          <InfoBlock label="Objetivo da apresentacao" value={deck.presentation_objective} />
        </div>
      </section>

      {slides.length ? (
        <div className="grid gap-5">
          {slides.map((slide, index) => (
            <article key={itemKey(slide, index)} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
              <p className="text-xs font-medium text-gold-400">
                Slide {safeText(slide?.slide_number ?? index + 1)}
              </p>
              <h3 className="mt-2 text-xl font-semibold text-slate-50">{safeText(slide?.title)}</h3>
              {slide?.subtitle ? <p className="mt-2 text-sm text-slate-400">{safeText(slide.subtitle)}</p> : null}

              <ListBlock title="Pontos principais" items={toArray(slide?.bullets)} />
              <InfoBlock label="Notas do apresentador" value={slide?.speaker_notes} />
              <InfoBlock label="Sugestao visual" value={slide?.visual_suggestion} />
              {slide?.interaction_question ? (
                <InfoBlock label="Pergunta de interacao" value={slide.interaction_question} />
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState text="Nenhum slide encontrado nesta apresentacao." />
      )}

      <InfoBlock label="Mensagem de encerramento" value={deck.closing_message} />
    </div>
  );
}

function safeText(value: unknown): string {
  if (value === null || value === undefined) return "Nao informado";

  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);

  if (Array.isArray(value)) {
    return value.map((item) => safeText(item)).join("\n");
  }

  if (typeof value === "object") {
    const record = value as Record<string, unknown>;

    const title = record.title ?? record.concept ?? record.step ?? record.action ?? record.name;
    const description =
      record.question ??
      record.description ??
      record.explanation ??
      record.text ??
      record.content ??
      record.value ??
      record.summary ??
      record.details;

    if (title && description) {
      return `${safeText(title)}: ${safeText(description)}`;
    }

    if (description) return safeText(description);
    if (title) return safeText(title);

    return JSON.stringify(record, null, 2);
  }

  return String(value);
}

function toArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined || value === "") return [];
  return [value];
}

function itemKey(item: unknown, index: number): string {
  return `${index}-${safeText(item).slice(0, 60)}`;
}

function ConceptBlock({ items }: { items?: unknown[] }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm text-slate-400">Conceitos-chave</p>
      <div className="mt-3 grid gap-3">
        {Array.isArray(items) && items.length ? (
          items.map((item, index) => {
            const record = typeof item === "object" && item !== null ? (item as Record<string, unknown>) : null;
            const title = safeText(record?.concept ?? record?.title ?? `Conceito ${index + 1}`);
            const explanation = safeText(record?.explanation ?? record?.description ?? record?.text ?? item);

            return (
              <div key={itemKey(item, index)} className="rounded border border-white/10 px-3 py-2">
                <p className="font-medium text-slate-100">{title}</p>
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-400">{explanation}</p>
              </div>
            );
          })
        ) : (
          <p className="text-slate-100">Nao informado</p>
        )}
      </div>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value?: unknown }) {
  return (
    <div className="mt-4 rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 whitespace-pre-wrap text-slate-100">{safeText(value)}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items?: unknown[] }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm text-slate-400">{title}</p>
      {Array.isArray(items) && items.length ? (
        <ul className="mt-3 grid gap-2 text-sm text-slate-100">
          {items.map((item, index) => (
            <li key={itemKey(item, index)} className="whitespace-pre-wrap rounded border border-white/10 bg-navy-950/60 px-3 py-2">
              {safeText(item)}
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
