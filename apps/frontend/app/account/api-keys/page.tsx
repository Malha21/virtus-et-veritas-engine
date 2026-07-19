"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { ApiError, deleteMyApiKey, listMyApiKeys, putMyApiKey } from "@/lib/api";
import type { UserAICredential } from "@/types/user-management";

const PROVIDERS: { value: UserAICredential["provider_type"]; label: string }[] = [
  { value: "anthropic", label: "Anthropic (Claude)" },
  { value: "openai", label: "OpenAI (GPT)" },
  { value: "gemini", label: "Google Gemini" },
];

export default function ApiKeysPage() {
  const [credentials, setCredentials] = useState<UserAICredential[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [provider, setProvider] = useState<UserAICredential["provider_type"]>("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  function refresh() {
    setLoading(true);
    listMyApiKeys()
      .then(setCredentials)
      .catch(() => setError("Não foi possível carregar suas chaves de API."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);

    try {
      await putMyApiKey(provider, apiKey);
      setSuccess("Chave salva com sucesso.");
      setApiKey("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a chave.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(providerType: UserAICredential["provider_type"]) {
    setError("");
    setSuccess("");
    try {
      await deleteMyApiKey(providerType);
      setSuccess("Chave removida com sucesso.");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível remover a chave.");
    }
  }

  function providerLabel(value: string): string {
    return PROVIDERS.find((item) => item.value === value)?.label || value;
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl">
        <p className="text-sm text-gold-400">Minha conta</p>
        <h1 className="mt-2 text-3xl font-semibold">Minhas chaves de API</h1>
        <p className="mt-2 text-slate-400">
          Cadastre suas próprias chaves de Anthropic, OpenAI ou Gemini para gerar conteúdo com IA. Cada usuário usa a
          própria chave — o custo de geração fica na sua conta, não na de outra pessoa.
        </p>

        <form
          onSubmit={handleSubmit}
          className="mt-8 grid gap-5 rounded-lg border border-white/10 bg-white/[0.035] p-6"
        >
          <label className="grid gap-2 text-sm text-slate-200">
            Provedor
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value as UserAICredential["provider_type"])}
              className="h-11 rounded-md border border-white/10 bg-navy-950 px-3 text-white outline-none focus:border-gold-500"
            >
              {PROVIDERS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-2 text-sm text-slate-200">
            Chave de API
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              required
              minLength={8}
              placeholder="Cole aqui a chave da sua conta"
              className="h-11 rounded-md border border-white/10 bg-navy-950 px-3 text-white outline-none focus:border-gold-500"
            />
          </label>

          {error ? <p className="text-sm text-red-300">{error}</p> : null}
          {success ? <p className="text-sm text-emerald-300">{success}</p> : null}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-gold-400 disabled:opacity-60"
            >
              {saving ? "Salvando..." : "Salvar chave"}
            </button>
          </div>
        </form>

        <section className="mt-8 rounded-lg border border-white/10 bg-white/[0.035] p-5">
          <h2 className="text-lg font-semibold text-white">Chaves cadastradas</h2>

          {loading ? (
            <p className="mt-4 text-sm text-slate-400">Carregando...</p>
          ) : !credentials.length ? (
            <p className="mt-4 text-sm text-slate-400">Nenhuma chave cadastrada ainda.</p>
          ) : (
            <div className="mt-4 grid gap-3">
              {credentials.map((credential) => (
                <div
                  key={credential.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/10 bg-navy-950/60 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-white">{providerLabel(credential.provider_type)}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      Termina em •••• {credential.key_last_four} — atualizada em{" "}
                      {new Date(credential.updated_at).toLocaleDateString("pt-BR")}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(credential.provider_type)}
                    className="rounded-md border border-white/10 px-3 py-2 text-sm text-red-300 transition hover:border-red-400/40"
                  >
                    Remover
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
