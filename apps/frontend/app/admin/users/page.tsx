"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/layout/AppShell";
import { LoadingProgress } from "@/components/ui/LoadingProgress";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError, createAdminUser, deactivateAdminUser, listAdminUsers, reactivateAdminUser } from "@/lib/api";
import type { AdminUser, AdminUserCreatePayload, UserRole } from "@/types/user-management";
import type { CurrentUser } from "@/types/auth";

const emptyForm: AdminUserCreatePayload = { name: "", email: "", password: "", role: "member" };

function AdminUsersContent({ currentUser }: { currentUser: CurrentUser }) {
  const router = useRouter();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState<AdminUserCreatePayload>(emptyForm);
  const [creating, setCreating] = useState(false);

  function refresh() {
    setLoading(true);
    listAdminUsers()
      .then(setUsers)
      .catch(() => setError("Não foi possível carregar os usuários."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (currentUser.role !== "admin") {
      router.replace("/dashboard");
      return;
    }
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser.role]);

  function updateField(field: keyof AdminUserCreatePayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setCreating(true);

    try {
      await createAdminUser(form);
      setSuccess("Usuário criado com sucesso.");
      setForm(emptyForm);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível criar o usuário.");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleStatus(user: AdminUser) {
    setError("");
    setSuccess("");
    try {
      if (user.status === "active") {
        await deactivateAdminUser(user.id);
        setSuccess(`${user.name} foi desativado.`);
      } else {
        await reactivateAdminUser(user.id);
        setSuccess(`${user.name} foi reativado.`);
      }
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível atualizar o status do usuário.");
    }
  }

  if (currentUser.role !== "admin") {
    return null;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <p className="font-mono text-xs uppercase tracking-wider text-accent-400">Administração</p>
      <h1 className="mt-2 text-3xl font-semibold">Usuários</h1>
      <p className="mt-2 text-zinc-400">
        Crie novos usuários da sua organização e gerencie o acesso deles. Cada usuário precisa cadastrar suas
        próprias chaves de IA em &quot;Minhas APIs&quot;.
      </p>

      <form onSubmit={handleCreate} className="mt-8 grid gap-5 rounded-lg border border-white/5 bg-white/[0.035] p-6">
        <h2 className="text-lg font-semibold text-white">Novo usuário</h2>

        <div className="grid gap-5 md:grid-cols-2">
          <label className="grid gap-2 text-sm text-zinc-200">
            Nome
            <input
              value={form.name}
              onChange={(event) => updateField("name", event.target.value)}
              required
              className="h-11 rounded-md border border-white/5 bg-navy-950 px-3 text-white outline-none focus:border-accent-500"
            />
          </label>

          <label className="grid gap-2 text-sm text-zinc-200">
            E-mail
            <input
              type="email"
              value={form.email}
              onChange={(event) => updateField("email", event.target.value)}
              required
              className="h-11 rounded-md border border-white/5 bg-navy-950 px-3 text-white outline-none focus:border-accent-500"
            />
          </label>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <label className="grid gap-2 text-sm text-zinc-200">
            Senha inicial
            <input
              type="password"
              value={form.password}
              onChange={(event) => updateField("password", event.target.value)}
              required
              minLength={8}
              className="h-11 rounded-md border border-white/5 bg-navy-950 px-3 text-white outline-none focus:border-accent-500"
            />
          </label>

          <label className="grid gap-2 text-sm text-zinc-200">
            Papel
            <select
              value={form.role}
              onChange={(event) => updateField("role", event.target.value as UserRole)}
              className="h-11 rounded-md border border-white/5 bg-navy-950 px-3 text-white outline-none focus:border-accent-500"
            >
              <option value="member">Usuário</option>
              <option value="admin">Administrador</option>
            </select>
          </label>
        </div>

        {error ? <p className="text-sm text-red-300">{error}</p> : null}
        {success ? <p className="text-sm text-emerald-300">{success}</p> : null}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={creating}
            className="rounded-md bg-accent-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-accent-400 hover:shadow-glow disabled:opacity-60"
          >
            {creating ? "Criando..." : "Criar usuário"}
          </button>
        </div>
      </form>

      <section className="mt-8 rounded-lg border border-white/5 bg-white/[0.035] p-5">
        <h2 className="text-lg font-semibold text-white">Usuários da organização</h2>

        {loading ? (
          <div className="mt-4">
            <LoadingProgress label="Carregando usuários..." />
          </div>
        ) : !users.length ? (
          <p className="mt-4 text-sm text-zinc-400">Nenhum usuário encontrado.</p>
        ) : (
          <div className="mt-4 grid gap-3">
            {users.map((user) => (
              <div
                key={user.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/5 bg-navy-950/60 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-white">
                    {user.name} <span className="text-xs text-zinc-400">({user.email})</span>
                  </p>
                  <p className="mt-1 text-xs text-zinc-400">
                    {user.role === "admin" ? "Administrador" : "Usuário"} • Criado em{" "}
                    {new Date(user.created_at).toLocaleDateString("pt-BR")}
                    {user.last_login_at
                      ? ` • Último acesso em ${new Date(user.last_login_at).toLocaleDateString("pt-BR")}`
                      : " • Nunca acessou"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge
                    label={user.status === "active" ? "ativo" : "inativo"}
                    tone={user.status === "active" ? "success" : "warning"}
                  />
                  {user.id !== currentUser.id ? (
                    <button
                      type="button"
                      onClick={() => handleToggleStatus(user)}
                      className="rounded-md border border-white/5 px-3 py-2 text-sm text-zinc-200 transition hover:border-accent-500/40"
                    >
                      {user.status === "active" ? "Desativar" : "Reativar"}
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default function AdminUsersPage() {
  return <AppShell>{(user) => <AdminUsersContent currentUser={user} />}</AppShell>;
}
