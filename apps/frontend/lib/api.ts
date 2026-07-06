import { getToken } from "./auth";
import type { GenerateStructureResponse } from "@/types/ai";
import type {
  ComplementaryMaterialContent,
  GenerateEducationalContentResponse,
  LessonScriptContent,
  ModuleQuizContent,
  PresentationDeckContent,
} from "@/types/educational-content";
import type { GeneratedContent } from "@/types/content";
import type { ProcessingJob, StartAIJobResponse } from "@/types/processing";

export type GenerationLanguage = "pt-BR" | "en-US";

export type GenerateNarrationAudioPayload = {
  generated_content_id?: string | null;
  block_index: number;
  title?: string | null;
  text: string;
  voice?: string | null;
  model?: string | null;
  format?: string;
};

export type GeneratedAudio = {
  id: string;
  project_id: string;
  generated_content_id: string | null;
  block_index: number;
  title: string | null;
  voice_provider: string | null;
  voice: string | null;
  model: string | null;
  format: string;
  personalized_voice_used: boolean;
  voice_notice: string | null;
  duration_seconds: number | null;
  status: string;
  created_at: string;
  download_url: string;
};

export type NarrationAudiosZipParams = {
  scope: "lesson" | "module" | "all";
  generated_content_id?: string | null;
  module_number?: number | null;
  title_contains?: string | null;
};

export type VideoProvider = "mock" | "heygen" | "did" | "sync";

export type GenerateProjectVideoPayload = {
  lesson_id?: string | null;
  module_id?: string | null;
  audio_id?: string | null;
  video_avatar_id?: string | null;
  provider?: VideoProvider | null;
  avatar_id?: string | null;
  avatar_name?: string | null;
  source_image_url?: string | null;
  source_video_url?: string | null;
  model?: string | null;
  resolution?: string | null;
  format?: string | null;
  extra_metadata?: Record<string, unknown> | null;
};

export type VideoAvatar = {
  id: string;
  project_id: string | null;
  name: string;
  provider: VideoProvider;
  avatar_id: string | null;
  source_image_url: string | null;
  source_video_url: string | null;
  default_model: string | null;
  description: string | null;
  is_active: boolean;
  is_default: boolean;
  extra_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string | null;
};

export type VideoAvatarCreatePayload = {
  name: string;
  provider: VideoProvider;
  avatar_id?: string | null;
  source_image_url?: string | null;
  source_video_url?: string | null;
  default_model?: string | null;
  description?: string | null;
  is_active?: boolean;
  is_default?: boolean;
};

export type VideoAvatarUpdatePayload = {
  name?: string;
  provider?: VideoProvider;
  avatar_id?: string | null;
  source_image_url?: string | null;
  source_video_url?: string | null;
  default_model?: string | null;
  description?: string | null;
  is_active?: boolean;
  is_default?: boolean;
};

export type GeneratedVideo = {
  id: string;
  project_id: string;
  lesson_id: string | null;
  module_id: string | null;
  audio_id: string | null;
  avatar_id: string | null;
  avatar_name: string | null;
  provider: string;
  status: string;
  resolution: string;
  format: string;
  file_name: string | null;
  file_size_bytes: number | null;
  duration_seconds: number | null;
  error_message: string | null;
  extra_metadata: Record<string, unknown> | null;
  provider_job_id: string | null;
  remote_video_url: string | null;
  source_image_url: string | null;
  source_video_url: string | null;
  last_status_check_at: string | null;
  created_at: string;
  updated_at: string | null;
  completed_at: string | null;
  generation_started_at: string | null;
  generation_completed_at: string | null;
  provider_latency_seconds: number | null;
  estimated_cost_usd: number | null;
  quality_rating: number | null;
  quality_notes: string | null;
  download_url: string | null;
};

export type VideoReviewUpdatePayload = {
  quality_rating?: number | null;
  quality_notes?: string | null;
  estimated_cost_usd?: number | null;
};

export type InstructorProfilePayload = {
  display_name: string | null;
  bio: string | null;
  teaching_style: string | null;
  voice_provider: string | null;
  voice_id: string | null;
  voice_name: string | null;
  voice_sample_notes: string | null;
  avatar_provider: string | null;
  avatar_id: string | null;
  avatar_name: string | null;
  avatar_style: string | null;
  avatar_image_path: string | null;
  consent_voice_clone: boolean;
  consent_avatar_use: boolean;
  consent_terms_text: string | null;
};

export type InstructorProfile = InstructorProfilePayload & {
  id: string;
  user_id: string;
  consent_updated_at: string | null;
  created_at: string;
  updated_at: string | null;
};

export type InstructorAssetType = "voice_sample" | "avatar_image";

export type InstructorAsset = {
  id: string;
  user_id: string;
  instructor_profile_id: string | null;
  asset_type: InstructorAssetType;
  original_filename: string | null;
  stored_filename: string;
  mime_type: string | null;
  size_bytes: number | null;
  description: string | null;
  consent_confirmed: boolean;
  created_at: string;
  updated_at: string | null;
  download_url: string;
};

export type InstructorAssetUpdatePayload = {
  description?: string | null;
  consent_confirmed?: boolean;
};

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

export async function getDocumentAnalysis(projectId: string): Promise<GeneratedContent | null> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedContent | null>(`/projects/${projectId}/document-analysis`, { token });
}

export async function generateDocumentAnalysis(projectId: string): Promise<GeneratedContent> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedContent>(`/projects/${projectId}/document-analysis/generate`, {
    method: "POST",
    token,
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

export async function getInstructorProfile(): Promise<InstructorProfile | null> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<InstructorProfile | null>("/instructor-profile", { token });
}

export async function saveInstructorProfile(payload: InstructorProfilePayload): Promise<InstructorProfile> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<InstructorProfile>("/instructor-profile", {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}

export async function listInstructorAssets(assetType?: InstructorAssetType): Promise<InstructorAsset[]> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  const query = assetType ? `?asset_type=${encodeURIComponent(assetType)}` : "";
  return apiFetch<InstructorAsset[]>(`/instructor-assets${query}`, { token });
}

export async function uploadInstructorAsset(payload: {
  file: File;
  asset_type: InstructorAssetType;
  description?: string;
  consent_confirmed: boolean;
}): Promise<InstructorAsset> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  const formData = new FormData();
  formData.append("file", payload.file);
  formData.append("asset_type", payload.asset_type);
  formData.append("consent_confirmed", String(payload.consent_confirmed));
  if (payload.description) {
    formData.append("description", payload.description);
  }

  return apiFetch<InstructorAsset>("/instructor-assets/upload", {
    method: "POST",
    token,
    body: formData,
  });
}

export async function updateInstructorAsset(
  assetId: string,
  payload: InstructorAssetUpdatePayload,
): Promise<InstructorAsset> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<InstructorAsset>(`/instructor-assets/${assetId}`, {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}

export async function deleteInstructorAsset(assetId: string): Promise<{ message: string }> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<{ message: string }>(`/instructor-assets/${assetId}`, {
    method: "DELETE",
    token,
  });
}

export function getInstructorAssetDownloadUrl(assetId: string): string {
  return `${baseURL}/instructor-assets/${assetId}/download`;
}

export async function fetchInstructorAssetBlob(assetId: string): Promise<Blob> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  const response = await fetch(getInstructorAssetDownloadUrl(assetId), {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiEnvelope<unknown> | null;
    throw new ApiError(getApiErrorMessage(payload), response.status);
  }

  return response.blob();
}

export async function downloadInstructorAsset(asset: InstructorAsset): Promise<void> {
  const blob = await fetchInstructorAssetBlob(asset.id);
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = asset.original_filename || asset.stored_filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export function getPresentationExportUrl(projectId: string): string {
  return `${baseURL}/projects/${projectId}/exports/presentation.pdf`;
}

export function getPresentationPptxExportUrl(projectId: string): string {
  return `${baseURL}/projects/${projectId}/exports/presentation.pptx`;
}

export function getLessonScriptsExportUrl(projectId: string): string {
  return `${baseURL}/projects/${projectId}/exports/lesson-scripts.pdf`;
}

export function getQuizzesExportUrl(projectId: string): string {
  return `${baseURL}/projects/${projectId}/exports/quizzes.pdf`;
}

export function getComplementaryMaterialsExportUrl(projectId: string): string {
  return `${baseURL}/projects/${projectId}/exports/complementary-materials.pdf`;
}

export function getFullCourseExportUrl(projectId: string): string {
  return `${baseURL}/projects/${projectId}/exports/full-course.pdf`;
}

export function getAudioDownloadUrl(projectId: string, audioId: string): string {
  return `${baseURL}/projects/${projectId}/audio/${audioId}/download`;
}

export function getVideoDownloadUrl(projectId: string, videoId: string): string {
  return `${baseURL}/projects/${projectId}/videos/${videoId}/download`;
}

export function getAudiosZipExportUrl(projectId: string, params: NarrationAudiosZipParams): string {
  const searchParams = new URLSearchParams();
  searchParams.set("scope", params.scope);
  if (params.generated_content_id) searchParams.set("generated_content_id", params.generated_content_id);
  if (params.module_number) searchParams.set("module_number", String(params.module_number));
  if (params.title_contains) searchParams.set("title_contains", params.title_contains);
  return `${baseURL}/projects/${projectId}/audio/export.zip?${searchParams.toString()}`;
}

export async function generateNarrationAudio(
  projectId: string,
  payload: GenerateNarrationAudioPayload,
): Promise<GeneratedAudio> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<GeneratedAudio>(`/projects/${projectId}/audio/generate`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export async function listProjectAudios(projectId: string): Promise<GeneratedAudio[]> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<GeneratedAudio[]>(`/projects/${projectId}/audio`, { token });
}

export async function deleteProjectAudio(projectId: string, audioId: string): Promise<{ message: string }> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  return apiFetch<{ message: string }>(`/projects/${projectId}/audio/${audioId}`, {
    method: "DELETE",
    token,
  });
}

export async function fetchNarrationAudioBlob(projectId: string, audioId: string): Promise<Blob> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessão expirou. Faça login novamente.", 401);
  }

  const response = await fetch(getAudioDownloadUrl(projectId, audioId), {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiEnvelope<unknown> | null;
    throw new ApiError(getApiErrorMessage(payload), response.status);
  }

  return response.blob();
}

export async function downloadNarrationAudio(projectId: string, audio: GeneratedAudio): Promise<void> {
  const blob = await fetchNarrationAudioBlob(projectId, audio.id);
  const filename = `${audio.title || "narration-audio"}-${audio.id}.${audio.format || "mp3"}`;
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

function getFilenameFromContentDisposition(value: string | null, fallback: string): string {
  if (!value) return fallback;
  const match = value.match(/filename="?([^"]+)"?/i);
  return match?.[1] || fallback;
}

export async function downloadNarrationAudiosZip(
  projectId: string,
  params: NarrationAudiosZipParams,
  fallbackFilename = "audios.zip",
): Promise<void> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  const response = await fetch(getAudiosZipExportUrl(projectId, params), {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiEnvelope<unknown> | null;
    throw new ApiError(getApiErrorMessage(payload), response.status);
  }

  const blob = await response.blob();
  const filename = getFilenameFromContentDisposition(response.headers.get("Content-Disposition"), fallbackFilename);
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export async function listProjectVideos(projectId: string): Promise<GeneratedVideo[]> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedVideo[]>(`/projects/${projectId}/videos`, { token });
}

export async function generateProjectVideo(
  projectId: string,
  payload: GenerateProjectVideoPayload,
): Promise<GeneratedVideo> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedVideo>(`/projects/${projectId}/videos/generate`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export async function getProjectVideo(projectId: string, videoId: string): Promise<GeneratedVideo> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedVideo>(`/projects/${projectId}/videos/${videoId}`, { token });
}

export async function refreshProjectVideoStatus(projectId: string, videoId: string): Promise<GeneratedVideo> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedVideo>(`/projects/${projectId}/videos/${videoId}/refresh-status`, {
    method: "POST",
    token,
  });
}

export async function updateProjectVideoReview(
  projectId: string,
  videoId: string,
  payload: VideoReviewUpdatePayload,
): Promise<GeneratedVideo> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<GeneratedVideo>(`/projects/${projectId}/videos/${videoId}/review`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export async function deleteProjectVideo(projectId: string, videoId: string): Promise<{ message: string }> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<{ message: string }>(`/projects/${projectId}/videos/${videoId}`, {
    method: "DELETE",
    token,
  });
}

export async function listProjectVideoAvatars(projectId: string): Promise<VideoAvatar[]> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<VideoAvatar[]>(`/projects/${projectId}/video-avatars`, { token });
}

export async function createProjectVideoAvatar(
  projectId: string,
  payload: VideoAvatarCreatePayload,
): Promise<VideoAvatar> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<VideoAvatar>(`/projects/${projectId}/video-avatars`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export async function updateProjectVideoAvatar(
  projectId: string,
  avatarId: string,
  payload: VideoAvatarUpdatePayload,
): Promise<VideoAvatar> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<VideoAvatar>(`/projects/${projectId}/video-avatars/${avatarId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export async function deleteProjectVideoAvatar(projectId: string, avatarId: string): Promise<{ message: string }> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  return apiFetch<{ message: string }>(`/projects/${projectId}/video-avatars/${avatarId}`, {
    method: "DELETE",
    token,
  });
}

export async function downloadProjectVideo(
  projectId: string,
  videoId: string,
  fallbackFilename = "video.mp4",
): Promise<void> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  const response = await fetch(getVideoDownloadUrl(projectId, videoId), {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiEnvelope<unknown> | null;
    throw new ApiError(getApiErrorMessage(payload), response.status);
  }

  const blob = await response.blob();
  const filename = getFilenameFromContentDisposition(
    response.headers.get("Content-Disposition"),
    fallbackFilename,
  );
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
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

export async function downloadPresentationPptx(projectId: string): Promise<void> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃ£o expirou. FaÃ§a login novamente.", 401);
  }

  const response = await fetch(getPresentationPptxExportUrl(projectId), {
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
  const filename = filenameMatch?.[1] || `presentation-${projectId}.pptx`;
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export async function downloadLessonScriptsPdf(projectId: string): Promise<void> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃƒÂ£o expirou. FaÃƒÂ§a login novamente.", 401);
  }

  const response = await fetch(getLessonScriptsExportUrl(projectId), {
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
  const filename = filenameMatch?.[1] || `lesson-scripts-${projectId}.pdf`;
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export async function downloadQuizzesPdf(projectId: string): Promise<void> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃƒÂ£o expirou. FaÃƒÂ§a login novamente.", 401);
  }

  const response = await fetch(getQuizzesExportUrl(projectId), {
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
  const filename = filenameMatch?.[1] || `quizzes-${projectId}.pdf`;
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export async function downloadComplementaryMaterialsPdf(projectId: string): Promise<void> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃƒÂ£o expirou. FaÃƒÂ§a login novamente.", 401);
  }

  const response = await fetch(getComplementaryMaterialsExportUrl(projectId), {
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
  const filename = filenameMatch?.[1] || `complementary-materials-${projectId}.pdf`;
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export async function downloadFullCoursePdf(projectId: string): Promise<void> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃƒÂ£o expirou. FaÃƒÂ§a login novamente.", 401);
  }

  const response = await fetch(getFullCourseExportUrl(projectId), {
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
  const filename = filenameMatch?.[1] || `full-course-${projectId}.pdf`;
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

export async function updateComplementaryMaterial(
  projectId: string,
  contentId: string,
  complementaryMaterial: ComplementaryMaterialContent,
): Promise<GeneratedContent> {
  const token = getToken();
  if (!token) {
    throw new ApiError("Sua sessÃƒÂ£o expirou. FaÃƒÂ§a login novamente.", 401);
  }

  return apiFetch<GeneratedContent>(`/projects/${projectId}/educational-content/complementary-materials/${contentId}`, {
    method: "PUT",
    token,
    body: JSON.stringify(complementaryMaterial),
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
