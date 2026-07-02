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


def build_course_summary_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    course_structure: dict[str, Any],
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    language_instruction = build_language_instruction(generation_language)
    user_prompt = f"""
{language_instruction}

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
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
