"use client";

import { useRouter } from "next/navigation";

import { hasToken } from "@/lib/auth";

const capabilities = [
  "Cursos",
  "Roteiros",
  "Materiais",
  "Experiências educacionais",
];

export default function Home() {
  const router = useRouter();

  function handleStart() {
    router.push(hasToken() ? "/dashboard" : "/login");
  }

  return (
    <main className="min-h-screen overflow-hidden bg-navy-950 text-white">
      <section className="relative flex min-h-screen items-center px-6 py-10 sm:px-10 lg:px-16">
        <div className="absolute inset-0 opacity-45">
          <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(200,162,74,0.16),transparent_32%,rgba(11,27,51,0.88)_70%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(228,199,102,0.12),transparent_34%)]" />
        </div>

        <div className="relative mx-auto grid w-full max-w-6xl gap-10 lg:grid-cols-[1.02fr_0.98fr] lg:items-center">
          <div className="max-w-3xl">
            <p className="mb-6 inline-flex rounded-full border border-white/5 bg-white/[0.04] px-4 py-2 text-sm font-medium text-accent-400">
              Inteligência para produção de conhecimento
            </p>

            <h1 className="max-w-4xl text-5xl font-semibold leading-tight text-white sm:text-6xl lg:text-7xl">
              Virtus et Veritas Engine
            </h1>

            <p className="mt-7 max-w-2xl text-lg leading-8 text-zinc-200 sm:text-xl">
              Transforme conhecimento bruto em cursos, roteiros, materiais e
              experiências educacionais com IA.
            </p>

            <div className="mt-10 flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={handleStart}
                className="inline-flex h-12 items-center justify-center rounded-md bg-accent-500 px-6 text-sm font-semibold text-navy-950 shadow-premium transition hover:bg-accent-400 hover:shadow-glow focus:outline-none focus:ring-2 focus:ring-accent-400 focus:ring-offset-2 focus:ring-offset-navy-950"
              >
                Iniciar Projeto
              </button>
              <span className="text-sm text-zinc-400">Área autenticada inicial</span>
            </div>
          </div>

          <div className="rounded-lg border border-white/5 bg-navy-900/70 p-5 shadow-premium backdrop-blur">
            <div className="flex items-center justify-between border-b border-white/5 pb-4">
              <div>
                <p className="text-sm text-zinc-400">Pipeline VVE</p>
                <p className="mt-1 text-lg font-semibold text-white">
                  Produção intelectual
                </p>
              </div>
              <span className="rounded-full bg-accent-500/12 px-3 py-1 text-xs font-medium text-accent-400">
                Fase 4
              </span>
            </div>

            <div className="mt-5 grid gap-3">
              {capabilities.map((item, index) => (
                <div
                  key={item}
                  className="flex items-center justify-between rounded-md border border-white/5 bg-white/[0.035] px-4 py-3"
                >
                  <span className="text-sm text-zinc-200">{item}</span>
                  <span className="text-xs font-medium text-accent-400">
                    0{index + 1}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
