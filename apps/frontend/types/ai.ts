export type GenerateStructureResponse = {
  project_id: string;
  processing_status: "ai_structure_generated" | string;
  message: string;
  contents: {
    document_analysis_id: string;
    course_structure_id: string;
  };
};
