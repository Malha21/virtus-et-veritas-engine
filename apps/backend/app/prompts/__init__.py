from app.prompts.course_structure_v1 import (
    COURSE_STRUCTURE_PROMPT_VERSION,
    build_course_structure_expansion_prompt,
    build_course_structure_prompt,
)
from app.prompts.complementary_material_v1 import (
    COMPLEMENTARY_MATERIAL_PROMPT_VERSION,
    build_complementary_material_prompt,
)
from app.prompts.coverage_lesson_script_v1 import (
    COVERAGE_LESSON_SCRIPT_PROMPT_VERSION,
    build_coverage_lesson_script_prompt,
)
from app.prompts.coverage_plan_v1 import COVERAGE_PLAN_PROMPT_VERSION, build_coverage_plan_prompt
from app.prompts.course_summary_v1 import COURSE_SUMMARY_PROMPT_VERSION, build_course_summary_prompt
from app.prompts.document_analysis_v1 import DOCUMENT_ANALYSIS_PROMPT_VERSION, build_document_analysis_prompt
from app.prompts.lesson_script_v1 import LESSON_SCRIPT_PROMPT_VERSION, build_lesson_script_prompt
from app.prompts.module_quiz_v1 import MODULE_QUIZ_PROMPT_VERSION, build_module_quiz_prompt
from app.prompts.presentation_deck_v1 import PRESENTATION_DECK_PROMPT_VERSION, build_presentation_deck_prompt
from app.prompts.source_inventory_v1 import (
    COVERAGE_CHECK_PROMPT_VERSION,
    SOURCE_INVENTORY_PROMPT_VERSION,
    build_coverage_check_prompt,
    build_source_inventory_chunk_prompt,
)

__all__ = [
    "COMPLEMENTARY_MATERIAL_PROMPT_VERSION",
    "COURSE_SUMMARY_PROMPT_VERSION",
    "COURSE_STRUCTURE_PROMPT_VERSION",
    "COVERAGE_CHECK_PROMPT_VERSION",
    "COVERAGE_LESSON_SCRIPT_PROMPT_VERSION",
    "COVERAGE_PLAN_PROMPT_VERSION",
    "DOCUMENT_ANALYSIS_PROMPT_VERSION",
    "LESSON_SCRIPT_PROMPT_VERSION",
    "MODULE_QUIZ_PROMPT_VERSION",
    "PRESENTATION_DECK_PROMPT_VERSION",
    "SOURCE_INVENTORY_PROMPT_VERSION",
    "build_complementary_material_prompt",
    "build_course_structure_expansion_prompt",
    "build_course_summary_prompt",
    "build_course_structure_prompt",
    "build_coverage_check_prompt",
    "build_coverage_lesson_script_prompt",
    "build_coverage_plan_prompt",
    "build_document_analysis_prompt",
    "build_lesson_script_prompt",
    "build_module_quiz_prompt",
    "build_presentation_deck_prompt",
    "build_source_inventory_chunk_prompt",
]
