import json
from typing import Any

from app.models.project import Project

COURSE_STRUCTURE_PROMPT_VERSION = "course_structure_v1"

SYSTEM_PROMPT = """
Voce e um arquiteto de cursos premium da Virtus et Veritas Academy.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Nao invente fontes, nao acrescente referencias inexistentes e preserve o conteudo original.
Crie uma progressao didatica coerente, com tom inspirador, claro, filosofico e pratico.
Adapte a estrutura ao publico-alvo informado no projeto e evite promessas milagrosas.
"""


def build_course_structure_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    extracted_text: str,
) -> tuple[str, str]:
    analysis_json = json.dumps(document_analysis, ensure_ascii=False, indent=2)
    user_prompt = f"""
Crie a estrutura inicial de um curso a partir da analise e do texto extraido.

Projeto:
- Titulo: {project.title}
- Tipo de produto: {project.product_type}
- Publico-alvo: {project.target_audience or "nao informado"}
- Tom de voz: {project.tone_of_voice or "claro, inspirador e pratico"}
- Duracao desejada: {project.desired_duration or "nao informada"}
- Descricao: {project.description or "nao informada"}

Analise do documento:
{analysis_json}

Retorne somente JSON valido exatamente neste formato:
{{
  "course": {{
    "title": "",
    "promise": "",
    "description": "",
    "target_audience": "",
    "learning_objectives": [],
    "modules": [
      {{
        "module_number": 1,
        "title": "",
        "description": "",
        "learning_goal": "",
        "lessons": [
          {{
            "lesson_number": 1,
            "title": "",
            "summary": "",
            "estimated_duration_minutes": 10,
            "learning_objective": ""
          }}
        ]
      }}
    ]
  }}
}}

Texto extraido:
{extracted_text}
"""
    return SYSTEM_PROMPT.strip(), user_prompt.strip()
