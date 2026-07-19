export type SourceContentItemStatus =
  | "pending"
  | "mapped"
  | "reviewed"
  | "approved"
  | "rejected"
  | "generated"
  | "validated"
  | "possible_duplicate"
  | "fragmented"
  | "requires_review";

export type SourceContentItemImportance = "essential" | "relevant" | "complementary";

export type SourceContentItem = {
  id: string;
  project_id: string;
  project_file_id: string;
  item_code: string;
  title: string;
  source_text: string;
  normalized_content: string | null;
  content_type: string;
  page_start: number | null;
  page_end: number | null;
  source_order: number;
  importance: SourceContentItemImportance;
  status: SourceContentItemStatus;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type SourceContentItemListResponse = {
  items: SourceContentItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type SourceContentItemBlock = {
  id: string;
  source_item_id: string;
  block_id: string;
  block_code: string;
  page_number: number;
  source_order: number;
  is_primary: boolean;
  created_at: string;
};

export type SourceItemDependency = {
  id: string;
  source_item_id: string;
  depends_on_source_item_id: string;
  dependency_type: string;
  created_at: string;
};

export type SourceContentItemDetail = SourceContentItem & {
  blocks: SourceContentItemBlock[];
  dependencies: SourceItemDependency[];
  dependents: SourceItemDependency[];
};

export type SourceInventorySummary = {
  project_id: string;
  project_file_id: string;
  status: string;
  inventory_version: number;
  total_pages: number;
  pages_processed: number;
  pages_not_processed: number;
  pages_requires_ocr: number;
  total_blocks: number;
  blocks_analyzed: number;
  blocks_ignored: number;
  total_chunks: number;
  chunks_completed: number;
  chunks_failed: number;
  total_items: number;
  items_by_type: Record<string, number>;
  items_by_importance: Record<string, number>;
  possible_duplicates: number;
  fragmented_items: number;
  requires_review_items: number;
  approved_items: number;
  rejected_items: number;
  page_coverage_percentage: number;
  block_coverage_percentage: number;
  model_name: string | null;
  prompt_version: string | null;
  generated_at: string | null;
};

export type SourceInventoryReprocessMode =
  | "generate_if_missing"
  | "reprocess_failed"
  | "reprocess_pages"
  | "full_rebuild"
  | "validate_only";

export type SourceInventoryItemManualUpdate = {
  title?: string;
  normalized_content?: string;
  content_type?: string;
  importance?: string;
  review_note?: string;
};

export type InventoryValidationIssue = {
  source_item_id: string | null;
  item_code: string | null;
  issue_type: string;
  message: string;
};

export type InventoryValidationResult = {
  status: string;
  total_items: number;
  valid_items: number;
  invalid_items: number;
  issues: InventoryValidationIssue[];
};
