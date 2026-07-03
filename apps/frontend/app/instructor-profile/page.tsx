"use client";

import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";
import {
  ApiError,
  getInstructorProfile,
  saveInstructorProfile,
  type InstructorProfilePayload,
} from "@/lib/api";

type FieldName = keyof InstructorProfilePayload;
type TextFieldName = Exclude<FieldName, "consent_voice_clone" | "consent_avatar_use">;
type ConsentFieldName = "consent_voice_clone" | "consent_avatar_use";

const emptyProfile: InstructorProfilePayload = {
  display_name: "",
  bio: "",
  teaching_style: "",
  voice_provider: "",
  voice_id: "",
  voice_name: "",
  voice_sample_notes: "",
  avatar_provider: "",
  avatar_id: "",
  avatar_name: "",
  avatar_style: "",
  avatar_image_path: "",
  consent_voice_clone: false,
  consent_avatar_use: false,
  consent_terms_text:
    "Declaro que tenho direito de uso sobre a voz e a imagem informadas neste perfil, ou autorização expressa da pessoa representada.",
};

function normalizeText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function toPayload(form: InstructorProfilePayload): InstructorProfilePayload {
  return {
    display_name: normalizeText(String(form.display_name || "")),
    bio: normalizeText(String(form.bio || "")),
    teaching_style: normalizeText(String(form.teaching_style || "")),
    voice_provider: normalizeText(String(form.voice_provider || "")),
    voice_id: normalizeText(String(form.voice_id || "")),
    voice_name: normalizeText(String(form.voice_name || "")),
    voice_sample_notes: normalizeText(String(form.voice_sample_notes || "")),
    avatar_provider: normalizeText(String(form.avatar_provider || "")),
    avatar_id: normalizeText(String(form.avatar_id || "")),
    avatar_name: normalizeText(String(form.avatar_name || "")),
    avatar_style: normalizeText(String(form.avatar_style || "")),
    avatar_image_path: normalizeText(String(form.avatar_image_path || "")),
    consent_voice_clone: Boolean(form.consent_voice_clone),
    consent_avatar_use: Boolean(form.consent_avatar_use),
    consent_terms_text: normalizeText(String(form.consent_terms_text || "")),
  };
}

function fromPayload(profile: InstructorProfilePayload | null): InstructorProfilePayload {
  if (!profile) return emptyProfile;
  return {
    display_name: profile.display_name || "",
    bio: profile.bio || "",
    teaching_style: profile.teaching_style || "",
    voice_provider: profile.voice_provider || "",
    voice_id: profile.voice_id || "",
    voice_name: profile.voice_name || "",
    voice_sample_notes: profile.voice_sample_notes || "",
    avatar_provider: profile.avatar_provider || "",
    avatar_id: profile.avatar_id || "",
    avatar_name: profile.avatar_name || "",
    avatar_style: profile.avatar_style || "",
    avatar_image_path: profile.avatar_image_path || "",
    consent_voice_clone: Boolean(profile.consent_voice_clone),
    consent_avatar_use: Boolean(profile.consent_avatar_use),
    consent_terms_text: profile.consent_terms_text || emptyProfile.consent_terms_text,
  };
}

export default function InstructorProfilePage() {
  const [form, setForm] = useState<InstructorProfilePayload>(emptyProfile);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getInstructorProfile()
      .then((profile) => setForm(fromPayload(profile)))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          setError("Sua sessão expirou. Faça login novamente.");
        } else if (err instanceof Error && err.message) {
          setError(err.message);
        } else {
          setError("Não foi possível carregar o perfil do instrutor.");
        }
      })
      .finally(() => setLoading(false));
  }, []);

  function updateTextField(field: TextFieldName, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateCheckbox(field: ConsentFieldName, checked: boolean) {
    setForm((current) => ({ ...current, [field]: checked }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");

    try {
      const savedProfile = await saveInstructorProfile(toPayload(form));
      setForm(fromPayload(savedProfile));
      setMessage("Perfil do instrutor salvo com sucesso.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Sua sessão expirou. Faça login novamente.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Não foi possível salvar o perfil do instrutor.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto grid max-w-6xl gap-6">
        <section className="rounded-lg border border-white/10 bg-navy-950/70 p-6">
          <p className="text-sm font-medium text-gold-400">Configuração do instrutor</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Perfil do Instrutor</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Prepare as informações para futuras gerações com voz e avatar personalizados. Nesta fase, o perfil
            apenas armazena as configurações; a geração com voz/avatar será ativada em etapas futuras.
          </p>
        </section>

        {loading ? (
          <p className="text-slate-300">Carregando perfil...</p>
        ) : (
          <form onSubmit={handleSubmit} className="grid gap-6">
            <ProfileSection title="Dados básicos" description="Identidade pública e estilo didático do instrutor.">
              <TextInput
                label="Nome de exibição"
                value={String(form.display_name || "")}
                onChange={(value) => updateTextField("display_name", value)}
              />
              <TextArea
                label="Bio curta"
                value={String(form.bio || "")}
                onChange={(value) => updateTextField("bio", value)}
              />
              <TextArea
                label="Estilo de ensino"
                value={String(form.teaching_style || "")}
                onChange={(value) => updateTextField("teaching_style", value)}
              />
            </ProfileSection>

            <ProfileSection title="Voz" description="Referências para futura narração personalizada.">
              <TextInput
                label="Provider de voz"
                value={String(form.voice_provider || "")}
                onChange={(value) => updateTextField("voice_provider", value)}
              />
              <TextInput
                label="Voice ID"
                value={String(form.voice_id || "")}
                onChange={(value) => updateTextField("voice_id", value)}
              />
              <TextInput
                label="Nome da voz"
                value={String(form.voice_name || "")}
                onChange={(value) => updateTextField("voice_name", value)}
              />
              <TextArea
                label="Observações/amostras de voz"
                value={String(form.voice_sample_notes || "")}
                onChange={(value) => updateTextField("voice_sample_notes", value)}
              />
            </ProfileSection>

            <ProfileSection title="Avatar" description="Identificadores e estilo para futuro avatar de vídeo.">
              <TextInput
                label="Provider de avatar"
                value={String(form.avatar_provider || "")}
                onChange={(value) => updateTextField("avatar_provider", value)}
              />
              <TextInput
                label="Avatar ID"
                value={String(form.avatar_id || "")}
                onChange={(value) => updateTextField("avatar_id", value)}
              />
              <TextInput
                label="Nome do avatar"
                value={String(form.avatar_name || "")}
                onChange={(value) => updateTextField("avatar_name", value)}
              />
              <TextArea
                label="Estilo do avatar"
                value={String(form.avatar_style || "")}
                onChange={(value) => updateTextField("avatar_style", value)}
              />
              <TextInput
                label="Caminho/imagem de referência"
                value={String(form.avatar_image_path || "")}
                onChange={(value) => updateTextField("avatar_image_path", value)}
              />
            </ProfileSection>

            <ProfileSection title="Consentimentos" description="Autorizações explícitas para uso futuro de voz e imagem.">
              <div className="grid gap-4">
                <p className="rounded-md border border-gold-500/20 bg-gold-500/10 px-4 py-3 text-sm leading-6 text-gold-100">
                  Use apenas voz e imagem próprias ou de pessoas que autorizaram expressamente.
                </p>
                <CheckboxInput
                  label="Autorizo o uso da minha voz para geração de narração por IA."
                  checked={form.consent_voice_clone}
                  onChange={(checked) => updateCheckbox("consent_voice_clone", checked)}
                />
                <CheckboxInput
                  label="Autorizo o uso da minha imagem/avatar para geração de vídeos por IA."
                  checked={form.consent_avatar_use}
                  onChange={(checked) => updateCheckbox("consent_avatar_use", checked)}
                />
                <TextArea
                  label="Texto dos termos/observações de consentimento"
                  value={String(form.consent_terms_text || "")}
                  onChange={(value) => updateTextField("consent_terms_text", value)}
                />
              </div>
            </ProfileSection>

            {message ? <p className="rounded-md border border-gold-500/20 bg-gold-500/10 px-4 py-3 text-sm text-gold-200">{message}</p> : null}
            {error ? <p className="rounded-md border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p> : null}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="rounded-md bg-gold-500 px-5 py-3 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "Salvando..." : "Salvar perfil"}
              </button>
            </div>
          </form>
        )}
      </div>
    </AppShell>
  );
}

function ProfileSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-white/10 bg-white/[0.03] p-5">
      <div className="mb-5">
        <h2 className="text-xl font-semibold text-white">{title}</h2>
        <p className="mt-1 text-sm text-slate-400">{description}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">{children}</div>
    </section>
  );
}

function TextInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-gold-500/60"
      />
    </label>
  );
}

function TextArea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2 text-sm text-slate-300 md:col-span-2">
      {label}
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        className="resize-y rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm leading-6 text-slate-100 outline-none transition focus:border-gold-500/60"
      />
    </label>
  );
}

function CheckboxInput({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 rounded-md border border-white/10 bg-black/20 p-3 text-sm text-slate-200 md:col-span-2">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 accent-gold-500"
      />
      <span>{label}</span>
    </label>
  );
}
