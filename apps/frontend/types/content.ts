export type GeneratedContent = {
  id: string;
  project_id: string;
  organization_id: string;
  content_type:
    | "document_analysis"
    | "course_structure"
    | "lesson_script"
    | "module_quiz"
    | "complementary_material"
    | "course_summary"
    | string;
  title: string | null;
  version: number;
  language: string;
  content_json: Record<string, unknown> | null;
  content_text: string | null;
  status: string;
  created_by_ai_provider_id: string | null;
  created_at: string;
  updated_at: string;
};

export type GeneratedContentListResponse = {
  items: GeneratedContent[];
};

export type DocumentAnalysisContent = {
  document_analysis?: {
    main_theme?: string;
    subthemes?: string[];
    complexity_level?: string;
    recommended_audience?: string;
    recommended_product_type?: string;
    didactic_risks?: string[];
    opportunities?: string[];
    suggested_approach?: string;
  };
};

export type CourseStructureContent = {
  course?: {
    title?: string;
    promise?: string;
    description?: string;
    target_audience?: string;
    learning_objectives?: string[];
    modules?: Array<{
      module_number?: number;
      title?: string;
      description?: string;
      learning_goal?: string;
      lessons?: Array<{
        lesson_number?: number;
        title?: string;
        summary?: string;
        estimated_duration_minutes?: number;
        learning_objective?: string;
      }>;
    }>;
  };
};
