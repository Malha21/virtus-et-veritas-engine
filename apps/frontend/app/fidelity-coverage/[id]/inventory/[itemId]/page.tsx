"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  ApiError,
  apiFetch,
  approveSourceInventoryItem,
  getSourceInventoryItemDetail,
  rejectSourceInventoryItem,
  updateSourceInventoryItem,
} from "@/lib/api";
import type { ProjectFile } from "@/types/file";
import type { SourceContentItemDetail } from "@/types/source-inventory";

export default function SourceInventoryItemDetailPage() {
  const params = useParams<{ id: string; itemId: string }>();
  const projectId = params.id;
  const itemId = params.itemId;

  const [sourceFile, setSourceFile] = useState<ProjectFile | null>(null);
  const [item, setItem] = useState<SourceContentItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editNormalized, setEditNormalized] = useState("");

  useEffect(() => {
    apiFetch<ProjectFile[]>(`/projects/${projectId}/files`)
      .then((files) => {
        const pdf = files.find((file) => file.file_type === "source_pdf");
        if (!pdf) throw new Error("Documento não encontrado.");
        setSourceFile(pdf);
        return getSourceInventoryItemDetail(projectId, pdf.id, itemId);
      })
      .then((data) => {
        setItem(data);
        setEditTitle(data.title);
        setEditNormalized(data.normalized_content || "");
      })
      .catch(() => setError("Não foi possível carregar este item."))
      .finally(() => setLoading(false));
  }, [projectId, itemId]);

  async function handleSave() {
    if (!sourceFile) return;
    setSaving(true);
    setActionError("");
    try {
      const updated = await updateSourceInventoryItem(projectId, sourceFile.id, itemId, {
        title: editTitle,
        normalized_content: editNormalized,
      });
      setItem((current) => (current ? { ...current, ...updated } : current));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setActionError("Sua sessão expirou. Faça login novamente.");
      } else {
        setActionError("Não foi possível salvar as alterações.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    if (!sourceFile) return;
    setActionError("");
    try {
      const updated = await approveSourceInventoryItem(projectId, sourceFile.id, itemId);
      setItem((current) => (current ? { ...current, ...updated } : current));
    } catch {
      setActionError("Não foi possível aprovar o item.");
    }
  }

  async function handleReject() {
    if (!sourceFile) return;
    setActionError("");
    try {
      const updated = await rejectSourceInventoryItem(projectId, sourceFile.id, itemId);
      setItem((current) => (current ? { ...current, ...updated } : current));
    } catch {
      setActionError("Não foi possível rejeitar o item.");
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <Link
          href={`/fidelity-coverage/${projectId}/inventory`}
          className="text-sm text-accent-400 hover:text-accent-500"
        >
          Voltar para o inventário
        </Link>

        {loading ? (
          <div className="mt-8">
            <LoadingProgress label="Carregando item..." />
          </div>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : item ? (
          <>
            <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="font-mono text-sm text-accent-400">{item.item_code}</p>
                <h1 className="mt-2 text-2xl font-semibold">{item.title}</h1>
                <p className="mt-2 text-sm text-zinc-400">
                  {item.content_type} · {item.importance} · páginas{" "}
                  {item.page_start === item.page_end ? item.page_start : `${item.page_start}–${item.page_end}`}
                </p>
              </div>
              <StatusBadge label={item.status} tone={item.status === "approved" ? "success" : "warning"} />
            </div>

            {actionError ? <p className="mt-4 text-sm text-red-300">{actionError}</p> : null}

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleApprove}
                disabled={item.status === "approved"}
                className="rounded-md bg-accent-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:cursor-not-allowed disabled:opacity-60"
              >
                Aprovar
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={item.status === "rejected"}
                className="rounded-md border border-red-400/30 px-4 py-2 text-sm text-red-300 transition hover:border-red-300/60 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Rejeitar
              </button>
            </div>

            <div className="mt-8 rounded-lg border border-white/5 bg-white/[0.035] p-6">
              <p className="font-medium text-white">Conteúdo normalizado (editável)</p>
              <p className="mt-1 text-xs text-zinc-500">
                Descrição fiel e reorganizada pela IA. Não é o texto original do documento.
              </p>
              <label htmlFor="edit-title" className="mt-4 block text-sm text-zinc-300">
                Título
              </label>
              <input
                id="edit-title"
                type="text"
                value={editTitle}
                onChange={(event) => setEditTitle(event.target.value)}
                className="mt-2 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
              />
              <label htmlFor="edit-normalized" className="mt-4 block text-sm text-zinc-300">
                Conteúdo normalizado
              </label>
              <textarea
                id="edit-normalized"
                value={editNormalized}
                onChange={(event) => setEditNormalized(event.target.value)}
                rows={6}
                className="mt-2 w-full rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="mt-4 rounded-md border border-white/5 px-4 py-2 text-sm text-zinc-200 transition hover:border-accent-500/40 hover:text-accent-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "Salvando..." : "Salvar alterações"}
              </button>
            </div>

            <div className="mt-6 rounded-lg border border-white/5 bg-white/[0.035] p-6">
              <p className="font-medium text-white">Texto original (fonte, não editável aqui)</p>
              <p className="mt-1 text-xs text-zinc-500">
                Trecho exato extraído do documento, preservado para rastreabilidade.
              </p>
              <pre className="mt-4 max-h-[300px] overflow-auto whitespace-pre-wrap break-words rounded-md bg-navy-950/60 p-4 text-sm text-zinc-200">
                {item.source_text}
              </pre>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="rounded-lg border border-white/5 bg-white/[0.035] p-5">
                <p className="font-medium text-white">Blocos de origem</p>
                <div className="mt-3 space-y-2">
                  {item.blocks.length === 0 ? (
                    <p className="text-sm text-zinc-400">Nenhum bloco associado.</p>
                  ) : (
                    item.blocks.map((block) => (
                      <Link
                        key={block.id}
                        href={`/fidelity-coverage/${projectId}/pages/${block.page_number}`}
                        className="flex items-center justify-between rounded-md border border-white/5 px-3 py-2 text-sm text-zinc-200 hover:border-accent-500/40"
                      >
                        <span>
                          {block.block_code} {block.is_primary ? "(principal)" : ""}
                        </span>
                        <span className="text-zinc-400">página {block.page_number}</span>
                      </Link>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-white/5 bg-white/[0.035] p-5">
                <p className="font-medium text-white">Dependências</p>
                <div className="mt-3 space-y-2">
                  {item.dependencies.length === 0 && item.dependents.length === 0 ? (
                    <p className="text-sm text-zinc-400">Nenhuma dependência registrada.</p>
                  ) : (
                    <>
                      {item.dependencies.map((dep) => (
                        <p key={dep.id} className="text-sm text-zinc-300">
                          depende de outro item ({dep.dependency_type})
                        </p>
                      ))}
                      {item.dependents.map((dep) => (
                        <p key={dep.id} className="text-sm text-zinc-300">
                          é referenciado por outro item ({dep.dependency_type})
                        </p>
                      ))}
                    </>
                  )}
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
