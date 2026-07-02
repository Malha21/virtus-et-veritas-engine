export type ProcessingStatus = {
  project_id: string;
  processing_status: string;
  progress: number;
  current_step: string;
  updated_at: string;
};

export type ProcessingLog = {
  id: string;
  level: string;
  message: string;
  context_json: Record<string, unknown> | null;
  created_at: string;
};

export type ProcessingJob = {
  id: string;
  project_id: string;
  job_type?: string;
  status?: string;
  progress: number;
  current_step: string | null;
  message: string | null;
  error_message?: string | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type StartProcessingResponse = {
  project_id: string;
  processing_status: string;
  message: string;
  job_id: string;
};

export type StartAIJobResponse = {
  job_id: string;
  status: string;
  message: string;
};
