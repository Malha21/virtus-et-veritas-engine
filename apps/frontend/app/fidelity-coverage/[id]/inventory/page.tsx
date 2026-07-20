"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  ApiError,
  apiFetch,
  approveSourceInventoryItem,
  listSourceInventoryItems,
  rejectSourceInventoryItem,
} from "@/lib/api";
import type { ProjectFile } from "@/types/file";
import type { SourceContentItem } from "@/types/source-inventory";

const STATUS_TONE: Record<string, "neutral" | "success" | "warning"> = {
  approved: "success",
  generated: "neutral",
  validated: "success",
  pending: "neutral",
  requires_review: "warning",
  possible_duplicate: "warning",
  fragmented: "warning",
  rejected: "warning",
};

export default function SourceInventoryListPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [sourceFile, setSourceFile] = useState<ProjectFile | null>(null);
  const [items, setItems] = useState<SourceContentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [importanceFilter, setImportanceFilter] = useState("all");
  const [actionError, setActionError] = useState("");

  const loadItems = useCallback(
    (fileId: string) => {
      setLoading(true);
      listSourceInventoryItems(projectId, fileId, {
        pageSize: 200,
        search: search || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        importance: importanceFilter === "all" ? undefined : importanceFilter,
      })
        .then((response) => {
          setItems(response.items);
          setTotal(response.total);
        })
        .catch(() => setError("Não foi possível carregar o inventário."))
        .finally(() => setLoading(false));
    },
    [projectId, search, statusFilter, importanceFilter],
  );

  useEffect(() => {
    apiFetch<ProjectFile[]>(`/projects/${projectId}/files`)
      .then((files) => {
        const pdf = files.find((file) => file.file_type === "source_pdf") || null;
        setSourceFile(pdf);
        if (pdf) loadItems(pdf.id);
        else setLoading(false);
      })
      .catch(() => {
        setError("Não foi possível carregar o documento.");
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (sourceFile) loadItems(sourceFile.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, statusFilter, importanceFilter]);

  async function handleApprove(itemId: string) {
    if (!sourceFile) return;
    setActionError("");
    try {
      await approveSourceInventoryItem(projectId, sourceFile.id, itemId);
      loadItems(sourceFile.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setActionError("Sua sessão expirou. Faça login novamente.");
      } else {
        setActionError("Não foi possível aprovar o item.");
      }
    }
  }

  async function handleReject(itemId: string) {
    if (!sourceFile) return;
    setActionError("");
    try {
      await rejectSourceInventoryItem(projectId, sourceFile.id, itemId);
      loadItems(sourceFile.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setActionError("Sua sessão expirou. Faça login novamente.");
      } else {
        setActionError("Não foi possível rejeitar o item.");
      }
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <Link href={`/fidelity-coverage/${projectId}`} className="text-sm text-accent-400 hover:text-accent-500">
          Voltar para o projeto
        </Link>

        <div className="mt-4">
          <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Inventário do Documento</p>
          <h1 className="mt-2 text-3xl font-semibold">Itens identificados</h1>
          {sourceFile ? <p className="mt-2 text-zinc-400">{sourceFile.original_filename}</p> : null}
        </div>

        {loading ? (
          <div className="mt-8">
            <LoadingProgress label="Carregando inventário..." />
          </div>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : !sourceFile ? (
          <p className="mt-8 text-zinc-300">Nenhum documento enviado neste projeto.</p>
        ) : !total ? (
          <div className="mt-8 rounded-lg border border-white/5 bg-white/[0.035] p-8 text-center">
            <p className="text-zinc-300">Nenhum item de inventário gerado ainda.</p>
          </div>
        ) : (
          <>
            {actionError ? <p className="mt-4 text-sm text-red-300">{actionError}</p> : null}

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <input
                type="text"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar por título"
                className="w-full max-w-xs rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-accent-500/40 focus:outline-none"
              />
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
              >
                <option value="all">Todos os status</option>
                <option value="generated">Gerado</option>
                <option value="requires_review">Requer revisão</option>
                <option value="possible_duplicate">Possível duplicidade</option>
                <option value="fragmented">Fragmentado</option>
                <option value="approved">Aprovado</option>
                <option value="rejected">Rejeitado</option>
              </select>
              <select
                value={importanceFilter}
                onChange={(event) => setImportanceFilter(event.target.value)}
                className="rounded-md border border-white/5 bg-navy-950/60 px-3 py-2 text-sm text-zinc-100 focus:border-accent-500/40 focus:outline-none"
              >
                <option value="all">Todas as importâncias</option>
                <option value="essential">Essencial</option>
                <option value="relevant">Relevante</option>
                <option value="complementary">Complementar</option>
              </select>
            </div>

            <div className="mt-6 overflow-x-auto rounded-lg border border-white/5 bg-white/[0.035]">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="border-b border-white/5 text-zinc-400">
                  <tr>
                    <th className="px-4 py-4 font-medium">Código</th>
                    <th className="px-4 py-4 font-medium">Título</th>
                    <th className="px-4 py-4 font-medium">Tipo</th>
                    <th className="px-4 py-4 font-medium">Importância</th>
                    <th className="px-4 py-4 font-medium">Páginas</th>
                    <th className="px-4 py-4 font-medium">Status</th>
                    <th className="px-4 py-4 font-medium">Ação</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} className="border-b border-white/5">
                      <td className="px-4 py-4 font-mono text-xs text-accent-400">{item.item_code}</td>
                      <td className="px-4 py-4 font-medium text-white">{item.title}</td>
                      <td className="px-4 py-4 text-zinc-300">{item.content_type}</td>
                      <td className="px-4 py-4 text-zinc-300">{item.importance}</td>
                      <td className="px-4 py-4 text-zinc-400">
                        {item.page_start === item.page_end ? item.page_start : `${item.page_start}–${item.page_end}`}
                      </td>
                      <td className="px-4 py-4">
                        <StatusBadge label={item.status} tone={STATUS_TONE[item.status] || "neutral"} />
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            href={`/fidelity-coverage/${projectId}/inventory/${item.id}`}
                            className="text-accent-400 hover:text-accent-500"
                          >
                            Detalhes
                          </Link>
                          {item.status !== "approved" ? (
                            <button
                              type="button"
                              onClick={() => handleApprove(item.id)}
                              className="rounded-md border border-emerald-400/30 px-2 py-1 text-xs text-emerald-300 transition hover:border-emerald-300/60"
                            >
                              Aprovar
                            </button>
                          ) : null}
                          {item.status !== "rejected" ? (
                            <button
                              type="button"
                              onClick={() => handleReject(item.id)}
                              className="rounded-md border border-red-400/30 px-2 py-1 text-xs text-red-300 transition hover:border-red-300/60"
                            >
                              Rejeitar
                            </button>
                          ) : null}
                        </div>
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
