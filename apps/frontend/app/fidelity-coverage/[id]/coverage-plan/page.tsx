"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { LessonScriptPanel } from "@/components/coverage-plan/LessonScriptPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  ApiError,
  apiFetch,
  addCoveragePlanLessonSourceItem,
  approveCoveragePlan,
  generateAllCoverageLessons,
  getCourseLessonGenerationJob,
  getCoveragePlan,
  getCoveragePlanSummary,
  getCoveragePlanVersion,
  listCoveragePlanVersions,
  listUnmappedCoverageItems,
  mergeCoveragePlanLessons,
  recalculateCoveragePlan,
  recalculateCoveragePlanLesson,
  regenerateCoveragePlan,
  removeCoveragePlanLessonSourceItem,
  splitCoveragePlanLesson,
  startCoveragePlanGeneration,
  updateCoveragePlanLesson,
  updateCoveragePlanModule,
  validateCoveragePlan,
} from "@/lib/api";
import type {
  CoveragePlan,
  CoveragePlanLesson,
  CoveragePlanModule,
  CoveragePlanSummary,
  CoveragePlanVersion,
  UnmappedSourceItem,
} from "@/types/coverage-plan";
import type { ProjectFile } from "@/types/file";
import type { ProcessingJob } from "@/types/processing";

const STATUS_LABEL: Record<string, string> = {
  not_started: "Não iniciado",
  pending: "Na fila",
  processing: "Processando",
  generated: "Gerado",
  requires_review: "Requer revisão",
  invalid: "Inválido",
  ready_for_review: "Pronto para revisão",
  approved: "Aprovado",
  stale: "Desatualizado",
  failed: "Falhou",
  planned: "Planejado",
};

function statusTone(status: string): "neutral" | "success" | "warning" {
  if (status === "approved") return "success";
  if (["invalid", "failed", "requires_review", "stale"].includes(status)) return "warning";
  return "neutral";
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.status === 401) {
    return "Sua sessão expirou. Faça login novamente.";
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}

function toMinutes(value: string | number): number {
  const parsed = typeof value === "number" ? value : parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export default function CoveragePlanPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [sourceFile, setSourceFile] = useState<ProjectFile | null>(null);
  const [summary, setSummary] = useState<CoveragePlanSummary | null>(null);
  const [plan, setPlan] = useState<CoveragePlan | null>(null);
  const [unmappedItems, setUnmappedItems] = useState<UnmappedSourceItem[]>([]);
  const [activeJob, setActiveJob] = useState<ProcessingJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [starting, setStarting] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [showUnmapped, setShowUnmapped] = useState(false);
  const [lessonGenerationJob, setLessonGenerationJob] = useState<ProcessingJob | null>(null);

  // Edicao de modulo
  const [editingModuleId, setEditingModuleId] = useState<string | null>(null);
  const [moduleForm, setModuleForm] = useState({ title: "", description: "", learning_objective: "" });
  const [moduleSaving, setModuleSaving] = useState(false);
  const [moduleError, setModuleError] = useState("");

  // Edicao de aula
  const [editingLessonId, setEditingLessonId] = useState<string | null>(null);
  const [lessonForm, setLessonForm] = useState({ title: "", description: "", learning_objective: "" });
  const [lessonSaving, setLessonSaving] = useState(false);
  const [lessonError, setLessonError] = useState("");

  // Divisao de aula
  const [splittingLessonId, setSplittingLessonId] = useState<string | null>(null);
  const [splitAssignment, setSplitAssignment] = useState<Record<string, "first" | "second">>({});
  const [splitTitles, setSplitTitles] = useState({ first: "", second: "" });
  const [splitSaving, setSplitSaving] = useState(false);
  const [splitError, setSplitError] = useState("");

  // Uniao de aulas
  const [mergingLessonId, setMergingLessonId] = useState<string | null>(null);
  const [mergeTargetId, setMergeTargetId] = useState("");
  const [mergeTitle, setMergeTitle] = useState("");
  const [mergeSaving, setMergeSaving] = useState(false);
  const [mergeError, setMergeError] = useState("");

  // Mover/associar/remover item
  const [itemActionBusy, setItemActionBusy] = useState("");
  const [itemActionError, setItemActionError] = useState("");
  const [moveTargetByItem, setMoveTargetByItem] = useState<Record<string, string>>({});
  const [addItemLessonId, setAddItemLessonId] = useState<string | null>(null);
  const [addItemSourceId, setAddItemSourceId] = useState("");

  // Versoes do plano
  const [showVersions, setShowVersions] = useState(false);
  const [versions, setVersions] = useState<CoveragePlanVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState("");
  const [viewingVersionNumber, setViewingVersionNumber] = useState<number | null>(null);
  const [viewingVersionPlan, setViewingVersionPlan] = useState<CoveragePlan | null>(null);
  const [viewingVersionLoading, setViewingVersionLoading] = useState(false);

  useEffect(() => {
    apiFetch<ProjectFile[]>(`/projects/${projectId}/files`)
      .then((files) => {
        const pdf = files.find((file) => file.file_type === "source_pdf") || null;
        setSourceFile(pdf);
      })
      .catch(() => setError("Não foi possível carregar o documento."))
      .finally(() => setLoading(false));
  }, [projectId]);

  const refreshSummary = useCallback(() => {
    if (!sourceFile) return;
    getCoveragePlanSummary(projectId, sourceFile.id)
      .then(setSummary)
      .catch(() => setError("Não foi possível carregar o resumo do plano de cobertura."));
  }, [projectId, sourceFile]);

  const refreshPlan = useCallback(() => {
    if (!sourceFile) return;
    getCoveragePlan(projectId, sourceFile.id)
      .then(setPlan)
      .catch(() => setPlan(null));
  }, [projectId, sourceFile]);

  const refreshUnmapped = useCallback(() => {
    if (!sourceFile) return;
    listUnmappedCoverageItems(projectId, sourceFile.id)
      .then(setUnmappedItems)
      .catch(() => setUnmappedItems([]));
  }, [projectId, sourceFile]);

  const refreshVersions = useCallback(() => {
    if (!sourceFile) return;
    setVersionsLoading(true);
    setVersionsError("");
    listCoveragePlanVersions(projectId, sourceFile.id)
      .then(setVersions)
      .catch((err) => setVersionsError(errorMessage(err, "Não foi possível carregar as versões do plano.")))
      .finally(() => setVersionsLoading(false));
  }, [projectId, sourceFile]);

  useEffect(() => {
    refreshSummary();
    refreshPlan();
    refreshUnmapped();
  }, [refreshSummary, refreshPlan, refreshUnmapped]);

  const pollJob = useCallback(
    (jobId: string) => {
      if (!sourceFile) return;
      apiFetch<ProcessingJob>(`/projects/${projectId}/jobs/${jobId}`)
        .then((job) => {
          setActiveJob(job);
          if (job.status === "pending" || job.status === "processing") {
            window.setTimeout(() => pollJob(jobId), 2000);
            return;
          }
          refreshSummary();
          refreshPlan();
          refreshUnmapped();
        })
        .catch(() => setError("Não foi possível acompanhar o progresso do plano de cobertura."));
    },
    [projectId, sourceFile, refreshSummary, refreshPlan, refreshUnmapped],
  );

  function flashSuccess(message: string) {
    setSuccessMessage(message);
    window.setTimeout(() => setSuccessMessage(""), 4000);
  }

  async function handleGenerate(force: boolean) {
    if (!sourceFile) return;
    setStarting(true);
    setError("");
    try {
      const job = force
        ? await regenerateCoveragePlan(projectId, sourceFile.id, "regenerate_draft")
        : await startCoveragePlanGeneration(projectId, sourceFile.id, force);
      setActiveJob(job);
      pollJob(job.id);
    } catch (err) {
      setError(errorMessage(err, "Não foi possível iniciar a geração do plano de cobertura."));
    } finally {
      setStarting(false);
    }
  }

  async function handleValidate() {
    if (!sourceFile) return;
    setBusyAction("validate");
    setError("");
    try {
      await validateCoveragePlan(projectId, sourceFile.id);
      refreshSummary();
      refreshPlan();
    } catch (err) {
      setError(errorMessage(err, "Não foi possível validar o plano de cobertura."));
    } finally {
      setBusyAction("");
    }
  }

  async function handleRecalculate() {
    if (!sourceFile) return;
    setBusyAction("recalculate");
    setError("");
    try {
      await recalculateCoveragePlan(projectId, sourceFile.id);
      refreshSummary();
      refreshPlan();
    } catch (err) {
      setError(errorMessage(err, "Não foi possível recalcular as estimativas."));
    } finally {
      setBusyAction("");
    }
  }

  async function handleApprove() {
    if (!sourceFile) return;
    setBusyAction("approve");
    setError("");
    try {
      await approveCoveragePlan(projectId, sourceFile.id);
      refreshSummary();
      refreshPlan();
    } catch (err) {
      setError(errorMessage(err, "Não foi possível aprovar o plano de cobertura."));
    } finally {
      setBusyAction("");
    }
  }

  const pollLessonGenerationJob = useCallback(
    (jobId: string) => {
      getCourseLessonGenerationJob(projectId)
        .then((current) => {
          if (!current || current.id !== jobId) return;
          setLessonGenerationJob(current);
          if (current.status === "pending" || current.status === "processing") {
            window.setTimeout(() => pollLessonGenerationJob(jobId), 3000);
            return;
          }
          setLessonGenerationJob(null);
          refreshPlan();
        })
        .catch(() => setError("Não foi possível acompanhar a geração das aulas."));
    },
    [projectId, refreshPlan],
  );

  async function handleGenerateAllLessons() {
    setBusyAction("generate-all-lessons");
    setError("");
    try {
      const job = await generateAllCoverageLessons(projectId);
      setLessonGenerationJob(job);
      pollLessonGenerationJob(job.id);
    } catch (err) {
      setError(errorMessage(err, "Não foi possível iniciar a geração das aulas."));
    } finally {
      setBusyAction("");
    }
  }

  async function handleRecalculateLesson(lessonId: string) {
    setBusyAction(`lesson-${lessonId}`);
    try {
      await recalculateCoveragePlanLesson(lessonId);
      refreshPlan();
      refreshSummary();
    } catch (err) {
      setError(errorMessage(err, "Não foi possível recalcular a aula."));
    } finally {
      setBusyAction("");
    }
  }

  // --- Edicao de modulo ---------------------------------------------------

  function startEditModule(module: CoveragePlanModule) {
    setEditingModuleId(module.id);
    setModuleForm({
      title: module.title,
      description: module.description || "",
      learning_objective: module.learning_objective || "",
    });
    setModuleError("");
  }

  function cancelEditModule() {
    setEditingModuleId(null);
    setModuleError("");
  }

  async function saveModule(moduleId: string) {
    if (!moduleForm.title.trim()) {
      setModuleError("O título do módulo não pode ficar vazio.");
      return;
    }
    setModuleSaving(true);
    setModuleError("");
    try {
      await updateCoveragePlanModule(moduleId, {
        title: moduleForm.title.trim(),
        description: moduleForm.description,
        learning_objective: moduleForm.learning_objective,
      });
      setEditingModuleId(null);
      refreshPlan();
      flashSuccess("Módulo atualizado.");
    } catch (err) {
      setModuleError(errorMessage(err, "Não foi possível salvar o módulo."));
    } finally {
      setModuleSaving(false);
    }
  }

  // --- Edicao de aula -------------------------------------------------------

  function startEditLesson(lesson: CoveragePlanLesson) {
    setEditingLessonId(lesson.id);
    setLessonForm({
      title: lesson.title,
      description: lesson.description || "",
      learning_objective: lesson.learning_objective || "",
    });
    setLessonError("");
  }

  function cancelEditLesson() {
    setEditingLessonId(null);
    setLessonError("");
  }

  async function saveLesson(lessonId: string) {
    if (!lessonForm.title.trim()) {
      setLessonError("O título da aula não pode ficar vazio.");
      return;
    }
    setLessonSaving(true);
    setLessonError("");
    try {
      await updateCoveragePlanLesson(lessonId, {
        title: lessonForm.title.trim(),
        description: lessonForm.description,
        learning_objective: lessonForm.learning_objective,
      });
      setEditingLessonId(null);
      refreshPlan();
      flashSuccess("Aula atualizada.");
    } catch (err) {
      setLessonError(errorMessage(err, "Não foi possível salvar a aula."));
    } finally {
      setLessonSaving(false);
    }
  }

  async function moveLessonToModule(lessonId: string, moduleId: string) {
    setModuleError("");
    try {
      await updateCoveragePlanLesson(lessonId, { module_id: moduleId });
      refreshPlan();
      flashSuccess("Aula movida de módulo.");
    } catch (err) {
      setError(errorMessage(err, "Não foi possível mover a aula para o módulo selecionado."));
    }
  }

  // --- Divisao de aula -----------------------------------------------------

  function startSplit(lesson: CoveragePlanLesson) {
    setSplittingLessonId(lesson.id);
    const half = Math.ceil(lesson.source_items.length / 2);
    const assignment: Record<string, "first" | "second"> = {};
    lesson.source_items.forEach((item, index) => {
      assignment[item.source_item_id] = index < half ? "first" : "second";
    });
    setSplitAssignment(assignment);
    setSplitTitles({ first: `${lesson.title} — Parte 1`, second: `${lesson.title} — Parte 2` });
    setSplitError("");
  }

  function cancelSplit() {
    setSplittingLessonId(null);
    setSplitError("");
  }

  async function confirmSplit(lesson: CoveragePlanLesson) {
    const firstIds = lesson.source_items
      .filter((item) => splitAssignment[item.source_item_id] !== "second")
      .map((item) => item.source_item_id);
    const secondIds = lesson.source_items
      .filter((item) => splitAssignment[item.source_item_id] === "second")
      .map((item) => item.source_item_id);

    if (firstIds.length === 0 || secondIds.length === 0) {
      setSplitError("Cada metade precisa ter pelo menos um item — nenhuma das aulas pode ficar vazia.");
      return;
    }
    if (!splitTitles.first.trim() || !splitTitles.second.trim()) {
      setSplitError("Informe um título para as duas aulas.");
      return;
    }

    setSplitSaving(true);
    setSplitError("");
    try {
      await splitCoveragePlanLesson(lesson.id, {
        first_title: splitTitles.first.trim(),
        second_title: splitTitles.second.trim(),
        first_source_item_ids: firstIds,
        second_source_item_ids: secondIds,
      });
      setSplittingLessonId(null);
      refreshPlan();
      refreshSummary();
      flashSuccess("Aula dividida em duas.");
    } catch (err) {
      setSplitError(errorMessage(err, "Não foi possível dividir a aula."));
    } finally {
      setSplitSaving(false);
    }
  }

  // --- Uniao de aulas -------------------------------------------------------

  function startMerge(lesson: CoveragePlanLesson) {
    setMergingLessonId(lesson.id);
    setMergeTargetId("");
    setMergeTitle(lesson.title);
    setMergeError("");
  }

  function cancelMerge() {
    setMergingLessonId(null);
    setMergeError("");
  }

  async function confirmMerge(lesson: CoveragePlanLesson) {
    if (!mergeTargetId) {
      setMergeError("Selecione outra aula do mesmo módulo para unir.");
      return;
    }
    if (!mergeTitle.trim()) {
      setMergeError("Informe um título para a aula unificada.");
      return;
    }
    setMergeSaving(true);
    setMergeError("");
    try {
      await mergeCoveragePlanLessons({
        lesson_ids: [lesson.id, mergeTargetId],
        title: mergeTitle.trim(),
      });
      setMergingLessonId(null);
      refreshPlan();
      refreshSummary();
      flashSuccess("Aulas unidas com sucesso.");
    } catch (err) {
      setMergeError(errorMessage(err, "Não foi possível unir as aulas (verifique o limite de 10 minutos)."));
    } finally {
      setMergeSaving(false);
    }
  }

  // --- Mover / associar / remover item --------------------------------------

  async function handleMoveItem(fromLessonId: string, sourceItemId: string, toLessonId: string, isRequired: boolean, coverageType: string) {
    if (!toLessonId || toLessonId === fromLessonId) return;
    const key = `move-${sourceItemId}`;
    setItemActionBusy(key);
    setItemActionError("");
    try {
      await addCoveragePlanLessonSourceItem(toLessonId, {
        source_item_id: sourceItemId,
        is_required: isRequired,
        coverage_type: coverageType,
      });
      await removeCoveragePlanLessonSourceItem(fromLessonId, sourceItemId);
      refreshPlan();
      refreshSummary();
      refreshUnmapped();
      flashSuccess("Item movido para outra aula.");
    } catch (err) {
      setItemActionError(errorMessage(err, "Não foi possível mover este item (aula não pode ficar sem fonte)."));
    } finally {
      setItemActionBusy("");
    }
  }

  async function handleRemoveItem(lessonId: string, sourceItemId: string) {
    const key = `remove-${sourceItemId}`;
    setItemActionBusy(key);
    setItemActionError("");
    try {
      await removeCoveragePlanLessonSourceItem(lessonId, sourceItemId);
      refreshPlan();
      refreshSummary();
      refreshUnmapped();
      flashSuccess("Item removido da aula.");
    } catch (err) {
      setItemActionError(errorMessage(err, "Não foi possível remover este item (aula ou item obrigatório ficaria órfão)."));
    } finally {
      setItemActionBusy("");
    }
  }

  async function handleAddUnmappedItem(lessonId: string) {
    if (!addItemSourceId) return;
    setItemActionBusy(`add-${lessonId}`);
    setItemActionError("");
    try {
      await addCoveragePlanLessonSourceItem(lessonId, { source_item_id: addItemSourceId });
      setAddItemLessonId(null);
      setAddItemSourceId("");
      refreshPlan();
      refreshSummary();
      refreshUnmapped();
      flashSuccess("Item associado à aula.");
    } catch (err) {
      setItemActionError(errorMessage(err, "Não foi possível associar este item à aula."));
    } finally {
      setItemActionBusy("");
    }
  }

  // --- Versoes ---------------------------------------------------------------

  function toggleVersions() {
    const next = !showVersions;
    setShowVersions(next);
    if (next && versions.length === 0) {
      refreshVersions();
    }
  }

  async function viewVersion(version: number) {
    if (!sourceFile) return;
    setViewingVersionLoading(true);
    setViewingVersionNumber(version);
    try {
      const data = await getCoveragePlanVersion(projectId, sourceFile.id, version);
      setViewingVersionPlan(data);
    } catch (err) {
      setVersionsError(errorMessage(err, "Não foi possível carregar esta versão."));
      setViewingVersionNumber(null);
    } finally {
      setViewingVersionLoading(false);
    }
  }

  function closeVersionView() {
    setViewingVersionNumber(null);
    setViewingVersionPlan(null);
  }

  const status = summary?.status || "not_started";
  const isRunning = status === "pending" || status === "processing";
  const canApprove = summary
    ? summary.unmapped_items === 0 &&
      summary.lessons_over_limit === 0 &&
      summary.lessons_without_sources === 0 &&
      summary.modules_without_lessons === 0 &&
      summary.pages_requires_ocr === 0 &&
      status !== "approved"
    : false;

  const allLessons: CoveragePlanLesson[] = plan ? plan.modules.flatMap((module) => module.lessons) : [];

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <Link href={`/fidelity-coverage/${projectId}`} className="text-sm text-accent-400 hover:text-accent-500">
          Voltar para o projeto
        </Link>

        <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold text-white">Plano de Cobertura</h1>
            <p className="mt-2 text-sm text-zinc-400">
              Estrutura pedagógica (módulos e aulas) gerada a partir do inventário aprovado, com no máximo 10
              minutos por aula e cobertura obrigatória de todos os itens.
            </p>
          </div>
          <StatusBadge label={STATUS_LABEL[status] || status} tone={statusTone(status)} />
        </div>

        {loading ? (
          <div className="mt-8">
            <LoadingProgress label="Carregando..." />
          </div>
        ) : !sourceFile ? (
          <div className="mt-8">
            <EmptyState
              title="Nenhum documento enviado"
              description="Envie um PDF e conclua o inventário deste projeto antes de gerar o plano de cobertura."
            />
          </div>
        ) : (
          <>
            {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}
            {successMessage ? <p className="mt-4 text-sm text-emerald-300">{successMessage}</p> : null}

            {isRunning && activeJob ? (
              <div className="mt-6 rounded-md border border-accent-500/20 bg-accent-500/10 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-accent-200">
                    {activeJob.current_item || activeJob.current_step || "Processando..."}
                  </p>
                  <span className="text-xs text-accent-300">
                    {activeJob.processed_items ?? 0}/{activeJob.total_items ?? "?"} lotes
                  </span>
                </div>
                <div className="mt-3 h-2 rounded-full bg-white/10">
                  <div
                    className="h-2 rounded-full bg-accent-500 transition-all"
                    style={{ width: `${activeJob.progress || 0}%` }}
                  />
                </div>
              </div>
            ) : null}

            {summary ? (
              <div className="mt-6 rounded-lg border border-white/5 bg-white/[0.035] p-6">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Metric label="Versão" value={summary.version || "—"} />
                  <Metric label="Módulos" value={summary.total_modules} />
                  <Metric label="Aulas" value={summary.total_lessons} />
                  <Metric label="Itens do inventário" value={summary.total_items} />
                  <Metric label="Itens mapeados" value={summary.mapped_items} />
                  <Metric label="Itens sem aula" value={summary.unmapped_items} />
                  <Metric label="Aulas acima de 10 min" value={summary.lessons_over_limit} />
                  <Metric label="Aulas curtas" value={summary.lessons_under_recommended_duration} />
                  <Metric label="Módulos sem aula" value={summary.modules_without_lessons} />
                  <Metric label="Dependências com problema" value={summary.dependency_violations} />
                  <Metric label="Páginas com OCR pendente" value={summary.pages_requires_ocr} />
                  <Metric label="Palavras estimadas" value={summary.estimated_total_words} />
                  <Metric label="Minutos estimados" value={summary.estimated_total_minutes} />
                </div>

                {summary.warnings && summary.warnings.length > 0 ? (
                  <div className="mt-4 rounded-md border border-accent-500/20 bg-accent-500/5 p-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-accent-400">Alertas</p>
                    <ul className="mt-2 space-y-1 text-xs text-zinc-300">
                      {summary.warnings.slice(0, 10).map((warning, index) => (
                        <li key={index}>• {warning}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="mt-6 flex flex-wrap gap-3">
                  {status === "not_started" || status === "failed" ? (
                    <button
                      type="button"
                      onClick={() => handleGenerate(false)}
                      disabled={starting || isRunning}
                      className="rounded-md bg-accent-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {starting ? "Iniciando..." : "Gerar plano"}
                    </button>
                  ) : null}

                  {status !== "not_started" ? (
                    <button
                      type="button"
                      onClick={() => handleGenerate(true)}
                      disabled={starting || isRunning}
                      className="rounded-md border border-white/5 px-4 py-2 text-sm text-zinc-200 transition hover:border-accent-500/40 hover:text-accent-400 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Regenerar rascunho
                    </button>
                  ) : null}

                  <button
                    type="button"
                    onClick={handleValidate}
                    disabled={busyAction === "validate" || status === "not_started"}
                    className="rounded-md border border-white/5 px-4 py-2 text-sm text-zinc-200 transition hover:border-accent-500/40 hover:text-accent-400 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busyAction === "validate" ? "Validando..." : "Validar"}
                  </button>

                  <button
                    type="button"
                    onClick={handleRecalculate}
                    disabled={busyAction === "recalculate" || status === "not_started"}
                    className="rounded-md border border-white/5 px-4 py-2 text-sm text-zinc-200 transition hover:border-accent-500/40 hover:text-accent-400 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busyAction === "recalculate" ? "Recalculando..." : "Recalcular duração"}
                  </button>

                  <button
                    type="button"
                    onClick={handleApprove}
                    disabled={busyAction === "approve" || !canApprove}
                    title={!canApprove ? "Resolva as pendências listadas acima antes de aprovar." : undefined}
                    className="rounded-md border border-emerald-400/30 px-4 py-2 text-sm text-emerald-200 transition hover:border-emerald-400/60 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {busyAction === "approve" ? "Aprovando..." : "Aprovar"}
                  </button>

                  {status === "approved" ? (
                    <button
                      type="button"
                      onClick={handleGenerateAllLessons}
                      disabled={busyAction === "generate-all-lessons" || lessonGenerationJob !== null}
                      className="rounded-md border border-accent-500/30 px-4 py-2 text-sm text-accent-400 transition hover:border-accent-500/60 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {lessonGenerationJob
                        ? `Gerando aulas... (${lessonGenerationJob.progress}%)`
                        : busyAction === "generate-all-lessons"
                          ? "Iniciando..."
                          : "Gerar todas as aulas"}
                    </button>
                  ) : null}

                  <button
                    type="button"
                    onClick={toggleVersions}
                    className="rounded-md border border-white/5 px-4 py-2 text-sm text-zinc-200 transition hover:border-accent-500/40 hover:text-accent-400"
                  >
                    {showVersions ? "Ocultar versões" : "Ver versões"}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      refreshSummary();
                      refreshPlan();
                      refreshUnmapped();
                    }}
                    className="rounded-md border border-white/5 px-4 py-2 text-sm text-zinc-200 transition hover:border-accent-500/40 hover:text-accent-400"
                  >
                    Atualizar status
                  </button>
                </div>
              </div>
            ) : null}

            {showVersions ? (
              <div className="mt-6 rounded-lg border border-white/5 bg-white/[0.035] p-6">
                <p className="font-medium text-white">Versões do plano</p>
                <p className="mt-1 text-sm text-zinc-400">
                  Histórico de gerações. A versão ativa é a mais recente listada abaixo; versões antigas ficam
                  marcadas como desatualizadas (stale) e podem ser abertas apenas em modo leitura.
                </p>

                {versionsError ? <p className="mt-3 text-sm text-red-300">{versionsError}</p> : null}

                {versionsLoading ? (
                  <LoadingProgress label="Carregando versões..." size="inline" />
                ) : versions.length === 0 ? (
                  <p className="mt-4 text-sm text-zinc-400">Nenhuma versão gerada ainda.</p>
                ) : (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[640px] border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wide text-zinc-500">
                          <th className="py-2 pr-4">Versão</th>
                          <th className="py-2 pr-4">Status</th>
                          <th className="py-2 pr-4">Criado em</th>
                          <th className="py-2 pr-4">Módulos/Aulas</th>
                          <th className="py-2 pr-4">Aprovado em</th>
                          <th className="py-2 pr-4" />
                        </tr>
                      </thead>
                      <tbody>
                        {versions.map((version) => (
                          <tr key={version.id} className="border-b border-white/5">
                            <td className="py-2 pr-4 text-zinc-200">
                              {version.version}
                              {plan && version.version === plan.version ? (
                                <span className="ml-2 text-xs text-accent-400">(ativa)</span>
                              ) : null}
                            </td>
                            <td className="py-2 pr-4">
                              <StatusBadge label={STATUS_LABEL[version.status] || version.status} tone={statusTone(version.status)} />
                            </td>
                            <td className="py-2 pr-4 text-zinc-400">{new Date(version.created_at).toLocaleString("pt-BR")}</td>
                            <td className="py-2 pr-4 text-zinc-400">
                              {version.total_modules} / {version.total_lessons}
                            </td>
                            <td className="py-2 pr-4 text-zinc-400">
                              {version.approved_at ? new Date(version.approved_at).toLocaleString("pt-BR") : "—"}
                            </td>
                            <td className="py-2 pr-4">
                              <button
                                type="button"
                                onClick={() => viewVersion(version.version)}
                                disabled={viewingVersionLoading && viewingVersionNumber === version.version}
                                className="text-xs text-accent-400 hover:text-accent-500 disabled:opacity-60"
                              >
                                Visualizar
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {viewingVersionNumber !== null ? (
                  <div className="mt-6 rounded-md border border-accent-500/20 bg-navy-950/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium text-accent-300">
                        Visualizando versão {viewingVersionNumber} — somente leitura
                      </p>
                      <button type="button" onClick={closeVersionView} className="text-xs text-zinc-400 hover:text-zinc-200">
                        Fechar visualização
                      </button>
                    </div>
                    {viewingVersionLoading ? (
                      <LoadingProgress label="Carregando versão..." size="inline" />
                    ) : viewingVersionPlan ? (
                      <div className="mt-4 space-y-3">
                        <div className="grid grid-cols-2 gap-2 text-xs text-zinc-400 sm:grid-cols-4">
                          <span>Modelo: {viewingVersionPlan.model_name || "—"}</span>
                          <span>Prompt: {viewingVersionPlan.prompt_version || "—"}</span>
                          <span>Módulos: {viewingVersionPlan.total_modules}</span>
                          <span>Aulas: {viewingVersionPlan.total_lessons}</span>
                        </div>
                        {viewingVersionPlan.modules.map((module) => (
                          <div key={module.id} className="rounded-md border border-white/5 bg-white/[0.02] p-3">
                            <p className="text-sm font-medium text-white">
                              Módulo {module.module_order} — {module.title}
                            </p>
                            <ul className="mt-2 space-y-1 pl-3 text-xs text-zinc-400">
                              {module.lessons.map((lesson) => (
                                <li key={lesson.id}>
                                  Aula {lesson.lesson_order} — {lesson.title} ({lesson.source_item_count} item(ns),{" "}
                                  {lesson.estimated_duration_minutes} min)
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="mt-6 rounded-lg border border-white/5 bg-white/[0.035] p-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium text-white">Itens sem aula</p>
                <button
                  type="button"
                  onClick={() => setShowUnmapped((value) => !value)}
                  className="text-xs text-accent-400 hover:text-accent-500"
                >
                  {showUnmapped ? "Ocultar" : `Mostrar (${unmappedItems.length})`}
                </button>
              </div>
              {unmappedItems.length === 0 ? (
                <p className="mt-2 text-sm text-zinc-400">
                  Nenhum item pendente — todo item elegível do inventário está associado a pelo menos uma aula.
                </p>
              ) : showUnmapped ? (
                <div className="mt-4 space-y-2">
                  {unmappedItems.map((item) => (
                    <div key={item.source_item_id} className="rounded-md border border-accent-500/20 bg-accent-500/5 p-3 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium text-white">
                          {item.item_code} — {item.title}
                        </span>
                        <span className="text-xs text-zinc-400">
                          {item.content_type} · {item.importance} · pág. {item.page_start ?? "?"}-{item.page_end ?? "?"}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-zinc-400">{item.reason}</p>
                      <p className="mt-1 text-xs text-accent-400">{item.recommended_action}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-accent-300">
                  {unmappedItems.length} item(ns) aguardando associação manual ou nova geração do plano.
                </p>
              )}
            </div>

            <div className="mt-6 rounded-lg border border-white/5 bg-white/[0.035] p-6">
              <p className="font-medium text-white">Mapa de Aulas</p>
              <p className="mt-1 text-sm text-zinc-400">
                Estrutura do curso: módulo, aula e itens do inventário cobertos em cada uma. Use as ações abaixo
                para renomear, dividir, unir aulas ou mover itens entre elas.
              </p>

              {itemActionError ? <p className="mt-3 text-sm text-red-300">{itemActionError}</p> : null}

              {!plan ? (
                <p className="mt-4 text-sm text-zinc-400">Gere o plano de cobertura para visualizar a estrutura.</p>
              ) : (
                <div className="mt-4 space-y-4">
                  {plan.modules.map((module) => (
                    <details key={module.id} className="rounded-md border border-white/5 bg-navy-950/40 p-4" open>
                      <summary className="cursor-pointer list-none">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-medium text-white">
                            Módulo {module.module_order} — {module.title}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-zinc-400">
                              {module.lessons.length} aula(s) · {module.estimated_total_minutes} min
                            </span>
                            <StatusBadge label={STATUS_LABEL[module.status] || module.status} tone={statusTone(module.status)} />
                            <button
                              type="button"
                              onClick={(event) => {
                                event.preventDefault();
                                startEditModule(module);
                              }}
                              className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400"
                            >
                              Editar
                            </button>
                          </div>
                        </div>
                        {module.learning_objective ? (
                          <p className="mt-1 text-xs text-zinc-400">{module.learning_objective}</p>
                        ) : null}
                      </summary>

                      {editingModuleId === module.id ? (
                        <div className="mt-4 rounded-md border border-accent-500/20 bg-accent-500/5 p-3">
                          <label htmlFor={`module-title-${module.id}`} className="block text-xs text-zinc-300">
                            Título do módulo
                          </label>
                          <input
                            id={`module-title-${module.id}`}
                            type="text"
                            value={moduleForm.title}
                            onChange={(event) => setModuleForm((form) => ({ ...form, title: event.target.value }))}
                            className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                          />
                          <label htmlFor={`module-desc-${module.id}`} className="mt-3 block text-xs text-zinc-300">
                            Descrição
                          </label>
                          <textarea
                            id={`module-desc-${module.id}`}
                            value={moduleForm.description}
                            onChange={(event) => setModuleForm((form) => ({ ...form, description: event.target.value }))}
                            rows={2}
                            className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                          />
                          <label htmlFor={`module-obj-${module.id}`} className="mt-3 block text-xs text-zinc-300">
                            Objetivo de aprendizagem
                          </label>
                          <textarea
                            id={`module-obj-${module.id}`}
                            value={moduleForm.learning_objective}
                            onChange={(event) => setModuleForm((form) => ({ ...form, learning_objective: event.target.value }))}
                            rows={2}
                            className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                          />
                          {moduleError ? <p className="mt-2 text-xs text-red-300">{moduleError}</p> : null}
                          <div className="mt-3 flex gap-2">
                            <button
                              type="button"
                              onClick={() => saveModule(module.id)}
                              disabled={moduleSaving}
                              className="rounded-md bg-accent-500 px-3 py-1.5 text-xs font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:opacity-60"
                            >
                              {moduleSaving ? "Salvando..." : "Salvar módulo"}
                            </button>
                            <button
                              type="button"
                              onClick={cancelEditModule}
                              className="rounded-md border border-white/5 px-3 py-1.5 text-xs text-zinc-300 hover:border-white/30"
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      ) : null}

                      <div className="mt-4 space-y-3 pl-4">
                        {module.lessons.map((lesson) => {
                          const overLimit = toMinutes(lesson.estimated_duration_minutes) > 10;
                          const sameModuleLessons = module.lessons.filter((candidate) => candidate.id !== lesson.id);
                          const otherModules = plan.modules.filter((candidate) => candidate.id !== module.id);

                          return (
                            <div key={lesson.id} className="rounded-md border border-white/5 bg-white/[0.02] p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-sm font-medium text-white">
                                  Aula {lesson.lesson_order} — {lesson.title}
                                </span>
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="text-xs text-zinc-400">
                                    {lesson.estimated_duration_minutes} min · {lesson.estimated_word_count} palavras ·{" "}
                                    {lesson.source_item_count} item(ns)
                                  </span>
                                  <StatusBadge
                                    label={STATUS_LABEL[lesson.status] || lesson.status}
                                    tone={statusTone(lesson.status)}
                                  />
                                </div>
                              </div>

                              {overLimit ? (
                                <p className="mt-2 rounded border border-red-400/30 bg-red-400/10 px-2 py-1 text-xs text-red-300">
                                  ⚠ Acima do limite de 10 minutos.
                                </p>
                              ) : null}

                              {lesson.learning_objective ? (
                                <p className="mt-1 text-xs text-zinc-400">{lesson.learning_objective}</p>
                              ) : null}
                              {lesson.warnings_json && lesson.warnings_json.length > 0 ? (
                                <ul className="mt-2 space-y-0.5 text-xs text-accent-400">
                                  {lesson.warnings_json.map((warning, index) => (
                                    <li key={index}>⚠ {warning}</li>
                                  ))}
                                </ul>
                              ) : null}

                              <ul className="mt-3 space-y-1">
                                {lesson.source_items.map((item) => (
                                  <li
                                    key={item.source_item_id}
                                    className="flex flex-wrap items-center justify-between gap-2 rounded border border-white/5 bg-navy-950/40 px-2 py-1 text-xs"
                                  >
                                    <span className="text-zinc-200">
                                      {item.item_code} — {item.title}
                                    </span>
                                    <span className="text-zinc-500">
                                      {item.content_type} · {item.coverage_type} ·{" "}
                                      {item.is_required ? "obrigatório" : "complementar"}
                                    </span>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Link
                                        href={`/fidelity-coverage/${projectId}/inventory/${item.source_item_id}`}
                                        className="text-accent-400 hover:text-accent-500"
                                      >
                                        ver origem
                                      </Link>
                                      <label className="sr-only" htmlFor={`move-target-${item.source_item_id}`}>
                                        Mover item para outra aula
                                      </label>
                                      <select
                                        id={`move-target-${item.source_item_id}`}
                                        value={moveTargetByItem[item.source_item_id] || ""}
                                        onChange={(event) =>
                                          setMoveTargetByItem((current) => ({
                                            ...current,
                                            [item.source_item_id]: event.target.value,
                                          }))
                                        }
                                        className="rounded border border-white/5 bg-navy-950/60 px-1 py-0.5 text-xs text-zinc-300"
                                      >
                                        <option value="">Mover para...</option>
                                        {allLessons
                                          .filter((candidate) => candidate.id !== lesson.id)
                                          .map((candidate) => (
                                            <option key={candidate.id} value={candidate.id}>
                                              {candidate.title}
                                            </option>
                                          ))}
                                      </select>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          handleMoveItem(
                                            lesson.id,
                                            item.source_item_id,
                                            moveTargetByItem[item.source_item_id] || "",
                                            item.is_required,
                                            item.coverage_type,
                                          )
                                        }
                                        disabled={
                                          !moveTargetByItem[item.source_item_id] ||
                                          itemActionBusy === `move-${item.source_item_id}`
                                        }
                                        className="rounded border border-white/5 px-2 py-0.5 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400 disabled:opacity-40"
                                      >
                                        Mover
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => {
                                          if (window.confirm(`Remover "${item.title}" desta aula?`)) {
                                            handleRemoveItem(lesson.id, item.source_item_id);
                                          }
                                        }}
                                        disabled={itemActionBusy === `remove-${item.source_item_id}`}
                                        className="rounded border border-red-400/30 px-2 py-0.5 text-xs text-red-300 hover:border-red-300/60 disabled:opacity-40"
                                      >
                                        Remover
                                      </button>
                                    </div>
                                  </li>
                                ))}
                              </ul>

                              {addItemLessonId === lesson.id ? (
                                <div className="mt-3 flex flex-wrap items-center gap-2 rounded border border-accent-500/20 bg-accent-500/5 p-2">
                                  <label className="sr-only" htmlFor={`add-item-${lesson.id}`}>
                                    Item não mapeado
                                  </label>
                                  <select
                                    id={`add-item-${lesson.id}`}
                                    value={addItemSourceId}
                                    onChange={(event) => setAddItemSourceId(event.target.value)}
                                    className="rounded border border-white/5 bg-navy-950/60 px-2 py-1 text-xs text-zinc-200"
                                  >
                                    <option value="">Selecione um item sem aula...</option>
                                    {unmappedItems.map((item) => (
                                      <option key={item.source_item_id} value={item.source_item_id}>
                                        {item.item_code} — {item.title}
                                      </option>
                                    ))}
                                  </select>
                                  <button
                                    type="button"
                                    onClick={() => handleAddUnmappedItem(lesson.id)}
                                    disabled={!addItemSourceId || itemActionBusy === `add-${lesson.id}`}
                                    className="rounded bg-accent-500 px-2 py-1 text-xs font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:opacity-50"
                                  >
                                    Associar
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setAddItemLessonId(null);
                                      setAddItemSourceId("");
                                    }}
                                    className="text-xs text-zinc-400 hover:text-zinc-200"
                                  >
                                    Cancelar
                                  </button>
                                </div>
                              ) : null}

                              <div className="mt-3 flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleRecalculateLesson(lesson.id)}
                                  disabled={busyAction === `lesson-${lesson.id}`}
                                  className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400 disabled:opacity-60"
                                >
                                  {busyAction === `lesson-${lesson.id}` ? "Recalculando..." : "Recalcular aula"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => startEditLesson(lesson)}
                                  className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400"
                                >
                                  Editar
                                </button>
                                <button
                                  type="button"
                                  onClick={() => (splittingLessonId === lesson.id ? cancelSplit() : startSplit(lesson))}
                                  disabled={lesson.source_items.length < 2}
                                  title={lesson.source_items.length < 2 ? "É preciso ao menos 2 itens para dividir." : undefined}
                                  className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400 disabled:opacity-40"
                                >
                                  Dividir aula
                                </button>
                                <button
                                  type="button"
                                  onClick={() => (mergingLessonId === lesson.id ? cancelMerge() : startMerge(lesson))}
                                  disabled={sameModuleLessons.length === 0}
                                  title={sameModuleLessons.length === 0 ? "Não há outra aula no mesmo módulo." : undefined}
                                  className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400 disabled:opacity-40"
                                >
                                  Unir aulas
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setAddItemLessonId(addItemLessonId === lesson.id ? null : lesson.id)}
                                  disabled={unmappedItems.length === 0}
                                  title={unmappedItems.length === 0 ? "Não há itens sem aula no momento." : undefined}
                                  className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400 disabled:opacity-40"
                                >
                                  Adicionar item
                                </button>
                                {otherModules.length > 0 ? (
                                  <>
                                    <label className="sr-only" htmlFor={`lesson-module-${lesson.id}`}>
                                      Mover aula para outro módulo
                                    </label>
                                    <select
                                      id={`lesson-module-${lesson.id}`}
                                      defaultValue=""
                                      onChange={(event) => {
                                        if (event.target.value) {
                                          moveLessonToModule(lesson.id, event.target.value);
                                          event.target.value = "";
                                        }
                                      }}
                                      className="rounded border border-white/5 bg-navy-950/60 px-2 py-1 text-xs text-zinc-300"
                                    >
                                      <option value="">Mover para módulo...</option>
                                      {otherModules.map((candidate) => (
                                        <option key={candidate.id} value={candidate.id}>
                                          {candidate.title}
                                        </option>
                                      ))}
                                    </select>
                                  </>
                                ) : null}
                              </div>

                              <LessonScriptPanel lessonId={lesson.id} planApproved={plan?.status === "approved"} />

                              {editingLessonId === lesson.id ? (
                                <div className="mt-3 rounded-md border border-accent-500/20 bg-accent-500/5 p-3">
                                  <label htmlFor={`lesson-title-${lesson.id}`} className="block text-xs text-zinc-300">
                                    Título da aula
                                  </label>
                                  <input
                                    id={`lesson-title-${lesson.id}`}
                                    type="text"
                                    value={lessonForm.title}
                                    onChange={(event) => setLessonForm((form) => ({ ...form, title: event.target.value }))}
                                    className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                                  />
                                  <label htmlFor={`lesson-desc-${lesson.id}`} className="mt-3 block text-xs text-zinc-300">
                                    Descrição
                                  </label>
                                  <textarea
                                    id={`lesson-desc-${lesson.id}`}
                                    value={lessonForm.description}
                                    onChange={(event) => setLessonForm((form) => ({ ...form, description: event.target.value }))}
                                    rows={2}
                                    className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                                  />
                                  <label htmlFor={`lesson-obj-${lesson.id}`} className="mt-3 block text-xs text-zinc-300">
                                    Objetivo de aprendizagem
                                  </label>
                                  <textarea
                                    id={`lesson-obj-${lesson.id}`}
                                    value={lessonForm.learning_objective}
                                    onChange={(event) =>
                                      setLessonForm((form) => ({ ...form, learning_objective: event.target.value }))
                                    }
                                    rows={2}
                                    className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                                  />
                                  {lessonError ? <p className="mt-2 text-xs text-red-300">{lessonError}</p> : null}
                                  <div className="mt-3 flex gap-2">
                                    <button
                                      type="button"
                                      onClick={() => saveLesson(lesson.id)}
                                      disabled={lessonSaving}
                                      className="rounded-md bg-accent-500 px-3 py-1.5 text-xs font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:opacity-60"
                                    >
                                      {lessonSaving ? "Salvando..." : "Salvar aula"}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={cancelEditLesson}
                                      className="rounded-md border border-white/5 px-3 py-1.5 text-xs text-zinc-300 hover:border-white/30"
                                    >
                                      Cancelar
                                    </button>
                                  </div>
                                </div>
                              ) : null}

                              {splittingLessonId === lesson.id ? (
                                <div className="mt-3 rounded-md border border-accent-500/20 bg-accent-500/5 p-3">
                                  <p className="text-xs font-medium text-accent-300">
                                    Dividir aula — selecione em qual metade cada item fica
                                  </p>
                                  <div className="mt-2 space-y-1">
                                    {lesson.source_items.map((item) => (
                                      <div
                                        key={item.source_item_id}
                                        className="flex flex-wrap items-center justify-between gap-2 rounded border border-white/5 bg-navy-950/40 px-2 py-1 text-xs"
                                      >
                                        <span className="text-zinc-200">
                                          {item.item_code} — {item.title}
                                        </span>
                                        <div className="flex gap-3">
                                          <label className="flex items-center gap-1 text-zinc-300">
                                            <input
                                              type="radio"
                                              name={`split-${lesson.id}-${item.source_item_id}`}
                                              checked={splitAssignment[item.source_item_id] !== "second"}
                                              onChange={() =>
                                                setSplitAssignment((current) => ({
                                                  ...current,
                                                  [item.source_item_id]: "first",
                                                }))
                                              }
                                            />
                                            Primeira
                                          </label>
                                          <label className="flex items-center gap-1 text-zinc-300">
                                            <input
                                              type="radio"
                                              name={`split-${lesson.id}-${item.source_item_id}`}
                                              checked={splitAssignment[item.source_item_id] === "second"}
                                              onChange={() =>
                                                setSplitAssignment((current) => ({
                                                  ...current,
                                                  [item.source_item_id]: "second",
                                                }))
                                              }
                                            />
                                            Segunda
                                          </label>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                  <label htmlFor={`split-first-title-${lesson.id}`} className="mt-3 block text-xs text-zinc-300">
                                    Título da primeira aula
                                  </label>
                                  <input
                                    id={`split-first-title-${lesson.id}`}
                                    type="text"
                                    value={splitTitles.first}
                                    onChange={(event) => setSplitTitles((titles) => ({ ...titles, first: event.target.value }))}
                                    className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                                  />
                                  <label htmlFor={`split-second-title-${lesson.id}`} className="mt-3 block text-xs text-zinc-300">
                                    Título da segunda aula
                                  </label>
                                  <input
                                    id={`split-second-title-${lesson.id}`}
                                    type="text"
                                    value={splitTitles.second}
                                    onChange={(event) => setSplitTitles((titles) => ({ ...titles, second: event.target.value }))}
                                    className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                                  />
                                  {splitError ? <p className="mt-2 text-xs text-red-300">{splitError}</p> : null}
                                  <div className="mt-3 flex gap-2">
                                    <button
                                      type="button"
                                      onClick={() => confirmSplit(lesson)}
                                      disabled={splitSaving}
                                      className="rounded-md bg-accent-500 px-3 py-1.5 text-xs font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:opacity-60"
                                    >
                                      {splitSaving ? "Dividindo..." : "Confirmar divisão"}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={cancelSplit}
                                      className="rounded-md border border-white/5 px-3 py-1.5 text-xs text-zinc-300 hover:border-white/30"
                                    >
                                      Cancelar
                                    </button>
                                  </div>
                                </div>
                              ) : null}

                              {mergingLessonId === lesson.id ? (
                                <div className="mt-3 rounded-md border border-accent-500/20 bg-accent-500/5 p-3">
                                  <p className="text-xs font-medium text-accent-300">Unir com outra aula do mesmo módulo</p>
                                  <label htmlFor={`merge-target-${lesson.id}`} className="mt-2 block text-xs text-zinc-300">
                                    Aula destino
                                  </label>
                                  <select
                                    id={`merge-target-${lesson.id}`}
                                    value={mergeTargetId}
                                    onChange={(event) => setMergeTargetId(event.target.value)}
                                    className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100"
                                  >
                                    <option value="">Selecione...</option>
                                    {sameModuleLessons.map((candidate) => (
                                      <option key={candidate.id} value={candidate.id}>
                                        {candidate.title} ({candidate.estimated_duration_minutes} min,{" "}
                                        {candidate.source_item_count} itens)
                                      </option>
                                    ))}
                                  </select>
                                  {mergeTargetId ? (
                                    (() => {
                                      const target = sameModuleLessons.find((candidate) => candidate.id === mergeTargetId);
                                      if (!target) return null;
                                      const combinedMinutes = toMinutes(lesson.estimated_duration_minutes) + toMinutes(target.estimated_duration_minutes);
                                      const combinedItems = lesson.source_item_count + target.source_item_count;
                                      return (
                                        <p
                                          className={`mt-2 text-xs ${combinedMinutes > 10 ? "text-red-300" : "text-zinc-300"}`}
                                        >
                                          Duração combinada estimada: {combinedMinutes.toFixed(2)} min · {combinedItems}{" "}
                                          item(ns) {combinedMinutes > 10 ? "— excede o limite de 10 min" : ""}
                                        </p>
                                      );
                                    })()
                                  ) : null}
                                  <label htmlFor={`merge-title-${lesson.id}`} className="mt-3 block text-xs text-zinc-300">
                                    Título da aula unificada
                                  </label>
                                  <input
                                    id={`merge-title-${lesson.id}`}
                                    type="text"
                                    value={mergeTitle}
                                    onChange={(event) => setMergeTitle(event.target.value)}
                                    className="mt-1 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
                                  />
                                  {mergeError ? <p className="mt-2 text-xs text-red-300">{mergeError}</p> : null}
                                  <div className="mt-3 flex gap-2">
                                    <button
                                      type="button"
                                      onClick={() => confirmMerge(lesson)}
                                      disabled={mergeSaving || !mergeTargetId}
                                      className="rounded-md bg-accent-500 px-3 py-1.5 text-xs font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:opacity-60"
                                    >
                                      {mergeSaving ? "Unindo..." : "Confirmar união"}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={cancelMerge}
                                      className="rounded-md border border-white/5 px-3 py-1.5 text-xs text-zinc-300 hover:border-white/30"
                                    >
                                      Cancelar
                                    </button>
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    </details>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-white/5 bg-navy-950/60 p-4">
      <p className="text-xs text-zinc-400">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}
