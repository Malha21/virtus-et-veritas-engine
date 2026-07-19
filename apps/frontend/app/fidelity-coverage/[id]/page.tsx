"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  ApiError,
  apiFetch,
  getCoveragePlanSummary,
  getDocumentExtractionSummary,
  getSourceInventorySummary,
  reprocessDocumentExtraction,
  reprocessSourceInventory,
  startDocumentExtraction,
  startSourceInventoryGeneration,
} from "@/lib/api";
import type { CoveragePlanSummary } from "@/types/coverage-plan";
import type { DocumentExtractionSummary } from "@/types/document-extraction";
import type { ProjectFile } from "@/types/file";
import type { ProcessingJob } from "@/types/processing";
import type { Project } from "@/types/project";
import type { SourceInventorySummary } from "@/types/source-inventory";

const SUBSECTIONS = [
  {
    title: "Auditoria",
    description: "Verificação de fidelidade: afirmações sem fonte, duplicidades e violações de duração.",
  },
  {
    title: "Pendências e Correções",
    description: "Lista de itens sem cobertura e inconsistências a corrigir antes da aprovação.",
  },
  {
    title: "Aprovação Final",
    description: "Registro da aprovação do curso quanto à fidelidade e cobertura documental.",
  },
];

const EXTRACTION_STATUS_LABEL: Record<string, string> = {
  not_started: "Não iniciado",
  pending: "Na fila",
  processing: "Processando",
  completed: "Concluído",
  partially_completed: "Concluído com alertas",
  failed: "Falhou",
};

function extractionStatusTone(status: string): "neutral" | "success" | "warning" {
  if (status === "completed") return "success";
  if (status === "failed") return "warning";
  if (status === "partially_completed") return "warning";
  return "neutral";
}

const INVENTORY_STATUS_LABEL: Record<string, string> = {
  not_started: "Não iniciado",
  pending: "Na fila",
  processing: "Processando",
  completed: "Concluído",
  partially_completed: "Concluído com alertas",
  failed: "Falhou",
};

const COVERAGE_PLAN_STATUS_LABEL: Record<string, string> = {
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
};

function coveragePlanStatusTone(status: string): "neutral" | "success" | "warning" {
  if (status === "approved") return "success";
  if (["invalid", "failed", "requires_review", "stale"].includes(status)) return "warning";
  return "neutral";
}

export default function FidelityCoverageProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [sourceFile, setSourceFile] = useState<ProjectFile | null>(null);
  const [summary, setSummary] = useState<DocumentExtractionSummary | null>(null);
  const [activeJob, setActiveJob] = useState<ProcessingJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [extractionError, setExtractionError] = useState("");
  const [starting, setStarting] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);

  const [inventorySummary, setInventorySummary] = useState<SourceInventorySummary | null>(null);
  const [inventoryJob, setInventoryJob] = useState<ProcessingJob | null>(null);
  const [inventoryError, setInventoryError] = useState("");
  const [inventoryStarting, setInventoryStarting] = useState(false);
  const [inventoryReprocessing, setInventoryReprocessing] = useState(false);

  const [coveragePlanSummary, setCoveragePlanSummary] = useState<CoveragePlanSummary | null>(null);
  const [coveragePlanError, setCoveragePlanError] = useState("");

  useEffect(() => {
    Promise.all([
      apiFetch<Project>(`/projects/${projectId}`),
      apiFetch<ProjectFile[]>(`/projects/${projectId}/files`),
    ])
      .then(([projectData, files]) => {
        setProject(projectData);
        const pdf = files.find((file) => file.file_type === "source_pdf") || null;
        setSourceFile(pdf);
      })
      .catch(() => setError("Não foi possível carregar este projeto."))
      .finally(() => setLoading(false));
  }, [projectId]);

  const refreshSummary = useCallback(() => {
    if (!sourceFile) return;
    getDocumentExtractionSummary(projectId, sourceFile.id)
      .then(setSummary)
      .catch(() => setExtractionError("Não foi possível carregar o resumo da extração."));
  }, [projectId, sourceFile]);

  useEffect(() => {
    refreshSummary();
  }, [refreshSummary]);

  const refreshInventorySummary = useCallback(() => {
    if (!sourceFile) return;
    getSourceInventorySummary(projectId, sourceFile.id)
      .then(setInventorySummary)
      .catch(() => setInventoryError("Não foi possível carregar o resumo do inventário."));
  }, [projectId, sourceFile]);

  useEffect(() => {
    refreshInventorySummary();
  }, [refreshInventorySummary]);

  const refreshCoveragePlanSummary = useCallback(() => {
    if (!sourceFile) return;
    getCoveragePlanSummary(projectId, sourceFile.id)
      .then(setCoveragePlanSummary)
      .catch(() => setCoveragePlanError("Não foi possível carregar o resumo do plano de cobertura."));
  }, [projectId, sourceFile]);

  useEffect(() => {
    refreshCoveragePlanSummary();
  }, [refreshCoveragePlanSummary]);

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
        })
        .catch(() => {
          setExtractionError("Não foi possível acompanhar o progresso da extração.");
        });
    },
    [projectId, sourceFile, refreshSummary],
  );

  async function handleStartExtraction() {
    if (!sourceFile) return;
    setStarting(true);
    setExtractionError("");
    try {
      const job = await startDocumentExtraction(projectId, sourceFile.id);
      setActiveJob(job);
      pollJob(job.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setExtractionError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setExtractionError(err.message);
      } else {
        setExtractionError("Não foi possível iniciar a extração do documento.");
      }
    } finally {
      setStarting(false);
    }
  }

  async function handleReprocessFailed() {
    if (!sourceFile) return;
    setReprocessing(true);
    setExtractionError("");
    try {
      const job = await reprocessDocumentExtraction(projectId, sourceFile.id, "failed");
      setActiveJob(job);
      pollJob(job.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setExtractionError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setExtractionError(err.message);
      } else {
        setExtractionError("Não foi possível reprocessar as páginas com falha.");
      }
    } finally {
      setReprocessing(false);
    }
  }

  const pollInventoryJob = useCallback(
    (jobId: string) => {
      if (!sourceFile) return;
      apiFetch<ProcessingJob>(`/projects/${projectId}/jobs/${jobId}`)
        .then((job) => {
          setInventoryJob(job);
          if (job.status === "pending" || job.status === "processing") {
            window.setTimeout(() => pollInventoryJob(jobId), 2000);
            return;
          }
          refreshInventorySummary();
        })
        .catch(() => {
          setInventoryError("Não foi possível acompanhar o progresso do inventário.");
        });
    },
    [projectId, sourceFile, refreshInventorySummary],
  );

  async function handleStartInventory() {
    if (!sourceFile) return;
    setInventoryStarting(true);
    setInventoryError("");
    try {
      const job = await startSourceInventoryGeneration(projectId, sourceFile.id);
      setInventoryJob(job);
      pollInventoryJob(job.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setInventoryError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setInventoryError(err.message);
      } else {
        setInventoryError("Não foi possível iniciar a geração do inventário.");
      }
    } finally {
      setInventoryStarting(false);
    }
  }

  async function handleReprocessInventoryFailed() {
    if (!sourceFile) return;
    setInventoryReprocessing(true);
    setInventoryError("");
    try {
      const job = await reprocessSourceInventory(projectId, sourceFile.id, "reprocess_failed");
      setInventoryJob(job);
      pollInventoryJob(job.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setInventoryError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setInventoryError(err.message);
      } else {
        setInventoryError("Não foi possível reprocessar os itens com falha.");
      }
    } finally {
      setInventoryReprocessing(false);
    }
  }

  const extractionStatus = summary?.status || "not_started";
  const isRunning = extractionStatus === "pending" || extractionStatus === "processing";
  const inventoryStatus = inventorySummary?.status || "not_started";
  const isInventoryRunning = inventoryStatus === "pending" || inventoryStatus === "processing";
  const extractionReady = extractionStatus === "completed" || extractionStatus === "partially_completed";

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <Link href="/fidelity-coverage" className="text-sm text-gold-400 hover:text-gold-500">
          Voltar para Fidelidade e Cobertura
        </Link>

        {loading ? (
          <p className="mt-8 text-slate-300">Carregando projeto...</p>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : project ? (
          <>
            <div className="mt-6 flex flex-wrap items-start justify-between gap-4 rounded-lg border border-white/10 bg-white/[0.035] p-6">
              <div>
                <p className="text-sm text-gold-400">{project.product_type}</p>
                <h1 className="mt-2 text-3xl font-semibold">{project.title}</h1>
                <p className="mt-2 text-sm text-slate-400">
                  Análise de fidelidade e cobertura documental deste projeto.
                </p>
              </div>
              <div className="flex gap-2">
                <StatusBadge label={project.status} tone="success" />
                <StatusBadge label={project.processing_status} tone="warning" />
              </div>
            </div>

            <div className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-white">Extração do Documento</p>
                  <p className="mt-1 text-sm text-slate-400">
                    Divisão do PDF em páginas e blocos rastreáveis, preservando o texto original.
                  </p>
                </div>
                <StatusBadge
                  label={EXTRACTION_STATUS_LABEL[extractionStatus] || extractionStatus}
                  tone={extractionStatusTone(extractionStatus)}
                />
              </div>

              {!sourceFile ? (
                <div className="mt-4">
                  <EmptyState
                    title="Nenhum documento enviado"
                    description="Envie um PDF neste projeto para iniciar a extração estruturada."
                    action={
                      <Link
                        href={`/projects/${project.id}/upload`}
                        className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-gold-400"
                      >
                        Enviar PDF
                      </Link>
                    }
                  />
                </div>
              ) : (
                <>
                  <p className="mt-4 text-sm text-slate-300">
                    Documento: <span className="text-white">{sourceFile.original_filename}</span>
                  </p>

                  {extractionError ? <p className="mt-3 text-sm text-red-300">{extractionError}</p> : null}

                  {isRunning && activeJob ? (
                    <div className="mt-4 rounded-md border border-gold-500/20 bg-gold-500/10 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm text-gold-200">
                          {activeJob.current_item || activeJob.current_step || "Processando..."}
                        </p>
                        <span className="text-xs text-gold-300">
                          {activeJob.processed_items ?? 0}/{activeJob.total_items ?? "?"} páginas
                        </span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-white/10">
                        <div
                          className="h-2 rounded-full bg-gold-500 transition-all"
                          style={{ width: `${activeJob.progress || 0}%` }}
                        />
                      </div>
                    </div>
                  ) : null}

                  {summary ? (
                    <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <Metric label="Total de páginas" value={summary.total_pages} />
                      <Metric label="Processadas" value={summary.extracted_pages} />
                      <Metric label="Com falha" value={summary.failed_pages} />
                      <Metric label="Vazias" value={summary.empty_pages} />
                      <Metric label="Requerem OCR" value={summary.requires_ocr_pages} />
                      <Metric label="Total de palavras" value={summary.total_words} />
                      <Metric label="Total de blocos" value={summary.total_blocks} />
                      <Metric
                        label="Última extração"
                        value={
                          summary.last_extracted_at
                            ? new Date(summary.last_extracted_at).toLocaleDateString("pt-BR")
                            : "—"
                        }
                      />
                    </div>
                  ) : null}

                  <div className="mt-6 flex flex-wrap gap-3">
                    {extractionStatus === "not_started" || extractionStatus === "failed" ? (
                      <button
                        type="button"
                        onClick={handleStartExtraction}
                        disabled={starting || isRunning}
                        className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {starting ? "Iniciando..." : "Iniciar extração"}
                      </button>
                    ) : null}

                    {summary && summary.failed_pages > 0 ? (
                      <button
                        type="button"
                        onClick={handleReprocessFailed}
                        disabled={reprocessing || isRunning}
                        className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {reprocessing ? "Reprocessando..." : "Reprocessar falhas"}
                      </button>
                    ) : null}

                    <button
                      type="button"
                      onClick={refreshSummary}
                      className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                    >
                      Atualizar status
                    </button>

                    {summary && summary.total_pages > 0 ? (
                      <Link
                        href={`/fidelity-coverage/${project.id}/pages`}
                        className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                      >
                        Visualizar páginas
                      </Link>
                    ) : null}
                  </div>
                </>
              )}
            </div>

            <div className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-white">Inventário do Documento</p>
                  <p className="mt-1 text-sm text-slate-400">
                    Unidades de conhecimento identificadas no documento, com página, bloco e trecho de origem.
                  </p>
                </div>
                <StatusBadge
                  label={INVENTORY_STATUS_LABEL[inventoryStatus] || inventoryStatus}
                  tone={extractionStatusTone(inventoryStatus)}
                />
              </div>

              {!sourceFile ? (
                <p className="mt-4 text-sm text-slate-400">Envie um documento para habilitar o inventário.</p>
              ) : !extractionReady ? (
                <p className="mt-4 text-sm text-slate-400">
                  Conclua a extração do documento acima para habilitar a geração do inventário.
                </p>
              ) : (
                <>
                  {inventoryError ? <p className="mt-3 text-sm text-red-300">{inventoryError}</p> : null}

                  {isInventoryRunning && inventoryJob ? (
                    <div className="mt-4 rounded-md border border-gold-500/20 bg-gold-500/10 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm text-gold-200">
                          {inventoryJob.current_item || inventoryJob.current_step || "Processando..."}
                        </p>
                        <span className="text-xs text-gold-300">
                          {inventoryJob.processed_items ?? 0}/{inventoryJob.total_items ?? "?"} chunks
                        </span>
                      </div>
                      <div className="mt-3 h-2 rounded-full bg-white/10">
                        <div
                          className="h-2 rounded-full bg-gold-500 transition-all"
                          style={{ width: `${inventoryJob.progress || 0}%` }}
                        />
                      </div>
                    </div>
                  ) : null}

                  {inventorySummary ? (
                    <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <Metric label="Itens identificados" value={inventorySummary.total_items} />
                      <Metric
                        label="Essenciais"
                        value={inventorySummary.items_by_importance["essential"] ?? 0}
                      />
                      <Metric
                        label="Relevantes"
                        value={inventorySummary.items_by_importance["relevant"] ?? 0}
                      />
                      <Metric
                        label="Complementares"
                        value={inventorySummary.items_by_importance["complementary"] ?? 0}
                      />
                      <Metric label="Possíveis duplicidades" value={inventorySummary.possible_duplicates} />
                      <Metric label="Fragmentados" value={inventorySummary.fragmented_items} />
                      <Metric label="Para revisão" value={inventorySummary.requires_review_items} />
                      <Metric label="Páginas com OCR pendente" value={inventorySummary.pages_requires_ocr} />
                    </div>
                  ) : null}

                  <div className="mt-6 flex flex-wrap gap-3">
                    {inventoryStatus === "not_started" || inventoryStatus === "failed" ? (
                      <button
                        type="button"
                        onClick={handleStartInventory}
                        disabled={inventoryStarting || isInventoryRunning}
                        className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {inventoryStarting ? "Iniciando..." : "Gerar inventário"}
                      </button>
                    ) : null}

                    {inventorySummary && inventorySummary.total_items > 0 && inventorySummary.chunks_failed > 0 ? (
                      <button
                        type="button"
                        onClick={handleReprocessInventoryFailed}
                        disabled={inventoryReprocessing || isInventoryRunning}
                        className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {inventoryReprocessing ? "Reprocessando..." : "Reprocessar falhas"}
                      </button>
                    ) : null}

                    <button
                      type="button"
                      onClick={refreshInventorySummary}
                      className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                    >
                      Atualizar status
                    </button>

                    {inventorySummary && inventorySummary.total_items > 0 ? (
                      <Link
                        href={`/fidelity-coverage/${projectId}/inventory`}
                        className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-gold-500/40 hover:text-gold-400"
                      >
                        Visualizar inventário
                      </Link>
                    ) : null}
                  </div>
                </>
              )}
            </div>

            <div className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-white">Plano de Cobertura</p>
                  <p className="mt-1 text-sm text-slate-400">
                    Estrutura pedagógica (módulos e aulas) e Mapa de Aulas: relação entre cada item do inventário e
                    a(s) aula(s) em que ele deve ser ensinado.
                  </p>
                </div>
                <StatusBadge
                  label={COVERAGE_PLAN_STATUS_LABEL[coveragePlanSummary?.status || "not_started"] || coveragePlanSummary?.status || "Não iniciado"}
                  tone={coveragePlanStatusTone(coveragePlanSummary?.status || "not_started")}
                />
              </div>

              {coveragePlanError ? <p className="mt-3 text-sm text-red-300">{coveragePlanError}</p> : null}

              {!sourceFile ? (
                <p className="mt-4 text-sm text-slate-400">Envie um documento para habilitar o plano de cobertura.</p>
              ) : !inventorySummary || inventorySummary.total_items === 0 ? (
                <p className="mt-4 text-sm text-slate-400">
                  Gere e revise o inventário acima para habilitar o plano de cobertura.
                </p>
              ) : coveragePlanSummary && coveragePlanSummary.total_items > 0 ? (
                <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Metric label="Versão" value={coveragePlanSummary.version} />
                  <Metric label="Módulos" value={coveragePlanSummary.total_modules} />
                  <Metric label="Aulas" value={coveragePlanSummary.total_lessons} />
                  <Metric label="Itens sem aula" value={coveragePlanSummary.unmapped_items} />
                </div>
              ) : null}

              <div className="mt-6">
                <Link
                  href={`/fidelity-coverage/${projectId}/coverage-plan`}
                  className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400"
                >
                  Abrir Plano de Cobertura
                </Link>
              </div>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-2">
              {SUBSECTIONS.map((section) => (
                <div key={section.title} className="rounded-lg border border-white/10 bg-white/[0.035] p-5">
                  <p className="font-medium text-white">{section.title}</p>
                  <p className="mt-2 text-sm text-slate-400">{section.description}</p>
                  <p className="mt-4 text-xs uppercase tracking-wide text-slate-500">Em breve</p>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-white/10 bg-navy-950/60 p-4">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}
