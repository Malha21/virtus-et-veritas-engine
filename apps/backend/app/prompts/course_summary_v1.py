import json
from typing import Any

from app.models.project import Project

COURSE_SUMMARY_PROMPT_VERSION = "course_summary_v1"

SYSTEM_PROMPT = """
Voce e um estrategista de produto educacional premium.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Escreva textos persuasivos, mas sem promessas milagrosas.
Use linguagem premium, com foco em transformacao humana e conhecimento aplicado.
"""


def build_course_summary_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    course_structure: dict[str, Any],
) -> tuple[str, str]:
    user_prompt = f"""
Gere um resumo executivo e comercial do curso.

Projeto:
- Titulo: {project.title}
- Publico-alvo: {project.target_audience or "nao informado"}
- Tom de voz: {project.tone_of_voice or "claro, inspirador e pratico"}

Analise do documento:
{json.dumps(document_analysis, ensure_ascii=False, indent=2)}

Estrutura do curso:
{json.dumps(course_structure, ensure_ascii=False, indent=2)}

Retorne somente JSON valido exatamente neste formato:
{{
  "course_summary": {{
    "title": "",
    "short_description": "",
    "long_description": "",
    "promise": "",
    "target_audience": "",
    "transformation_statement": "",
    "what_student_will_learn": [],
    "course_differentials": [],
    "suggested_sales_copy": "",
    "suggested_instagram_caption": "",
    "suggested_whatsapp_message": ""
  }}
}}
"""
    return SYSTEM_PROMPT.strip(), user_prompt.strip()
