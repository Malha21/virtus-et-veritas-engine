"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import {
  ApiError,
  apiFetch,
  cancelVideoPipelineJob,
  createCourseExport,
  createProjectVideoAvatar,
  createVideoPipelineJob,
  deleteCourseExport,
  deleteProjectAudio,
  deleteProjectVideo,
  deleteProjectVideoAvatar,
  downloadComplementaryMaterialsPdf,
  downloadCourseExport,
  downloadFullCoursePdf,
  downloadLessonScriptsPdf,
  downloadNarrationAudiosZip,
  downloadNarrationAudio,
  downloadProjectVideo,
  downloadPresentationPdf,
  downloadPresentationPptx,
  downloadQuizzesPdf,
  fetchNarrationAudioBlob,
  generateNarrationAudio,
  generateDocumentAnalysis,
  getInstructorProfile,
  getCourseExport,
  getDocumentAnalysis,
  generateProjectVideo,
  getProjectVideoSettings,
  getVideoPipelineJob,
  listCourseExports,
  listProjectAudios,
  listProjectVideoAvatars,
  listProjectVideos,
  listVideoPipelineJobs,
  refreshProjectVideoStatus,
  retryFailedVideoPipelineJob,
  runVideoPipelineJob,
  type CourseExport,
  type CourseExportCreatePayload,
  type CourseExportTextFormat,
  type GeneratedAudio,
  type GeneratedVideo,
  type InstructorProfile,
  type ProjectVideoSettings,
  type ProjectVideoSettingsUpdatePayload,
  type VideoAvatar,
  type VideoAvatarCreatePayload,
  type VideoAvatarUpdatePayload,
  type VideoPipelineJob,
  type VideoPipelineScope,
  type VideoProvider,
  type VideoReviewUpdatePayload,
  updateComplementaryMaterial,
  updateLessonScript,
  updateModuleQuiz,
  updatePresentationDeck,
  updateProjectVideoAvatar,
  updateProjectVideoReview,
  updateProjectVideoSettings,
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

type Tab =
  | "document-base"
  | "summary"
  | "scripts"
  | "quizzes"
  | "materials"
  | "presentation"
  | "teleprompter"
  | "narration"
  | "video"
  | "export";
type NarrationMode = "lesson" | "module";

type LessonModuleGroup = {
  key: string;
  moduleNumber: number;
  moduleTitle: string;
  lessons: GeneratedContent[];
};

type NarrationAudioGroups = {
  byLessonId: Record<string, GeneratedAudio[]>;
  byModuleKey: Record<string, GeneratedAudio[]>;
  others: GeneratedAudio[];
};

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
  const [documentAnalysis, setDocumentAnalysis] = useState<GeneratedContent | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("document-base");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [documentAnalysisError, setDocumentAnalysisError] = useState("");
  const [generatingDocumentAnalysis, setGeneratingDocumentAnalysis] = useState(false);
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

    getDocumentAnalysis(params.id)
      .then((content) => setDocumentAnalysis(content))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          setDocumentAnalysisError("Sua sessao expirou. Faca login novamente.");
        } else if (err instanceof Error && err.message) {
          setDocumentAnalysisError(err.message);
        } else {
          setDocumentAnalysisError("Nao foi possivel carregar a analise do documento base.");
        }
      });
  }, [params.id]);

  async function handleGenerateDocumentAnalysis() {
    setGeneratingDocumentAnalysis(true);
    setDocumentAnalysisError("");
    try {
      const content = await generateDocumentAnalysis(params.id);
      setDocumentAnalysis(content);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setDocumentAnalysisError("Sua sessao expirou. Faca login novamente.");
      } else if (err instanceof Error && err.message) {
        setDocumentAnalysisError(err.message);
      } else {
        setDocumentAnalysisError("Nao foi possivel gerar a analise do documento base.");
      }
    } finally {
      setGeneratingDocumentAnalysis(false);
    }
  }

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
            <TabButton active={activeTab === "document-base"} onClick={() => setActiveTab("document-base")}>
              Documento Base
            </TabButton>
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
            <TabButton active={activeTab === "video"} onClick={() => setActiveTab("video")}>
              Vídeo
            </TabButton>
            <TabButton active={activeTab === "export"} onClick={() => setActiveTab("export")}>
              Exportação
            </TabButton>
          </div>

          {loading ? (
            <p className="mt-8 text-slate-300">Carregando conteudos...</p>
          ) : error ? (
            <p className="mt-8 text-red-300">{error}</p>
          ) : data ? (
            <div className="mt-8">
              {activeTab === "document-base" ? (
                <DocumentBaseView
                  content={documentAnalysis}
                  error={documentAnalysisError}
                  generating={generatingDocumentAnalysis}
                  onGenerate={handleGenerateDocumentAnalysis}
                />
              ) : null}
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
              {activeTab === "narration" ? <NarrationView contents={data.lesson_scripts} projectId={params.id} /> : null}
              {activeTab === "video" ? <VideoView contents={data.lesson_scripts} projectId={params.id} /> : null}
              {activeTab === "export" ? <ExportView projectId={params.id} /> : null}
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

function getDocumentAnalysisPayload(content: GeneratedContent | null): Record<string, unknown> | null {
  const contentJson = content?.content_json || null;
  const documentAnalysis = contentJson?.document_analysis;
  if (typeof documentAnalysis === "object" && documentAnalysis !== null && !Array.isArray(documentAnalysis)) {
    return documentAnalysis as Record<string, unknown>;
  }
  return contentJson;
}

function DocumentBaseView({
  content,
  error,
  generating,
  onGenerate,
}: {
  content: GeneratedContent | null;
  error: string;
  generating: boolean;
  onGenerate: () => void;
}) {
  const analysis = getDocumentAnalysisPayload(content);
  const originality = analysis?.originality_strategy as Record<string, unknown> | undefined;

  return (
    <div className="grid gap-5">
      <section className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-gold-400">Documento Base</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">Analise Inteligente do Documento Base</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              Esta analise interpreta o PDF enviado com linguagem propria, sem inventar informacoes externas.
            </p>
          </div>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating}
            className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {generating ? "Gerando analise..." : "Gerar analise do documento"}
          </button>
        </div>
        {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}
        {!analysis ? (
          <p className="mt-4 rounded-md border border-white/10 bg-black/20 p-4 text-sm text-slate-300">
            A analise do documento base ainda nao foi gerada.
          </p>
        ) : null}
      </section>

      {analysis ? (
        <>
          <InfoBlock label="Titulo do documento" value={analysis.document_title} />
          <InfoBlock label="Visao geral" value={analysis.source_overview} />
          <InfoBlock label="Resumo autoral" value={analysis.authorial_summary} />
          <div className="grid gap-5 md:grid-cols-2">
            <ListBlock title="Ideias centrais" items={Array.isArray(analysis.central_ideas) ? analysis.central_ideas : []} />
            <ListBlock title="Conceitos-chave" items={Array.isArray(analysis.key_concepts) ? analysis.key_concepts : []} />
          </div>
          <DocumentSequenceBlock items={Array.isArray(analysis.document_sequence) ? analysis.document_sequence : []} />
          <CoursePathBlock items={Array.isArray(analysis.suggested_course_path) ? analysis.suggested_course_path : []} />
          <InfoBlock label="Notas de cobertura" value={analysis.coverage_notes} />
          <ListBlock title="Limitacoes" items={Array.isArray(analysis.limitations) ? analysis.limitations : []} />
          <div className="grid gap-5 md:grid-cols-2">
            <InfoBlock label="Estrategia de reescrita" value={originality?.rewrite_guidance} />
            <InfoBlock label="Tom sugerido" value={originality?.tone} />
          </div>
          <ListBlock title="O que evitar" items={Array.isArray(originality?.what_to_avoid) ? originality?.what_to_avoid : []} />
          <ListBlock title="Regras de fidelidade" items={Array.isArray(analysis.fidelity_rules) ? analysis.fidelity_rules : []} />
        </>
      ) : null}
    </div>
  );
}

function DocumentSequenceBlock({ items }: { items: unknown[] }) {
  if (!items.length) return <ListBlock title="Sequencia do documento" items={[]} />;
  return (
    <section className="rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm text-slate-400">Sequencia do documento</p>
      <div className="mt-3 grid gap-3">
        {items.map((item, index) => {
          const record = typeof item === "object" && item !== null ? (item as Record<string, unknown>) : {};
          return (
            <article key={itemKey(item, index)} className="rounded border border-white/10 bg-navy-950/60 px-3 py-2">
              <p className="font-medium text-slate-100">
                {safeText(record.order ?? index + 1)}. {safeText(record.topic)}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{safeText(record.summary)}</p>
              <p className="mt-2 whitespace-pre-wrap text-xs text-gold-300">{safeText(record.didactic_relevance)}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function CoursePathBlock({ items }: { items: unknown[] }) {
  if (!items.length) return <ListBlock title="Caminho sugerido para o curso" items={[]} />;
  return (
    <section className="rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm text-slate-400">Caminho sugerido para o curso</p>
      <div className="mt-3 grid gap-3">
        {items.map((item, index) => {
          const record = typeof item === "object" && item !== null ? (item as Record<string, unknown>) : {};
          return (
            <article key={itemKey(item, index)} className="rounded border border-white/10 bg-navy-950/60 px-3 py-2">
              <p className="font-medium text-slate-100">{safeText(record.module_title ?? `Modulo ${index + 1}`)}</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{safeText(record.reason)}</p>
              <ListBlock title="Possiveis aulas" items={Array.isArray(record.possible_lessons) ? record.possible_lessons : []} />
            </article>
          );
        })}
      </div>
    </section>
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
    const copied = await copyTextToClipboard(teleprompterText);
    if (copied) {
      setCopyMessage("Texto copiado");
    } else {
      setCopyMessage("Não foi possível copiar automaticamente. Selecione o texto e copie manualmente.");
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

function NarrationView({ contents, projectId }: { contents: GeneratedContent[]; projectId: string }) {
  const sortedContents = sortLessonScripts(contents);
  const moduleGroups = groupLessonsByModule(sortedContents);
  const [mode, setMode] = useState<NarrationMode>("lesson");
  const [selectedId, setSelectedId] = useState(sortedContents[0]?.id || "");
  const [selectedModuleKey, setSelectedModuleKey] = useState(moduleGroups[0]?.key || "");
  const [copiedKey, setCopiedKey] = useState("");
  const [audios, setAudios] = useState<GeneratedAudio[]>([]);
  const [audioUrls, setAudioUrls] = useState<Record<string, string>>({});
  const [loadingAudioByBlock, setLoadingAudioByBlock] = useState<Record<number, boolean>>({});
  const [instructorProfile, setInstructorProfile] = useState<InstructorProfile | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [audioMessage, setAudioMessage] = useState("");
  const [audioError, setAudioError] = useState("");
  const [exportingAudioZip, setExportingAudioZip] = useState(false);

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

  useEffect(() => {
    if (!moduleGroups.length) {
      setSelectedModuleKey("");
      return;
    }
    const selectedStillExists = moduleGroups.some((group) => group.key === selectedModuleKey);
    if (!selectedStillExists) {
      setSelectedModuleKey(moduleGroups[0]?.key || "");
    }
  }, [moduleGroups, selectedModuleKey]);

  useEffect(() => {
    setCopiedKey("");
    setAudioMessage("");
    setAudioError("");
  }, [mode, selectedId, selectedModuleKey]);

  useEffect(() => {
    let isActive = true;
    setProfileError("");
    getInstructorProfile()
      .then((profile) => {
        if (isActive) setInstructorProfile(profile);
      })
      .catch((err) => {
        if (!isActive) return;
        if (err instanceof ApiError && err.status === 401) {
          setProfileError("Sua sessão expirou. Faça login novamente.");
        } else if (err instanceof Error && err.message) {
          setProfileError(err.message);
        } else {
          setProfileError("Não foi possível carregar o perfil do instrutor.");
        }
      })
      .finally(() => {
        if (isActive) setProfileLoaded(true);
      });
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    let isActive = true;
    setAudioError("");
    listProjectAudios(projectId)
      .then((items) => {
        if (isActive) setAudios(items);
      })
      .catch((err) => {
        if (!isActive) return;
        if (err instanceof ApiError && err.status === 401) {
          setAudioError("Sua sessão expirou. Faça login novamente.");
        } else if (err instanceof Error && err.message) {
          setAudioError(err.message);
        } else {
          setAudioError("Não foi possível carregar os áudios gerados.");
        }
      });
    return () => {
      isActive = false;
    };
  }, [projectId]);

  useEffect(() => {
    let isActive = true;
    const objectUrls: string[] = [];

    async function loadAudioUrls() {
      const entries = await Promise.all(
        audios.map(async (audio) => {
          try {
            const blob = await fetchNarrationAudioBlob(projectId, audio.id);
            const objectUrl = URL.createObjectURL(blob);
            objectUrls.push(objectUrl);
            return [audio.id, objectUrl] as const;
          } catch {
            return null;
          }
        }),
      );

      if (!isActive) return;
      setAudioUrls(Object.fromEntries(entries.filter((entry): entry is readonly [string, string] => entry !== null)));
    }

    loadAudioUrls();

    return () => {
      isActive = false;
      objectUrls.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
    };
  }, [audios, projectId]);

  if (!sortedContents.length) {
    return <EmptyState text="Gere ou edite os roteiros de aula antes de preparar a narração." />;
  }

  const selectedContent = sortedContents.find((content) => content.id === selectedId) || sortedContents[0];
  const selectedScript = (selectedContent?.content_json as LessonScriptContent | null)?.lesson_script;
  const selectedModule = moduleGroups.find((group) => group.key === selectedModuleKey) || moduleGroups[0];
  const narrationText =
    mode === "module"
      ? selectedModule
        ? buildModuleNarrationText(selectedModule)
        : ""
      : selectedScript
        ? buildNarrationText(selectedScript)
        : "";
  const narrationBlocks = splitNarrationBlocks(narrationText);
  const narrationTitle =
    mode === "module" && selectedModule
      ? getModuleNarrationLabel(selectedModule)
      : getLessonScriptLabel(selectedScript, selectedContent);
  const audioGeneratedContentId = mode === "module" ? null : selectedContent?.id || null;
  const audioBaseTitle =
    mode === "module" && selectedModule
      ? getModuleAudioBaseTitle(selectedModule)
      : getLessonAudioBaseTitle(selectedScript, selectedContent);
  const groupedAudios = groupAudiosForNarration(audios, sortedContents, moduleGroups);
  const selectedAudios =
    mode === "module" && selectedModule
      ? groupedAudios.byModuleKey[selectedModule.key] || []
      : selectedContent
        ? groupedAudios.byLessonId[selectedContent.id] || []
        : [];
  const otherAudios = audios
    .filter((audio) => !selectedAudios.some((selectedAudio) => selectedAudio.id === audio.id))
    .sort(sortAudiosByCreatedAtDesc);
  async function copyNarration(key: string, text: string) {
    setCopiedKey("");
    const copied = await copyTextToClipboard(text);
    if (copied) {
      setCopiedKey(key);
    } else {
      setCopiedKey("error");
    }
  }

  async function handleGenerateBlockAudio(blockIndex: number, block: string) {
    setAudioError("");
    setAudioMessage("");
    setLoadingAudioByBlock((current) => ({ ...current, [blockIndex]: true }));
    try {
      const audio = await generateNarrationAudio(projectId, {
        generated_content_id: audioGeneratedContentId,
        block_index: blockIndex,
        title: `${audioBaseTitle} - Bloco ${blockIndex}`,
        text: block,
        format: "mp3",
      });
      setAudios((current) => [audio, ...current.filter((item) => item.id !== audio.id)]);
      setAudioMessage("Áudio gerado com sucesso.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setAudioError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setAudioError(err.message);
      } else {
        setAudioError("Não foi possível gerar o áudio agora.");
      }
    } finally {
      setLoadingAudioByBlock((current) => ({ ...current, [blockIndex]: false }));
    }
  }

  async function handleDownloadAudio(audio: GeneratedAudio) {
    setAudioError("");
    setAudioMessage("");
    try {
      await downloadNarrationAudio(projectId, audio);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setAudioError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setAudioError(err.message);
      } else {
        setAudioError("Não foi possível baixar o áudio.");
      }
    }
  }

  async function handleDeleteAudio(audio: GeneratedAudio) {
    const confirmed = window.confirm("Tem certeza que deseja excluir este áudio?");
    if (!confirmed) return;

    setAudioError("");
    setAudioMessage("");
    try {
      await deleteProjectAudio(projectId, audio.id);
      setAudios((current) => current.filter((item) => item.id !== audio.id));
      setAudioMessage("Áudio excluído com sucesso.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setAudioError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setAudioError(err.message);
      } else {
        setAudioError("Não foi possível excluir o áudio.");
      }
    }
  }

  async function handleDownloadSelectedAudiosZip() {
    if (!selectedAudios.length) {
      setAudioError(mode === "module" ? "Nenhum audio gerado para este modulo ainda." : "Nenhum audio gerado para esta aula ainda.");
      return;
    }

    setAudioError("");
    setAudioMessage("");
    setExportingAudioZip(true);
    try {
      if (mode === "module" && selectedModule) {
        await downloadNarrationAudiosZip(
          projectId,
          {
            scope: "module",
            module_number: selectedModule.moduleNumber === 9999 ? null : selectedModule.moduleNumber,
            title_contains: audioBaseTitle,
          },
          "audios-modulo.zip",
        );
      } else {
        await downloadNarrationAudiosZip(
          projectId,
          {
            scope: "lesson",
            generated_content_id: selectedContent?.id || null,
          },
          "audios-aula.zip",
        );
      }
      setAudioMessage("Exportacao de audios iniciada.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setAudioError("Sua sessÃ£o expirou. FaÃ§a login novamente.");
      } else if (err instanceof Error && err.message) {
        setAudioError(err.message);
      } else {
        setAudioError("Nao foi possivel baixar os audios agora.");
      }
    } finally {
      setExportingAudioZip(false);
    }
  }

  const numberedBlocksText = narrationBlocks.map((block, index) => `Bloco ${index + 1}\n${block}`).join("\n\n");

  return (
    <div className="grid gap-6">
      <section className="rounded-lg border border-white/10 bg-navy-950/60 p-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="grid gap-2 text-sm text-slate-300">
            Modo de narracao
            <div className="flex rounded-md border border-white/10 bg-black/20 p-1">
              <button
                type="button"
                onClick={() => setMode("lesson")}
                className={`rounded px-4 py-2 text-sm font-semibold transition ${
                  mode === "lesson" ? "bg-gold-500 text-navy-950" : "text-slate-300 hover:text-gold-300"
                }`}
              >
                Aula
              </button>
              <button
                type="button"
                onClick={() => setMode("module")}
                className={`rounded px-4 py-2 text-sm font-semibold transition ${
                  mode === "module" ? "bg-gold-500 text-navy-950" : "text-slate-300 hover:text-gold-300"
                }`}
              >
                Modulo
              </button>
            </div>
          </div>
          <label className={`${mode === "module" ? "hidden " : ""}grid min-w-[260px] flex-1 gap-2 text-sm text-slate-300`}>
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
          {mode === "module" ? (
            <label className="grid min-w-[260px] flex-1 gap-2 text-sm text-slate-300">
              Modulo para narracao
              <select
                value={selectedModule?.key || ""}
                onChange={(event) => setSelectedModuleKey(event.target.value)}
                className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              >
                {moduleGroups.map((group) => (
                  <option key={group.key} value={group.key} className="bg-navy-950 text-slate-100">
                    {getModuleNarrationLabel(group)} ({group.lessons.length} aulas)
                  </option>
                ))}
              </select>
            </label>
          ) : null}
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
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">{narrationTitle}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              A narracao e montada a partir do roteiro completo, sem reescrita por IA.
            </p>
          </div>
          <div className="rounded-md border border-white/10 bg-black/20 px-4 py-3 text-right">
            <p className="text-xs text-slate-500">Tempo estimado total</p>
            <p className="mt-1 text-lg font-semibold text-gold-300">{formatSpeechTime(narrationText)}</p>
          </div>
        </div>
        {copiedKey ? (
          <p className={`mt-4 text-sm ${copiedKey === "error" ? "text-red-300" : "text-gold-300"}`}>
            {copiedKey === "error"
              ? "Não foi possível copiar automaticamente. Selecione o texto e copie manualmente."
              : "Copiado"}
          </p>
        ) : null}
        {audioMessage ? <p className="mt-3 text-sm text-gold-300">{audioMessage}</p> : null}
        {audioError ? <p className="mt-3 text-sm text-red-300">{audioError}</p> : null}
      </section>

      <VoiceSettingsCard profile={instructorProfile} loaded={profileLoaded} error={profileError} />

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
            const blockIndex = index + 1;
            const audioTitle = `${audioBaseTitle} - Bloco ${blockIndex}`;
            const audio = findAudioForBlock(audios, blockIndex, audioGeneratedContentId, audioTitle);
            const audioUrl = audio ? audioUrls[audio.id] : "";
            const isGeneratingAudio = Boolean(loadingAudioByBlock[blockIndex]);
            return (
              <article key={blockKey} className="rounded-lg border border-white/10 bg-navy-950/50 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-50">Bloco {blockIndex}</h3>
                    <p className="mt-1 text-xs text-slate-500">Tempo estimado: {formatSpeechTime(block)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => copyNarration(blockKey, block)}
                      className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                    >
                      Copiar bloco
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateBlockAudio(blockIndex, block)}
                      disabled={isGeneratingAudio}
                      className="rounded-md border border-gold-500/30 px-3 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isGeneratingAudio ? "Gerando áudio..." : "Gerar áudio"}
                    </button>
                  </div>
                </div>
                <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-300">{block}</p>
                {copiedKey === blockKey ? <p className="mt-3 text-sm text-gold-300">Copiado</p> : null}
                {audio ? (
                  <div className="mt-5 rounded-md border border-white/10 bg-black/20 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-slate-100">{audio.title || `Áudio do bloco ${blockIndex}`}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          Voz {audio.voice || "padrão"} · {audio.format.toUpperCase()}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Provider {audio.voice_provider || "OpenAI"} ·{" "}
                          Modelo {audio.model || "padrão"} ·{" "}
                          {audio.personalized_voice_used ? "voz personalizada configurada" : "voz padrão do sistema"}
                        </p>
                        {audio.voice_notice ? <p className="mt-2 text-xs text-gold-300">{audio.voice_notice}</p> : null}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => handleDownloadAudio(audio)}
                          className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                        >
                          Baixar áudio
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteAudio(audio)}
                          className="rounded-md border border-red-400/40 px-3 py-2 text-sm text-red-300 transition hover:border-red-300 hover:text-red-200"
                        >
                          Excluir áudio
                        </button>
                      </div>
                    </div>
                    {audioUrl ? (
                      <audio controls src={audioUrl} className="mt-4 w-full" />
                    ) : (
                      <p className="mt-4 text-sm text-slate-400">Carregando player de áudio...</p>
                    )}
                  </div>
                ) : null}
              </article>
            );
          })
        ) : (
          <EmptyState text="Não foi possível dividir a narração em blocos." />
        )}
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-100">Audios gerados</p>
            <p className="mt-1 text-xs text-slate-500">
              {mode === "module" ? "Audios do modulo selecionado" : "Audios da aula selecionada"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-xs text-slate-500">{audios.length} audios no projeto</p>
            <button
              type="button"
              onClick={handleDownloadSelectedAudiosZip}
              disabled={!selectedAudios.length || exportingAudioZip}
              className="rounded-md border border-gold-500/30 px-4 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exportingAudioZip
                ? "Preparando ZIP..."
                : mode === "module"
                  ? "Baixar audios do modulo"
                  : "Baixar audios da aula"}
            </button>
          </div>
        </div>

        <NarrationAudioList
          title={mode === "module" ? "Modulo selecionado" : "Aula selecionada"}
          emptyText={mode === "module" ? "Nenhum audio gerado para este modulo ainda." : "Nenhum audio gerado para esta aula ainda."}
          audios={selectedAudios}
          audioUrls={audioUrls}
          onDownload={handleDownloadAudio}
          onDelete={handleDeleteAudio}
        />

        <NarrationAudioList
          title="Outros audios do projeto"
          emptyText="Nenhum outro audio gerado neste projeto."
          audios={otherAudios}
          audioUrls={audioUrls}
          onDownload={handleDownloadAudio}
          onDelete={handleDeleteAudio}
        />
      </section>

    </div>
  );
}

const VIDEO_PROVIDER_LABELS: Record<VideoProvider, string> = {
  mock: "Mock",
  heygen: "HeyGen",
  did: "D-ID",
  sync: "Sync Labs",
};

function VideoView({ contents, projectId }: { contents: GeneratedContent[]; projectId: string }) {
  const sortedContents = sortLessonScripts(contents);
  const [audios, setAudios] = useState<GeneratedAudio[]>([]);
  const [videos, setVideos] = useState<GeneratedVideo[]>([]);
  const [avatars, setAvatars] = useState<VideoAvatar[]>([]);
  const [avatarsError, setAvatarsError] = useState("");
  const [videoSettings, setVideoSettings] = useState<ProjectVideoSettings | null>(null);
  const [videoSettingsError, setVideoSettingsError] = useState("");
  const [videoSettingsMessage, setVideoSettingsMessage] = useState("");
  const [savingVideoSettings, setSavingVideoSettings] = useState(false);
  const [defaultsApplied, setDefaultsApplied] = useState(false);
  const [settingsDefaultProvider, setSettingsDefaultProvider] = useState<VideoProvider | "">("");
  const [settingsMockAvatarId, setSettingsMockAvatarId] = useState("");
  const [settingsHeygenAvatarId, setSettingsHeygenAvatarId] = useState("");
  const [settingsDidAvatarId, setSettingsDidAvatarId] = useState("");
  const [settingsSyncAvatarId, setSettingsSyncAvatarId] = useState("");
  const [settingsResolution, setSettingsResolution] = useState("1080p");
  const [settingsFormat, setSettingsFormat] = useState("mp4");
  const [settingsAutoDownload, setSettingsAutoDownload] = useState(true);
  const [selectedAudioId, setSelectedAudioId] = useState("");
  const [selectedVideoAvatarId, setSelectedVideoAvatarId] = useState("");
  const [videoProvider, setVideoProvider] = useState<VideoProvider>("mock");
  const [videoAvatarId, setVideoAvatarId] = useState("");
  const [videoAvatarName, setVideoAvatarName] = useState("");
  const [videoSourceImageUrl, setVideoSourceImageUrl] = useState("");
  const [videoSourceVideoUrl, setVideoSourceVideoUrl] = useState("");
  const [videoModel, setVideoModel] = useState("");
  const [videoResolution, setVideoResolution] = useState("1080p");
  const [videoFormat, setVideoFormat] = useState("mp4");
  const [generatingVideo, setGeneratingVideo] = useState(false);
  const [refreshingVideoId, setRefreshingVideoId] = useState("");
  const [videoMessage, setVideoMessage] = useState("");
  const [videoError, setVideoError] = useState("");

  const [pipelineScope, setPipelineScope] = useState<VideoPipelineScope>("lesson");
  const [pipelineModuleIndex, setPipelineModuleIndex] = useState("");
  const [pipelineLessonId, setPipelineLessonId] = useState("");
  const [pipelineProvider, setPipelineProvider] = useState<VideoProvider | "">("");
  const [pipelineAvatarId, setPipelineAvatarId] = useState("");
  const [pipelineSkipExistingAudio, setPipelineSkipExistingAudio] = useState(true);
  const [pipelineSkipExistingVideo, setPipelineSkipExistingVideo] = useState(true);
  const [pipelineForceRegenerateAudio, setPipelineForceRegenerateAudio] = useState(false);
  const [pipelineForceRegenerateVideo, setPipelineForceRegenerateVideo] = useState(false);
  const [pipelineJobs, setPipelineJobs] = useState<VideoPipelineJob[]>([]);
  const [currentPipelineJob, setCurrentPipelineJob] = useState<VideoPipelineJob | null>(null);
  const [pipelineIsPolling, setPipelineIsPolling] = useState(false);
  const [creatingPipeline, setCreatingPipeline] = useState(false);
  const [pipelineActionLoading, setPipelineActionLoading] = useState(false);
  const [pipelineMessage, setPipelineMessage] = useState("");
  const [pipelineError, setPipelineError] = useState("");

  useEffect(() => {
    let isActive = true;
    setVideoError("");
    listProjectAudios(projectId)
      .then((items) => {
        if (isActive) setAudios([...items].sort(sortAudiosByCreatedAtDesc));
      })
      .catch((err) => {
        if (!isActive) return;
        if (err instanceof ApiError && err.status === 401) {
          setVideoError("Sua sessão expirou. Faça login novamente.");
        } else if (err instanceof Error && err.message) {
          setVideoError(err.message);
        } else {
          setVideoError("Não foi possível carregar os áudios gerados.");
        }
      });
    return () => {
      isActive = false;
    };
  }, [projectId]);

  useEffect(() => {
    let isActive = true;
    setVideoError("");
    listProjectVideos(projectId)
      .then((items) => {
        if (isActive) setVideos(items);
      })
      .catch((err) => {
        if (!isActive) return;
        if (err instanceof ApiError && err.status === 401) {
          setVideoError("Sua sessão expirou. Faça login novamente.");
        } else if (err instanceof Error && err.message) {
          setVideoError(err.message);
        } else {
          setVideoError("Não foi possível carregar os vídeos gerados.");
        }
      });
    return () => {
      isActive = false;
    };
  }, [projectId]);

  useEffect(() => {
    let isActive = true;
    setAvatarsError("");
    listProjectVideoAvatars(projectId)
      .then((items) => {
        if (isActive) setAvatars(items);
      })
      .catch((err) => {
        if (!isActive) return;
        if (err instanceof ApiError && err.status === 401) {
          setAvatarsError("Sua sessão expirou. Faça login novamente.");
        } else if (err instanceof Error && err.message) {
          setAvatarsError(err.message);
        } else {
          setAvatarsError("Não foi possível carregar os avatares.");
        }
      });
    return () => {
      isActive = false;
    };
  }, [projectId]);

  useEffect(() => {
    let isActive = true;
    setVideoSettingsError("");
    getProjectVideoSettings(projectId)
      .then((data) => {
        if (!isActive) return;
        setVideoSettings(data);
        setSettingsDefaultProvider(data.default_provider || "");
        setSettingsMockAvatarId(data.default_mock_avatar_id || "");
        setSettingsHeygenAvatarId(data.default_heygen_avatar_id || "");
        setSettingsDidAvatarId(data.default_did_avatar_id || "");
        setSettingsSyncAvatarId(data.default_sync_avatar_id || "");
        setSettingsResolution(data.default_resolution || "1080p");
        setSettingsFormat(data.default_format || "mp4");
        setSettingsAutoDownload(data.auto_download_completed_videos);
      })
      .catch((err) => {
        if (!isActive) return;
        if (err instanceof ApiError && err.status === 401) {
          setVideoSettingsError("Sua sessão expirou. Faça login novamente.");
        } else if (err instanceof Error && err.message) {
          setVideoSettingsError(err.message);
        } else {
          setVideoSettingsError("Não foi possível carregar as configurações padrão do projeto.");
        }
      });
    return () => {
      isActive = false;
    };
  }, [projectId]);

  useEffect(() => {
    if (!audios.length) {
      setSelectedAudioId("");
      return;
    }
    const selectedStillExists = audios.some((audio) => audio.id === selectedAudioId);
    if (!selectedStillExists) {
      setSelectedAudioId(audios[0]?.id || "");
    }
  }, [audios, selectedAudioId]);

  useEffect(() => {
    const avatar = avatars.find((item) => item.id === selectedVideoAvatarId && item.is_active);
    if (avatar) {
      setVideoProvider(avatar.provider);
    }
  }, [selectedVideoAvatarId, avatars]);

  useEffect(() => {
    if (!videoSettings || defaultsApplied) return;
    if (videoSettings.default_provider) {
      setVideoProvider(videoSettings.default_provider);
    }
    const effectiveProvider = videoSettings.default_provider || videoProvider;
    const defaultAvatarId = pickDefaultAvatarIdForProvider(videoSettings, effectiveProvider);
    if (defaultAvatarId) {
      setSelectedVideoAvatarId(defaultAvatarId);
    }
    if (videoSettings.default_resolution) setVideoResolution(videoSettings.default_resolution);
    if (videoSettings.default_format) setVideoFormat(videoSettings.default_format);
    setDefaultsApplied(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoSettings, defaultsApplied]);

  useEffect(() => {
    let isActive = true;
    listVideoPipelineJobs(projectId)
      .then((jobs) => {
        if (!isActive) return;
        setPipelineJobs(jobs);
        if (jobs.length) {
          setCurrentPipelineJob(jobs[0]);
          if (jobs[0].status === "running") setPipelineIsPolling(true);
        }
      })
      .catch(() => {
        // Silencioso: histórico de pipelines é informativo, não bloqueia a tela.
      });
    return () => {
      isActive = false;
    };
  }, [projectId]);

  useEffect(() => {
    if (!pipelineIsPolling || !currentPipelineJob) return;
    let isActive = true;
    let timeoutId: number | undefined;
    const jobId = currentPipelineJob.id;

    async function poll() {
      try {
        const job = await getVideoPipelineJob(projectId, jobId);
        if (!isActive) return;
        setCurrentPipelineJob(job);
        setPipelineJobs((current) => current.map((item) => (item.id === job.id ? job : item)));
        if (job.status === "pending" || job.status === "running") {
          timeoutId = window.setTimeout(poll, 4000);
        } else {
          setPipelineIsPolling(false);
        }
      } catch {
        if (isActive) setPipelineIsPolling(false);
      }
    }

    poll();

    return () => {
      isActive = false;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipelineIsPolling, currentPipelineJob?.id, projectId]);

  const activeVideoAvatars = avatars.filter((avatar) => avatar.is_active);
  const selectedVideoAvatar = activeVideoAvatars.find((avatar) => avatar.id === selectedVideoAvatarId) || null;
  const selectedAudio = audios.find((audio) => audio.id === selectedAudioId) || audios[0] || null;
  const selectedLesson = selectedAudio?.generated_content_id
    ? sortedContents.find((content) => content.id === selectedAudio.generated_content_id) || null
    : null;
  const selectedScript = (selectedLesson?.content_json as LessonScriptContent | null)?.lesson_script;
  const selectedAudioTitle = selectedAudio
    ? selectedAudio.title || getLessonAudioBaseTitle(selectedScript, selectedLesson || undefined)
    : "";
  const pipelineModuleGroups = groupLessonsByModule(sortedContents).filter((group) => group.moduleNumber !== 9999);

  async function handleGenerateVideo() {
    if (!selectedAudio) {
      setVideoError("Selecione um áudio gerado antes de criar o vídeo.");
      return;
    }

    setVideoError("");
    setVideoMessage("");
    setGeneratingVideo(true);
    try {
      const video = await generateProjectVideo(projectId, {
        lesson_id: selectedLesson?.id || null,
        module_id: null,
        audio_id: selectedAudio.id,
        video_avatar_id: selectedVideoAvatar?.id || null,
        provider: videoProvider,
        avatar_id: videoAvatarId.trim() || null,
        avatar_name: videoAvatarName.trim() || null,
        source_image_url: videoSourceImageUrl.trim() || null,
        source_video_url: videoSourceVideoUrl.trim() || null,
        model: videoModel.trim() || null,
        resolution: videoResolution,
        format: videoFormat,
        extra_metadata: {
          narration_title: selectedAudioTitle || null,
          audio_title: selectedAudio.title || null,
          source_tab: "video",
        },
      });
      setVideos((current) => [video, ...current.filter((item) => item.id !== video.id)]);
      setVideoMessage(
        videoProvider === "mock"
          ? "Vídeo mock gerado com sucesso."
          : `Job de vídeo criado na ${VIDEO_PROVIDER_LABELS[videoProvider]}. Acompanhe o status abaixo.`,
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setVideoError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setVideoError(err.message);
      } else {
        setVideoError("Não foi possível gerar o vídeo agora.");
      }
    } finally {
      setGeneratingVideo(false);
    }
  }

  async function handleRefreshVideoStatus(video: GeneratedVideo) {
    setVideoError("");
    setVideoMessage("");
    setRefreshingVideoId(video.id);
    try {
      const updated = await refreshProjectVideoStatus(projectId, video.id);
      setVideos((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setVideoMessage("Status do vídeo atualizado.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setVideoError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setVideoError(err.message);
      } else {
        setVideoError("Não foi possível atualizar o status do vídeo.");
      }
    } finally {
      setRefreshingVideoId("");
    }
  }

  async function handleDownloadVideo(video: GeneratedVideo) {
    setVideoError("");
    setVideoMessage("");
    try {
      await downloadProjectVideo(projectId, video.id, video.file_name || `video-${video.id}.${video.format || "mp4"}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setVideoError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setVideoError(err.message);
      } else {
        setVideoError("Não foi possível baixar o vídeo.");
      }
    }
  }

  async function handleDeleteVideo(video: GeneratedVideo) {
    const confirmed = window.confirm("Tem certeza que deseja excluir este vídeo?");
    if (!confirmed) return;

    setVideoError("");
    setVideoMessage("");
    try {
      await deleteProjectVideo(projectId, video.id);
      setVideos((current) => current.filter((item) => item.id !== video.id));
      setVideoMessage("Vídeo excluído com sucesso.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setVideoError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setVideoError(err.message);
      } else {
        setVideoError("Não foi possível excluir o vídeo.");
      }
    }
  }

  async function handleSaveVideoSettings() {
    setVideoSettingsError("");
    setVideoSettingsMessage("");
    setSavingVideoSettings(true);
    try {
      const updated = await updateProjectVideoSettings(projectId, {
        default_provider: settingsDefaultProvider || null,
        default_mock_avatar_id: settingsMockAvatarId || null,
        default_heygen_avatar_id: settingsHeygenAvatarId || null,
        default_did_avatar_id: settingsDidAvatarId || null,
        default_sync_avatar_id: settingsSyncAvatarId || null,
        default_resolution: settingsResolution,
        default_format: settingsFormat,
        auto_download_completed_videos: settingsAutoDownload,
      });
      setVideoSettings(updated);
      setVideoSettingsMessage("Configurações padrão salvas.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setVideoSettingsError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setVideoSettingsError(err.message);
      } else {
        setVideoSettingsError("Não foi possível salvar as configurações padrão.");
      }
    } finally {
      setSavingVideoSettings(false);
    }
  }

  function reportPipelineError(err: unknown, fallback: string) {
    if (err instanceof ApiError && err.status === 401) {
      setPipelineError("Sua sessão expirou. Faça login novamente.");
    } else if (err instanceof Error && err.message) {
      setPipelineError(err.message);
    } else {
      setPipelineError(fallback);
    }
  }

  async function handleCreatePipeline() {
    setPipelineError("");
    setPipelineMessage("");

    if (pipelineScope === "module" && !pipelineModuleIndex) {
      setPipelineError("Selecione um módulo.");
      return;
    }
    if (pipelineScope === "lesson" && !pipelineLessonId) {
      setPipelineError("Selecione uma aula.");
      return;
    }
    if (pipelineScope === "course") {
      const confirmed = window.confirm(
        "Gerar áudio e vídeo para TODAS as aulas do curso pode consumir créditos da ElevenLabs e do provider de vídeo selecionado. Deseja continuar?",
      );
      if (!confirmed) return;
    }

    setCreatingPipeline(true);
    try {
      const job = await createVideoPipelineJob(projectId, {
        scope: pipelineScope,
        module_index: pipelineScope === "module" ? Number(pipelineModuleIndex) : null,
        lesson_id: pipelineScope === "lesson" ? pipelineLessonId : null,
        provider: pipelineProvider || null,
        video_avatar_id: pipelineAvatarId || null,
        skip_existing_audio: pipelineSkipExistingAudio,
        skip_existing_video: pipelineSkipExistingVideo,
        force_regenerate_audio: pipelineForceRegenerateAudio,
        force_regenerate_video: pipelineForceRegenerateVideo,
      });
      setPipelineJobs((current) => [job, ...current]);
      setCurrentPipelineJob(job);
      setPipelineMessage(
        `Pipeline criado com ${job.total_items} aula(s). Clique em "Iniciar geração" para começar.`,
      );
    } catch (err) {
      reportPipelineError(err, "Não foi possível criar o pipeline agora.");
    } finally {
      setCreatingPipeline(false);
    }
  }

  async function handleRunPipeline(job: VideoPipelineJob) {
    setPipelineError("");
    setPipelineMessage("");
    setPipelineActionLoading(true);
    try {
      const updated = await runVideoPipelineJob(projectId, job.id);
      setCurrentPipelineJob(updated);
      setPipelineJobs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setPipelineIsPolling(true);
      setPipelineMessage("Geração iniciada. Acompanhe o progresso abaixo.");
    } catch (err) {
      reportPipelineError(err, "Não foi possível iniciar a geração agora.");
    } finally {
      setPipelineActionLoading(false);
    }
  }

  async function handleRetryFailedPipeline(job: VideoPipelineJob) {
    setPipelineError("");
    setPipelineMessage("");
    setPipelineActionLoading(true);
    try {
      const updated = await retryFailedVideoPipelineJob(projectId, job.id);
      setCurrentPipelineJob(updated);
      setPipelineJobs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setPipelineIsPolling(true);
      setPipelineMessage("Reprocessando itens com falha.");
    } catch (err) {
      reportPipelineError(err, "Não foi possível reprocessar as falhas agora.");
    } finally {
      setPipelineActionLoading(false);
    }
  }

  async function handleCancelPipeline(job: VideoPipelineJob) {
    const confirmed = window.confirm("Tem certeza que deseja cancelar este pipeline?");
    if (!confirmed) return;

    setPipelineError("");
    setPipelineMessage("");
    setPipelineActionLoading(true);
    try {
      const updated = await cancelVideoPipelineJob(projectId, job.id);
      setCurrentPipelineJob(updated);
      setPipelineJobs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setPipelineIsPolling(false);
      setPipelineMessage("Pipeline cancelado.");
    } catch (err) {
      reportPipelineError(err, "Não foi possível cancelar o pipeline agora.");
    } finally {
      setPipelineActionLoading(false);
    }
  }

  return (
    <div className="grid gap-6">
      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-100">Base de vídeo por aula</p>
            <p className="mt-1 text-xs text-slate-500">
              Geração mock para preparar futuro avatar sincronizado com áudio.
            </p>
          </div>
          <button
            type="button"
            onClick={handleGenerateVideo}
            disabled={!selectedAudio || generatingVideo}
            className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {generatingVideo ? "Gerando vídeo..." : `Gerar vídeo ${VIDEO_PROVIDER_LABELS[videoProvider]}`}
          </button>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
            Avatar
            <select
              value={selectedVideoAvatarId}
              onChange={(event) => setSelectedVideoAvatarId(event.target.value)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="" className="bg-navy-950 text-slate-100">
                Manual (preencher campos abaixo)
              </option>
              {activeVideoAvatars.map((avatar) => (
                <option key={avatar.id} value={avatar.id} className="bg-navy-950 text-slate-100">
                  {getVideoProviderLabel(avatar.provider)} - {avatar.name}
                  {avatar.is_default ? " (padrão)" : ""}
                </option>
              ))}
            </select>
          </label>
          {!activeVideoAvatars.length ? (
            <p className="-mt-2 text-xs text-slate-500 md:col-span-2">
              Nenhum avatar cadastrado ainda. Use a Biblioteca de Avatares abaixo ou preencha os campos manualmente.
            </p>
          ) : null}
          {(() => {
            const defaultAvatarId = videoSettings ? pickDefaultAvatarIdForProvider(videoSettings, videoProvider) : "";
            if (selectedVideoAvatarId && selectedVideoAvatarId === defaultAvatarId) {
              return (
                <p className="-mt-2 text-xs text-gold-300 md:col-span-2">Usando avatar padrão do projeto.</p>
              );
            }
            if (!defaultAvatarId) {
              return (
                <p className="-mt-2 text-xs text-slate-500 md:col-span-2">
                  Nenhum avatar padrão configurado para este provider.
                </p>
              );
            }
            return null;
          })()}
          {selectedVideoAvatar ? (
            <div className="min-w-0 rounded-md border border-white/10 bg-black/20 p-3 text-xs text-slate-300 md:col-span-2">
              <p>
                Provider: <span className="text-slate-100">{getVideoProviderLabel(selectedVideoAvatar.provider)}</span>
              </p>
              {selectedVideoAvatar.avatar_id ? (
                <p className="mt-1 break-words">Avatar ID: {selectedVideoAvatar.avatar_id}</p>
              ) : null}
              {selectedVideoAvatar.source_image_url ? (
                <p className="mt-1 break-words">Imagem: {selectedVideoAvatar.source_image_url}</p>
              ) : null}
              {selectedVideoAvatar.source_video_url ? (
                <p className="mt-1 break-words">Vídeo base: {selectedVideoAvatar.source_video_url}</p>
              ) : null}
              {selectedVideoAvatar.default_model ? <p className="mt-1">Modelo: {selectedVideoAvatar.default_model}</p> : null}
            </div>
          ) : (
            <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
              Provider
              <select
                value={videoProvider}
                onChange={(event) => {
                  const nextProvider = event.target.value as VideoProvider;
                  setVideoProvider(nextProvider);
                  const defaultAvatarId = videoSettings
                    ? pickDefaultAvatarIdForProvider(videoSettings, nextProvider)
                    : "";
                  if (defaultAvatarId) {
                    setSelectedVideoAvatarId(defaultAvatarId);
                  }
                }}
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              >
                <option value="mock" className="bg-navy-950 text-slate-100">
                  Mock
                </option>
                <option value="heygen" className="bg-navy-950 text-slate-100">
                  HeyGen
                </option>
                <option value="did" className="bg-navy-950 text-slate-100">
                  D-ID
                </option>
                <option value="sync" className="bg-navy-950 text-slate-100">
                  Sync Labs
                </option>
              </select>
            </label>
          )}
          <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
            Áudio base
            <select
              value={selectedAudio?.id || ""}
              onChange={(event) => setSelectedAudioId(event.target.value)}
              disabled={!audios.length}
              className="w-full min-w-0 truncate overflow-hidden text-ellipsis rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {audios.length ? (
                audios.map((audio) => (
                  <option key={audio.id} value={audio.id} className="bg-navy-950 text-slate-100">
                    {getVideoAudioLabel(audio, sortedContents)}
                  </option>
                ))
              ) : (
                <option value="" className="bg-navy-950 text-slate-100">
                  Nenhum áudio disponível
                </option>
              )}
            </select>
          </label>
          {!selectedVideoAvatar && videoProvider === "heygen" ? (
            <>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300">
                Avatar ID
                <input
                  value={videoAvatarId}
                  onChange={(event) => setVideoAvatarId(event.target.value)}
                  placeholder="Usar avatar padrão (HEYGEN_DEFAULT_AVATAR_ID)"
                  className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
                />
              </label>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300">
                Nome do avatar
                <input
                  value={videoAvatarName}
                  onChange={(event) => setVideoAvatarName(event.target.value)}
                  placeholder="Instrutor Virtus"
                  className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
                />
              </label>
            </>
          ) : null}
          {!selectedVideoAvatar && videoProvider === "did" ? (
            <>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
                Source image URL
                <input
                  value={videoSourceImageUrl}
                  onChange={(event) => setVideoSourceImageUrl(event.target.value)}
                  placeholder="Usar padrão (DID_DEFAULT_SOURCE_IMAGE_URL)"
                  className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
                />
              </label>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300">
                Nome do avatar (opcional)
                <input
                  value={videoAvatarName}
                  onChange={(event) => setVideoAvatarName(event.target.value)}
                  placeholder="Instrutor Virtus"
                  className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
                />
              </label>
            </>
          ) : null}
          {!selectedVideoAvatar && videoProvider === "sync" ? (
            <>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
                Source video URL
                <input
                  value={videoSourceVideoUrl}
                  onChange={(event) => setVideoSourceVideoUrl(event.target.value)}
                  placeholder="Usar padrão (SYNC_DEFAULT_SOURCE_VIDEO_URL)"
                  className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
                />
              </label>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300">
                Source image URL (opcional)
                <input
                  value={videoSourceImageUrl}
                  onChange={(event) => setVideoSourceImageUrl(event.target.value)}
                  placeholder="Alternativa a um vídeo base"
                  className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
                />
              </label>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300">
                Model (opcional)
                <input
                  value={videoModel}
                  onChange={(event) => setVideoModel(event.target.value)}
                  placeholder="lipsync-2"
                  className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
                />
              </label>
            </>
          ) : null}
          <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 md:col-span-2">
            <label className="grid min-w-0 gap-2 text-sm text-slate-300">
              Resolução
              <select
                value={videoResolution}
                onChange={(event) => setVideoResolution(event.target.value)}
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              >
                <option value="1080p" className="bg-navy-950 text-slate-100">
                  1080p
                </option>
                <option value="720p" className="bg-navy-950 text-slate-100">
                  720p
                </option>
              </select>
            </label>
            <label className="grid min-w-0 gap-2 text-sm text-slate-300">
              Formato
              <select
                value={videoFormat}
                onChange={(event) => setVideoFormat(event.target.value)}
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              >
                <option value="mp4" className="bg-navy-950 text-slate-100">
                  mp4
                </option>
              </select>
            </label>
          </div>
        </div>

        {videoMessage ? <p className="mt-4 text-sm text-gold-300">{videoMessage}</p> : null}
        {videoError ? <p className="mt-4 text-sm text-red-300">{videoError}</p> : null}
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">Configurações padrão do projeto</p>
        <p className="mt-1 text-xs text-slate-500">
          Defina o provider e os avatares padrão usados automaticamente ao gerar vídeos neste projeto.
        </p>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Provider padrão
            <select
              value={settingsDefaultProvider}
              onChange={(event) => setSettingsDefaultProvider(event.target.value as VideoProvider | "")}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="" className="bg-navy-950 text-slate-100">
                Nenhum (usar padrão do sistema)
              </option>
              <option value="mock" className="bg-navy-950 text-slate-100">
                Mock
              </option>
              <option value="heygen" className="bg-navy-950 text-slate-100">
                HeyGen
              </option>
              <option value="did" className="bg-navy-950 text-slate-100">
                D-ID
              </option>
              <option value="sync" className="bg-navy-950 text-slate-100">
                Sync Labs
              </option>
            </select>
          </label>
          <div className="grid min-w-0 grid-cols-2 gap-3">
            <label className="grid min-w-0 gap-2 text-sm text-slate-300">
              Resolução padrão
              <select
                value={settingsResolution}
                onChange={(event) => setSettingsResolution(event.target.value)}
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              >
                <option value="1080p" className="bg-navy-950 text-slate-100">
                  1080p
                </option>
                <option value="720p" className="bg-navy-950 text-slate-100">
                  720p
                </option>
              </select>
            </label>
            <label className="grid min-w-0 gap-2 text-sm text-slate-300">
              Formato padrão
              <select
                value={settingsFormat}
                onChange={(event) => setSettingsFormat(event.target.value)}
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              >
                <option value="mp4" className="bg-navy-950 text-slate-100">
                  mp4
                </option>
              </select>
            </label>
          </div>
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Avatar padrão Mock
            <select
              value={settingsMockAvatarId}
              onChange={(event) => setSettingsMockAvatarId(event.target.value)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="" className="bg-navy-950 text-slate-100">
                Nenhum
              </option>
              {avatars
                .filter((avatar) => avatar.is_active && avatar.provider === "mock")
                .map((avatar) => (
                  <option key={avatar.id} value={avatar.id} className="bg-navy-950 text-slate-100">
                    {avatar.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Avatar padrão HeyGen
            <select
              value={settingsHeygenAvatarId}
              onChange={(event) => setSettingsHeygenAvatarId(event.target.value)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="" className="bg-navy-950 text-slate-100">
                Nenhum
              </option>
              {avatars
                .filter((avatar) => avatar.is_active && avatar.provider === "heygen")
                .map((avatar) => (
                  <option key={avatar.id} value={avatar.id} className="bg-navy-950 text-slate-100">
                    {avatar.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Avatar padrão D-ID
            <select
              value={settingsDidAvatarId}
              onChange={(event) => setSettingsDidAvatarId(event.target.value)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="" className="bg-navy-950 text-slate-100">
                Nenhum
              </option>
              {avatars
                .filter((avatar) => avatar.is_active && avatar.provider === "did")
                .map((avatar) => (
                  <option key={avatar.id} value={avatar.id} className="bg-navy-950 text-slate-100">
                    {avatar.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Avatar padrão Sync Labs
            <select
              value={settingsSyncAvatarId}
              onChange={(event) => setSettingsSyncAvatarId(event.target.value)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="" className="bg-navy-950 text-slate-100">
                Nenhum
              </option>
              {avatars
                .filter((avatar) => avatar.is_active && avatar.provider === "sync")
                .map((avatar) => (
                  <option key={avatar.id} value={avatar.id} className="bg-navy-950 text-slate-100">
                    {avatar.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-300 md:col-span-2">
            <input
              type="checkbox"
              checked={settingsAutoDownload}
              onChange={(event) => setSettingsAutoDownload(event.target.checked)}
            />
            Baixar/salvar automaticamente vídeos concluídos
          </label>
        </div>

        <button
          type="button"
          onClick={handleSaveVideoSettings}
          disabled={savingVideoSettings}
          className="mt-4 rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {savingVideoSettings ? "Salvando..." : "Salvar configurações padrão"}
        </button>

        {videoSettingsMessage ? <p className="mt-4 text-sm text-gold-300">{videoSettingsMessage}</p> : null}
        {videoSettingsError ? <p className="mt-4 text-sm text-red-300">{videoSettingsError}</p> : null}
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">Pipeline automático</p>
        <p className="mt-1 text-xs text-slate-500">
          Gere áudio e vídeo automaticamente a partir dos roteiros das aulas, para uma aula, um módulo inteiro ou o
          curso inteiro.
        </p>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Escopo
            <select
              value={pipelineScope}
              onChange={(event) => setPipelineScope(event.target.value as VideoPipelineScope)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="lesson" className="bg-navy-950 text-slate-100">
                Aula específica
              </option>
              <option value="module" className="bg-navy-950 text-slate-100">
                Módulo inteiro
              </option>
              <option value="course" className="bg-navy-950 text-slate-100">
                Curso inteiro
              </option>
            </select>
          </label>

          {pipelineScope === "module" ? (
            <label className="grid min-w-0 gap-2 text-sm text-slate-300">
              Módulo
              <select
                value={pipelineModuleIndex}
                onChange={(event) => setPipelineModuleIndex(event.target.value)}
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              >
                <option value="" className="bg-navy-950 text-slate-100">
                  Selecione um módulo
                </option>
                {pipelineModuleGroups.map((group) => (
                  <option key={group.key} value={group.moduleNumber} className="bg-navy-950 text-slate-100">
                    {getModuleNarrationLabel(group)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {pipelineScope === "lesson" ? (
            <label className="grid min-w-0 gap-2 text-sm text-slate-300">
              Aula
              <select
                value={pipelineLessonId}
                onChange={(event) => setPipelineLessonId(event.target.value)}
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              >
                <option value="" className="bg-navy-950 text-slate-100">
                  Selecione uma aula
                </option>
                {sortedContents.map((content) => {
                  const script = (content.content_json as LessonScriptContent | null)?.lesson_script;
                  return (
                    <option key={content.id} value={content.id} className="bg-navy-950 text-slate-100">
                      {getLessonAudioBaseTitle(script, content)}
                    </option>
                  );
                })}
              </select>
            </label>
          ) : null}

          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Provider de vídeo
            <select
              value={pipelineProvider}
              onChange={(event) => setPipelineProvider(event.target.value as VideoProvider | "")}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="" className="bg-navy-950 text-slate-100">
                Usar padrão do projeto
              </option>
              <option value="mock" className="bg-navy-950 text-slate-100">
                Mock
              </option>
              <option value="heygen" className="bg-navy-950 text-slate-100">
                HeyGen
              </option>
              <option value="did" className="bg-navy-950 text-slate-100">
                D-ID
              </option>
              <option value="sync" className="bg-navy-950 text-slate-100">
                Sync Labs
              </option>
            </select>
          </label>

          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Avatar
            <select
              value={pipelineAvatarId}
              onChange={(event) => setPipelineAvatarId(event.target.value)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="" className="bg-navy-950 text-slate-100">
                Usar avatar padrão do projeto
              </option>
              {activeVideoAvatars
                .filter((avatar) => !pipelineProvider || avatar.provider === pipelineProvider)
                .map((avatar) => (
                  <option key={avatar.id} value={avatar.id} className="bg-navy-950 text-slate-100">
                    {avatar.name} ({getVideoProviderLabel(avatar.provider)})
                  </option>
                ))}
            </select>
          </label>

          <div className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={pipelineSkipExistingAudio}
                onChange={(event) => setPipelineSkipExistingAudio(event.target.checked)}
              />
              Reaproveitar áudios já gerados
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={pipelineSkipExistingVideo}
                onChange={(event) => setPipelineSkipExistingVideo(event.target.checked)}
              />
              Reaproveitar vídeos já gerados
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={pipelineForceRegenerateAudio}
                onChange={(event) => setPipelineForceRegenerateAudio(event.target.checked)}
              />
              Forçar regeração de áudio
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={pipelineForceRegenerateVideo}
                onChange={(event) => setPipelineForceRegenerateVideo(event.target.checked)}
              />
              Forçar regeração de vídeo
            </label>
          </div>
        </div>

        <button
          type="button"
          onClick={handleCreatePipeline}
          disabled={creatingPipeline}
          className="mt-4 rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {creatingPipeline ? "Criando pipeline..." : "Criar pipeline"}
        </button>

        {pipelineMessage ? <p className="mt-4 text-sm text-gold-300">{pipelineMessage}</p> : null}
        {pipelineError ? <p className="mt-4 text-sm text-red-300">{pipelineError}</p> : null}

        {currentPipelineJob ? (
          <PipelineJobCard
            job={currentPipelineJob}
            actionLoading={pipelineActionLoading}
            onRun={() => handleRunPipeline(currentPipelineJob)}
            onRetryFailed={() => handleRetryFailedPipeline(currentPipelineJob)}
            onCancel={() => handleCancelPipeline(currentPipelineJob)}
          />
        ) : null}

        {pipelineJobs.length > 1 ? (
          <div className="mt-5">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">Histórico de pipelines</p>
            <div className="mt-3 grid gap-2">
              {pipelineJobs
                .filter((job) => job.id !== currentPipelineJob?.id)
                .map((job) => (
                  <button
                    key={job.id}
                    type="button"
                    onClick={() => {
                      setCurrentPipelineJob(job);
                      setPipelineIsPolling(job.status === "running");
                    }}
                    className="flex items-center justify-between rounded-md border border-white/10 bg-black/20 px-4 py-2 text-left text-sm text-slate-300 transition hover:border-gold-500/40"
                  >
                    <span>
                      {getPipelineScopeLabel(job)} - {job.completed_items}/{job.total_items} aula(s)
                    </span>
                    <PipelineStatusBadge status={job.status} />
                  </button>
                ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">Biblioteca de avatares</p>
        <p className="mt-1 text-xs text-slate-500">
          Cadastre avatares reutilizáveis por provider para agilizar a geração de vídeo.
        </p>

        <VideoAvatarCreateForm
          projectId={projectId}
          onCreated={(avatar) => setAvatars((current) => [avatar, ...current])}
        />

        {avatarsError ? <p className="mt-4 text-sm text-red-300">{avatarsError}</p> : null}

        <div className="mt-5 grid gap-3">
          {avatars.length ? (
            avatars.map((avatar) => (
              <VideoAvatarRow
                key={avatar.id}
                avatar={avatar}
                projectId={projectId}
                onUpdated={(updated) =>
                  setAvatars((current) => current.map((item) => (item.id === updated.id ? updated : item)))
                }
                onDeactivated={(avatarId) =>
                  setAvatars((current) =>
                    current.map((item) =>
                      item.id === avatarId ? { ...item, is_active: false, is_default: false } : item,
                    ),
                  )
                }
              />
            ))
          ) : (
            <p className="rounded-md border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
              Nenhum avatar cadastrado neste projeto.
            </p>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">Vídeos gerados</p>
        <div className="mt-4 grid gap-3">
          {videos.length ? (
            videos.map((video) => (
              <article key={video.id} className="rounded-md border border-white/10 bg-black/20 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-slate-100">
                      {video.avatar_name || video.avatar_id || "Avatar mock"} - {video.status}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {video.resolution} - {video.format.toUpperCase()} - {formatAudioDate(video.created_at)}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Provider {getVideoProviderLabel(video.provider)} - Áudio{" "}
                      {video.audio_id ? "vinculado" : "não informado"}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Origem: {getVideoOriginLabel(video)}</p>
                    {video.error_message ? <p className="mt-2 text-xs text-red-300">{video.error_message}</p> : null}
                    {!video.download_url && (video.status === "pending" || video.status === "processing") ? (
                      <p className="mt-2 text-xs text-gold-300">
                        Vídeo ainda em processamento na {getVideoProviderLabel(video.provider)}. Atualize o status
                        para acompanhar.
                      </p>
                    ) : null}
                    {!video.download_url && video.status === "completed_mock" ? (
                      <p className="mt-2 text-xs text-gold-300">Não foi possível gerar o MP4 mock para este vídeo.</p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {video.provider !== "mock" && video.status !== "completed" && video.status !== "failed" ? (
                      <button
                        type="button"
                        onClick={() => handleRefreshVideoStatus(video)}
                        disabled={refreshingVideoId === video.id}
                        className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {refreshingVideoId === video.id ? "Atualizando..." : "Atualizar status"}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => handleDownloadVideo(video)}
                      disabled={video.status !== "completed" || !video.download_url}
                      className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Baixar vídeo
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteVideo(video)}
                      className="rounded-md border border-red-400/40 px-3 py-2 text-sm text-red-300 transition hover:border-red-300 hover:text-red-200"
                    >
                      Excluir vídeo
                    </button>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <p className="rounded-md border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
              Nenhum vídeo gerado neste projeto.
            </p>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-white/10 bg-black/30 p-5">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">Comparação de providers</p>
        <p className="mt-1 text-xs text-slate-500">
          Compare qualidade, custo e desempenho entre Mock, HeyGen, D-ID e Sync Labs.
        </p>
        {videos.length ? (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[1080px] border-separate border-spacing-0 text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-slate-500">
                  <th className="border-b border-white/10 px-3 py-2">Provider</th>
                  <th className="border-b border-white/10 px-3 py-2">Aula / áudio base</th>
                  <th className="border-b border-white/10 px-3 py-2">Status</th>
                  <th className="border-b border-white/10 px-3 py-2">Duração</th>
                  <th className="border-b border-white/10 px-3 py-2">Tempo de geração</th>
                  <th className="border-b border-white/10 px-3 py-2">Tamanho</th>
                  <th className="border-b border-white/10 px-3 py-2">Custo estimado</th>
                  <th className="border-b border-white/10 px-3 py-2">Nota</th>
                  <th className="border-b border-white/10 px-3 py-2">Observações</th>
                  <th className="border-b border-white/10 px-3 py-2">Ações</th>
                </tr>
              </thead>
              <tbody>
                {videos.map((video) => (
                  <VideoComparisonRow
                    key={video.id}
                    video={video}
                    audioLabel={getVideoAudioBaseLabel(video, audios, sortedContents)}
                    projectId={projectId}
                    refreshing={refreshingVideoId === video.id}
                    onRefreshStatus={() => handleRefreshVideoStatus(video)}
                    onDownload={() => handleDownloadVideo(video)}
                    onUpdated={(updated) =>
                      setVideos((current) => current.map((item) => (item.id === updated.id ? updated : item)))
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 rounded-md border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
            Gere vídeos para começar a comparar providers.
          </p>
        )}
      </section>
    </div>
  );
}

const COURSE_EXPORT_STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  running: "Gerando ZIP...",
  completed: "Concluído",
  failed: "Falhou",
};

function CourseExportStatusBadge({ status }: { status: string }) {
  const stylesByStatus: Record<string, string> = {
    pending: "border-slate-400/40 bg-slate-400/10 text-slate-300",
    running: "border-sky-400/40 bg-sky-400/10 text-sky-300",
    completed: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
    failed: "border-red-400/40 bg-red-400/10 text-red-300",
  };
  const style = stylesByStatus[status] || "border-white/20 bg-white/5 text-slate-300";
  return (
    <span className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>
      {COURSE_EXPORT_STATUS_LABELS[status] || status}
    </span>
  );
}

function formatExportBytes(value: number | null): string {
  if (!value) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function ExportView({ projectId }: { projectId: string }) {
  const [includeDocumentBase, setIncludeDocumentBase] = useState(true);
  const [includeCourseSummary, setIncludeCourseSummary] = useState(true);
  const [includeCourseStructure, setIncludeCourseStructure] = useState(true);
  const [includeLessonScripts, setIncludeLessonScripts] = useState(true);
  const [includeQuizzes, setIncludeQuizzes] = useState(true);
  const [includeMaterials, setIncludeMaterials] = useState(true);
  const [includePresentation, setIncludePresentation] = useState(true);
  const [includeTeleprompter, setIncludeTeleprompter] = useState(true);
  const [includeAudio, setIncludeAudio] = useState(true);
  const [includeVideo, setIncludeVideo] = useState(true);
  const [onlyCompletedVideo, setOnlyCompletedVideo] = useState(true);
  const [formatText, setFormatText] = useState<CourseExportTextFormat>("md");

  const [exports, setExports] = useState<CourseExport[]>([]);
  const [currentExport, setCurrentExport] = useState<CourseExport | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let isActive = true;
    listCourseExports(projectId)
      .then((items) => {
        if (!isActive) return;
        setExports(items);
        if (items.length && items[0].status === "running") {
          setCurrentExport(items[0]);
          setIsPolling(true);
        }
      })
      .catch(() => {
        // Silencioso: historico de exports e informativo, nao bloqueia a tela.
      });
    return () => {
      isActive = false;
    };
  }, [projectId]);

  useEffect(() => {
    if (!isPolling || !currentExport) return;
    let isActive = true;
    let timeoutId: number | undefined;
    const exportId = currentExport.id;

    async function poll() {
      try {
        const item = await getCourseExport(projectId, exportId);
        if (!isActive) return;
        setCurrentExport(item);
        setExports((current) => current.map((entry) => (entry.id === item.id ? item : entry)));
        if (item.status === "pending" || item.status === "running") {
          timeoutId = window.setTimeout(poll, 3000);
        } else {
          setIsPolling(false);
        }
      } catch {
        if (isActive) setIsPolling(false);
      }
    }

    poll();

    return () => {
      isActive = false;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPolling, currentExport?.id, projectId]);

  async function handleCreateExport() {
    setError("");
    setMessage("");

    const confirmed = window.confirm(
      "Gerar o ZIP do curso completo pode demorar alguns minutos, especialmente com muitos audios e videos. Deseja continuar?",
    );
    if (!confirmed) return;

    setCreating(true);
    try {
      const payload: CourseExportCreatePayload = {
        include_document_base: includeDocumentBase,
        include_course_summary: includeCourseSummary,
        include_course_structure: includeCourseStructure,
        include_lesson_scripts: includeLessonScripts,
        include_quizzes: includeQuizzes,
        include_materials: includeMaterials,
        include_presentation: includePresentation,
        include_teleprompter: includeTeleprompter,
        include_audio: includeAudio,
        include_video: includeVideo,
        only_completed_video: onlyCompletedVideo,
        format_text: formatText,
      };
      const item = await createCourseExport(projectId, payload);
      setExports((current) => [item, ...current]);
      setCurrentExport(item);
      setIsPolling(true);
      setMessage("Exportação iniciada. Acompanhe o progresso abaixo.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Não foi possível iniciar a exportação agora.");
      }
    } finally {
      setCreating(false);
    }
  }

  async function handleDownloadExport(item: CourseExport) {
    setError("");
    setMessage("");
    try {
      await downloadCourseExport(projectId, item.id, `curso-${item.id}.zip`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Não foi possível baixar a exportação.");
      }
    }
  }

  async function handleDeleteExport(item: CourseExport) {
    const confirmed = window.confirm("Tem certeza que deseja excluir esta exportação?");
    if (!confirmed) return;

    setError("");
    setMessage("");
    try {
      await deleteCourseExport(projectId, item.id);
      setExports((current) => current.filter((entry) => entry.id !== item.id));
      if (currentExport?.id === item.id) setCurrentExport(null);
      setMessage("Exportação excluída com sucesso.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Não foi possível excluir a exportação.");
      }
    }
  }

  return (
    <div className="grid gap-6">
      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">Exportar curso completo</p>
        <p className="mt-1 text-xs text-slate-500">
          Gere um ZIP organizado com os conteudos educacionais, roteiros, quizzes, materiais, apresentação, áudios e
          vídeos deste projeto. Cursos grandes podem demorar alguns minutos.
        </p>

        <div className="mt-4 grid gap-2 text-sm text-slate-300 md:grid-cols-2">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeDocumentBase} onChange={(e) => setIncludeDocumentBase(e.target.checked)} />
            Documento Base
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeCourseSummary} onChange={(e) => setIncludeCourseSummary(e.target.checked)} />
            Resumo do Curso
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeCourseStructure}
              onChange={(e) => setIncludeCourseStructure(e.target.checked)}
            />
            Estrutura do Curso
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeLessonScripts} onChange={(e) => setIncludeLessonScripts(e.target.checked)} />
            Roteiros
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeQuizzes} onChange={(e) => setIncludeQuizzes(e.target.checked)} />
            Quizzes
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeMaterials} onChange={(e) => setIncludeMaterials(e.target.checked)} />
            Materiais Complementares
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includePresentation} onChange={(e) => setIncludePresentation(e.target.checked)} />
            Apresentação
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeTeleprompter} onChange={(e) => setIncludeTeleprompter(e.target.checked)} />
            Teleprompter
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeAudio} onChange={(e) => setIncludeAudio(e.target.checked)} />
            Áudios
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeVideo} onChange={(e) => setIncludeVideo(e.target.checked)} />
            Vídeos
          </label>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={onlyCompletedVideo} onChange={(e) => setOnlyCompletedVideo(e.target.checked)} />
            Exportar somente vídeos concluídos
          </label>
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Formato dos textos
            <select
              value={formatText}
              onChange={(event) => setFormatText(event.target.value as CourseExportTextFormat)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="md" className="bg-navy-950 text-slate-100">
                Markdown
              </option>
              <option value="txt" className="bg-navy-950 text-slate-100">
                TXT
              </option>
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={handleCreateExport}
          disabled={creating}
          className="mt-4 rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {creating ? "Criando exportação..." : "Gerar ZIP do curso"}
        </button>

        {message ? <p className="mt-4 text-sm text-gold-300">{message}</p> : null}
        {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}

        {currentExport ? (
          <div className="mt-5 rounded-md border border-gold-500/20 bg-gold-500/5 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-100">
                Exportação de {formatAudioDate(currentExport.created_at)}
              </p>
              <CourseExportStatusBadge status={currentExport.status} />
            </div>
            {currentExport.status === "completed" ? (
              <button
                type="button"
                onClick={() => handleDownloadExport(currentExport)}
                className="mt-3 rounded-md bg-gold-500 px-3 py-1.5 text-xs font-semibold text-navy-950 transition hover:bg-gold-400"
              >
                Baixar ZIP ({formatExportBytes(currentExport.file_size_bytes)})
              </button>
            ) : null}
            {currentExport.status === "failed" && currentExport.error_message ? (
              <p className="mt-3 text-xs text-red-300">{currentExport.error_message}</p>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">Exportações anteriores</p>
        <div className="mt-4 grid gap-3">
          {exports.length ? (
            exports.map((item) => (
              <article key={item.id} className="rounded-md border border-white/10 bg-black/20 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-slate-100">
                      {item.export_type} - {formatAudioDate(item.created_at)}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">{formatExportBytes(item.file_size_bytes)}</p>
                  </div>
                  <CourseExportStatusBadge status={item.status} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.status === "completed" ? (
                    <button
                      type="button"
                      onClick={() => handleDownloadExport(item)}
                      className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-slate-300 transition hover:border-gold-500/40 hover:text-gold-400"
                    >
                      Baixar
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => handleDeleteExport(item)}
                    className="rounded-md border border-red-400/30 px-3 py-1.5 text-xs text-red-300 transition hover:border-red-400/60"
                  >
                    Excluir
                  </button>
                </div>
                {item.error_message ? <p className="mt-3 text-xs text-red-300">{item.error_message}</p> : null}
              </article>
            ))
          ) : (
            <p className="rounded-md border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
              Nenhuma exportação gerada ainda.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

function validateVideoAvatarFields(
  provider: VideoProvider,
  avatarId: string,
  sourceImageUrl: string,
  sourceVideoUrl: string,
): string {
  if (provider === "heygen" && !avatarId.trim()) return "Avatar HeyGen precisa de Avatar ID.";
  if (provider === "did" && !sourceImageUrl.trim()) return "Avatar D-ID precisa de Source Image URL.";
  if (provider === "sync" && !sourceVideoUrl.trim() && !sourceImageUrl.trim()) {
    return "Avatar Sync Labs precisa de Source Video URL ou Source Image URL.";
  }
  return "";
}

function videoAvatarErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.status === 401) return "Sua sessão expirou. Faça login novamente.";
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

function VideoAvatarCreateForm({
  projectId,
  onCreated,
}: {
  projectId: string;
  onCreated: (avatar: VideoAvatar) => void;
}) {
  const [name, setName] = useState("");
  const [provider, setProvider] = useState<VideoProvider>("mock");
  const [avatarId, setAvatarId] = useState("");
  const [sourceImageUrl, setSourceImageUrl] = useState("");
  const [sourceVideoUrl, setSourceVideoUrl] = useState("");
  const [defaultModel, setDefaultModel] = useState("");
  const [description, setDescription] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate() {
    setError("");
    if (!name.trim()) {
      setError("Informe um nome para o avatar.");
      return;
    }
    const validationError = validateVideoAvatarFields(provider, avatarId, sourceImageUrl, sourceVideoUrl);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    try {
      const payload: VideoAvatarCreatePayload = {
        name: name.trim(),
        provider,
        avatar_id: avatarId.trim() || null,
        source_image_url: sourceImageUrl.trim() || null,
        source_video_url: sourceVideoUrl.trim() || null,
        default_model: defaultModel.trim() || null,
        description: description.trim() || null,
        is_active: true,
        is_default: isDefault,
      };
      const avatar = await createProjectVideoAvatar(projectId, payload);
      onCreated(avatar);
      setName("");
      setAvatarId("");
      setSourceImageUrl("");
      setSourceVideoUrl("");
      setDefaultModel("");
      setDescription("");
      setIsDefault(false);
    } catch (err) {
      setError(videoAvatarErrorMessage(err, "Não foi possível criar o avatar."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-4 rounded-md border border-white/10 bg-black/20 p-4">
      <p className="text-sm font-medium text-slate-100">Novo avatar</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <label className="grid min-w-0 gap-2 text-sm text-slate-300">
          Nome
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Instrutor Virtus"
            className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
          />
        </label>
        <label className="grid min-w-0 gap-2 text-sm text-slate-300">
          Provider
          <select
            value={provider}
            onChange={(event) => setProvider(event.target.value as VideoProvider)}
            className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
          >
            <option value="mock" className="bg-navy-950 text-slate-100">
              Mock
            </option>
            <option value="heygen" className="bg-navy-950 text-slate-100">
              HeyGen
            </option>
            <option value="did" className="bg-navy-950 text-slate-100">
              D-ID
            </option>
            <option value="sync" className="bg-navy-950 text-slate-100">
              Sync Labs
            </option>
          </select>
        </label>
        {provider === "heygen" ? (
          <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
            Avatar ID
            <input
              value={avatarId}
              onChange={(event) => setAvatarId(event.target.value)}
              placeholder="ID do avatar na HeyGen"
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
            />
          </label>
        ) : null}
        {provider === "did" ? (
          <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
            Source Image URL
            <input
              value={sourceImageUrl}
              onChange={(event) => setSourceImageUrl(event.target.value)}
              placeholder="https://..."
              className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
            />
          </label>
        ) : null}
        {provider === "sync" ? (
          <>
            <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
              Source Video URL
              <input
                value={sourceVideoUrl}
                onChange={(event) => setSourceVideoUrl(event.target.value)}
                placeholder="https://..."
                className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
              />
            </label>
            <label className="grid min-w-0 gap-2 text-sm text-slate-300">
              Source Image URL (opcional)
              <input
                value={sourceImageUrl}
                onChange={(event) => setSourceImageUrl(event.target.value)}
                placeholder="https://..."
                className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
              />
            </label>
            <label className="grid min-w-0 gap-2 text-sm text-slate-300">
              Modelo (opcional)
              <input
                value={defaultModel}
                onChange={(event) => setDefaultModel(event.target.value)}
                placeholder="lipsync-2"
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
              />
            </label>
          </>
        ) : null}
        <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
          Descrição
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={2}
            placeholder="Observações sobre este avatar"
            className="w-full min-w-0 resize-none rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-gold-500/60"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300 md:col-span-2">
          <input type="checkbox" checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} />
          Marcar como padrão para este provider
        </label>
      </div>
      {error ? <p className="mt-3 text-xs text-red-300">{error}</p> : null}
      <button
        type="button"
        onClick={handleCreate}
        disabled={saving}
        className="mt-3 rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {saving ? "Salvando..." : "Adicionar avatar"}
      </button>
    </div>
  );
}

function VideoAvatarRow({
  avatar,
  projectId,
  onUpdated,
  onDeactivated,
}: {
  avatar: VideoAvatar;
  projectId: string;
  onUpdated: (avatar: VideoAvatar) => void;
  onDeactivated: (avatarId: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(avatar.name);
  const [provider, setProvider] = useState<VideoProvider>(avatar.provider);
  const [avatarIdField, setAvatarIdField] = useState(avatar.avatar_id || "");
  const [sourceImageUrl, setSourceImageUrl] = useState(avatar.source_image_url || "");
  const [sourceVideoUrl, setSourceVideoUrl] = useState(avatar.source_video_url || "");
  const [defaultModel, setDefaultModel] = useState(avatar.default_model || "");
  const [description, setDescription] = useState(avatar.description || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function startEditing() {
    setName(avatar.name);
    setProvider(avatar.provider);
    setAvatarIdField(avatar.avatar_id || "");
    setSourceImageUrl(avatar.source_image_url || "");
    setSourceVideoUrl(avatar.source_video_url || "");
    setDefaultModel(avatar.default_model || "");
    setDescription(avatar.description || "");
    setError("");
    setIsEditing(true);
  }

  async function handleSaveEdit() {
    setError("");
    if (!name.trim()) {
      setError("Informe um nome para o avatar.");
      return;
    }
    const validationError = validateVideoAvatarFields(provider, avatarIdField, sourceImageUrl, sourceVideoUrl);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    try {
      const payload: VideoAvatarUpdatePayload = {
        name: name.trim(),
        provider,
        avatar_id: avatarIdField.trim() || null,
        source_image_url: sourceImageUrl.trim() || null,
        source_video_url: sourceVideoUrl.trim() || null,
        default_model: defaultModel.trim() || null,
        description: description.trim() || null,
      };
      const updated = await updateProjectVideoAvatar(projectId, avatar.id, payload);
      onUpdated(updated);
      setIsEditing(false);
    } catch (err) {
      setError(videoAvatarErrorMessage(err, "Não foi possível salvar o avatar."));
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleDefault() {
    setError("");
    setSaving(true);
    try {
      const updated = await updateProjectVideoAvatar(projectId, avatar.id, { is_default: !avatar.is_default });
      onUpdated(updated);
    } catch (err) {
      setError(videoAvatarErrorMessage(err, "Não foi possível atualizar o avatar padrão."));
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive() {
    setError("");
    if (avatar.is_active) {
      const confirmed = window.confirm("Desativar este avatar? Ele deixará de aparecer para novas gerações.");
      if (!confirmed) return;
      setSaving(true);
      try {
        await deleteProjectVideoAvatar(projectId, avatar.id);
        onDeactivated(avatar.id);
      } catch (err) {
        setError(videoAvatarErrorMessage(err, "Não foi possível desativar o avatar."));
      } finally {
        setSaving(false);
      }
      return;
    }

    setSaving(true);
    try {
      const updated = await updateProjectVideoAvatar(projectId, avatar.id, { is_active: true });
      onUpdated(updated);
    } catch (err) {
      setError(videoAvatarErrorMessage(err, "Não foi possível reativar o avatar."));
    } finally {
      setSaving(false);
    }
  }

  if (isEditing) {
    return (
      <article className="rounded-md border border-gold-500/30 bg-black/20 p-4">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Nome
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            />
          </label>
          <label className="grid min-w-0 gap-2 text-sm text-slate-300">
            Provider
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value as VideoProvider)}
              className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            >
              <option value="mock" className="bg-navy-950 text-slate-100">
                Mock
              </option>
              <option value="heygen" className="bg-navy-950 text-slate-100">
                HeyGen
              </option>
              <option value="did" className="bg-navy-950 text-slate-100">
                D-ID
              </option>
              <option value="sync" className="bg-navy-950 text-slate-100">
                Sync Labs
              </option>
            </select>
          </label>
          {provider === "heygen" ? (
            <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
              Avatar ID
              <input
                value={avatarIdField}
                onChange={(event) => setAvatarIdField(event.target.value)}
                className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              />
            </label>
          ) : null}
          {provider === "did" ? (
            <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
              Source Image URL
              <input
                value={sourceImageUrl}
                onChange={(event) => setSourceImageUrl(event.target.value)}
                className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
              />
            </label>
          ) : null}
          {provider === "sync" ? (
            <>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
                Source Video URL
                <input
                  value={sourceVideoUrl}
                  onChange={(event) => setSourceVideoUrl(event.target.value)}
                  className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
                />
              </label>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300">
                Source Image URL (opcional)
                <input
                  value={sourceImageUrl}
                  onChange={(event) => setSourceImageUrl(event.target.value)}
                  className="w-full min-w-0 truncate rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
                />
              </label>
              <label className="grid min-w-0 gap-2 text-sm text-slate-300">
                Modelo (opcional)
                <input
                  value={defaultModel}
                  onChange={(event) => setDefaultModel(event.target.value)}
                  className="w-full min-w-0 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
                />
              </label>
            </>
          ) : null}
          <label className="grid min-w-0 gap-2 text-sm text-slate-300 md:col-span-2">
            Descrição
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
              className="w-full min-w-0 resize-none rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
            />
          </label>
        </div>
        {error ? <p className="mt-3 text-xs text-red-300">{error}</p> : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleSaveEdit}
            disabled={saving}
            className="rounded-md bg-gold-500 px-3 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? "Salvando..." : "Salvar"}
          </button>
          <button
            type="button"
            onClick={() => setIsEditing(false)}
            disabled={saving}
            className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancelar
          </button>
        </div>
      </article>
    );
  }

  return (
    <article className="rounded-md border border-white/10 bg-black/20 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <VideoProviderBadge provider={avatar.provider} />
            <p className="text-sm font-medium text-slate-100">{avatar.name}</p>
            {avatar.is_default ? (
              <span className="inline-block whitespace-nowrap rounded-full border border-gold-400/40 bg-gold-400/10 px-2 py-0.5 text-xs font-medium text-gold-300">
                Padrão
              </span>
            ) : null}
            {!avatar.is_active ? (
              <span className="inline-block whitespace-nowrap rounded-full border border-white/20 bg-white/5 px-2 py-0.5 text-xs font-medium text-slate-400">
                Inativo
              </span>
            ) : null}
          </div>
          {avatar.avatar_id ? (
            <p className="mt-1 max-w-full break-words text-xs text-slate-500">Avatar ID: {avatar.avatar_id}</p>
          ) : null}
          {avatar.source_image_url ? (
            <p className="mt-1 max-w-full break-words text-xs text-slate-500">Imagem: {avatar.source_image_url}</p>
          ) : null}
          {avatar.source_video_url ? (
            <p className="mt-1 max-w-full break-words text-xs text-slate-500">Vídeo base: {avatar.source_video_url}</p>
          ) : null}
          {avatar.default_model ? <p className="mt-1 text-xs text-slate-500">Modelo: {avatar.default_model}</p> : null}
          {avatar.description ? (
            <p className="mt-1 max-w-full break-words text-xs text-slate-400">{avatar.description}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={startEditing}
            className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
          >
            Editar
          </button>
          {avatar.is_active ? (
            <button
              type="button"
              onClick={handleToggleDefault}
              disabled={saving}
              className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {avatar.is_default ? "Remover padrão" : "Marcar como padrão"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={handleToggleActive}
            disabled={saving}
            className={
              avatar.is_active
                ? "rounded-md border border-red-400/40 px-3 py-2 text-sm text-red-300 transition hover:border-red-300 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-60"
                : "rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            }
          >
            {avatar.is_active ? "Desativar" : "Reativar"}
          </button>
        </div>
      </div>
      {error ? <p className="mt-2 text-xs text-red-300">{error}</p> : null}
    </article>
  );
}

function VideoStatusBadge({ status }: { status: string }) {
  const stylesByStatus: Record<string, string> = {
    completed: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
    completed_mock: "border-amber-400/40 bg-amber-400/10 text-amber-300",
    processing: "border-sky-400/40 bg-sky-400/10 text-sky-300",
    pending: "border-slate-400/40 bg-slate-400/10 text-slate-300",
    failed: "border-red-400/40 bg-red-400/10 text-red-300",
  };
  const labelsByStatus: Record<string, string> = {
    completed: "Concluído",
    completed_mock: "Mock parcial",
    processing: "Processando",
    pending: "Pendente",
    failed: "Falhou",
  };
  const style = stylesByStatus[status] || "border-white/20 bg-white/5 text-slate-300";
  const label = labelsByStatus[status] || status;

  return (
    <span className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>
      {label}
    </span>
  );
}

function VideoProviderBadge({ provider }: { provider: string }) {
  const stylesByProvider: Record<string, string> = {
    mock: "border-slate-400/40 bg-slate-400/10 text-slate-300",
    heygen: "border-violet-400/40 bg-violet-400/10 text-violet-300",
    did: "border-blue-400/40 bg-blue-400/10 text-blue-300",
    sync: "border-teal-400/40 bg-teal-400/10 text-teal-300",
  };
  const style = stylesByProvider[provider] || "border-white/20 bg-white/5 text-slate-300";

  return (
    <span className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>
      {getVideoProviderLabel(provider)}
    </span>
  );
}

const PIPELINE_JOB_STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  running: "Em andamento",
  completed: "Concluído",
  failed: "Falhou",
  partially_completed: "Concluído parcialmente",
  cancelled: "Cancelado",
};

const PIPELINE_ITEM_STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  generating_audio: "Gerando áudio",
  audio_completed: "Áudio concluído",
  generating_video: "Gerando vídeo",
  video_processing: "Vídeo processando",
  completed: "Concluído",
  failed: "Falhou",
  skipped: "Pulado",
};

function PipelineStatusBadge({ status }: { status: string }) {
  const stylesByStatus: Record<string, string> = {
    pending: "border-slate-400/40 bg-slate-400/10 text-slate-300",
    running: "border-sky-400/40 bg-sky-400/10 text-sky-300",
    generating_audio: "border-sky-400/40 bg-sky-400/10 text-sky-300",
    audio_completed: "border-sky-400/40 bg-sky-400/10 text-sky-300",
    generating_video: "border-sky-400/40 bg-sky-400/10 text-sky-300",
    video_processing: "border-sky-400/40 bg-sky-400/10 text-sky-300",
    completed: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
    partially_completed: "border-amber-400/40 bg-amber-400/10 text-amber-300",
    failed: "border-red-400/40 bg-red-400/10 text-red-300",
    cancelled: "border-white/20 bg-white/5 text-slate-300",
    skipped: "border-white/20 bg-white/5 text-slate-300",
  };
  const style = stylesByStatus[status] || "border-white/20 bg-white/5 text-slate-300";
  const label = PIPELINE_JOB_STATUS_LABELS[status] || PIPELINE_ITEM_STATUS_LABELS[status] || status;

  return (
    <span className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>
      {label}
    </span>
  );
}

function getPipelineScopeLabel(job: VideoPipelineJob): string {
  if (job.scope === "course") return "Curso inteiro";
  if (job.scope === "module") return `Módulo ${job.module_index ?? "?"}`;
  return `Aula ${job.lesson_index ?? "?"}`;
}

function PipelineJobCard({
  job,
  actionLoading,
  onRun,
  onRetryFailed,
  onCancel,
}: {
  job: VideoPipelineJob;
  actionLoading: boolean;
  onRun: () => void;
  onRetryFailed: () => void;
  onCancel: () => void;
}) {
  const progressPercent = job.total_items > 0 ? Math.round((job.completed_items / job.total_items) * 100) : 0;
  const canRun = job.status === "pending";
  const canRetryFailed = (job.status === "failed" || job.status === "partially_completed") && job.failed_items > 0;
  const canCancel = job.status === "pending" || job.status === "running";

  return (
    <div className="mt-5 rounded-md border border-gold-500/20 bg-gold-500/5 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-100">{getPipelineScopeLabel(job)}</p>
          <p className="mt-1 text-xs text-slate-400">
            {job.current_item_label ? `Processando: ${job.current_item_label}` : "Aguardando início"}
          </p>
        </div>
        <PipelineStatusBadge status={job.status} />
      </div>

      <div className="mt-4 h-2 rounded-full bg-white/10">
        <div className="h-2 rounded-full bg-gold-500 transition-all" style={{ width: `${progressPercent}%` }} />
      </div>
      <p className="mt-2 text-xs text-slate-400">
        {job.completed_items}/{job.total_items} concluídas
        {job.failed_items > 0 ? ` - ${job.failed_items} com falha` : ""} ({progressPercent}%)
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {canRun ? (
          <button
            type="button"
            onClick={onRun}
            disabled={actionLoading}
            className="rounded-md bg-gold-500 px-3 py-1.5 text-xs font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Iniciar geração
          </button>
        ) : null}
        {canRetryFailed ? (
          <button
            type="button"
            onClick={onRetryFailed}
            disabled={actionLoading}
            className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-slate-300 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Tentar novamente falhas
          </button>
        ) : null}
        {canCancel ? (
          <button
            type="button"
            onClick={onCancel}
            disabled={actionLoading}
            className="rounded-md border border-red-400/30 px-3 py-1.5 text-xs text-red-300 transition hover:border-red-400/60 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancelar
          </button>
        ) : null}
      </div>

      {job.error_message ? <p className="mt-3 text-xs text-red-300">{job.error_message}</p> : null}

      <div className="mt-4 grid gap-2">
        {job.items.map((item) => (
          <div
            key={item.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-white/10 bg-black/20 px-3 py-2"
          >
            <span className="text-xs text-slate-300">{item.lesson_title || "Aula"}</span>
            <div className="flex items-center gap-2">
              {item.error_message ? <span className="text-xs text-red-300">{item.error_message}</span> : null}
              <PipelineStatusBadge status={item.status} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatSecondsLabel(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value < 60) return `${value.toFixed(1)}s`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes}m ${seconds}s`;
}

function formatBytesLabel(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(0)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function VideoComparisonRow({
  video,
  audioLabel,
  projectId,
  refreshing,
  onRefreshStatus,
  onDownload,
  onUpdated,
}: {
  video: GeneratedVideo;
  audioLabel: string;
  projectId: string;
  refreshing: boolean;
  onRefreshStatus: () => void;
  onDownload: () => void;
  onUpdated: (video: GeneratedVideo) => void;
}) {
  const initialRating = video.quality_rating ? String(video.quality_rating) : "";
  const initialNotes = video.quality_notes || "";
  const initialCost =
    video.estimated_cost_usd === null || video.estimated_cost_usd === undefined ? "" : String(video.estimated_cost_usd);

  const [rating, setRating] = useState(initialRating);
  const [notes, setNotes] = useState(initialNotes);
  const [cost, setCost] = useState(initialCost);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setRating(initialRating);
    setNotes(initialNotes);
    setCost(initialCost);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video.id, initialRating, initialNotes, initialCost]);

  const isDirty = rating !== initialRating || notes !== initialNotes || cost !== initialCost;

  async function handleSave() {
    setError("");

    const trimmedCost = cost.trim();
    const parsedCost = trimmedCost ? Number(trimmedCost) : null;
    if (trimmedCost && (Number.isNaN(parsedCost) || (parsedCost !== null && parsedCost < 0))) {
      setError("Custo estimado inválido.");
      return;
    }

    const trimmedRating = rating.trim();
    const parsedRating = trimmedRating ? Number(trimmedRating) : null;
    if (trimmedRating && (!Number.isInteger(parsedRating) || (parsedRating || 0) < 1 || (parsedRating || 0) > 5)) {
      setError("Nota deve ser um número inteiro de 1 a 5.");
      return;
    }

    const payload: VideoReviewUpdatePayload = {
      quality_rating: parsedRating,
      quality_notes: notes.trim() || null,
      estimated_cost_usd: parsedCost,
    };

    setSaving(true);
    try {
      const updated = await updateProjectVideoReview(projectId, video.id, payload);
      onUpdated(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Não foi possível salvar a avaliação.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr className="align-top text-slate-200">
      <td className="border-b border-white/5 px-3 py-3">
        <VideoProviderBadge provider={video.provider} />
      </td>
      <td className="max-w-[220px] border-b border-white/5 px-3 py-3 text-xs text-slate-300">
        <span className="line-clamp-2 break-words">{audioLabel}</span>
      </td>
      <td className="border-b border-white/5 px-3 py-3">
        <VideoStatusBadge status={video.status} />
        {video.error_message ? (
          <p className="mt-1 max-w-[160px] break-words text-xs text-red-300">{video.error_message}</p>
        ) : null}
      </td>
      <td className="whitespace-nowrap border-b border-white/5 px-3 py-3 text-xs text-slate-300">
        {formatSecondsLabel(video.duration_seconds)}
      </td>
      <td className="whitespace-nowrap border-b border-white/5 px-3 py-3 text-xs text-slate-300">
        {formatSecondsLabel(video.provider_latency_seconds)}
      </td>
      <td className="whitespace-nowrap border-b border-white/5 px-3 py-3 text-xs text-slate-300">
        {formatBytesLabel(video.file_size_bytes)}
      </td>
      <td className="border-b border-white/5 px-3 py-3">
        <input
          type="number"
          min="0"
          step="0.01"
          value={cost}
          onChange={(event) => setCost(event.target.value)}
          placeholder="USD"
          className="w-24 rounded-md border border-white/10 bg-black/30 px-2 py-1 text-xs text-slate-100 focus:border-gold-500/50 focus:outline-none"
        />
      </td>
      <td className="border-b border-white/5 px-3 py-3">
        <select
          value={rating}
          onChange={(event) => setRating(event.target.value)}
          className="w-20 rounded-md border border-white/10 bg-black/30 px-2 py-1 text-xs text-slate-100 focus:border-gold-500/50 focus:outline-none"
        >
          <option value="">—</option>
          {[1, 2, 3, 4, 5].map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </td>
      <td className="border-b border-white/5 px-3 py-3">
        <textarea
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={2}
          placeholder="Observações"
          className="w-40 resize-none rounded-md border border-white/10 bg-black/30 px-2 py-1 text-xs text-slate-100 focus:border-gold-500/50 focus:outline-none"
        />
      </td>
      <td className="border-b border-white/5 px-3 py-3">
        <div className="flex flex-col gap-1.5">
          {isDirty ? (
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-md border border-gold-500/40 px-2 py-1 text-xs text-gold-300 transition hover:border-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Salvando..." : "Salvar avaliação"}
            </button>
          ) : null}
          {video.provider !== "mock" && video.status !== "completed" && video.status !== "failed" ? (
            <button
              type="button"
              onClick={onRefreshStatus}
              disabled={refreshing}
              className="rounded-md border border-white/10 px-2 py-1 text-xs text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {refreshing ? "Atualizando..." : "Atualizar status"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onDownload}
            disabled={video.status !== "completed" || !video.download_url}
            className="rounded-md border border-white/10 px-2 py-1 text-xs text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Baixar
          </button>
          {error ? <p className="max-w-[140px] break-words text-xs text-red-300">{error}</p> : null}
        </div>
      </td>
    </tr>
  );
}

function NarrationAudioList({
  title,
  emptyText,
  audios,
  audioUrls,
  onDownload,
  onDelete,
}: {
  title: string;
  emptyText: string;
  audios: GeneratedAudio[];
  audioUrls: Record<string, string>;
  onDownload: (audio: GeneratedAudio) => void;
  onDelete: (audio: GeneratedAudio) => void;
}) {
  return (
    <div className="mt-6 grid gap-3">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-gold-400">{title}</p>
      {audios.length ? (
        audios.map((audio) => (
          <article key={audio.id} className="rounded-md border border-white/10 bg-black/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-slate-100">{audio.title || `Audio do bloco ${audio.block_index}`}</p>
                <p className="mt-1 text-xs text-slate-500">
                  Bloco {audio.block_index} - {formatAudioDate(audio.created_at)}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Provider {audio.voice_provider || "OpenAI"} - Voz {audio.voice || "padrao"} - Modelo {audio.model || "padrao"}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {audio.personalized_voice_used ? "Voz personalizada configurada" : "Voz padrao do sistema"}
                </p>
                {audio.voice_notice ? <p className="mt-2 text-xs text-gold-300">{audio.voice_notice}</p> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onDownload(audio)}
                  className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                >
                  Baixar audio
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(audio)}
                  className="rounded-md border border-red-400/40 px-3 py-2 text-sm text-red-300 transition hover:border-red-300 hover:text-red-200"
                >
                  Excluir audio
                </button>
              </div>
            </div>
            {audioUrls[audio.id] ? (
              <audio controls src={audioUrls[audio.id]} className="mt-4 w-full" />
            ) : (
              <p className="mt-4 text-sm text-slate-400">Carregando player de audio...</p>
            )}
          </article>
        ))
      ) : (
        <p className="rounded-md border border-white/10 bg-black/20 p-4 text-sm text-slate-400">{emptyText}</p>
      )}
    </div>
  );
}

function VoiceSettingsCard({
  profile,
  loaded,
  error,
}: {
  profile: InstructorProfile | null;
  loaded: boolean;
  error: string;
}) {
  const provider = profile?.voice_provider?.trim() || "OpenAI";
  const voiceLabel = profile?.voice_id?.trim() || profile?.voice_name?.trim() || "voz padrão do sistema";
  const normalizedProvider = provider.toLowerCase().replace(/[\s_]/g, "");
  const isElevenLabsProvider = normalizedProvider === "elevenlabs";
  const hasUnsupportedProvider = Boolean(
    profile?.voice_provider && normalizedProvider !== "openai" && !isElevenLabsProvider,
  );

  return (
    <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-gold-400">Configuração de voz</p>
          <h3 className="mt-1 text-xl font-semibold text-slate-50">Perfil do Instrutor</h3>
        </div>
        <Link
          href="/instructor-profile"
          className="rounded-md border border-gold-500/30 px-3 py-2 text-sm font-semibold text-gold-300 transition hover:border-gold-400 hover:text-gold-200"
        >
          Configurar Perfil do Instrutor
        </Link>
      </div>

      {!loaded ? <p className="mt-4 text-sm text-slate-400">Carregando configuração de voz...</p> : null}
      {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}
      {loaded && !error && !profile ? (
        <p className="mt-4 text-sm leading-6 text-slate-300">
          Nenhum perfil de instrutor configurado. A geração usará a voz padrão do sistema.
        </p>
      ) : null}

      {loaded && !error && profile ? (
        <div className="mt-4 grid gap-3 text-sm text-slate-300 md:grid-cols-3">
          <div className="rounded-md border border-white/10 bg-black/20 p-3">
            <p className="text-xs text-slate-500">Provider de voz</p>
            <p className="mt-1 font-medium text-slate-100">{provider}</p>
          </div>
          <div className="rounded-md border border-white/10 bg-black/20 p-3">
            <p className="text-xs text-slate-500">Nome/ID da voz</p>
            <p className="mt-1 font-medium text-slate-100">{voiceLabel}</p>
          </div>
          <div className="rounded-md border border-white/10 bg-black/20 p-3">
            <p className="text-xs text-slate-500">Consentimento</p>
            <p className="mt-1 font-medium text-slate-100">
              {profile.consent_voice_clone ? "ativo" : "não ativo"}
            </p>
          </div>
        </div>
      ) : null}

      {loaded && profile && !profile.consent_voice_clone ? (
        <p className="mt-4 text-sm leading-6 text-gold-200">
          A voz personalizada não será usada porque o consentimento ainda não está ativo.
        </p>
      ) : null}
      {loaded && profile && profile.consent_voice_clone && isElevenLabsProvider ? (
        <p className="mt-4 text-sm leading-6 text-gold-200">
          Provider: ElevenLabs. Voice ID: {profile.voice_id || "não informado"}. A voz será usada se a chave
          ElevenLabs estiver configurada no servidor.
        </p>
      ) : null}
      {loaded && profile && hasUnsupportedProvider ? (
        <p className="mt-4 text-sm leading-6 text-gold-200">
          Este provider ainda será integrado em etapa futura.
        </p>
      ) : null}
    </section>
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

async function copyTextToClipboard(text: string): Promise<boolean> {
  if (!text.trim()) return false;

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall back to textarea copy for HTTP or restricted clipboard contexts.
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.top = "0";
    textarea.style.left = "0";
    textarea.style.opacity = "0";
    textarea.setAttribute("readonly", "true");
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    try {
      return document.execCommand("copy");
    } finally {
      document.body.removeChild(textarea);
    }
  } catch {
    return false;
  }
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

function isCompleteNarrationCandidate(text: string): boolean {
  return text.length >= 500 && countWords(text) >= 80;
}

function normalizeNarrationFingerprint(text: string): string {
  return cleanNarrationText(text).toLowerCase().replace(/\s+/g, " ").trim();
}

function pushUniqueNarrationPart(parts: string[], value: unknown) {
  const text = cleanNarrationText(narrationValueToText(value));
  if (!text) return;

  const fingerprint = normalizeNarrationFingerprint(text);
  if (!fingerprint) return;

  const alreadyIncluded = parts.some((part) => {
    const current = normalizeNarrationFingerprint(part);
    return current === fingerprint || current.includes(fingerprint) || fingerprint.includes(current);
  });

  if (!alreadyIncluded) parts.push(text);
}

function getLessonNarrationHeading(script: NonNullable<LessonScriptContent["lesson_script"]>): string {
  const moduleNumber = safeText(script.module_number);
  const lessonNumber = safeText(script.lesson_number);
  const moduleTitle = safeText(script.module_title);
  const lessonTitle = safeText(script.lesson_title);
  const parts: string[] = [];

  if (moduleNumber !== "Nao informado" || moduleTitle !== "Nao informado") {
    const label = moduleNumber === "Nao informado" ? "Modulo" : `Modulo ${moduleNumber}`;
    parts.push(moduleTitle === "Nao informado" ? label : `${label}: ${moduleTitle}`);
  }

  if (lessonNumber !== "Nao informado" || lessonTitle !== "Nao informado") {
    const label = lessonNumber === "Nao informado" ? "Aula" : `Aula ${lessonNumber}`;
    parts.push(lessonTitle === "Nao informado" ? label : `${label}: ${lessonTitle}`);
  }

  return parts.join("\n");
}

function getBestCompleteNarrationText(record: Record<string, unknown>): string {
  const narrationText = cleanNarrationText(narrationValueToText(record.narration_text));
  const scriptText = cleanNarrationText(narrationValueToText(record.script_text));
  const legacyNarration = cleanNarrationText(narrationValueToText(record.narration));

  if (isCompleteNarrationCandidate(narrationText) && narrationText.length >= scriptText.length * 0.9) {
    return narrationText;
  }

  if (isCompleteNarrationCandidate(scriptText)) {
    return scriptText;
  }

  if (isCompleteNarrationCandidate(narrationText)) {
    return narrationText;
  }

  if (isCompleteNarrationCandidate(legacyNarration)) {
    return legacyNarration;
  }

  return "";
}

function buildNarrationText(script: NonNullable<LessonScriptContent["lesson_script"]>): string {
  const record = script as Record<string, unknown>;
  const parts: string[] = [];
  const heading = getLessonNarrationHeading(script);
  const completeText = getBestCompleteNarrationText(record);

  if (heading) parts.push(heading);

  if (completeText) {
    parts.push(completeText);
    return cleanNarrationText(parts.join("\n\n"));
  }

  pushUniqueNarrationPart(parts, script.opening);
  pushUniqueNarrationPart(parts, record.introduction);
  pushUniqueNarrationPart(parts, record.development);
  pushUniqueNarrationPart(parts, script.main_script);
  pushUniqueNarrationPart(parts, record.sections ?? record.blocks);
  pushUniqueNarrationPart(parts, record.examples ?? script.practical_example);
  pushUniqueNarrationPart(parts, record.practical_activity);
  pushUniqueNarrationPart(parts, script.reflection_question);
  pushUniqueNarrationPart(parts, record.conclusion ?? script.closing);
  pushUniqueNarrationPart(parts, script.call_to_action);
  pushUniqueNarrationPart(parts, record.instructor_notes);

  return cleanNarrationText(parts.join("\n\n"));
}

function getModuleNarrationLabel(group: LessonModuleGroup): string {
  const moduleLabel = group.moduleNumber === 9999 ? "Modulo" : `Modulo ${group.moduleNumber}`;
  return group.moduleTitle && group.moduleTitle !== "Nao informado"
    ? `${moduleLabel}: ${group.moduleTitle}`
    : moduleLabel;
}

function groupLessonsByModule(contents: GeneratedContent[]): LessonModuleGroup[] {
  const groups = new Map<string, LessonModuleGroup>();

  sortLessonScripts(contents).forEach((content, index) => {
    const script = (content.content_json as LessonScriptContent | null)?.lesson_script;
    const moduleNumber = getContentNumber(content, "lesson_script", "module_number");
    const moduleTitle = safeText(script?.module_title);
    const key = moduleNumber === 9999 ? `module-unknown-${index}` : `module-${moduleNumber}`;
    const existing = groups.get(key);

    if (existing) {
      if (existing.moduleTitle === "Nao informado" && moduleTitle !== "Nao informado") {
        existing.moduleTitle = moduleTitle;
      }
      existing.lessons.push(content);
    } else {
      groups.set(key, {
        key,
        moduleNumber,
        moduleTitle,
        lessons: [content],
      });
    }
  });

  return Array.from(groups.values()).map((group) => ({
    ...group,
    lessons: sortLessonScripts(group.lessons),
  }));
}

function buildModuleNarrationText(group: LessonModuleGroup): string {
  const parts = [getModuleNarrationLabel(group)];

  group.lessons.forEach((content, index) => {
    const script = (content.content_json as LessonScriptContent | null)?.lesson_script;
    if (!script) return;
    const lessonText = buildNarrationText(script);
    if (!lessonText) return;
    parts.push(`Aula ${index + 1}\n${lessonText}`);
  });

  return cleanNarrationText(parts.join("\n\n---\n\n"));
}

function getLessonAudioBaseTitle(
  script: LessonScriptContent["lesson_script"] | undefined,
  content?: GeneratedContent,
): string {
  const moduleNumber = safeText(script?.module_number);
  const lessonNumber = safeText(script?.lesson_number);
  const moduleLabel = moduleNumber === "Nao informado" ? "Modulo" : `Modulo ${moduleNumber}`;
  const lessonLabel = lessonNumber === "Nao informado" ? "Aula" : `Aula ${lessonNumber}`;
  const lessonTitle = safeText(script?.lesson_title || content?.title);

  return lessonTitle === "Nao informado" ? `${moduleLabel} - ${lessonLabel}` : `${moduleLabel} - ${lessonLabel}: ${lessonTitle}`;
}

function getModuleAudioBaseTitle(group: LessonModuleGroup): string {
  const moduleLabel = group.moduleNumber === 9999 ? "Modulo" : `Modulo ${group.moduleNumber}`;
  return `${moduleLabel} - Consolidado`;
}

function sortAudiosByCreatedAtDesc(first: GeneratedAudio, second: GeneratedAudio): number {
  return new Date(second.created_at).getTime() - new Date(first.created_at).getTime();
}

function groupAudiosForNarration(
  audios: GeneratedAudio[],
  lessons: GeneratedContent[],
  moduleGroups: LessonModuleGroup[],
): NarrationAudioGroups {
  const byLessonId: Record<string, GeneratedAudio[]> = {};
  const byModuleKey: Record<string, GeneratedAudio[]> = {};
  const others: GeneratedAudio[] = [];

  const lessonIds = new Set(lessons.map((lesson) => lesson.id));
  const lessonTitleMap = new Map<string, string>();
  lessons.forEach((lesson) => {
    const script = (lesson.content_json as LessonScriptContent | null)?.lesson_script;
    lessonTitleMap.set(lesson.id, getLessonAudioBaseTitle(script, lesson));
  });

  audios.forEach((audio) => {
    if (audio.generated_content_id && lessonIds.has(audio.generated_content_id)) {
      byLessonId[audio.generated_content_id] = byLessonId[audio.generated_content_id] || [];
      byLessonId[audio.generated_content_id].push(audio);
      return;
    }

    const title = audio.title || "";
    const titleLesson = lessons.find((lesson) => {
      const baseTitle = lessonTitleMap.get(lesson.id) || "";
      return Boolean(baseTitle && title.startsWith(baseTitle));
    });
    if (titleLesson) {
      byLessonId[titleLesson.id] = byLessonId[titleLesson.id] || [];
      byLessonId[titleLesson.id].push(audio);
      return;
    }

    const titleModule = moduleGroups.find((group) => {
      const baseTitle = getModuleAudioBaseTitle(group);
      const legacyTitle = getModuleNarrationLabel(group);
      return title.startsWith(baseTitle) || title.startsWith(legacyTitle);
    });
    if (titleModule) {
      byModuleKey[titleModule.key] = byModuleKey[titleModule.key] || [];
      byModuleKey[titleModule.key].push(audio);
      return;
    }

    others.push(audio);
  });

  Object.values(byLessonId).forEach((items) => items.sort(sortAudiosByCreatedAtDesc));
  Object.values(byModuleKey).forEach((items) => items.sort(sortAudiosByCreatedAtDesc));
  others.sort(sortAudiosByCreatedAtDesc);

  return { byLessonId, byModuleKey, others };
}

function formatAudioDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "data nao informada";
  return date.toLocaleString("pt-BR");
}

function getVideoAudioLabel(audio: GeneratedAudio, lessons: GeneratedContent[]): string {
  const lesson = audio.generated_content_id
    ? lessons.find((content) => content.id === audio.generated_content_id)
    : undefined;
  const script = (lesson?.content_json as LessonScriptContent | null)?.lesson_script;
  const lessonLabel = lesson ? getLessonAudioBaseTitle(script, lesson) : "";
  const audioLabel = audio.title || `Áudio bloco ${audio.block_index || "sem número"}`;

  return lessonLabel ? `${lessonLabel} - ${audioLabel}` : audioLabel;
}

function getVideoOriginLabel(video: GeneratedVideo): string {
  const title = video.extra_metadata?.narration_title;
  if (typeof title === "string" && title.trim()) return title;
  if (video.lesson_id) return "Aula vinculada";
  return "Origem nao informada";
}

function getVideoProviderLabel(provider: string): string {
  return VIDEO_PROVIDER_LABELS[provider as VideoProvider] || provider;
}

function getVideoAudioBaseLabel(video: GeneratedVideo, audios: GeneratedAudio[], lessons: GeneratedContent[]): string {
  const audio = video.audio_id ? audios.find((item) => item.id === video.audio_id) : undefined;
  if (audio) return getVideoAudioLabel(audio, lessons);
  return getVideoOriginLabel(video);
}

function pickDefaultAvatarIdForProvider(settings: ProjectVideoSettings, provider: string): string {
  const fieldByProvider: Record<string, string | null> = {
    mock: settings.default_mock_avatar_id,
    heygen: settings.default_heygen_avatar_id,
    did: settings.default_did_avatar_id,
    sync: settings.default_sync_avatar_id,
  };
  return fieldByProvider[provider] || "";
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

function findAudioForBlock(
  audios: GeneratedAudio[],
  blockIndex: number,
  generatedContentId?: string | null,
  title?: string,
): GeneratedAudio | null {
  const matchingAudios = audios.filter((audio) => {
    const matchesBlock = audio.block_index === blockIndex;
    if (generatedContentId === undefined) return matchesBlock;
    if (generatedContentId === null) {
      return matchesBlock && audio.generated_content_id === null && (!title || audio.title === title);
    }
    return matchesBlock && audio.generated_content_id === generatedContentId;
  });
  if (!matchingAudios.length) return null;
  return matchingAudios.sort((first, second) => {
    const firstTime = new Date(first.created_at).getTime();
    const secondTime = new Date(second.created_at).getTime();
    return secondTime - firstTime;
  })[0] ?? null;
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
