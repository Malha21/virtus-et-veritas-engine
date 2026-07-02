"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import type { Project } from "@/types/project";

export default function ProjectDetailPage() {
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
      <div className="mx-auto max-w-4xl">
        <Link href="/projects" className="text-sm text-gold-400 hover:text-gold-500">
          Voltar para projetos
        </Link>

        {loading ? (
          <p className="mt-8 text-slate-300">Carregando projeto...</p>
        ) : error ? (
          <p className="mt-8 text-red-300">{error}</p>
        ) : project ? (
          <section className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm text-gold-400">{project.product_type}</p>
                <h1 className="mt-2 text-3xl font-semibold">{project.title}</h1>
                <p className="mt-2 text-sm text-slate-400">Slug: {project.slug}</p>
              </div>
              <div className="flex gap-2">
                <StatusBadge label={project.status} tone="success" />
                <StatusBadge label={project.processing_status} tone="warning" />
              </div>
            </div>

            <div className="mt-8 grid gap-5 md:grid-cols-2">
              <Info label="Público-alvo" value={project.target_audience} />
              <Info label="Tom de voz" value={project.tone_of_voice} />
              <Info label="Duração desejada" value={project.desired_duration} />
              <Info label="Atualizado em" value={new Date(project.updated_at).toLocaleDateString("pt-BR")} />
            </div>

            <div className="mt-6">
              <p className="text-sm text-slate-400">Descrição</p>
              <p className="mt-2 whitespace-pre-wrap text-slate-200">
                {project.description || "Nenhuma descrição informada."}
              </p>
            </div>

            <button
              type="button"
              disabled
              className="mt-8 rounded-md border border-white/10 px-4 py-2 text-sm text-slate-500"
            >
              Enviar PDF — disponível na próxima fase
            </button>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-md border border-white/10 bg-navy-950/60 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-slate-100">{value || "Não informado"}</p>
    </div>
  );
}
