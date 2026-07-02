import { getToken } from "./auth";
import type { GenerateStructureResponse } from "@/types/ai";
import type { GenerateEducationalContentResponse } from "@/types/educational-content";

export type GenerationLanguage = "pt-BR" | "en-US";

type ApiEnvelope<T> = {
  success: boolean;
  data?: T;
  detail?: string | Array<{ msg?: string }>;
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

const baseURL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getApiErrorMessage<T>(payload: ApiEnvelope<T> | null): string {
  if (payload?.error?.message) {
    return payload.error.message;
  }

  if (typeof payload?.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload?.detail)) {
    const validationMessage = payload.detail.find((item) => item.msg)?.msg;
    if (validationMessage?.includes("Idioma de geração inválido")) {
      return "Idioma de geração inválido.";
    }
    if (validationMessage) {
      return validationMessage;
    }
  }

  return "Nao foi possivel concluir a solicitacao.";
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const token = options.token ?? getToken();
  const headers = new Headers(options.headers);

  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;

  if (!headers.has("Content-Type") && options.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${baseURL}${path}`, {
    ...options,
    headers,
  });

  const payload = (await response.json().catch(() => null)) as ApiEnvelope<T> | null;

  if (!response.ok || payload?.success === false) {
    const message = getApiErrorMessage(payload);
    throw new ApiError(message, response.status);
  }

  return payload?.data as T;
}

export async function generateStructure(
  projectId: string,
  generationLanguage: GenerationLanguage = "pt-BR",
): Promise<GenerateStructureResponse> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<GenerateStructureResponse>(`/projects/${projectId}/generate-structure`, {
    method: "POST",
    token,
    body: JSON.stringify({ generation_language: generationLanguage }),
  });
}

export async function generateEducationalContent(
  projectId: string,
  generationLanguage: GenerationLanguage = "pt-BR",
): Promise<GenerateEducationalContentResponse> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<GenerateEducationalContentResponse>(`/projects/${projectId}/generate-educational-content`, {
    method: "POST",
    token,
    body: JSON.stringify({ generation_language: generationLanguage }),
  });
}

export async function deleteProject(projectId: string): Promise<{ message: string }> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<{ message: string }>(`/projects/${projectId}`, {
    method: "DELETE",
    token,
  });
}
