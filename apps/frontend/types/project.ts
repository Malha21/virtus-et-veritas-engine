export type Project = {
  id: string;
  title: string;
  slug: string;
  product_type: string;
  target_audience: string | null;
  tone_of_voice: string | null;
  desired_duration: string | null;
  description: string | null;
  status: string;
  processing_status: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

export type ProjectListItem = Pick<
  Project,
  "id" | "title" | "product_type" | "status" | "processing_status" | "created_at" | "updated_at"
>;

export type ProjectListResponse = {
  items: ProjectListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type ProjectCreate = {
  title: string;
  product_type: string;
  target_audience?: string;
  tone_of_voice?: string;
  desired_duration?: string;
  description?: string;
};
