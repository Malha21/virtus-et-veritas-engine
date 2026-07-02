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


def build_language_instruction(generation_language: str) -> str:
    if generation_language == "en-US":
        return """
Language rule:
- Respond 100% in English.
- Do not write Portuguese in titles, questions, options, explanations, materials, calls to action or texts.
- Even if the original document is in Portuguese, translate and adapt the output to English.
"""
    return """
Regra de idioma:
- Responda 100% em portugues do Brasil.
- Nao use ingles nos titulos, perguntas, alternativas, explicacoes, materiais, chamadas ou textos.
- Mesmo que o documento original esteja em ingles, traduza e adapte a saida para portugues do Brasil.
- Mantenha termos tecnicos em ingles apenas quando forem nomes proprios, siglas ou expressoes consagradas, explicando em portugues quando necessario.
"""


def build_course_structure_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    extracted_text: str,
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    language_instruction = build_language_instruction(generation_language)
    analysis_json = json.dumps(document_analysis, ensure_ascii=False, indent=2)
    user_prompt = f"""
{language_instruction}

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
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
