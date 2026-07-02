"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, apiFetch, generateStructure as generateStructureRequest } from "@/lib/api";
import type { GenerationLanguage } from "@/lib/api";
import type { ProcessingLog, ProcessingStatus } from "@/types/processing";

const steps = ["Recebendo arquivo", "Extraindo texto", "Texto extraido", "Estrutura com IA"];

export default function ProcessingPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [status, setStatus] = useState<ProcessingStatus | null>(null);
  const [logs, setLogs] = useState<ProcessingLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generationLanguage, setGenerationLanguage] = useState<GenerationLanguage>("pt-BR");

  useEffect(() => {
    Promise.all([
      apiFetch<ProcessingStatus>(`/projects/${params.id}/status`),
      apiFetch<ProcessingLog[]>(`/projects/${params.id}/logs`),
    ])
      .then(([statusData, logData]) => {
        setStatus(statusData);
        setLogs(logData);
      })
      .catch(() => setError("Nao foi possivel carregar o processamento."))
      .finally(() => setLoading(false));
  }, [params.id]);

  async function generateStructure() {
    setGenerating(true);
    setError("");
    try {
      await generateStructureRequest(params.id, generationLanguage);
      router.push(`/projects/${params.id}/review`);
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

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <Link href={`/projects/${params.id}`} className="text-sm text-gold-400 hover:text-gold-500">
          Voltar para o projeto
        </Link>

        {loading ? (
          <p className="mt-8 text-slate-300">Carregando processamento...</p>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : status ? (
          <div className="mt-6 grid gap-6">
            <section className="rounded-lg border border-white/10 bg-white/[0.035] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm text-gold-400">Processamento</p>
                  <h1 className="mt-2 text-3xl font-semibold">Processamento inteligente</h1>
                  <p className="mt-2 text-slate-400">{status.current_step}</p>
                </div>
                <StatusBadge
                  label={status.processing_status}
                  tone={status.processing_status === "failed" ? "neutral" : "success"}
                />
              </div>

              <div className="mt-8">
                <div className="h-2 rounded-full bg-white/10">
                  <div
                    className="h-2 rounded-full bg-gold-500 transition-all"
                    style={{ width: `${status.progress}%` }}
                  />
                </div>
                <p className="mt-2 text-sm text-slate-400">{status.progress}% concluido</p>
              </div>

              <div className="mt-8 grid gap-3 md:grid-cols-4">
                {steps.map((step, index) => (
                  <div key={step} className="rounded-md border border-white/10 bg-navy-950/60 p-4">
                    <p className="text-xs font-medium text-gold-400">0{index + 1}</p>
                    <p className="mt-2 text-sm text-slate-100">{step}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-white/10 bg-white/[0.035] p-6">
              <h2 className="text-lg font-semibold">Logs de processamento</h2>
              {!logs.length ? (
                <p className="mt-4 text-sm text-slate-400">Nenhum log registrado ainda.</p>
              ) : (
                <div className="mt-4 grid gap-3">
                  {logs.map((log) => (
                    <div key={log.id} className="rounded-md border border-white/10 bg-navy-950/60 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <StatusBadge label={log.level} tone={log.level === "error" ? "neutral" : "warning"} />
                        <span className="text-xs text-slate-500">
                          {new Date(log.created_at).toLocaleString("pt-BR")}
                        </span>
                      </div>
                      <p className="mt-3 text-sm text-slate-200">{log.message}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <div className="flex flex-wrap gap-3">
              {status.processing_status === "ai_structure_generated" ? (
                <Link
                  href={`/projects/${params.id}/review`}
                  className="inline-flex rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400"
                >
                  Revisar estrutura
                </Link>
              ) : (
                <div className="flex flex-wrap items-end gap-3">
                  <label className="grid gap-2 text-sm text-slate-300">
                    Idioma da estrutura
                    <select
                      value={generationLanguage}
                      onChange={(event) => setGenerationLanguage(event.target.value as GenerationLanguage)}
                      className="rounded-md border border-white/10 bg-navy-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
                    >
                      <option value="pt-BR">Português do Brasil</option>
                      <option value="en-US">English</option>
                    </select>
                  </label>
                  <button
                    type="button"
                    onClick={generateStructure}
                    disabled={status.processing_status !== "text_extracted" || generating}
                    className="inline-flex rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {generating ? "Gerando estrutura..." : "Gerar estrutura com IA"}
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
