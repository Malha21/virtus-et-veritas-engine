"use client";

import { FormEvent, useState } from "react";
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
      <section className="w-full max-w-md rounded-lg border border-white/10 bg-navy-900/80 p-6 shadow-premium">
        <p className="text-sm font-medium text-gold-400">Virtus et Veritas Engine</p>
        <h1 className="mt-3 text-3xl font-semibold">Entrar</h1>
        <p className="mt-2 text-sm text-slate-300">
          Inteligência para produção de conhecimento
        </p>

        <form onSubmit={handleSubmit} className="mt-8 grid gap-4">
          <label className="grid gap-2 text-sm text-slate-200">
            E-mail
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="h-11 rounded-md border border-white/10 bg-white/[0.04] px-3 text-white outline-none transition focus:border-gold-500"
            />
          </label>

          <label className="grid gap-2 text-sm text-slate-200">
            Senha
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              className="h-11 rounded-md border border-white/10 bg-white/[0.04] px-3 text-white outline-none transition focus:border-gold-500"
            />
          </label>

          {error ? <p className="text-sm text-red-300">{error}</p> : null}

          <button
            type="submit"
            disabled={loading}
            className="mt-2 h-11 rounded-md bg-gold-500 px-4 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}
