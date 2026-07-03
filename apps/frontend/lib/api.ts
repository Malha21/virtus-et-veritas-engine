import { getToken } from "./auth";
import type { GenerateStructureResponse } from "@/types/ai";
import type {
  GenerateEducationalContentResponse,
  LessonScriptContent,
  ModuleQuizContent,
  PresentationDeckContent,
} from "@/types/educational-content";
import type { GeneratedContent } from "@/types/content";
import type { ProcessingJob, StartAIJobResponse } from "@/types/processing";

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

export async function startAiStructureJob(
  projectId: string,
  generationLanguage: GenerationLanguage = "pt-BR",
): Promise<StartAIJobResponse> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<StartAIJobResponse>(`/projects/${projectId}/ai-structure/jobs`, {
    method: "POST",
    token,
    body: JSON.stringify({ generation_language: generationLanguage }),
  });
}

export async function startEducationalContentJob(
  projectId: string,
  generationLanguage: GenerationLanguage = "pt-BR",
): Promise<StartAIJobResponse> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<StartAIJobResponse>(`/projects/${projectId}/educational-content/jobs`, {
    method: "POST",
    token,
    body: JSON.stringify({ generation_language: generationLanguage }),
  });
}

export async function getProjectJob(projectId: string, jobId: string): Promise<ProcessingJob> {
  return apiFetch<ProcessingJob>(`/projects/${projectId}/jobs/${jobId}`);
}

export function getPresentationExportUrl(projectId: string): string {
  return `${baseURL}/projects/${projectId}/exports/presentation.pdf`;
}

export async function downloadPresentationPdf(projectId: string): Promise<void> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  const response = await fetch(getPresentationExportUrl(projectId), {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiEnvelope<unknown> | null;
    throw new ApiError(getApiErrorMessage(payload), response.status);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);
  const filename = filenameMatch?.[1] || `presentation-${projectId}.pdf`;
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export async function updatePresentationDeck(
  projectId: string,
  presentationDeck: PresentationDeckContent,
): Promise<GeneratedContent> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedContent>(`/projects/${projectId}/educational-content/presentation-deck`, {
    method: "PUT",
    token,
    body: JSON.stringify(presentationDeck),
  });
}

export async function updateLessonScript(
  projectId: string,
  contentId: string,
  lessonScript: LessonScriptContent,
): Promise<GeneratedContent> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedContent>(`/projects/${projectId}/educational-content/lesson-scripts/${contentId}`, {
    method: "PUT",
    token,
    body: JSON.stringify(lessonScript),
  });
}

export async function updateModuleQuiz(
  projectId: string,
  contentId: string,
  moduleQuiz: ModuleQuizContent,
): Promise<GeneratedContent> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedContent>(`/projects/${projectId}/educational-content/module-quizzes/${contentId}`, {
    method: "PUT",
    token,
    body: JSON.stringify(moduleQuiz),
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
