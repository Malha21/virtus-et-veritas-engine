"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { FileUploader } from "@/components/upload/FileUploader";
import { apiFetch, deleteProjectFile } from "@/lib/api";
import { translateFileStatus } from "@/lib/status-labels";
import type { ProjectFile } from "@/types/file";
import type { StartProcessingResponse } from "@/types/processing";
import type { Project } from "@/types/project";

export default function ProjectUploadPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);
  const [removing, setRemoving] = useState(false);

  function refreshFiles() {
    apiFetch<ProjectFile[]>(`/projects/${params.id}/files`)
      .then(setFiles)
      .catch(() => setError("Não foi possível carregar os arquivos enviados."));
  }

  async function removeFile(fileId: string) {
    const confirmed = window.confirm(
      "Remover este documento também apaga a extração, o inventário e o plano de cobertura já gerados a partir dele. Deseja continuar?",
    );
    if (!confirmed) {
      return;
    }

    setRemoving(true);
    setError("");
    try {
      await deleteProjectFile(params.id, fileId);
      refreshFiles();
    } catch {
      setError("Não foi possível remover o documento.");
    } finally {
      setRemoving(false);
    }
  }

  useEffect(() => {
    Promise.all([
      apiFetch<Project>(`/projects/${params.id}`),
      apiFetch<ProjectFile[]>(`/projects/${params.id}/files`),
    ])
      .then(([projectData, fileData]) => {
        setProject(projectData);
        setFiles(fileData);
      })
      .catch(() => setError("Não foi possível carregar os dados do projeto."))
      .finally(() => setLoading(false));
  }, [params.id]);

  async function startProcessing() {
    setProcessing(true);
    setError("");
    try {
      await apiFetch<StartProcessingResponse>(`/projects/${params.id}/process`, {
        method: "POST",
      });
      router.push(`/projects/${params.id}/processing`);
    } catch {
      setError("Não foi possível iniciar o processamento do documento.");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <Link href={`/projects/${params.id}`} className="text-sm text-accent-400 hover:text-accent-500">
          Voltar para detalhes
        </Link>

        {loading ? (
          <div className="mt-8">
            <LoadingProgress label="Carregando área de upload..." />
          </div>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : project ? (
          <div className="mt-6 grid gap-6">
            <section>
              <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Documento do projeto</p>
              <h1 className="mt-2 text-3xl font-semibold">{project.title}</h1>
              <p className="mt-2 text-zinc-400">
                {files.length
                  ? "Este é o documento-base usado em todo o projeto: extração, inventário, plano de cobertura e roteiros. Para trocar, remova o atual e envie um novo."
                  : "Envie o PDF ou EPUB-base que será usado em todo o projeto."}
              </p>
            </section>

            {files.length ? (
              <section className="rounded-lg border border-white/5 bg-white/[0.035] p-5">
                <h2 className="text-lg font-semibold text-white">Documento atual</h2>
                <div className="mt-4 grid gap-3">
                  {files.map((file) => (
                    <div
                      key={file.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/5 bg-navy-950/60 px-4 py-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-white">{file.original_filename}</p>
                        <p className="mt-1 text-xs text-zinc-400">
                          {formatFileSize(file.file_size)} • {new Date(file.created_at).toLocaleDateString("pt-BR")}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge label={translateFileStatus(file.status)} tone="success" />
                        <button
                          type="button"
                          onClick={() => removeFile(file.id)}
                          disabled={removing}
                          className="rounded-md border border-red-400/30 px-3 py-1.5 text-xs text-red-300 transition hover:border-red-300/60 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {removing ? "Removendo..." : "Remover documento"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : (
              <FileUploader projectId={project.id} onUploaded={refreshFiles} />
            )}

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={startProcessing}
                disabled={!files.length || processing}
                className="w-fit rounded-md bg-accent-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:cursor-not-allowed disabled:opacity-60"
              >
                {processing ? "Processando..." : "Iniciar processamento"}
              </button>
              {!files.length ? (
                <p className="self-center text-sm text-zinc-400">
                  Envie um PDF ou EPUB antes de iniciar o processamento.
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}

function formatFileSize(size: number | null): string {
  if (!size) {
    return "Tamanho não informado";
  }

  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
