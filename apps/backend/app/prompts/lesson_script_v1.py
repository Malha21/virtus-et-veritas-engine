import json
from typing import Any

from app.models.project import Project

LESSON_SCRIPT_PROMPT_VERSION = "lesson_script_v1"

SYSTEM_PROMPT = """
Voce e um roteirista educacional premium da Virtus et Veritas Academy.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Nao invente fontes externas e preserve a base do documento original.
A linguagem deve ser clara, inspiradora, filosofica e pratica quando aplicavel.
O roteiro deve parecer pronto para gravacao, sem ser generico.
Mantenha progressao didatica; se o tema for tecnico, explique com clareza e exemplos.
Se o tema for filosofico ou humano, conecte conhecimento, vida pratica e transformacao.
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


def build_lesson_script_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    course_structure: dict[str, Any],
    module: dict[str, Any],
    lesson: dict[str, Any],
    extracted_text_excerpt: str,
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    language_instruction = build_language_instruction(generation_language)
    user_prompt = f"""
{language_instruction}

Gere um roteiro completo para a aula indicada.

Projeto:
- Titulo: {project.title}
- Publico-alvo: {project.target_audience or "nao informado"}
- Tom de voz: {project.tone_of_voice or "claro, inspirador e pratico"}
- Duracao desejada: {project.desired_duration or "nao informada"}

Analise do documento:
{json.dumps(document_analysis, ensure_ascii=False, indent=2)}

Estrutura do curso:
{json.dumps(course_structure, ensure_ascii=False, indent=2)}

Modulo:
{json.dumps(module, ensure_ascii=False, indent=2)}

Aula:
{json.dumps(lesson, ensure_ascii=False, indent=2)}

Retorne somente JSON valido exatamente neste formato:
{{
  "lesson_script": {{
    "course_title": "",
    "module_number": 1,
    "module_title": "",
    "lesson_number": 1,
    "lesson_title": "",
    "estimated_duration_minutes": 10,
    "opening": "",
    "learning_objective": "",
    "main_script": [
      {{
        "section_title": "",
        "narration": "",
        "teaching_notes": "",
        "visual_suggestion": ""
      }}
    ],
    "practical_example": "",
    "reflection_question": "",
    "closing": "",
    "call_to_action": ""
  }}
}}

Trecho do texto extraido:
{extracted_text_excerpt}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
