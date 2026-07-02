export type ProjectFile = {
  id: string;
  project_id: string;
  file_type: string;
  original_filename: string;
  mime_type: string | null;
  file_size: number | null;
  status: string;
  created_at: string;
};

export type ProjectFileListResponse = ProjectFile[];
