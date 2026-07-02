"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { FileUploader } from "@/components/upload/FileUploader";
import { apiFetch } from "@/lib/api";
import type { ProjectFile } from "@/types/file";
import type { Project } from "@/types/project";

export default function ProjectUploadPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function refreshFiles() {
    apiFetch<ProjectFile[]>(`/projects/${params.id}/files`)
      .then(setFiles)
      .catch(() => setError("Não foi possível carregar os arquivos enviados."));
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

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <Link href={`/projects/${params.id}`} className="text-sm text-gold-400 hover:text-gold-500">
          Voltar para detalhes
        </Link>

        {loading ? (
          <p className="mt-8 text-slate-300">Carregando área de upload...</p>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : project ? (
          <div className="mt-6 grid gap-6">
            <section>
              <p className="text-sm text-gold-400">Upload de PDF</p>
              <h1 className="mt-2 text-3xl font-semibold">{project.title}</h1>
              <p className="mt-2 text-slate-400">
                Envie o PDF-base que será usado para criar o curso.
              </p>
            </section>

            <FileUploader projectId={project.id} onUploaded={refreshFiles} />

            <section className="rounded-lg border border-white/10 bg-white/[0.035] p-5">
              <h2 className="text-lg font-semibold text-white">Arquivos enviados</h2>

              {!files.length ? (
                <p className="mt-4 text-sm text-slate-400">Nenhum PDF enviado ainda.</p>
              ) : (
                <div className="mt-4 grid gap-3">
                  {files.map((file) => (
                    <div
                      key={file.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/10 bg-navy-950/60 px-4 py-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-white">{file.original_filename}</p>
                        <p className="mt-1 text-xs text-slate-400">
                          {formatFileSize(file.file_size)} • {new Date(file.created_at).toLocaleDateString("pt-BR")}
                        </p>
                      </div>
                      <StatusBadge label={file.status} tone="success" />
                    </div>
                  ))}
                </div>
              )}
            </section>

            <button
              type="button"
              disabled
              className="w-fit rounded-md border border-white/10 px-4 py-2 text-sm text-slate-500"
            >
              Iniciar processamento — disponível na próxima fase
            </button>
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
