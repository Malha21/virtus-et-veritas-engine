export type DocumentExtractionStatus =
  | "pending"
  | "processing"
  | "extracted"
  | "empty"
  | "failed"
  | "requires_ocr"
  | "reviewed";

export type DocumentBlockType =
  | "title"
  | "heading"
  | "paragraph"
  | "list_item"
  | "table"
  | "table_row"
  | "image_caption"
  | "footnote"
  | "quotation"
  | "page_header"
  | "page_footer"
  | "unknown";

export type DocumentBlock = {
  id: string;
  project_file_id: string;
  page_id: string;
  block_code: string;
  block_type: DocumentBlockType;
  block_order: number;
  source_text: string;
  normalized_text: string | null;
  bounding_box: Record<string, unknown> | null;
  confidence_score: number | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type DocumentPage = {
  id: string;
  project_file_id: string;
  page_number: number;
  raw_text: string | null;
  normalized_text: string | null;
  character_count: number;
  word_count: number;
  extraction_status: DocumentExtractionStatus;
  extraction_method: string | null;
  has_text: boolean;
  requires_ocr: boolean;
  metadata_json: Record<string, unknown> | null;
  block_count: number;
  created_at: string;
  updated_at: string;
};

export type DocumentPageDetail = DocumentPage & { blocks: DocumentBlock[] };

export type DocumentPageListResponse = {
  items: DocumentPage[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type DocumentBlockListResponse = { items: DocumentBlock[] };

export type DocumentExtractionSummary = {
  project_file_id: string;
  total_pages: number;
  extracted_pages: number;
  empty_pages: number;
  failed_pages: number;
  requires_ocr_pages: number;
  total_characters: number;
  total_words: number;
  total_blocks: number;
  blocks_by_type: Record<string, number>;
  extraction_method: string | null;
  status: string;
  last_extracted_at: string | null;
};

export type DocumentReprocessScope = "all" | "failed" | "requires_ocr" | "page";
