export type CoveragePlanStatus =
  | "pending"
  | "processing"
  | "generated"
  | "requires_review"
  | "invalid"
  | "ready_for_review"
  | "approved"
  | "stale"
  | "failed"
  | "not_started";

export type CoveragePlanModuleStatus = "planned" | "requires_review" | "approved" | "stale";
export type CoveragePlanLessonStatus = "planned" | "requires_review" | "approved" | "stale";

export type CoveragePlanRegenerateMode =
  | "generate_if_missing"
  | "regenerate_draft"
  | "validate_only"
  | "recalculate_estimates"
  | "rebuild_from_inventory"
  | "preserve_manual_changes";

export type CoveragePlanLessonSourceItem = {
  source_item_id: string;
  item_code: string;
  title: string;
  content_type: string;
  importance: string;
  page_start: number | null;
  page_end: number | null;
  status: string;
  coverage_type: string;
  source_order_in_lesson: number;
  is_required: boolean;
  coverage_notes: string | null;
};

export type CoveragePlanLesson = {
  id: string;
  coverage_plan_id: string;
  module_id: string;
  title: string;
  description: string | null;
  learning_objective: string | null;
  lesson_order: number;
  target_duration_minutes: string | null;
  estimated_duration_minutes: string;
  estimated_source_words: number;
  estimated_explanation_words: number;
  estimated_transition_words: number;
  estimated_word_count: number;
  source_item_count: number;
  status: CoveragePlanLessonStatus;
  plan_version: number;
  requires_review: boolean;
  grouping_reason: string | null;
  warnings_json: string[] | null;
  generated_content_id: string | null;
  created_at: string;
  updated_at: string;
  source_items: CoveragePlanLessonSourceItem[];
};

export type CoveragePlanModule = {
  id: string;
  coverage_plan_id: string;
  project_id: string;
  title: string;
  description: string | null;
  learning_objective: string | null;
  module_order: number;
  estimated_total_minutes: string;
  estimated_total_words: number;
  source_item_count: number;
  status: CoveragePlanModuleStatus;
  plan_version: number;
  created_at: string;
  updated_at: string;
  lessons: CoveragePlanLesson[];
};

export type CoveragePlan = {
  id: string;
  project_id: string;
  project_file_id: string;
  version: number;
  status: CoveragePlanStatus;
  inventory_item_count: number;
  total_modules: number;
  total_lessons: number;
  total_items: number;
  mapped_items: number;
  unmapped_items: number;
  estimated_total_words: number;
  estimated_total_minutes: string;
  model_name: string | null;
  prompt_version: string | null;
  settings_json: Record<string, unknown> | null;
  report_data: Record<string, unknown> | null;
  error_message: string | null;
  approved_at: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
  modules: CoveragePlanModule[];
};

export type CoveragePlanVersion = {
  id: string;
  version: number;
  status: CoveragePlanStatus;
  total_modules: number;
  total_lessons: number;
  total_items: number;
  mapped_items: number;
  unmapped_items: number;
  created_at: string;
  approved_at: string | null;
};

export type CoveragePlanSummary = {
  project_id: string;
  project_file_id: string;
  status: CoveragePlanStatus;
  version: number;
  total_modules: number;
  total_lessons: number;
  total_items: number;
  mapped_items: number;
  unmapped_items: number;
  lessons_over_limit: number;
  lessons_under_recommended_duration: number;
  modules_without_lessons: number;
  lessons_without_sources: number;
  dependency_violations: number;
  requires_review_items: number;
  pages_requires_ocr: number;
  estimated_total_words: number;
  estimated_total_minutes: string;
  model_name: string | null;
  prompt_version: string | null;
  generated_at: string | null;
  approved_at: string | null;
  warnings: string[];
};

export type UnmappedSourceItem = {
  source_item_id: string;
  item_code: string;
  title: string;
  content_type: string;
  importance: string;
  page_start: number | null;
  page_end: number | null;
  status: string;
  reason: string;
  recommended_action: string;
};

export type CoveragePlanValidationIssue = {
  issue_type: string;
  severity: string;
  message: string;
  module_id: string | null;
  lesson_id: string | null;
  source_item_id: string | null;
};

export type CoveragePlanValidationResult = {
  status: string;
  total_source_items: number;
  mapped_items: number;
  unmapped_items: number;
  duplicate_mappings: number;
  lessons_over_limit: number;
  lessons_under_recommended_duration: number;
  modules_without_lessons: number;
  lessons_without_sources: number;
  dependency_violations: number;
  requires_review_source_items: number;
  pages_requires_ocr: number;
  issues: CoveragePlanValidationIssue[];
  warnings: string[];
};

export type CoveragePlanModuleUpdate = {
  title?: string;
  description?: string;
  learning_objective?: string;
  module_order?: number;
  status?: CoveragePlanModuleStatus;
};

export type CoveragePlanLessonUpdate = {
  title?: string;
  description?: string;
  learning_objective?: string;
  lesson_order?: number;
  module_id?: string;
  status?: CoveragePlanLessonStatus;
};

export type CoveragePlanLessonSplitRequest = {
  first_title: string;
  second_title: string;
  first_source_item_ids: string[];
  second_source_item_ids: string[];
  first_description?: string;
  second_description?: string;
  first_learning_objective?: string;
  second_learning_objective?: string;
};

export type CoveragePlanLessonMergeRequest = {
  lesson_ids: string[];
  title: string;
  description?: string;
  learning_objective?: string;
};

export type CoveragePlanLessonSourceItemAddRequest = {
  source_item_id: string;
  coverage_type?: string;
  is_required?: boolean;
  source_order_in_lesson?: number;
  coverage_notes?: string;
};
