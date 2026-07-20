"use client";

import { FormEvent, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { saveToken } from "@/lib/auth";
import type { LoginResponse } from "@/types/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      saveToken(data.access_token);
      router.replace("/dashboard");
    } catch {
      setError("Não foi possível entrar. Confira o e-mail e a senha.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-950 px-6 py-10 text-white">
      <section className="w-full max-w-md rounded-lg border border-white/5 bg-navy-900/80 p-6 shadow-premium">
        <div className="group flex justify-center">
          <Image
            src="/vve-shield.png"
            alt="Virtus et Veritas Engine"
            width={160}
            height={160}
            priority
            className="h-14 w-auto object-contain transition-all duration-500 group-hover:scale-[1.04] drop-shadow-[0_2px_14px_rgba(184,146,63,0.35)] md:h-16 lg:h-20"
          />
        </div>
        <h1 className="mt-5 text-center text-3xl font-semibold">Entrar</h1>
        <p className="mt-2 text-center text-sm text-zinc-300">
          Inteligência para produção de conhecimento
        </p>

        <form onSubmit={handleSubmit} className="mt-8 grid gap-4">
          <label className="grid gap-2 text-sm text-zinc-200">
            E-mail
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="h-11 rounded-md border border-white/5 bg-white/[0.04] px-3 text-white outline-none transition focus:border-accent-500"
            />
          </label>

          <label className="grid gap-2 text-sm text-zinc-200">
            Senha
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              className="h-11 rounded-md border border-white/5 bg-white/[0.04] px-3 text-white outline-none transition focus:border-accent-500"
            />
          </label>

          {error ? <p className="text-sm text-red-300">{error}</p> : null}

          <button
            type="submit"
            disabled={loading}
            className="mt-2 h-11 rounded-md bg-accent-500 px-4 text-sm font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}
