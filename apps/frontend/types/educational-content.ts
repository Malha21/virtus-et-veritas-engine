import type { GeneratedContent } from "./content";

export type EducationalContentCounts = {
  lesson_scripts: number;
  module_quizzes: number;
  complementary_materials: number;
  course_summaries: number;
  presentation_decks: number;
};

export type GenerateEducationalContentResponse = {
  project_id: string;
  processing_status: "educational_content_generated" | string;
  message: string;
  contents_created: EducationalContentCounts;
};

export type EducationalContentSummaryResponse = {
  lesson_scripts: GeneratedContent[];
  module_quizzes: GeneratedContent[];
  complementary_materials: GeneratedContent[];
  course_summaries: GeneratedContent[];
  presentation_decks: GeneratedContent[];
};

export type LessonScriptContent = {
  lesson_script?: {
    course_title?: string;
    module_number?: number;
    module_title?: string;
    lesson_number?: number;
    lesson_title?: string;
    estimated_duration_minutes?: number;
    opening?: string;
    learning_objective?: string;
    main_script?: Array<{
      section_title?: string;
      narration?: string;
      teaching_notes?: string;
      visual_suggestion?: string;
    }>;
    practical_example?: string;
    reflection_question?: string;
    closing?: string;
    call_to_action?: string;
  };
};

export type ModuleQuizContent = {
  module_quiz?: {
    course_title?: string;
    module_number?: number;
    module_title?: string;
    instructions?: string;
    questions?: Array<{
      question_number?: number;
      question?: string;
      options?: Array<{
        letter?: string;
        text?: string;
      }>;
      correct_answer?: string;
      explanation?: string;
    }>;
  };
};

export type ComplementaryMaterialContent = {
  complementary_material?: {
    course_title?: string;
    material_title?: string;
    material_type?: string;
    overview?: string;
    key_concepts?: Array<{
      concept?: string;
      explanation?: string;
    }>;
    practical_applications?: string[];
    reflection_exercises?: string[];
    recommended_next_steps?: string[];
  };
};

export type CourseSummaryContent = {
  course_summary?: {
    title?: string;
    short_description?: string;
    long_description?: string;
    promise?: string;
    target_audience?: string;
    transformation_statement?: string;
    what_student_will_learn?: string[];
    course_differentials?: string[];
    suggested_sales_copy?: string;
    suggested_instagram_caption?: string;
    suggested_whatsapp_message?: string;
  };
};

export type PresentationDeckContent = {
  presentation_title?: unknown;
  target_audience?: unknown;
  estimated_duration?: unknown;
  visual_style?: unknown;
  presentation_objective?: unknown;
  slides?: Array<{
    slide_number?: unknown;
    title?: unknown;
    subtitle?: unknown;
    bullets?: unknown[];
    speaker_notes?: unknown;
    visual_suggestion?: unknown;
    interaction_question?: unknown;
  }>;
  closing_message?: unknown;
};
