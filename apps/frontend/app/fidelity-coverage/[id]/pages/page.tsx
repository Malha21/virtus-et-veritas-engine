"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch, listDocumentPages } from "@/lib/api";
import type { DocumentPage } from "@/types/document-extraction";
import type { ProjectFile } from "@/types/file";

const STATUS_TONE: Record<string, "neutral" | "success" | "warning"> = {
  extracted: "success",
  reviewed: "success",
  empty: "neutral",
  pending: "neutral",
  processing: "warning",
  failed: "warning",
  requires_ocr: "warning",
};

export default function DocumentPagesListPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [sourceFile, setSourceFile] = useState<ProjectFile | null>(null);
  const [pages, setPages] = useState<DocumentPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [ocrOnly, setOcrOnly] = useState(false);

  useEffect(() => {
    apiFetch<ProjectFile[]>(`/projects/${projectId}/files`)
      .then((files) => {
        const pdf = files.find((file) => file.file_type === "source_pdf") || null;
        setSourceFile(pdf);
        if (!pdf) {
          setLoading(false);
          return null;
        }
        return listDocumentPages(projectId, pdf.id, { pageSize: 200 });
      })
      .then((response) => {
        if (response) setPages(response.items);
      })
      .catch(() => setError("Não foi possível carregar as páginas do documento."))
      .finally(() => setLoading(false));
  }, [projectId]);

  const statusOptions = useMemo(() => Array.from(new Set(pages.map((p) => p.extraction_status))), [pages]);

  const filteredPages = useMemo(() => {
    return pages.filter((p) => {
      const matchesStatus = statusFilter === "all" || p.extraction_status === statusFilter;
      const matchesOcr = !ocrOnly || p.requires_ocr;
      return matchesStatus && matchesOcr;
    });
  }, [pages, statusFilter, ocrOnly]);

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <Link href={`/fidelity-coverage/${projectId}`} className="text-sm text-accent-400 hover:text-accent-500">
          Voltar para o projeto
        </Link>

        <div className="mt-4">
          <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Extração do Documento</p>
          <h1 className="mt-2 text-3xl font-semibold">Páginas extraídas</h1>
          {sourceFile ? (
            <p className="mt-2 text-zinc-400">{sourceFile.original_filename}</p>
          ) : null}
        </div>

        {loading ? (
          <div className="mt-8">
            <LoadingProgress label="Carregando páginas..." />
          </div>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : !sourceFile ? (
          <p className="mt-8 text-zinc-300">Nenhum documento enviado neste projeto.</p>
        ) : !pages.length ? (
          <div className="mt-8 rounded-lg border border-white/5 bg-white/[0.035] p-8 text-center">
            <p className="text-zinc-300">Nenhuma página extraída ainda. Inicie a extração no projeto.</p>
          </div>
        ) : (
          <>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
              >
                <option value="all">Todos os status</option>
                {statusOptions.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-sm text-zinc-300">
                <input
                  type="checkbox"
                  checked={ocrOnly}
                  onChange={(event) => setOcrOnly(event.target.checked)}
                  className="h-4 w-4 rounded border-white/20 bg-navy-950"
                />
                Somente páginas que requerem OCR
              </label>
            </div>

            <div className="mt-6 overflow-x-auto rounded-lg border border-white/5 bg-white/[0.035]">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="border-b border-white/5 text-zinc-400">
                  <tr>
                    <th className="px-5 py-4 font-medium">Página</th>
                    <th className="px-5 py-4 font-medium">Status</th>
                    <th className="px-5 py-4 font-medium">Palavras</th>
                    <th className="px-5 py-4 font-medium">Caracteres</th>
                    <th className="px-5 py-4 font-medium">Blocos</th>
                    <th className="px-5 py-4 font-medium">Método</th>
                    <th className="px-5 py-4 font-medium">Requer OCR</th>
                    <th className="px-5 py-4 font-medium">Ação</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPages.map((docPage) => (
                    <tr key={docPage.id} className="border-b border-white/5">
                      <td className="px-5 py-4 font-medium text-white">{docPage.page_number}</td>
                      <td className="px-5 py-4">
                        <StatusBadge
                          label={docPage.extraction_status}
                          tone={STATUS_TONE[docPage.extraction_status] || "neutral"}
                        />
                      </td>
                      <td className="px-5 py-4 text-zinc-300">{docPage.word_count}</td>
                      <td className="px-5 py-4 text-zinc-300">{docPage.character_count}</td>
                      <td className="px-5 py-4 text-zinc-300">{docPage.block_count}</td>
                      <td className="px-5 py-4 text-zinc-400">{docPage.extraction_method || "—"}</td>
                      <td className="px-5 py-4 text-zinc-300">{docPage.requires_ocr ? "Sim" : "Não"}</td>
                      <td className="px-5 py-4">
                        <Link
                          href={`/fidelity-coverage/${projectId}/pages/${docPage.page_number}`}
                          className="text-accent-400 hover:text-accent-500"
                        >
                          Abrir detalhes
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
