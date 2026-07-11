"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import type { Project } from "@/types/project";

const SUBSECTIONS = [
  {
    title: "Inventário do Documento",
    description: "Unidades de conhecimento identificadas no documento fonte, com página e trecho de origem.",
  },
  {
    title: "Plano de Cobertura",
    description: "Relação entre cada item do inventário e as aulas em que ele deve ser ensinado.",
  },
  {
    title: "Mapa de Aulas",
    description: "Visão consolidada de módulos e aulas com os itens de conteúdo cobertos em cada uma.",
  },
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

export default function FidelityCoverageProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Project>(`/projects/${params.id}`)
      .then(setProject)
      .catch(() => setError("Não foi possível carregar este projeto."))
      .finally(() => setLoading(false));
  }, [params.id]);

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

            <div className="mt-6">
              <EmptyState
                title="Nenhuma análise de fidelidade disponível"
                description="As análises aparecerão aqui após o processamento e a auditoria dos documentos deste projeto."
                action={
                  <Link
                    href={`/projects/${project.id}`}
                    className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-gold-400"
                  >
                    Abrir projeto
                  </Link>
                }
              />
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
