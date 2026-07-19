"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import type { Project, ProjectCreate } from "@/types/project";

export default function NewProjectPage() {
  const router = useRouter();
  const [form, setForm] = useState<ProjectCreate>({
    title: "",
    product_type: "course",
    target_audience: "",
    tone_of_voice: "",
    desired_duration: "",
    description: "",
    ai_provider: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function updateField(field: keyof ProjectCreate, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const project = await apiFetch<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({ ...form, ai_provider: form.ai_provider || undefined }),
      });
      router.replace(`/projects/${project.id}`);
    } catch {
      setError("Não foi possível criar o projeto. Revise os campos e tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-gold-400">Novo Projeto</p>
        <h1 className="mt-2 text-3xl font-semibold">Criar produção educacional</h1>
        <p className="mt-2 text-slate-400">Nesta fase, o tipo habilitado é curso.</p>

        <form onSubmit={handleSubmit} className="mt-8 grid gap-5 rounded-lg border border-white/10 bg-white/[0.035] p-6">
          <label className="grid gap-2 text-sm text-slate-200">
            Título
            <input
              value={form.title}
              onChange={(event) => updateField("title", event.target.value)}
              required
              className="h-11 rounded-md border border-white/10 bg-navy-950 px-3 text-white outline-none focus:border-gold-500"
            />
          </label>

          <label className="grid gap-2 text-sm text-slate-200">
            Tipo de produto
            <select
              value={form.product_type}
              onChange={(event) => updateField("product_type", event.target.value)}
              className="h-11 rounded-md border border-white/10 bg-navy-950 px-3 text-white outline-none focus:border-gold-500"
            >
              <option value="course">Curso</option>
            </select>
          </label>

          <label className="grid gap-2 text-sm text-slate-200">
            IA para geração de conteúdo
            <select
              value={form.ai_provider}
              onChange={(event) => updateField("ai_provider", event.target.value)}
              className="h-11 rounded-md border border-white/10 bg-navy-950 px-3 text-white outline-none focus:border-gold-500"
            >
              <option value="">Padrão do sistema</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="openai">OpenAI (GPT)</option>
              {/* Gemini desativado: custo de créditos da API acima do esperado */}
            </select>
          </label>

          <label className="grid gap-2 text-sm text-slate-200">
            Público-alvo
            <input
              value={form.target_audience}
              onChange={(event) => updateField("target_audience", event.target.value)}
              className="h-11 rounded-md border border-white/10 bg-navy-950 px-3 text-white outline-none focus:border-gold-500"
            />
          </label>

          <div className="grid gap-5 md:grid-cols-2">
            <label className="grid gap-2 text-sm text-slate-200">
              Tom de voz
              <input
                value={form.tone_of_voice}
                onChange={(event) => updateField("tone_of_voice", event.target.value)}
                className="h-11 rounded-md border border-white/10 bg-navy-950 px-3 text-white outline-none focus:border-gold-500"
              />
            </label>

            <label className="grid gap-2 text-sm text-slate-200">
              Duração desejada
              <input
                value={form.desired_duration}
                onChange={(event) => updateField("desired_duration", event.target.value)}
                className="h-11 rounded-md border border-white/10 bg-navy-950 px-3 text-white outline-none focus:border-gold-500"
              />
            </label>
          </div>

          <label className="grid gap-2 text-sm text-slate-200">
            Descrição
            <textarea
              value={form.description}
              onChange={(event) => updateField("description", event.target.value)}
              rows={5}
              className="rounded-md border border-white/10 bg-navy-950 px-3 py-3 text-white outline-none focus:border-gold-500"
            />
          </label>

          {error ? <p className="text-sm text-red-300">{error}</p> : null}

          <div className="flex flex-wrap justify-end gap-3">
            <button
              type="button"
              onClick={() => router.push("/projects")}
              className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 hover:border-gold-500/40"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-gold-400 disabled:opacity-60"
            >
              {loading ? "Criando..." : "Criar Projeto"}
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
