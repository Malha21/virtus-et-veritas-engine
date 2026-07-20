"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, BookOpen, FolderKanban, Flame, KeyRound, Plus, TrendingUp } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatCard } from "@/components/ui/StatCard";
import { apiFetch, getMarketInsights, listMyApiKeys } from "@/lib/api";
import type { CurrentUser } from "@/types/auth";
import type { MarketInsights } from "@/types/market-insight";
import type { ProjectListResponse } from "@/types/project";
import type { UserAICredential } from "@/types/user-management";

function formatVolume(value: number): string {
  return new Intl.NumberFormat("pt-BR").format(value);
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectListResponse | null>(null);
  const [insights, setInsights] = useState<MarketInsights | null>(null);
  const [credentials, setCredentials] = useState<UserAICredential[] | null>(null);

  useEffect(() => {
    apiFetch<ProjectListResponse>("/projects?page=1&page_size=100")
      .then(setProjects)
      .catch(() => setProjects(null));

    getMarketInsights()
      .then(setInsights)
      .catch(() => setInsights(null));

    listMyApiKeys()
      .then(setCredentials)
      .catch(() => setCredentials(null));
  }, []);

  return (
    <AppShell>
      {(user: CurrentUser) => {
        const items = projects?.items || [];
        const completed = items.filter((item) => item.processing_status === "completed").length;
        const processing = items.filter((item) =>
          ["queued", "extracting_text", "analyzing", "generating_structure"].includes(item.processing_status),
        ).length;

        const failedProjects = items.filter((item) => item.processing_status === "failed");
        const awaitingReviewProjects = items.filter((item) => item.processing_status === "ai_structure_generated");
        const hasPendencias = failedProjects.length > 0 || awaitingReviewProjects.length > 0;

        const showApiKeyWarning = user.role !== "admin" && credentials !== null && credentials.length === 0;

        const topTheme = insights?.themes[0];

        return (
          <div className="mx-auto max-w-6xl">
            <div className="relative overflow-hidden rounded-2xl border border-white/5 bg-navy-900 px-6 py-8">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-accent-500/20 blur-[100px]"
              />
              <div className="relative">
                <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Dashboard</p>
                <h1 className="mt-2 text-4xl font-semibold">Bem-vindo, {user.name.split(" ")[0]}!</h1>
                <p className="mt-2 text-zinc-400">{user.organization.name}</p>
              </div>
            </div>

            {showApiKeyWarning ? (
              <div className="mt-6 flex flex-wrap items-center gap-3 rounded-lg border border-amber-400/30 bg-amber-500/10 p-4">
                <KeyRound className="h-5 w-5 shrink-0 text-amber-300" strokeWidth={1.8} aria-hidden="true" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-amber-200">Nenhuma chave de API cadastrada</p>
                  <p className="mt-1 text-sm text-amber-100/80">
                    Cadastre sua chave pessoal de OpenAI ou Gemini antes de gerar conteúdo com IA.
                  </p>
                </div>
                <Link
                  href="/account/api-keys"
                  className="rounded-md border border-amber-400/40 px-3 py-2 text-sm font-semibold text-amber-200 transition hover:border-amber-300/70 hover:text-amber-100"
                >
                  Cadastrar chave
                </Link>
              </div>
            ) : null}

            {hasPendencias ? (
              <div className="mt-6 rounded-lg border border-red-400/30 bg-red-500/10 p-4">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-red-300" strokeWidth={1.8} aria-hidden="true" />
                  <p className="text-sm font-semibold text-red-200">Pendências</p>
                </div>
                <div className="mt-3 grid gap-2">
                  {failedProjects.map((project) => (
                    <Link
                      key={project.id}
                      href={`/projects/${project.id}`}
                      className="flex items-center justify-between gap-3 rounded-md border border-red-400/20 bg-navy-950/40 px-3 py-2 text-sm transition hover:border-red-300/40"
                    >
                      <span className="truncate text-zinc-100">{project.title}</span>
                      <span className="shrink-0 text-xs text-red-300">Processamento falhou</span>
                    </Link>
                  ))}
                  {awaitingReviewProjects.map((project) => (
                    <Link
                      key={project.id}
                      href={`/projects/${project.id}/review`}
                      className="flex items-center justify-between gap-3 rounded-md border border-red-400/20 bg-navy-950/40 px-3 py-2 text-sm transition hover:border-red-300/40"
                    >
                      <span className="truncate text-zinc-100">{project.title}</span>
                      <span className="shrink-0 text-xs text-zinc-400">Aguardando revisão da estrutura</span>
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Link
                href="/projects/new"
                className="rounded-lg border border-accent-500/20 bg-gradient-to-br from-accent-500/15 to-transparent p-5 shadow-premium transition hover:border-accent-500/40"
              >
                <div className="flex items-center gap-2 text-sm text-zinc-400">
                  <Plus className="h-4 w-4 text-accent-400" strokeWidth={1.8} aria-hidden="true" />
                  Ação rápida
                </div>
                <p className="mt-3 text-xl font-semibold text-white">Novo Projeto</p>
                <p className="mt-2 text-sm text-zinc-500">Criar projeto e enviar documento-base</p>
              </Link>
              <Link
                href="/projects"
                className="rounded-lg border border-white/5 bg-white/[0.035] p-5 shadow-premium transition hover:border-accent-500/40"
              >
                <div className="flex items-center gap-2 text-sm text-zinc-400">
                  <FolderKanban className="h-4 w-4 text-accent-400" strokeWidth={1.8} aria-hidden="true" />
                  Ação rápida
                </div>
                <p className="mt-3 text-xl font-semibold text-white">Ver Projetos</p>
                <p className="mt-2 text-sm text-zinc-500">Acompanhar todos os projetos criados</p>
              </Link>
              <StatCard label="Cursos concluídos" value={completed} tone="accent" />
              <StatCard label="Em processamento" value={processing} tone="violet" />
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <StatCard label="Projetos criados" value={projects?.total ?? 0} />
              <StatCard
                label="Tema mais quente do mês"
                value={topTheme?.category ?? "—"}
                hint={topTheme ? `${formatVolume(topTheme.total_volume)} exemplares vendidos` : undefined}
              />
            </div>

            <div className="mt-8 grid gap-4 lg:grid-cols-2">
              <section className="rounded-lg border border-white/5 bg-white/[0.035] p-5">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-accent-400" strokeWidth={1.8} aria-hidden="true" />
                    <p className="font-mono text-xs uppercase tracking-wider text-accent-400">
                      Top 10 livros mais vendidos
                    </p>
                  </div>
                  {insights?.period_label ? (
                    <span className="text-xs text-zinc-500">{insights.period_label}</span>
                  ) : null}
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  Ranking mensal do mercado editorial brasileiro (fonte: PublishNews / Nielsen BookScan)
                </p>

                {!insights ? (
                  <LoadingProgress label="Carregando dados de mercado..." size="inline" />
                ) : !insights.books.length ? (
                  <p className="mt-6 text-sm text-zinc-500">
                    Dados de mercado ainda não disponíveis. Tente novamente mais tarde.
                  </p>
                ) : (
                  <ol className="mt-4 grid gap-1">
                    {insights.books.map((book) => (
                      <li
                        key={book.id}
                        className="flex items-center gap-3 rounded-md px-2 py-2 transition hover:bg-white/[0.03]"
                      >
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/5 font-mono text-xs text-zinc-400">
                          {book.rank}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-zinc-100">{book.title}</p>
                          <p className="truncate text-xs text-zinc-500">
                            {book.author || "Autor não informado"}
                            {book.category ? ` · ${book.category}` : ""}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </section>

              <section className="rounded-lg border border-white/5 bg-white/[0.035] p-5">
                <div className="flex items-center gap-2">
                  <Flame className="h-4 w-4 text-accent-400" strokeWidth={1.8} aria-hidden="true" />
                  <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Temas em alta no mês</p>
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  Categorias com mais vendas entre os livros mais vendidos do mês — use como direção para novos
                  cursos.
                </p>

                {!insights ? (
                  <LoadingProgress label="Carregando dados de mercado..." size="inline" />
                ) : !insights.themes.length ? (
                  <p className="mt-6 text-sm text-zinc-500">Nenhum tema disponível no momento.</p>
                ) : (
                  <div className="mt-4 grid gap-3">
                    {insights.themes.map((theme, index) => {
                      const maxVolume = insights.themes[0]?.total_volume || 1;
                      const percentage = Math.max(6, Math.round((theme.total_volume / maxVolume) * 100));
                      return (
                        <div key={theme.category}>
                          <div className="flex items-center justify-between gap-3 text-sm">
                            <span className="flex items-center gap-2 text-zinc-100">
                              <TrendingUp
                                className={`h-3.5 w-3.5 ${index === 0 ? "text-accent-400" : "text-zinc-500"}`}
                                strokeWidth={1.8}
                                aria-hidden="true"
                              />
                              {theme.category}
                            </span>
                            <span className="font-mono text-xs text-zinc-500">
                              {theme.book_count} {theme.book_count === 1 ? "livro" : "livros"}
                            </span>
                          </div>
                          <div className="mt-1.5 h-1.5 rounded-full bg-white/5">
                            <div
                              className={`h-1.5 rounded-full ${index === 0 ? "bg-accent-500" : "bg-violet-400/60"}`}
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            </div>
          </div>
        );
      }}
    </AppShell>
  );
}
