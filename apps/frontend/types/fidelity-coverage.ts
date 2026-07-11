// Tipos do frontend para a central global "Fidelidade e Cobertura".
// Espelham os models/schemas do backend (fase 19.1: source_content_items,
// lesson_source_items, lesson_generations, course_coverage_reports), adaptados
// para o consumo ainda parcial: a API ainda nao expõe endpoints dedicados para
// estas entidades, entao os campos abaixo sao majoritariamente opcionais/nulos
// ate que essas rotas existam.

export type CoverageStatus =
  | "pending"
  | "processing"
  | "passed"
  | "failed"
  | "requires_review"
  | "approved_with_exceptions";

export type AuditStatus = "pending" | "valid" | "invalid" | "requires_review" | "approved";

export type FidelityIssueType =
  | "unsupported_claim"
  | "duration_violation"
  | "duplicate_content"
  | "missing_coverage"
  | "other";

export type FidelityIssue = {
  id: string;
  project_id: string;
  type: FidelityIssueType;
  description: string;
  severity: "low" | "medium" | "high";
  lesson_id?: string | null;
  source_item_id?: string | null;
  created_at: string;
};

export type FidelityCoverageProjectSummary = {
  project_id: string;
  project_title: string;
  product_type: string;
  processing_status: string;
  primary_document_name: string | null;
  last_analysis_at: string | null;
  total_source_items: number | null;
  coverage_percentage: number | null;
  fidelity_score: number | null;
  pending_issues: number | null;
  coverage_status: CoverageStatus | null;
};

export type FidelityCoverageGlobalMetrics = {
  total_projects_analyzed: number | null;
  projects_inventory_completed: number | null;
  projects_awaiting_audit: number | null;
  projects_with_pending_issues: number | null;
  projects_approved: number | null;
  average_coverage_percentage: number | null;
  items_without_coverage: number | null;
  unsupported_claims: number | null;
  lessons_over_ten_minutes: number | null;
};

export type ProjectCoverageReport = {
  version: number;
  status: CoverageStatus;
  coverage_percentage: number;
  fidelity_score: number | null;
  total_source_items: number;
  covered_items: number;
  partially_covered_items: number;
  uncovered_items: number;
  unsupported_claims: number;
  duration_violations: number;
  duplicate_content_count: number;
  created_at: string;
};

export type ProjectCoverageDetails = {
  project_id: string;
  latest_report: ProjectCoverageReport | null;
  issues: FidelityIssue[];
};
