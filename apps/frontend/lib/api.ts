import { getToken } from "./auth";
import type { GenerateEducationalContentResponse } from "@/types/educational-content";

type ApiEnvelope<T> = {
  success: boolean;
  data?: T;
  detail?: string;
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
    const message = payload?.error?.message || payload?.detail || "Nao foi possivel concluir a solicitacao.";
    throw new ApiError(message, response.status);
  }

  return payload?.data as T;
}

export async function generateEducationalContent(projectId: string): Promise<GenerateEducationalContentResponse> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<GenerateEducationalContentResponse>(`/projects/${projectId}/generate-educational-content`, {
    method: "POST",
    token,
  });
}
