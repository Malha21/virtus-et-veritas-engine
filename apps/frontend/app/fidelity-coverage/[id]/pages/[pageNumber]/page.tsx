"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch, getDocumentPageDetail } from "@/lib/api";
import type { DocumentPageDetail } from "@/types/document-extraction";
import type { ProjectFile } from "@/types/file";

export default function DocumentPageDetailPage() {
  const params = useParams<{ id: string; pageNumber: string }>();
  const projectId = params.id;
  const pageNumber = Number(params.pageNumber);

  const [detail, setDetail] = useState<DocumentPageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [textView, setTextView] = useState<"normalized" | "raw">("normalized");

  useEffect(() => {
    apiFetch<ProjectFile[]>(`/projects/${projectId}/files`)
      .then((files) => {
        const pdf = files.find((file) => file.file_type === "source_pdf");
        if (!pdf) {
          throw new Error("Documento não encontrado.");
        }
        return getDocumentPageDetail(projectId, pdf.id, pageNumber);
      })
      .then(setDetail)
      .catch(() => setError("Não foi possível carregar esta página."))
      .finally(() => setLoading(false));
  }, [projectId, pageNumber]);

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <Link
          href={`/fidelity-coverage/${projectId}/pages`}
          className="text-sm text-gold-400 hover:text-gold-500"
        >
          Voltar para páginas
        </Link>

        {loading ? (
          <p className="mt-8 text-slate-300">Carregando página...</p>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : detail ? (
          <>
            <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm text-gold-400">Página {detail.page_number}</p>
                <h1 className="mt-2 text-2xl font-semibold">
                  {detail.word_count} palavras · {detail.character_count} caracteres · {detail.blocks.length} blocos
                </h1>
              </div>
              <div className="flex gap-2">
                <StatusBadge label={detail.extraction_status} tone={detail.extraction_status === "extracted" ? "success" : "warning"} />
                {detail.requires_ocr ? <StatusBadge label="Requer OCR" tone="warning" /> : null}
              </div>
            </div>

            <div className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-6">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setTextView("normalized")}
                  className={`rounded-md px-3 py-1.5 text-sm transition ${
                    textView === "normalized" ? "bg-gold-500 text-navy-950" : "border border-white/10 text-slate-300"
                  }`}
                >
                  Texto normalizado
                </button>
                <button
                  type="button"
                  onClick={() => setTextView("raw")}
                  className={`rounded-md px-3 py-1.5 text-sm transition ${
                    textView === "raw" ? "bg-gold-500 text-navy-950" : "border border-white/10 text-slate-300"
                  }`}
                >
                  Texto bruto (original)
                </button>
              </div>
              <pre className="mt-4 max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-md bg-navy-950/60 p-4 text-sm text-slate-200">
                {(textView === "normalized" ? detail.normalized_text : detail.raw_text) || "Sem texto extraído."}
              </pre>
            </div>

            <div className="mt-6">
              <p className="font-medium text-white">Blocos, na ordem de leitura</p>
              <div className="mt-3 space-y-3">
                {detail.blocks.length === 0 ? (
                  <p className="text-sm text-slate-400">Nenhum bloco identificado nesta página.</p>
                ) : (
                  detail.blocks.map((block) => (
                    <div key={block.id} className="rounded-md border border-white/10 bg-white/[0.035] p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-xs uppercase tracking-wide text-gold-400">{block.block_type}</span>
                        <span className="text-xs text-slate-500">{block.block_code}</span>
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-200">{block.source_text}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
