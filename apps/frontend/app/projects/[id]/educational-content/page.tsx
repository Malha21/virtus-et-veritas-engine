"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import {
  ApiError,
  apiFetch,
  downloadComplementaryMaterialsPdf,
  downloadFullCoursePdf,
  downloadLessonScriptsPdf,
  downloadPresentationPdf,
  downloadPresentationPptx,
  downloadQuizzesPdf,
  updateComplementaryMaterial,
  updateLessonScript,
  updateModuleQuiz,
  updatePresentationDeck,
} from "@/lib/api";
import type { GeneratedContent } from "@/types/content";
import type {
  ComplementaryMaterialContent,
  CourseSummaryContent,
  EducationalContentSummaryResponse,
  LessonScriptContent,
  ModuleQuizContent,
  PresentationDeckContent,
} from "@/types/educational-content";

type Tab = "summary" | "scripts" | "quizzes" | "materials" | "presentation" | "teleprompter" | "narration";

type PresentationSlideDraft = {
  slide_number: number;
  title: string;
  subtitle: string;
  bulletsText: string;
  speaker_notes: string;
  visual_suggestion: string;
  interaction_question: string;
};

type PresentationDeckDraft = {
  presentation_title: string;
  target_audience: string;
  estimated_duration: string;
  visual_style: string;
  presentation_objective: string;
  slides: PresentationSlideDraft[];
  closing_message: string;
};

type LessonSectionDraft = {
  section_title: string;
  narration: string;
  teaching_notes: string;
  visual_suggestion: string;
};

type LessonScriptDraft = {
  course_title: string;
  module_number: string;
  module_title: string;
  lesson_number: string;
  lesson_title: string;
  estimated_duration_minutes: string;
  opening: string;
  learning_objective: string;
  main_script: LessonSectionDraft[];
  practical_example: string;
  reflection_question: string;
  closing: string;
  call_to_action: string;
};

type QuizQuestionDraft = {
  question_number: number;
  question: string;
  optionsText: string;
  correct_answer: string;
  explanation: string;
};

type ModuleQuizDraft = {
  course_title: string;
  module_number: string;
  module_title: string;
  instructions: string;
  questions: QuizQuestionDraft[];
};

type MaterialConceptDraft = {
  concept: string;
  explanation: string;
};

type ComplementaryMaterialDraft = {
  course_title: string;
  material_title: string;
  material_type: string;
  overview: string;
  key_concepts: MaterialConceptDraft[];
  practicalApplicationsText: string;
  reflectionExercisesText: string;
  recommendedNextStepsText: string;
};

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

function hasAnyEducationalContent(data: EducationalContentSummaryResponse): boolean {
  return (
    data.course_summaries.length > 0 ||
    data.lesson_scripts.length > 0 ||
    data.module_quizzes.length > 0 ||
    data.complementary_materials.length > 0 ||
    data.presentation_decks.length > 0
  );
}

export default function EducationalContentPage() {
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<EducationalContentSummaryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("summary");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generationMessage, setGenerationMessage] = useState("");
  const [exportingLessonScripts, setExportingLessonScripts] = useState(false);
  const [lessonScriptsExportError, setLessonScriptsExportError] = useState("");
  const [exportingQuizzes, setExportingQuizzes] = useState(false);
  const [quizzesExportError, setQuizzesExportError] = useState("");
  const [exportingMaterials, setExportingMaterials] = useState(false);
  const [materialsExportError, setMaterialsExportError] = useState("");
  const [exportingFullCourse, setExportingFullCourse] = useState(false);
  const [fullCourseExportError, setFullCourseExportError] = useState("");
  const [exportingPresentation, setExportingPresentation] = useState(false);
  const [exportError, setExportError] = useState("");
  const [exportingPresentationPptx, setExportingPresentationPptx] = useState(false);
  const [presentationPptxError, setPresentationPptxError] = useState("");

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

  async function handleExportFullCourse() {
    setExportingFullCourse(true);
    setFullCourseExportError("");
    try {
      await downloadFullCoursePdf(params.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setFullCourseExportError("Sua sessao expirou. Faca login novamente.");
      } else if (err instanceof Error && err.message) {
        setFullCourseExportError(err.message);
      } else {
        setFullCourseExportError("Nao foi possivel exportar o curso completo.");
      }
    } finally {
      setExportingFullCourse(false);
    }
  }

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
          {data && hasAnyEducationalContent(data) ? (
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-navy-950/60 p-4">
              <div>
                <p className="text-sm font-medium text-slate-100">Exportacao completa</p>
                <p className="mt-1 text-xs text-slate-500">
                  Gere um PDF consolidado com resumo, estrutura, roteiros, quizzes, materiais e apresentacao.
                </p>
              </div>
              <button
                type="button"
                onClick={handleExportFullCourse}
                disabled={exportingFullCourse}
                className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {exportingFullCourse ? "Gerando PDF..." : "Exportar curso completo"}
              </button>
              {fullCourseExportError ? <p className="w-full text-sm text-red-300">{fullCourseExportError}</p> : null}
            </div>
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
            <TabButton active={activeTab === "teleprompter"} onClick={() => setActiveTab("teleprompter")}>
              Teleprompter
            </TabButton>
            <TabButton active={activeTab === "narration"} onClick={() => setActiveTab("narration")}>
              Narração
            </TabButton>
          </div>

          {loading ? (
            <p className="mt-8 text-slate-300">Carregando conteudos...</p>
          ) : error ? (
            <p className="mt-8 text-red-300">{error}</p>
          ) : data ? (
            <div className="mt-8">
              {activeTab === "summary" ? <SummaryView contents={data.course_summaries} /> : null}
              {activeTab === "scripts" ? (
                <ScriptsView
                  contents={data.lesson_scripts}
                  projectId={params.id}
                  exporting={exportingLessonScripts}
                  exportError={lessonScriptsExportError}
                  onUpdated={(updatedContent) => {
                    setData((current) => {
                      if (!current) return current;
                      return {
                        ...current,
                        lesson_scripts: sortLessonScripts([
                          updatedContent,
                          ...current.lesson_scripts.filter((item) => item.id !== updatedContent.id),
                        ]),
                      };
                    });
                  }}
                  onExport={async () => {
                    setExportingLessonScripts(true);
                    setLessonScriptsExportError("");
                    try {
                      await downloadLessonScriptsPdf(params.id);
                    } catch (err) {
                      if (err instanceof ApiError && err.status === 401) {
                        setLessonScriptsExportError("Sua sessao expirou. Faca login novamente.");
                      } else if (err instanceof Error && err.message) {
                        setLessonScriptsExportError(err.message);
                      } else {
                        setLessonScriptsExportError("Nao foi possivel baixar os roteiros.");
                      }
                    } finally {
                      setExportingLessonScripts(false);
                    }
                  }}
                />
              ) : null}
              {activeTab === "quizzes" ? (
                <QuizzesView
                  contents={data.module_quizzes}
                  projectId={params.id}
                  exporting={exportingQuizzes}
                  exportError={quizzesExportError}
                  onUpdated={(updatedContent) => {
                    setData((current) => {
                      if (!current) return current;
                      return {
                        ...current,
                        module_quizzes: sortModuleQuizzes([
                          updatedContent,
                          ...current.module_quizzes.filter((item) => item.id !== updatedContent.id),
                        ]),
                      };
                    });
                  }}
                  onExport={async () => {
                    setExportingQuizzes(true);
                    setQuizzesExportError("");
                    try {
                      await downloadQuizzesPdf(params.id);
                    } catch (err) {
                      if (err instanceof ApiError && err.status === 401) {
                        setQuizzesExportError("Sua sessao expirou. Faca login novamente.");
                      } else if (err instanceof Error && err.message) {
                        setQuizzesExportError(err.message);
                      } else {
                        setQuizzesExportError("Nao foi possivel baixar os quizzes.");
                      }
                    } finally {
                      setExportingQuizzes(false);
                    }
                  }}
                />
              ) : null}
              {activeTab === "materials" ? (
                <MaterialsView
                  contents={data.complementary_materials}
                  projectId={params.id}
                  exporting={exportingMaterials}
                  exportError={materialsExportError}
                  onUpdated={(updatedContent) => {
                    setData((current) => {
                      if (!current) return current;
                      return {
                        ...current,
                        complementary_materials: sortByCreatedAt([
                          updatedContent,
                          ...current.complementary_materials.filter((item) => item.id !== updatedContent.id),
                        ]),
                      };
                    });
                  }}
                  onExport={async () => {
                    setExportingMaterials(true);
                    setMaterialsExportError("");
                    try {
                      await downloadComplementaryMaterialsPdf(params.id);
                    } catch (err) {
                      if (err instanceof ApiError && err.status === 401) {
                        setMaterialsExportError("Sua sessao expirou. Faca login novamente.");
                      } else if (err instanceof Error && err.message) {
                        setMaterialsExportError(err.message);
                      } else {
                        setMaterialsExportError("Nao foi possivel baixar os materiais.");
                      }
                    } finally {
                      setExportingMaterials(false);
                    }
                  }}
                />
              ) : null}
              {activeTab === "presentation" ? (
                <PresentationView
                  contents={data.presentation_decks}
                  projectId={params.id}
                  exporting={exportingPresentation}
                  exportError={exportError}
                  exportingPptx={exportingPresentationPptx}
                  pptxError={presentationPptxError}
                  onUpdated={(updatedContent) => {
                    setData((current) => {
                      if (!current) return current;
                      return {
                        ...current,
                        presentation_decks: sortSummaries([
                          updatedContent,
                          ...current.presentation_decks.filter((item) => item.id !== updatedContent.id),
                        ]),
                      };
                    });
                  }}
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
                  onExportPptx={async () => {
                    setExportingPresentationPptx(true);
                    setPresentationPptxError("");
                    try {
                      await downloadPresentationPptx(params.id);
                    } catch (err) {
                      if (err instanceof ApiError && err.status === 401) {
                        setPresentationPptxError("Sua sessao expirou. Faca login novamente.");
                      } else if (err instanceof Error && err.message) {
                        setPresentationPptxError(err.message);
                      } else {
                        setPresentationPptxError("Nao foi possivel baixar a apresentacao em PPTX.");
                      }
                    } finally {
                      setExportingPresentationPptx(false);
                    }
                  }}
                />
              ) : null}
              {activeTab === "teleprompter" ? <TeleprompterView contents={data.lesson_scripts} /> : null}
              {activeTab === "narration" ? <NarrationView contents={data.lesson_scripts} /> : null}
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

function TeleprompterView({ contents }: { contents: GeneratedContent[] }) {
  const sortedContents = sortLessonScripts(contents);
  const [selectedId, setSelectedId] = useState(sortedContents[0]?.id || "");
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [fontSize, setFontSize] = useState<"small" | "medium" | "large" | "xlarge">("large");
  const [copyMessage, setCopyMessage] = useState("");
  const teleprompterRef = useRef<HTMLDivElement | null>(null);
  const scrollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!sortedContents.length) {
      setSelectedId("");
      return;
    }
    const selectedStillExists = sortedContents.some((content) => content.id === selectedId);
    if (!selectedStillExists) {
      setSelectedId(sortedContents[0]?.id || "");
    }
  }, [selectedId, sortedContents]);

  const selectedContent = sortedContents.find((content) => content.id === selectedId) || sortedContents[0];
  const selectedScript = (selectedContent?.content_json as LessonScriptContent | null)?.lesson_script;
  const teleprompterText = selectedScript ? buildTeleprompterText(selectedScript) : "";
  const estimatedTime = getEstimatedSpeechTime(teleprompterText);

  useEffect(() => {
    if (scrollTimerRef.current !== null) {
      clearInterval(scrollTimerRef.current);
      scrollTimerRef.current = null;
    }

    if (!isPlaying) {
      return;
    }

    scrollTimerRef.current = setInterval(() => {
      const element = teleprompterRef.current;
      if (!element) return;

      const maxScrollTop = element.scrollHeight - element.clientHeight;
      if (element.scrollTop >= maxScrollTop) {
        setIsPlaying(false);
        return;
      }

      element.scrollTop = Math.min(element.scrollTop + speed, maxScrollTop);
    }, 30);

    return () => {
      if (scrollTimerRef.current !== null) {
        clearInterval(scrollTimerRef.current);
        scrollTimerRef.current = null;
      }
    };
  }, [isPlaying, speed]);

  useEffect(() => {
    return () => {
      if (scrollTimerRef.current !== null) {
        clearInterval(scrollTimerRef.current);
        scrollTimerRef.current = null;
      }
    };
  }, []);

  if (!sortedContents.length) {
    return <EmptyState text="Gere ou edite os roteiros de aula antes de usar o teleprompter." />;
  }

  function resetTeleprompter() {
    setIsPlaying(false);
    if (teleprompterRef.current) {
      teleprompterRef.current.scrollTop = 0;
    }
  }

  async function copyText() {
    setCopyMessage("");
    try {
      await navigator.clipboard.writeText(teleprompterText);
      setCopyMessage("Texto copiado");
    } catch {
      setCopyMessage("Nao foi possivel copiar o texto.");
    }
  }

  function enterFullscreen() {
    if (teleprompterRef.current?.requestFullscreen) {
      teleprompterRef.current.requestFullscreen().catch(() => undefined);
    }
  }

  const fontClass = {
    small: "text-xl leading-9",
    medium: "text-2xl leading-10",
    large: "text-3xl leading-[1.55]",
    xlarge: "text-4xl leading-[1.55]",
  }[fontSize];

  return (
    <div className="grid gap-5">
      <section className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <label className="grid min-w-[260px] flex-1 gap-2 text-sm text-slate-300">
            Aula para gravacao
            <select
              value={selectedContent?.id || ""}
              onChange={(event) => {
                setSelectedId(event.target.value);
                resetTeleprompter();
              }}
              className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              {sortedContents.map((content) => {
                const script = (content.content_json as LessonScriptContent | null)?.lesson_script;
                return (
                  <option key={content.id} value={content.id} className="bg-navy-950 text-slate-100">
                    {getLessonScriptLabel(script, content)}
                  </option>
                );
              })}
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setIsPlaying(true)}
              className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400"
            >
              Iniciar
            </button>
            <button
              type="button"
              onClick={() => setIsPlaying(false)}
              className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
            >
              Pausar
            </button>
            <button
              type="button"
              onClick={resetTeleprompter}
              className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
            >
              Reiniciar
            </button>
            <button
              type="button"
              onClick={copyText}
              className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
            >
              Copiar texto
            </button>
            <button
              type="button"
              onClick={enterFullscreen}
              className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
            >
              Tela cheia
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <label className="grid gap-2 text-sm text-slate-300">
            Velocidade
            <select
              value={speed}
              onChange={(event) => setSpeed(Number(event.target.value))}
              className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value={0.5} className="bg-navy-950">0.5x</option>
              <option value={1} className="bg-navy-950">1x</option>
              <option value={1.5} className="bg-navy-950">1.5x</option>
              <option value={2} className="bg-navy-950">2x</option>
            </select>
          </label>
          <label className="grid gap-2 text-sm text-slate-300">
            Tamanho da fonte
            <select
              value={fontSize}
              onChange={(event) => setFontSize(event.target.value as "small" | "medium" | "large" | "xlarge")}
              className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="small" className="bg-navy-950">Pequeno</option>
              <option value="medium" className="bg-navy-950">Medio</option>
              <option value="large" className="bg-navy-950">Grande</option>
              <option value="xlarge" className="bg-navy-950">Extra grande</option>
            </select>
          </label>
          <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2">
            <p className="text-sm text-slate-400">Tempo estimado</p>
            <p className="mt-1 text-lg font-semibold text-gold-300">{estimatedTime}</p>
          </div>
        </div>
        {copyMessage ? <p className="mt-4 text-sm text-gold-300">{copyMessage}</p> : null}
      </section>

      <section className="rounded-lg border border-white/10 bg-black/40 p-4">
        <div className="mb-4">
          <p className="text-xs font-medium text-gold-400">Modo teleprompter</p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-50">{getLessonScriptLabel(selectedScript, selectedContent)}</h2>
        </div>
        <div
          ref={teleprompterRef}
          className="h-[620px] max-h-[70vh] overflow-y-auto rounded-md border border-white/10 bg-navy-950 px-8 py-10 text-slate-50 outline-none"
        >
          <div className={`${fontClass} mx-auto max-w-4xl whitespace-pre-wrap`}>
            {teleprompterText || "Nao foi possivel montar o texto deste roteiro."}
          </div>
        </div>
      </section>
    </div>
  );
}

function NarrationView({ contents }: { contents: GeneratedContent[] }) {
  const sortedContents = sortLessonScripts(contents);
  const [selectedId, setSelectedId] = useState(sortedContents[0]?.id || "");
  const [copiedKey, setCopiedKey] = useState("");

  useEffect(() => {
    if (!sortedContents.length) {
      setSelectedId("");
      return;
    }
    const selectedStillExists = sortedContents.some((content) => content.id === selectedId);
    if (!selectedStillExists) {
      setSelectedId(sortedContents[0]?.id || "");
    }
  }, [selectedId, sortedContents]);

  if (!sortedContents.length) {
    return <EmptyState text="Gere ou edite os roteiros de aula antes de preparar a narração." />;
  }

  const selectedContent = sortedContents.find((content) => content.id === selectedId) || sortedContents[0];
  const selectedScript = (selectedContent?.content_json as LessonScriptContent | null)?.lesson_script;
  const narrationText = selectedScript ? buildNarrationText(selectedScript) : "";
  const narrationBlocks = splitNarrationBlocks(narrationText);
  const lessonTitle = getLessonScriptLabel(selectedScript, selectedContent);

  async function copyNarration(key: string, text: string) {
    setCopiedKey("");
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
    } catch {
      setCopiedKey("error");
    }
  }

  const numberedBlocksText = narrationBlocks.map((block, index) => `Bloco ${index + 1}\n${block}`).join("\n\n");

  return (
    <div className="grid gap-6">
      <section className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <label className="grid min-w-[260px] flex-1 gap-2 text-sm text-slate-300">
            Aula para narração
            <select
              value={selectedContent?.id || ""}
              onChange={(event) => {
                setSelectedId(event.target.value);
                setCopiedKey("");
              }}
              className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              {sortedContents.map((content) => {
                const script = (content.content_json as LessonScriptContent | null)?.lesson_script;
                return (
                  <option key={content.id} value={content.id} className="bg-navy-950 text-slate-100">
                    {getLessonScriptLabel(script, content)}
                  </option>
                );
              })}
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => copyNarration("full", narrationText)}
              disabled={!narrationText}
              className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Copiar narração completa
            </button>
            <button
              type="button"
              onClick={() => copyNarration("all-blocks", numberedBlocksText)}
              disabled={!numberedBlocksText}
              className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Copiar blocos numerados
            </button>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">
              Pronta para geração de voz
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">{lessonTitle}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Texto limpo em blocos para futura narração por voz, sem gerar áudio nesta etapa.
            </p>
          </div>
          <div className="rounded-md border border-white/10 bg-black/20 px-4 py-3 text-right">
            <p className="text-xs text-slate-500">Tempo estimado total</p>
            <p className="mt-1 text-lg font-semibold text-gold-300">{formatSpeechTime(narrationText)}</p>
          </div>
        </div>
        {copiedKey ? (
          <p className={`mt-4 text-sm ${copiedKey === "error" ? "text-red-300" : "text-gold-300"}`}>
            {copiedKey === "error" ? "Não foi possível copiar." : "Copiado"}
          </p>
        ) : null}
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-100">Narração completa</p>
            <p className="mt-1 text-xs text-slate-500">{countWords(narrationText)} palavras</p>
          </div>
        </div>
        <div className="mt-4 max-h-[420px] overflow-y-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/20 p-4 text-sm leading-7 text-slate-200">
          {narrationText || "Não foi possível montar a narração deste roteiro."}
        </div>
      </section>

      <section className="grid gap-4">
        <div>
          <p className="text-sm font-medium text-slate-100">Blocos de narração</p>
          <p className="mt-1 text-xs text-slate-500">
            {narrationBlocks.length} {narrationBlocks.length === 1 ? "bloco preparado" : "blocos preparados"}
          </p>
        </div>
        {narrationBlocks.length ? (
          narrationBlocks.map((block, index) => {
            const blockKey = `block-${index}`;
            return (
              <article key={blockKey} className="rounded-lg border border-white/10 bg-navy-950/50 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-50">Bloco {index + 1}</h3>
                    <p className="mt-1 text-xs text-slate-500">Tempo estimado: {formatSpeechTime(block)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => copyNarration(blockKey, block)}
                    className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                  >
                    Copiar bloco
                  </button>
                </div>
                <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-300">{block}</p>
                {copiedKey === blockKey ? <p className="mt-3 text-sm text-gold-300">Copiado</p> : null}
              </article>
            );
          })
        ) : (
          <EmptyState text="Não foi possível dividir a narração em blocos." />
        )}
      </section>
    </div>
  );
}

function ScriptsView({
  contents,
  projectId,
  exporting,
  exportError,
  onUpdated,
  onExport,
}: {
  contents: GeneratedContent[];
  projectId: string;
  exporting: boolean;
  exportError: string;
  onUpdated: (content: GeneratedContent) => void;
  onExport: () => void;
}) {
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
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-navy-950/60 p-4">
        <div>
          <p className="text-sm font-medium text-slate-100">Roteiros de aula</p>
          <p className="mt-1 text-xs text-slate-500">Exporte todos os roteiros editados deste projeto.</p>
        </div>
        <button
          type="button"
          onClick={onExport}
          disabled={exporting}
          className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {exporting ? "Gerando PDF..." : "Baixar roteiros em PDF"}
        </button>
        {exportError ? <p className="w-full text-sm text-red-300">{exportError}</p> : null}
      </div>
      {Object.entries(grouped).map(([moduleKey, moduleContents]) => {
        const firstScript = (moduleContents[0]?.content_json as LessonScriptContent | null)?.lesson_script;
        return (
          <section key={moduleKey} className="grid gap-4">
            <div>
              <p className="text-xs font-medium text-gold-400">Modulo {firstScript?.module_number || moduleKey}</p>
              <h3 className="mt-1 text-xl font-semibold text-slate-50">{firstScript?.module_title || "Modulo"}</h3>
            </div>
            {moduleContents.map((content) => {
              return (
                <LessonScriptCard
                  key={content.id}
                  content={content}
                  projectId={projectId}
                  onUpdated={onUpdated}
                />
              );
            })}
          </section>
        );
      })}
    </div>
  );
}

function QuizzesView({
  contents,
  projectId,
  exporting,
  exportError,
  onUpdated,
  onExport,
}: {
  contents: GeneratedContent[];
  projectId: string;
  exporting: boolean;
  exportError: string;
  onUpdated: (content: GeneratedContent) => void;
  onExport: () => void;
}) {
  if (!contents.length) {
    return <EmptyState text="Quizzes ainda nao encontrados." />;
  }

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-navy-950/60 p-4">
        <div>
          <p className="text-sm font-medium text-slate-100">Quizzes</p>
          <p className="mt-1 text-xs text-slate-500">Exporte todos os quizzes editados deste projeto.</p>
        </div>
        <button
          type="button"
          onClick={onExport}
          disabled={exporting}
          className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {exporting ? "Gerando PDF..." : "Baixar quizzes em PDF"}
        </button>
        {exportError ? <p className="w-full text-sm text-red-300">{exportError}</p> : null}
      </div>
      {sortModuleQuizzes(contents).map((content) => (
        <ModuleQuizCard key={content.id} content={content} projectId={projectId} onUpdated={onUpdated} />
      ))}
    </div>
  );
}

function ModuleQuizCard({
  content,
  projectId,
  onUpdated,
}: {
  content: GeneratedContent;
  projectId: string;
  onUpdated: (content: GeneratedContent) => void;
}) {
  const quiz = (content.content_json as ModuleQuizContent | null)?.module_quiz;
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<ModuleQuizDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  if (!quiz) return null;

  function startEditing() {
    if (!quiz) {
      setSaveError("Quiz ainda nao encontrado para edicao.");
      return;
    }

    setDraft(quizToDraft(quiz));
    setSaveError("");
    setIsEditing(true);
  }

  function updateDraftField(field: keyof Omit<ModuleQuizDraft, "questions">, value: string) {
    setDraft((current) => (current ? { ...current, [field]: value } : current));
  }

  function updateQuestion(index: number, field: keyof Omit<QuizQuestionDraft, "question_number">, value: string) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        questions: current.questions.map((question, questionIndex) =>
          questionIndex === index ? { ...question, [field]: value } : question,
        ),
      };
    });
  }

  function removeQuestion(index: number) {
    const confirmed = window.confirm("Tem certeza que deseja remover esta pergunta?");
    if (!confirmed) return;
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        questions: current.questions
          .filter((_, questionIndex) => questionIndex !== index)
          .map((question, questionIndex) => ({ ...question, question_number: questionIndex + 1 })),
      };
    });
  }

  function addQuestion() {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        questions: [
          ...current.questions,
          {
            question_number: current.questions.length + 1,
            question: "",
            optionsText: "\n\n\n",
            correct_answer: "",
            explanation: "",
          },
        ],
      };
    });
  }

  async function saveQuiz() {
    if (!draft) return;

    setSaving(true);
    setSaveError("");
    try {
      const updated = await updateModuleQuiz(projectId, content.id, draftToModuleQuizPayload(draft));
      onUpdated(updated);
      setIsEditing(false);
      setDraft(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setSaveError("Sua sessao expirou. Faca login novamente.");
      } else if (err instanceof Error && err.message) {
        setSaveError(err.message);
      } else {
        setSaveError("Nao foi possivel salvar o quiz.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (isEditing && draft) {
    return (
      <article className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-gold-400">Editor de quiz</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">{draft.module_title || "Quiz"}</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={saveQuiz}
              disabled={saving}
              className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Salvando..." : "Salvar alteracoes"}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsEditing(false);
                setDraft(null);
                setSaveError("");
              }}
              disabled={saving}
              className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancelar
            </button>
          </div>
        </div>
        {saveError ? <p className="mt-4 text-sm text-red-300">{saveError}</p> : null}

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <InputField label="Titulo do quiz / modulo" value={draft.module_title} onChange={(value) => updateDraftField("module_title", value)} />
          <InputField label="Numero do modulo" value={draft.module_number} onChange={(value) => updateDraftField("module_number", value)} />
          <InputField label="Titulo do curso" value={draft.course_title} onChange={(value) => updateDraftField("course_title", value)} />
          <TextAreaField label="Instrucoes" value={draft.instructions} onChange={(value) => updateDraftField("instructions", value)} />
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={addQuestion}
            disabled={saving}
            className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Adicionar pergunta
          </button>
        </div>

        <div className="mt-4 grid gap-4">
          {draft.questions.map((question, index) => (
            <div key={`${question.question_number}-${index}`} className="rounded-md border border-white/10 bg-black/20 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="text-sm font-semibold text-gold-400">Pergunta {index + 1}</p>
                <button
                  type="button"
                  onClick={() => removeQuestion(index)}
                  disabled={saving}
                  className="rounded-md border border-red-400/30 px-3 py-1.5 text-sm text-red-300 transition hover:border-red-300/60 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Remover pergunta
                </button>
              </div>
              <div className="mt-4 grid gap-4">
                <TextAreaField
                  label="Pergunta"
                  value={question.question}
                  rows={3}
                  onChange={(value) => updateQuestion(index, "question", value)}
                />
                <TextAreaField
                  label="Alternativas - uma por linha"
                  value={question.optionsText}
                  rows={5}
                  onChange={(value) => updateQuestion(index, "optionsText", value)}
                />
                <InputField
                  label="Resposta correta"
                  value={question.correct_answer}
                  onChange={(value) => updateQuestion(index, "correct_answer", value)}
                />
                <TextAreaField
                  label="Explicacao / comentario da resposta"
                  value={question.explanation}
                  onChange={(value) => updateQuestion(index, "explanation", value)}
                />
              </div>
            </div>
          ))}
        </div>
      </article>
    );
  }

  return (
    <article className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-gold-400">Modulo {safeText(quiz.module_number)}</p>
          <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-50">{safeText(quiz.module_title)}</h3>
          {quiz.instructions ? <p className="mt-2 text-sm text-slate-400">{safeText(quiz.instructions)}</p> : null}
        </div>
        <button
          type="button"
          onClick={startEditing}
          className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
        >
          Editar quiz
        </button>
      </div>
      <div className="mt-5 grid gap-4">
        {toArray(quiz.questions).map((question, index) => {
          const record = typeof question === "object" && question !== null ? (question as Record<string, unknown>) : null;
          return (
            <div key={itemKey(question, index)} className="rounded-md border border-white/10 bg-black/20 p-4">
              <p className="font-semibold text-slate-100">
                {safeText(record?.question_number ?? index + 1)}. {safeText(record?.question ?? question)}
              </p>
              <div className="mt-3 grid gap-2">
                {toArray(record?.options).map((option, optionIndex) => {
                  const optionRecord = typeof option === "object" && option !== null ? (option as Record<string, unknown>) : null;
                  return (
                    <p key={itemKey(option, optionIndex)} className="rounded border border-white/10 px-3 py-2 text-sm text-slate-300">
                      {safeText(optionRecord?.letter ?? String.fromCharCode(65 + optionIndex))}. {safeText(optionRecord?.text ?? option)}
                    </p>
                  );
                })}
              </div>
              <p className="mt-3 text-sm text-gold-400">Resposta correta: {safeText(record?.correct_answer)}</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-400">{safeText(record?.explanation)}</p>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function MaterialsView({
  contents,
  projectId,
  exporting,
  exportError,
  onUpdated,
  onExport,
}: {
  contents: GeneratedContent[];
  projectId: string;
  exporting: boolean;
  exportError: string;
  onUpdated: (content: GeneratedContent) => void;
  onExport: () => void;
}) {
  if (!contents.length) {
    return <EmptyState text="Materiais complementares ainda nao encontrados." />;
  }

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-navy-950/60 p-4">
        <div>
          <p className="text-sm font-medium text-slate-100">Materiais complementares</p>
          <p className="mt-1 text-xs text-slate-500">Exporte todos os materiais editados deste projeto.</p>
        </div>
        <button
          type="button"
          onClick={onExport}
          disabled={exporting}
          className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {exporting ? "Gerando PDF..." : "Baixar materiais em PDF"}
        </button>
        {exportError ? <p className="w-full text-sm text-red-300">{exportError}</p> : null}
      </div>
      {sortByCreatedAt(contents).map((content) => (
        <MaterialCard key={content.id} content={content} projectId={projectId} onUpdated={onUpdated} />
      ))}
    </div>
  );
}

function MaterialCard({
  content,
  projectId,
  onUpdated,
}: {
  content: GeneratedContent;
  projectId: string;
  onUpdated: (content: GeneratedContent) => void;
}) {
  const raw = content.content_json || {};
  const material = (raw as ComplementaryMaterialContent | null)?.complementary_material;
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<ComplementaryMaterialDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  if (!material) {
    return (
      <article className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <p className="text-xs font-medium text-gold-400">Material complementar</p>
        <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
        <pre className="mt-5 max-h-[720px] overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-black/30 p-4 text-sm leading-6 text-slate-200">
          {JSON.stringify(raw, null, 2)}
        </pre>
      </article>
    );
  }

  function startEditing() {
    if (!material) {
      setSaveError("Material complementar ainda nao encontrado para edicao.");
      return;
    }

    setDraft(materialToDraft(material));
    setSaveError("");
    setIsEditing(true);
  }

  function updateDraftField(field: keyof Omit<ComplementaryMaterialDraft, "key_concepts">, value: string) {
    setDraft((current) => (current ? { ...current, [field]: value } : current));
  }

  function updateConcept(index: number, field: keyof MaterialConceptDraft, value: string) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        key_concepts: current.key_concepts.map((concept, conceptIndex) =>
          conceptIndex === index ? { ...concept, [field]: value } : concept,
        ),
      };
    });
  }

  function addConcept() {
    setDraft((current) =>
      current
        ? {
            ...current,
            key_concepts: [...current.key_concepts, { concept: "", explanation: "" }],
          }
        : current,
    );
  }

  function removeConcept(index: number) {
    const confirmed = window.confirm("Tem certeza que deseja remover este conceito?");
    if (!confirmed) return;
    setDraft((current) =>
      current
        ? {
            ...current,
            key_concepts: current.key_concepts.filter((_, conceptIndex) => conceptIndex !== index),
          }
        : current,
    );
  }

  async function saveMaterial() {
    if (!draft) return;

    setSaving(true);
    setSaveError("");
    try {
      const updated = await updateComplementaryMaterial(projectId, content.id, draftToMaterialPayload(draft));
      onUpdated(updated);
      setIsEditing(false);
      setDraft(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setSaveError("Sua sessao expirou. Faca login novamente.");
      } else if (err instanceof Error && err.message) {
        setSaveError(err.message);
      } else {
        setSaveError("Nao foi possivel salvar o material complementar.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (isEditing && draft) {
    return (
      <article className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-gold-400">Editor de material complementar</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">{draft.material_title || "Material complementar"}</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={saveMaterial}
              disabled={saving}
              className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Salvando..." : "Salvar alteracoes"}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsEditing(false);
                setDraft(null);
                setSaveError("");
              }}
              disabled={saving}
              className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancelar
            </button>
          </div>
        </div>
        {saveError ? <p className="mt-4 text-sm text-red-300">{saveError}</p> : null}

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <InputField label="Titulo do material" value={draft.material_title} onChange={(value) => updateDraftField("material_title", value)} />
          <InputField label="Tipo do material" value={draft.material_type} onChange={(value) => updateDraftField("material_type", value)} />
          <InputField label="Titulo do curso" value={draft.course_title} onChange={(value) => updateDraftField("course_title", value)} />
          <TextAreaField label="Visao geral" value={draft.overview} rows={5} onChange={(value) => updateDraftField("overview", value)} />
        </div>

        <section className="mt-6 rounded-md border border-white/10 bg-black/20 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold text-gold-400">Conceitos-chave</p>
            <button
              type="button"
              onClick={addConcept}
              disabled={saving}
              className="rounded-md border border-gold-500/30 px-3 py-1.5 text-sm text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Adicionar conceito
            </button>
          </div>
          <div className="mt-4 grid gap-4">
            {draft.key_concepts.map((concept, index) => (
              <div key={`${index}-${concept.concept}`} className="rounded-md border border-white/10 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <p className="text-sm text-slate-300">Conceito {index + 1}</p>
                  <button
                    type="button"
                    onClick={() => removeConcept(index)}
                    disabled={saving}
                    className="rounded-md border border-red-400/30 px-3 py-1.5 text-sm text-red-300 transition hover:border-red-300/60 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Remover conceito
                  </button>
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <InputField label="Conceito" value={concept.concept} onChange={(value) => updateConcept(index, "concept", value)} />
                  <TextAreaField
                    label="Explicacao"
                    value={concept.explanation}
                    onChange={(value) => updateConcept(index, "explanation", value)}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <TextAreaField
            label="Aplicacoes praticas - uma por linha"
            value={draft.practicalApplicationsText}
            rows={6}
            onChange={(value) => updateDraftField("practicalApplicationsText", value)}
          />
          <TextAreaField
            label="Exercicios reflexivos - um por linha"
            value={draft.reflectionExercisesText}
            rows={6}
            onChange={(value) => updateDraftField("reflectionExercisesText", value)}
          />
          <TextAreaField
            label="Proximos passos - um por linha"
            value={draft.recommendedNextStepsText}
            rows={6}
            onChange={(value) => updateDraftField("recommendedNextStepsText", value)}
          />
        </div>
      </article>
    );
  }

  return (
    <article className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-gold-400">{safeText(material.material_type || "Material complementar")}</p>
          <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-50">{safeText(material.material_title || "Material complementar")}</h3>
        </div>
        <button
          type="button"
          onClick={startEditing}
          className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
        >
          Editar material
        </button>
      </div>
      <p className="mt-3 whitespace-pre-wrap leading-7 text-slate-400">{safeText(material.overview)}</p>

      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <ConceptBlock items={Array.isArray(material.key_concepts) ? material.key_concepts : []} />
        <ListBlock title="Aplicacoes praticas" items={Array.isArray(material.practical_applications) ? material.practical_applications : []} />
        <ListBlock title="Exercicios reflexivos" items={Array.isArray(material.reflection_exercises) ? material.reflection_exercises : []} />
        <ListBlock title="Proximos passos" items={Array.isArray(material.recommended_next_steps) ? material.recommended_next_steps : []} />
      </div>
    </article>
  );
}

function LessonScriptCard({
  content,
  projectId,
  onUpdated,
}: {
  content: GeneratedContent;
  projectId: string;
  onUpdated: (content: GeneratedContent) => void;
}) {
  const script = (content.content_json as LessonScriptContent | null)?.lesson_script;
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<LessonScriptDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  if (!script) return null;

  function startEditing() {
    if (!script) {
      setSaveError("Roteiro ainda nao encontrado para edicao.");
      return;
    }

    setDraft(lessonScriptToDraft(script));
    setSaveError("");
    setIsEditing(true);
  }

  function updateDraftField(field: keyof Omit<LessonScriptDraft, "main_script">, value: string) {
    setDraft((current) => (current ? { ...current, [field]: value } : current));
  }

  function updateSection(index: number, field: keyof LessonSectionDraft, value: string) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        main_script: current.main_script.map((section, sectionIndex) =>
          sectionIndex === index ? { ...section, [field]: value } : section,
        ),
      };
    });
  }

  function removeSection(index: number) {
    const confirmed = window.confirm("Tem certeza que deseja remover esta secao do roteiro?");
    if (!confirmed) return;
    setDraft((current) =>
      current
        ? {
            ...current,
            main_script: current.main_script.filter((_, sectionIndex) => sectionIndex !== index),
          }
        : current,
    );
  }

  async function saveLessonScript() {
    if (!draft) return;

    setSaving(true);
    setSaveError("");
    try {
      const updated = await updateLessonScript(projectId, content.id, draftToLessonScriptPayload(draft));
      onUpdated(updated);
      setIsEditing(false);
      setDraft(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setSaveError("Sua sessao expirou. Faca login novamente.");
      } else if (err instanceof Error && err.message) {
        setSaveError(err.message);
      } else {
        setSaveError("Nao foi possivel salvar o roteiro.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (isEditing && draft) {
    return (
      <article className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-gold-400">Editor de roteiro</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">{draft.lesson_title || "Roteiro de aula"}</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={saveLessonScript}
              disabled={saving}
              className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Salvando..." : "Salvar alteracoes"}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsEditing(false);
                setDraft(null);
                setSaveError("");
              }}
              disabled={saving}
              className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancelar
            </button>
          </div>
        </div>
        {saveError ? <p className="mt-4 text-sm text-red-300">{saveError}</p> : null}

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <InputField label="Titulo da aula" value={draft.lesson_title} onChange={(value) => updateDraftField("lesson_title", value)} />
          <InputField label="Modulo" value={draft.module_title} onChange={(value) => updateDraftField("module_title", value)} />
          <InputField label="Numero do modulo" value={draft.module_number} onChange={(value) => updateDraftField("module_number", value)} />
          <InputField label="Numero da aula" value={draft.lesson_number} onChange={(value) => updateDraftField("lesson_number", value)} />
          <InputField
            label="Duracao estimada em minutos"
            value={draft.estimated_duration_minutes}
            onChange={(value) => updateDraftField("estimated_duration_minutes", value)}
          />
          <InputField label="Titulo do curso" value={draft.course_title} onChange={(value) => updateDraftField("course_title", value)} />
          <TextAreaField label="Introducao / abertura" value={draft.opening} onChange={(value) => updateDraftField("opening", value)} />
          <TextAreaField
            label="Objetivo da aula"
            value={draft.learning_objective}
            onChange={(value) => updateDraftField("learning_objective", value)}
          />
          <TextAreaField
            label="Exemplo pratico"
            value={draft.practical_example}
            onChange={(value) => updateDraftField("practical_example", value)}
          />
          <TextAreaField
            label="Atividade / pergunta reflexiva"
            value={draft.reflection_question}
            onChange={(value) => updateDraftField("reflection_question", value)}
          />
          <TextAreaField label="Conclusao" value={draft.closing} onChange={(value) => updateDraftField("closing", value)} />
          <TextAreaField
            label="Call to action"
            value={draft.call_to_action}
            onChange={(value) => updateDraftField("call_to_action", value)}
          />
        </div>

        <div className="mt-6 grid gap-4">
          {draft.main_script.map((section, index) => (
            <div key={`${index}-${section.section_title}`} className="rounded-md border border-white/10 bg-black/20 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-semibold text-gold-400">Secao {index + 1}</p>
                <button
                  type="button"
                  onClick={() => removeSection(index)}
                  disabled={saving}
                  className="rounded-md border border-red-400/30 px-3 py-1.5 text-sm text-red-300 transition hover:border-red-300/60 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Remover secao
                </button>
              </div>
              <div className="mt-4 grid gap-4">
                <InputField
                  label="Titulo da secao"
                  value={section.section_title}
                  onChange={(value) => updateSection(index, "section_title", value)}
                />
                <TextAreaField
                  label="Texto de narracao / desenvolvimento"
                  value={section.narration}
                  rows={7}
                  onChange={(value) => updateSection(index, "narration", value)}
                />
                <TextAreaField
                  label="Notas do instrutor"
                  value={section.teaching_notes}
                  onChange={(value) => updateSection(index, "teaching_notes", value)}
                />
                <TextAreaField
                  label="Sugestao visual"
                  value={section.visual_suggestion}
                  onChange={(value) => updateSection(index, "visual_suggestion", value)}
                />
              </div>
            </div>
          ))}
        </div>
      </article>
    );
  }

  return (
    <article className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-gold-400">
            Modulo {safeText(script.module_number)} - Aula {safeText(script.lesson_number)}
          </p>
          <p className="mt-1 text-xs text-slate-500">{getLanguageLabel(getGenerationLanguage(content))}</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-50">{safeText(script.lesson_title)}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-gold-400">{safeText(script.estimated_duration_minutes || 10)} min</span>
          <button
            type="button"
            onClick={startEditing}
            className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
          >
            Editar roteiro
          </button>
        </div>
      </div>
      <InfoBlock label="Abertura" value={script.opening} />
      <InfoBlock label="Objetivo" value={script.learning_objective} />
      <div className="mt-4 grid gap-3">
        {toArray(script.main_script).map((section, index) => {
          const record = typeof section === "object" && section !== null ? (section as Record<string, unknown>) : null;
          return (
            <div key={itemKey(section, index)} className="rounded-md border border-white/10 bg-black/20 p-4">
              <h4 className="font-semibold text-slate-100">{safeText(record?.section_title ?? `Secao ${index + 1}`)}</h4>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{safeText(record?.narration ?? section)}</p>
              <p className="mt-3 whitespace-pre-wrap text-xs text-slate-500">{safeText(record?.teaching_notes)}</p>
              <p className="mt-2 whitespace-pre-wrap text-xs text-gold-400">{safeText(record?.visual_suggestion)}</p>
            </div>
          );
        })}
      </div>
      <InfoBlock label="Exemplo pratico" value={script.practical_example} />
      <InfoBlock label="Pergunta reflexiva" value={script.reflection_question} />
      <InfoBlock label="Fechamento" value={script.closing} />
      <InfoBlock label="Call to action" value={script.call_to_action} />
    </article>
  );
}

function PresentationView({
  contents,
  projectId,
  exporting,
  exportError,
  exportingPptx,
  pptxError,
  onUpdated,
  onExport,
  onExportPptx,
}: {
  contents: GeneratedContent[];
  projectId: string;
  exporting: boolean;
  exportError: string;
  exportingPptx: boolean;
  pptxError: string;
  onUpdated: (content: GeneratedContent) => void;
  onExport: () => Promise<void>;
  onExportPptx: () => Promise<void>;
}) {
  const content = sortSummaries(contents)[0];
  const deck = content?.content_json as PresentationDeckContent | undefined;
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<PresentationDeckDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  if (!deck) {
    return (
      <EmptyState text="A apresentacao ainda nao foi gerada. Gere os conteudos educacionais para criar a apresentacao." />
    );
  }

  const slides = Array.isArray(deck.slides) ? deck.slides : [];

  function startEditing() {
    if (!deck) {
      setSaveError("Apresentacao ainda nao encontrada para edicao.");
      return;
    }

    setDraft(deckToDraft(deck));
    setSaveError("");
    setIsEditing(true);
  }

  function updateDraftField(field: keyof Omit<PresentationDeckDraft, "slides">, value: string) {
    setDraft((current) => (current ? { ...current, [field]: value } : current));
  }

  function updateSlide(index: number, field: keyof PresentationSlideDraft, value: string) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        slides: current.slides.map((slide, slideIndex) =>
          slideIndex === index ? { ...slide, [field]: value } : slide,
        ),
      };
    });
  }

  function removeSlide(index: number) {
    const confirmed = window.confirm("Tem certeza que deseja remover este slide?");
    if (!confirmed) return;

    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        slides: current.slides
          .filter((_, slideIndex) => slideIndex !== index)
          .map((slide, slideIndex) => ({ ...slide, slide_number: slideIndex + 1 })),
      };
    });
  }

  async function savePresentation() {
    if (!draft) return;

    setSaving(true);
    setSaveError("");
    try {
      const updated = await updatePresentationDeck(projectId, draftToPayload(draft));
      onUpdated(updated);
      setIsEditing(false);
      setDraft(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setSaveError("Sua sessao expirou. Faca login novamente.");
      } else if (err instanceof Error && err.message) {
        setSaveError(err.message);
      } else {
        setSaveError("Nao foi possivel salvar a apresentacao.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (isEditing && draft) {
    return (
      <div className="grid gap-6">
        <section className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm text-gold-400">Editor da apresentacao</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-50">Editar apresentacao</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={savePresentation}
                disabled={saving}
                className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "Salvando..." : "Salvar alteracoes"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsEditing(false);
                  setDraft(null);
                  setSaveError("");
                }}
                disabled={saving}
                className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-300 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancelar
              </button>
            </div>
          </div>
          {saveError ? <p className="mt-4 text-sm text-red-300">{saveError}</p> : null}

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <InputField
              label="Titulo da apresentacao"
              value={draft.presentation_title}
              onChange={(value) => updateDraftField("presentation_title", value)}
            />
            <InputField
              label="Publico-alvo"
              value={draft.target_audience}
              onChange={(value) => updateDraftField("target_audience", value)}
            />
            <InputField
              label="Duracao estimada"
              value={draft.estimated_duration}
              onChange={(value) => updateDraftField("estimated_duration", value)}
            />
            <InputField
              label="Estilo visual"
              value={draft.visual_style}
              onChange={(value) => updateDraftField("visual_style", value)}
            />
            <TextAreaField
              label="Objetivo da apresentacao"
              value={draft.presentation_objective}
              onChange={(value) => updateDraftField("presentation_objective", value)}
            />
            <TextAreaField
              label="Mensagem de encerramento"
              value={draft.closing_message}
              onChange={(value) => updateDraftField("closing_message", value)}
            />
          </div>
        </section>

        <div className="grid gap-5">
          {draft.slides.map((slide, index) => (
            <article key={`${slide.slide_number}-${index}`} className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="text-sm font-semibold text-gold-400">Slide {slide.slide_number}</p>
                <button
                  type="button"
                  onClick={() => removeSlide(index)}
                  disabled={saving}
                  className="rounded-md border border-red-400/30 px-3 py-1.5 text-sm text-red-300 transition hover:border-red-300/60 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Remover slide
                </button>
              </div>
              <div className="mt-4 grid gap-4">
                <InputField label="Titulo" value={slide.title} onChange={(value) => updateSlide(index, "title", value)} />
                <InputField
                  label="Subtitulo"
                  value={slide.subtitle}
                  onChange={(value) => updateSlide(index, "subtitle", value)}
                />
                <TextAreaField
                  label="Bullets - um por linha"
                  value={slide.bulletsText}
                  rows={5}
                  onChange={(value) => updateSlide(index, "bulletsText", value)}
                />
                <TextAreaField
                  label="Notas do apresentador"
                  value={slide.speaker_notes}
                  onChange={(value) => updateSlide(index, "speaker_notes", value)}
                />
                <TextAreaField
                  label="Sugestao visual"
                  value={slide.visual_suggestion}
                  onChange={(value) => updateSlide(index, "visual_suggestion", value)}
                />
                <TextAreaField
                  label="Pergunta de interacao"
                  value={slide.interaction_question}
                  onChange={(value) => updateSlide(index, "interaction_question", value)}
                />
              </div>
            </article>
          ))}
        </div>
      </div>
    );
  }

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
          <button
            type="button"
            onClick={onExportPptx}
            disabled={exportingPptx}
            className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exportingPptx ? "Gerando PPTX..." : "Baixar apresentacao em PPTX"}
          </button>
          <button
            type="button"
            onClick={startEditing}
            className="rounded-md border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
          >
            Editar apresentacao
          </button>
        </div>
        {exportError ? <p className="mt-4 text-sm text-red-300">{exportError}</p> : null}
        {pptxError ? <p className="mt-4 text-sm text-red-300">{pptxError}</p> : null}
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

function getLessonScriptLabel(script: LessonScriptContent["lesson_script"] | undefined, content?: GeneratedContent): string {
  if (!script) return content?.title || "Roteiro de aula";
  const moduleNumber = safeText(script.module_number);
  const lessonNumber = safeText(script.lesson_number);
  const lessonTitle = safeText(script.lesson_title || content?.title || "Roteiro de aula");
  const moduleLabel = moduleNumber === "Nao informado" ? "Modulo" : `Modulo ${moduleNumber}`;
  const lessonLabel = lessonNumber === "Nao informado" ? "Aula" : `Aula ${lessonNumber}`;
  return `${moduleLabel} - ${lessonLabel}: ${lessonTitle}`;
}

function appendTeleprompterSection(parts: string[], title: string, value: unknown) {
  const text = editText(value).trim();
  if (!text) return;
  parts.push(`${title}\n${text}`);
}

function buildBlockText(block: unknown, index: number): string {
  const record = typeof block === "object" && block !== null ? (block as Record<string, unknown>) : null;
  if (!record) return editText(block);
  const parts: string[] = [];
  const title = editText(record.section_title ?? record.title ?? record.name);
  if (title) parts.push(title);
  const narration = editText(record.narration ?? record.script_text ?? record.content ?? record.text ?? record.description);
  if (narration) parts.push(narration);
  const example = editText(record.example ?? record.practical_example);
  if (example) parts.push(example);
  const note = editText(record.instructor_notes ?? record.teaching_notes);
  if (note) parts.push(`Nota para o instrutor: ${note}`);
  const visual = editText(record.visual_suggestion);
  if (visual) parts.push(`Sugestao visual: ${visual}`);
  return parts.join("\n") || `Bloco ${index + 1}`;
}

function buildTeleprompterText(script: NonNullable<LessonScriptContent["lesson_script"]>): string {
  const parts: string[] = [];

  appendTeleprompterSection(parts, "Abertura", script.opening);
  appendTeleprompterSection(parts, "Introducao", (script as Record<string, unknown>).introduction);
  appendTeleprompterSection(parts, "Objetivo da aula", script.learning_objective);
  appendTeleprompterSection(parts, "Texto de narracao", (script as Record<string, unknown>).narration_text);
  appendTeleprompterSection(parts, "Roteiro principal", (script as Record<string, unknown>).script_text);
  appendTeleprompterSection(parts, "Narracao", (script as Record<string, unknown>).narration);
  appendTeleprompterSection(parts, "Desenvolvimento", (script as Record<string, unknown>).development);

  const blocks =
    toArray(script.main_script).length > 0
      ? toArray(script.main_script)
      : toArray((script as Record<string, unknown>).sections || (script as Record<string, unknown>).blocks);
  const blockTexts = blocks.map((block, index) => buildBlockText(block, index)).filter(Boolean);
  if (blockTexts.length) {
    parts.push(["Blocos da aula", ...blockTexts].join("\n\n"));
  }

  appendTeleprompterSection(parts, "Exemplo pratico", script.practical_example ?? (script as Record<string, unknown>).examples);
  appendTeleprompterSection(parts, "Atividade pratica", (script as Record<string, unknown>).practical_activity);
  appendTeleprompterSection(parts, "Pergunta de reflexao", script.reflection_question);
  appendTeleprompterSection(parts, "Conclusao", script.closing ?? (script as Record<string, unknown>).conclusion);
  appendTeleprompterSection(parts, "Call to action", script.call_to_action);
  appendTeleprompterSection(parts, "Notas do instrutor", (script as Record<string, unknown>).instructor_notes);

  return parts.join("\n\n").trim();
}

function cleanNarrationText(text: string): string {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .split("\n")
    .map((line) => line.trim())
    .join("\n")
    .trim();
}

function narrationValueToText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);

  if (Array.isArray(value)) {
    return value.map((item) => narrationValueToText(item)).filter(Boolean).join("\n\n");
  }

  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const parts = [
      record.narration_text,
      record.narration,
      record.script_text,
      record.content,
      record.text,
      record.description,
      record.explanation,
      record.example,
      record.practical_example,
    ]
      .map((item) => narrationValueToText(item))
      .filter(Boolean);

    if (parts.length) return parts.join("\n\n");

    return Object.entries(record)
      .filter(([key]) => !["module_number", "lesson_number", "metadata", "estimated_duration", "estimated_duration_minutes"].includes(key))
      .map(([, item]) => narrationValueToText(item))
      .filter(Boolean)
      .join("\n\n");
  }

  return "";
}

function appendNarrationSection(parts: string[], value: unknown) {
  const text = cleanNarrationText(narrationValueToText(value));
  if (text) parts.push(text);
}

function buildNarrationText(script: NonNullable<LessonScriptContent["lesson_script"]>): string {
  const record = script as Record<string, unknown>;
  const parts: string[] = [];

  appendNarrationSection(parts, record.narration_text);
  appendNarrationSection(parts, record.narration);
  appendNarrationSection(parts, record.script_text);

  if (!parts.length) {
    appendNarrationSection(parts, script.opening);
    appendNarrationSection(parts, record.introduction);
    appendNarrationSection(parts, record.development);
    appendNarrationSection(parts, script.main_script);
    appendNarrationSection(parts, record.sections);
    appendNarrationSection(parts, record.examples ?? script.practical_example);
    appendNarrationSection(parts, record.practical_activity);
    appendNarrationSection(parts, record.conclusion ?? script.closing);
    appendNarrationSection(parts, script.call_to_action);
  } else {
    appendNarrationSection(parts, script.opening);
    appendNarrationSection(parts, record.development);
    appendNarrationSection(parts, record.conclusion ?? script.closing);
    appendNarrationSection(parts, script.call_to_action);
  }

  return cleanNarrationText(parts.join("\n\n"));
}

function splitNarrationBlocks(text: string): string[] {
  const cleanText = cleanNarrationText(text);
  if (!cleanText) return [];
  if (cleanText.length <= 1200) return [cleanText];

  const paragraphs = cleanText.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
  const chunks = paragraphs.length > 1 ? paragraphs : cleanText.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [cleanText];
  const blocks: string[] = [];
  let current = "";

  chunks.forEach((chunk) => {
    const candidate = current ? `${current}\n\n${chunk.trim()}` : chunk.trim();
    if (candidate.length <= 1200 || current.length < 700) {
      current = candidate;
      return;
    }

    if (current) blocks.push(current);
    current = chunk.trim();
  });

  if (current) blocks.push(current);

  return blocks.flatMap((block) => {
    if (block.length <= 1400) return [block];
    const sentences = block.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [block];
    const sentenceBlocks: string[] = [];
    let currentSentenceBlock = "";
    sentences.forEach((sentence) => {
      const candidate = currentSentenceBlock ? `${currentSentenceBlock} ${sentence.trim()}` : sentence.trim();
      if (candidate.length <= 1200 || !currentSentenceBlock) {
        currentSentenceBlock = candidate;
      } else {
        sentenceBlocks.push(currentSentenceBlock);
        currentSentenceBlock = sentence.trim();
      }
    });
    if (currentSentenceBlock) sentenceBlocks.push(currentSentenceBlock);
    return sentenceBlocks;
  });
}

function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function formatSpeechTime(text: string): string {
  const words = countWords(text);
  if (!words) return "menos de 1 min";
  const minutes = Math.round(words / 130);
  if (minutes < 1) return "menos de 1 min";
  return `${minutes} min`;
}

function getEstimatedSpeechTime(text: string): string {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  if (!words) return "menos de 1 min";
  const minutes = Math.round(words / 130);
  if (minutes < 1) return "menos de 1 min";
  return `Tempo estimado: ${minutes} min`;
}

function toArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined || value === "") return [];
  return [value];
}

function editText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((item) => editText(item)).filter(Boolean).join("\n");
  return safeText(value);
}

function lessonScriptToDraft(script: NonNullable<LessonScriptContent["lesson_script"]>): LessonScriptDraft {
  return {
    course_title: editText(script.course_title),
    module_number: editText(script.module_number),
    module_title: editText(script.module_title),
    lesson_number: editText(script.lesson_number),
    lesson_title: editText(script.lesson_title),
    estimated_duration_minutes: editText(script.estimated_duration_minutes || 10),
    opening: editText(script.opening),
    learning_objective: editText(script.learning_objective),
    practical_example: editText(script.practical_example),
    reflection_question: editText(script.reflection_question),
    closing: editText(script.closing),
    call_to_action: editText(script.call_to_action),
    main_script: toArray(script.main_script).map((section) => {
      const record = typeof section === "object" && section !== null ? (section as Record<string, unknown>) : null;
      return {
        section_title: editText(record?.section_title),
        narration: editText(record?.narration ?? section),
        teaching_notes: editText(record?.teaching_notes),
        visual_suggestion: editText(record?.visual_suggestion),
      };
    }),
  };
}

function draftToLessonScriptPayload(draft: LessonScriptDraft): LessonScriptContent {
  const toNumber = (value: string, fallback: number) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  return {
    lesson_script: {
      course_title: draft.course_title,
      module_number: toNumber(draft.module_number, 1),
      module_title: draft.module_title,
      lesson_number: toNumber(draft.lesson_number, 1),
      lesson_title: draft.lesson_title,
      estimated_duration_minutes: toNumber(draft.estimated_duration_minutes, 10),
      opening: draft.opening,
      learning_objective: draft.learning_objective,
      main_script: draft.main_script.map((section) => ({
        section_title: section.section_title,
        narration: section.narration,
        teaching_notes: section.teaching_notes,
        visual_suggestion: section.visual_suggestion,
      })),
      practical_example: draft.practical_example,
      reflection_question: draft.reflection_question,
      closing: draft.closing,
      call_to_action: draft.call_to_action,
    },
  };
}

function quizToDraft(quiz: NonNullable<ModuleQuizContent["module_quiz"]>): ModuleQuizDraft {
  return {
    course_title: editText(quiz.course_title),
    module_number: editText(quiz.module_number),
    module_title: editText(quiz.module_title),
    instructions: editText(quiz.instructions),
    questions: toArray(quiz.questions).map((question, index) => {
      const record = typeof question === "object" && question !== null ? (question as Record<string, unknown>) : null;
      return {
        question_number: index + 1,
        question: editText(record?.question ?? question),
        optionsText: toArray(record?.options)
          .map((option) => {
            const optionRecord = typeof option === "object" && option !== null ? (option as Record<string, unknown>) : null;
            return editText(optionRecord?.text ?? option);
          })
          .filter(Boolean)
          .join("\n"),
        correct_answer: editText(record?.correct_answer),
        explanation: editText(record?.explanation),
      };
    }),
  };
}

function draftToModuleQuizPayload(draft: ModuleQuizDraft): ModuleQuizContent {
  const parsedModuleNumber = Number(draft.module_number);
  const moduleNumber = Number.isFinite(parsedModuleNumber) ? parsedModuleNumber : 1;

  return {
    module_quiz: {
      course_title: draft.course_title,
      module_number: moduleNumber,
      module_title: draft.module_title,
      instructions: draft.instructions,
      questions: draft.questions.map((question, questionIndex) => ({
        question_number: questionIndex + 1,
        question: question.question,
        options: question.optionsText
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean)
          .map((line, optionIndex) => ({
            letter: String.fromCharCode(65 + optionIndex),
            text: line,
          })),
        correct_answer: question.correct_answer,
        explanation: question.explanation,
      })),
    },
  };
}

function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function materialToDraft(
  material: NonNullable<ComplementaryMaterialContent["complementary_material"]>,
): ComplementaryMaterialDraft {
  return {
    course_title: editText(material.course_title),
    material_title: editText(material.material_title),
    material_type: editText(material.material_type),
    overview: editText(material.overview),
    key_concepts: toArray(material.key_concepts).map((concept) => {
      const record = typeof concept === "object" && concept !== null ? (concept as Record<string, unknown>) : null;
      return {
        concept: editText(record?.concept ?? record?.title ?? record?.name ?? concept),
        explanation: editText(record?.explanation ?? record?.description ?? record?.text),
      };
    }),
    practicalApplicationsText: toArray(material.practical_applications).map((item) => editText(item)).filter(Boolean).join("\n"),
    reflectionExercisesText: toArray(material.reflection_exercises).map((item) => editText(item)).filter(Boolean).join("\n"),
    recommendedNextStepsText: toArray(material.recommended_next_steps).map((item) => editText(item)).filter(Boolean).join("\n"),
  };
}

function draftToMaterialPayload(draft: ComplementaryMaterialDraft): ComplementaryMaterialContent {
  return {
    complementary_material: {
      course_title: draft.course_title,
      material_title: draft.material_title,
      material_type: draft.material_type,
      overview: draft.overview,
      key_concepts: draft.key_concepts.filter((concept) => concept.concept.trim() || concept.explanation.trim()),
      practical_applications: linesToList(draft.practicalApplicationsText),
      reflection_exercises: linesToList(draft.reflectionExercisesText),
      recommended_next_steps: linesToList(draft.recommendedNextStepsText),
    },
  };
}

function deckToDraft(deck: PresentationDeckContent): PresentationDeckDraft {
  const slides = Array.isArray(deck.slides) ? deck.slides : [];
  return {
    presentation_title: editText(deck.presentation_title),
    target_audience: editText(deck.target_audience),
    estimated_duration: editText(deck.estimated_duration),
    visual_style: editText(deck.visual_style),
    presentation_objective: editText(deck.presentation_objective),
    closing_message: editText(deck.closing_message),
    slides: slides.map((slide, index) => ({
      slide_number: index + 1,
      title: editText(slide?.title),
      subtitle: editText(slide?.subtitle),
      bulletsText: toArray(slide?.bullets).map((item) => editText(item)).filter(Boolean).join("\n"),
      speaker_notes: editText(slide?.speaker_notes),
      visual_suggestion: editText(slide?.visual_suggestion),
      interaction_question: editText(slide?.interaction_question),
    })),
  };
}

function draftToPayload(draft: PresentationDeckDraft): PresentationDeckContent {
  return {
    presentation_title: draft.presentation_title,
    target_audience: draft.target_audience,
    estimated_duration: draft.estimated_duration,
    visual_style: draft.visual_style,
    presentation_objective: draft.presentation_objective,
    closing_message: draft.closing_message,
    slides: draft.slides.map((slide, index) => ({
      slide_number: index + 1,
      title: slide.title,
      subtitle: slide.subtitle,
      bullets: slide.bulletsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      speaker_notes: slide.speaker_notes,
      visual_suggestion: slide.visual_suggestion,
      interaction_question: slide.interaction_question,
    })),
  };
}

function itemKey(item: unknown, index: number): string {
  return `${index}-${safeText(item).slice(0, 60)}`;
}

function InputField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
      />
    </label>
  );
}

function TextAreaField({
  label,
  value,
  rows = 4,
  onChange,
}: {
  label: string;
  value: string;
  rows?: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      {label}
      <textarea
        value={value}
        rows={rows}
        onChange={(event) => onChange(event.target.value)}
        className="resize-y rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-gold-500/60"
      />
    </label>
  );
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
