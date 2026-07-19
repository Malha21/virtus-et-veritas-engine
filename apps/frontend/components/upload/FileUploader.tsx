"use client";

import { ChangeEvent, DragEvent, useState } from "react";

import { apiFetch } from "@/lib/api";
import type { ProjectFile } from "@/types/file";

type FileUploaderProps = {
  projectId: string;
  onUploaded?: (file: ProjectFile) => void;
};

export function FileUploader({ projectId, onUploaded }: FileUploaderProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const ALLOWED_MIME_TYPES = ["application/pdf", "application/epub+zip"];
  const ALLOWED_EXTENSIONS = [".pdf", ".epub"];

  function validateFile(file: File): boolean {
    const lowerName = file.name.toLowerCase();
    const hasAllowedExtension = ALLOWED_EXTENSIONS.some((extension) => lowerName.endsWith(extension));

    if (!hasAllowedExtension) {
      setError("O arquivo precisa ter extensão .pdf ou .epub.");
      return false;
    }

    if (file.type && !ALLOWED_MIME_TYPES.includes(file.type)) {
      setError("Envie apenas arquivos PDF ou EPUB.");
      return false;
    }

    setError("");
    return true;
  }

  function chooseFile(file: File | null) {
    setSuccess("");
    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (validateFile(file)) {
      setSelectedFile(file);
    } else {
      setSelectedFile(null);
    }
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0] || null);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    chooseFile(event.dataTransfer.files?.[0] || null);
  }

  async function uploadFile() {
    if (!selectedFile) {
      setError("Selecione um PDF ou EPUB antes de enviar.");
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const uploadedFile = await apiFetch<ProjectFile>(`/projects/${projectId}/files`, {
        method: "POST",
        body: formData,
      });
      setSuccess("Arquivo enviado com sucesso.");
      setSelectedFile(null);
      onUploaded?.(uploadedFile);
    } catch {
      setError("Não foi possível enviar o arquivo. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] p-5">
      <label
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        className="flex min-h-40 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-gold-500/35 bg-navy-950/60 px-5 py-8 text-center transition hover:border-gold-400"
      >
        <span className="text-sm font-medium text-gold-400">Selecionar PDF ou EPUB</span>
        <span className="mt-2 max-w-md text-sm text-slate-300">
          Arraste o arquivo para esta área ou clique para escolher o PDF ou EPUB-base do curso.
        </span>
        <input
          type="file"
          accept="application/pdf,.pdf,application/epub+zip,.epub"
          onChange={handleInputChange}
          className="hidden"
        />
      </label>

      {selectedFile ? (
        <p className="mt-4 text-sm text-slate-200">
          Arquivo selecionado: <span className="text-white">{selectedFile.name}</span>
        </p>
      ) : null}

      {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}
      {success ? <p className="mt-4 text-sm text-emerald-300">{success}</p> : null}

      <button
        type="button"
        onClick={uploadFile}
        disabled={loading || !selectedFile}
        className="mt-5 rounded-md bg-gold-500 px-4 py-2 text-sm font-semibold text-navy-950 transition hover:bg-gold-400 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Enviando..." : "Enviar arquivo"}
      </button>
    </div>
  );
}
