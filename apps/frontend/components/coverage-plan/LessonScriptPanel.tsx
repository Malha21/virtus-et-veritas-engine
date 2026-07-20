"use client";

import { useCallback, useEffect, useState } from "react";

import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  ApiError,
  approveCoverageLessonGeneration,
  generateCoverageLesson,
  getCoverageLessonGenerationJob,
  getLatestCoverageLessonGeneration,
  regenerateCoverageLesson,
  rejectCoverageLessonGeneration,
  validateCoverageLessonGeneration,
} from "@/lib/api";
import type { LessonGenerationDetail, LessonGenerationValidationResult } from "@/types/coverage-plan";
import type { ProcessingJob } from "@/types/processing";

const GENERATION_STATUS_LABEL: Record<string, string> = {
  pending: "Aguardando",
  queued: "Na fila",
  processing: "Gerando",
  completed: "Gerado",
  failed: "Falhou",
  requires_review: "Requer revisão",
  requires_split: "Requer divisão",
  approved: "Aprovado",
  rejected: "Rejeitado",
  stale: "Desatualizado",
  cancelled: "Cancelado",
};

function generationTone(status: string): "neutral" | "success" | "warning" | "progress" {
  if (status === "approved" || status === "completed") return "success";
  if (status === "processing" || status === "queued" || status === "pending") return "progress";
  if (["failed", "requires_review", "requires_split", "rejected", "stale"].includes(status)) return "warning";
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

type LessonScriptPanelProps = {
  lessonId: string;
  planApproved: boolean;
};

export function LessonScriptPanel({ lessonId, planApproved }: LessonScriptPanelProps) {
  const [generation, setGeneration] = useState<LessonGenerationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [validation, setValidation] = useState<LessonGenerationValidationResult | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    getLatestCoverageLessonGeneration(lessonId)
      .then(setGeneration)
      .catch(() => setGeneration(null))
      .finally(() => setLoading(false));
  }, [lessonId]);

  useEffect(() => {
    refresh();
    getCoverageLessonGenerationJob(lessonId)
      .then((activeJob) => {
        if (activeJob && (activeJob.status === "pending" || activeJob.status === "processing")) {
          setJob(activeJob);
        }
      })
      .catch(() => undefined);
  }, [lessonId, refresh]);

  const pollJob = useCallback(
    (jobId: string) => {
      getCoverageLessonGenerationJob(lessonId)
        .then((current) => {
          if (!current || current.id !== jobId) return;
          setJob(current);
          if (current.status === "pending" || current.status === "processing") {
            window.setTimeout(() => pollJob(jobId), 2500);
            return;
          }
          setJob(null);
          refresh();
        })
        .catch(() => setError("Não foi possível acompanhar a geração do roteiro."));
    },
    [lessonId, refresh],
  );

  async function handleGenerate() {
    setBusy(true);
    setError("");
    try {
      const startedJob = await generateCoverageLesson(lessonId, false);
      setJob(startedJob);
      pollJob(startedJob.id);
    } catch (err) {
      setError(errorMessage(err, "Não foi possível iniciar a geração do roteiro."));
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerate() {
    setBusy(true);
    setError("");
    try {
      const startedJob = await regenerateCoverageLesson(lessonId, "regenerate");
      setJob(startedJob);
      pollJob(startedJob.id);
    } catch (err) {
      setError(errorMessage(err, "Não foi possível iniciar a regeneração do roteiro."));
    } finally {
      setBusy(false);
    }
  }

  async function handleValidate() {
    if (!generation) return;
    setBusy(true);
    setError("");
    try {
      const result = await validateCoverageLessonGeneration(lessonId, generation.version);
      setValidation(result);
    } catch (err) {
      setError(errorMessage(err, "Não foi possível validar o roteiro."));
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    if (!generation) return;
    setBusy(true);
    setError("");
    try {
      await approveCoverageLessonGeneration(lessonId, generation.version);
      refresh();
    } catch (err) {
      setError(errorMessage(err, "Não foi possível aprovar o roteiro."));
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    if (!generation) return;
    const reason = window.prompt("Motivo da rejeição:");
    if (!reason || !reason.trim()) return;
    setBusy(true);
    setError("");
    try {
      await rejectCoverageLessonGeneration(lessonId, generation.version, reason.trim());
      refresh();
    } catch (err) {
      setError(errorMessage(err, "Não foi possível rejeitar o roteiro."));
    } finally {
      setBusy(false);
    }
  }

  const isGenerating = job !== null && (job.status === "pending" || job.status === "processing");

  return (
    <div className="mt-3 rounded-md border border-white/5 bg-navy-950/30 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-zinc-300">Roteiro de aula</p>
        {loading ? (
          <LoadingProgress label="Carregando" size="inline" />
        ) : isGenerating ? (
          <StatusBadge label={`${GENERATION_STATUS_LABEL.processing} (${job?.progress ?? 0}%)`} tone="progress" />
        ) : generation ? (
          <StatusBadge
            label={GENERATION_STATUS_LABEL[generation.generation_status] ?? generation.generation_status}
            tone={generationTone(generation.generation_status)}
          />
        ) : (
          <StatusBadge label="Não gerado" tone="neutral" />
        )}
      </div>

      {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}

      {!planApproved ? (
        <p className="mt-2 text-xs text-zinc-500">Aprove o plano de cobertura para gerar o roteiro desta aula.</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          {!generation ? (
            <button
              type="button"
              onClick={handleGenerate}
              disabled={busy || isGenerating}
              className="rounded border border-accent-500/30 px-2 py-1 text-xs text-accent-400 hover:border-accent-500/60 disabled:opacity-60"
            >
              {isGenerating ? "Gerando..." : "Gerar roteiro"}
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setExpanded((value) => !value)}
                className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400"
              >
                {expanded ? "Ocultar roteiro" : "Ver roteiro"}
              </button>
              <button
                type="button"
                onClick={handleRegenerate}
                disabled={busy || isGenerating}
                className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400 disabled:opacity-60"
              >
                Regenerar
              </button>
              <button
                type="button"
                onClick={handleValidate}
                disabled={busy || isGenerating}
                className="rounded border border-white/5 px-2 py-1 text-xs text-zinc-300 hover:border-accent-500/40 hover:text-accent-400 disabled:opacity-60"
              >
                Validar
              </button>
              {generation.generation_status !== "approved" ? (
                <>
                  <button
                    type="button"
                    onClick={handleApprove}
                    disabled={busy || isGenerating}
                    className="rounded border border-emerald-500/30 px-2 py-1 text-xs text-emerald-300 hover:border-emerald-500/60 disabled:opacity-60"
                  >
                    Aprovar
                  </button>
                  <button
                    type="button"
                    onClick={handleReject}
                    disabled={busy || isGenerating}
                    className="rounded border border-red-500/30 px-2 py-1 text-xs text-red-300 hover:border-red-500/60 disabled:opacity-60"
                  >
                    Rejeitar
                  </button>
                </>
              ) : null}
            </>
          )}
        </div>
      )}

      {validation ? (
        <div className="mt-2 rounded border border-white/5 bg-white/[0.02] p-2 text-xs text-zinc-300">
          <p className="font-medium text-zinc-200">Validação: {validation.status}</p>
          <p className="mt-1 text-zinc-400">
            {validation.covered_item_count} de {validation.expected_item_count} itens cobertos.
          </p>
          {validation.missing_required_item_codes.length > 0 ? (
            <p className="mt-1 text-accent-400">
              Itens obrigatórios faltando: {validation.missing_required_item_codes.join(", ")}
            </p>
          ) : null}
          {validation.warnings.map((warning, index) => (
            <p key={index} className="mt-1 text-zinc-500">
              {warning}
            </p>
          ))}
        </div>
      ) : null}

      {expanded && generation ? (
        <div className="mt-2 space-y-2 rounded border border-white/5 bg-white/[0.02] p-3 text-xs text-zinc-300">
          <p className="text-zinc-500">
            Versão {generation.version} · {generation.word_count ?? 0} palavras
            {generation.estimated_duration_seconds
              ? ` · ~${Math.round(generation.estimated_duration_seconds / 60)} min`
              : ""}
          </p>
          <p className="whitespace-pre-wrap leading-relaxed text-zinc-200">
            {generation.generated_content || "Roteiro sem conteúdo salvo."}
          </p>
        </div>
      ) : null}
    </div>
  );
}
