const PROJECT_STATUS_LABELS: Record<string, string> = {
  active: "Ativo",
  archived: "Arquivado",
};

const PROCESSING_STATUS_LABELS: Record<string, string> = {
  draft: "Rascunho",
  uploaded: "Documento enviado",
  extracting_text: "Extraindo texto",
  text_extracted: "Texto extraído",
  ai_generating_structure: "Gerando estrutura",
  ai_structure_generated: "Estrutura gerada",
  ai_generating_educational_content: "Gerando conteúdos educacionais",
  educational_content_generated: "Conteúdos educacionais gerados",
  failed: "Falhou",
};

const JOB_STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  running: "Em execução",
  completed: "Concluído",
  failed: "Falhou",
  cancelled: "Cancelado",
  partially_completed: "Parcialmente concluído",
};

const FILE_STATUS_LABELS: Record<string, string> = {
  uploaded: "Enviado",
};

const CONTENT_STATUS_LABELS: Record<string, string> = {
  generated: "Gerado",
  approved: "Aprovado",
  rejected: "Rejeitado",
};

const LOG_LEVEL_LABELS: Record<string, string> = {
  info: "Informação",
  warning: "Aviso",
  error: "Erro",
};

const PRODUCT_TYPE_LABELS: Record<string, string> = {
  course: "Curso",
};

function translate(map: Record<string, string>, value: string): string {
  return map[value] || value;
}

export function translateProjectStatus(status: string): string {
  return translate(PROJECT_STATUS_LABELS, status);
}

export function translateProcessingStatus(status: string): string {
  return translate(PROCESSING_STATUS_LABELS, status);
}

export function translateJobStatus(status: string): string {
  return translate(JOB_STATUS_LABELS, status);
}

export function translateFileStatus(status: string): string {
  return translate(FILE_STATUS_LABELS, status);
}

export function translateContentStatus(status: string): string {
  return translate(CONTENT_STATUS_LABELS, status);
}

export function translateLogLevel(level: string): string {
  return translate(LOG_LEVEL_LABELS, level);
}

export function translateProductType(productType: string): string {
  return translate(PRODUCT_TYPE_LABELS, productType);
}
