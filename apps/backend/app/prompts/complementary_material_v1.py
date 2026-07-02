import json
from typing import Any

from app.models.project import Project

COMPLEMENTARY_MATERIAL_PROMPT_VERSION = "complementary_material_v1"

SYSTEM_PROMPT = """
Voce e um produtor de materiais complementares educacionais premium.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Crie material util para o aluno, como guia de estudo, resumo, checklist ou exercicios reflexivos.
Nao crie bibliografia falsa nem cite fontes externas inexistentes.
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


def build_complementary_material_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    course_structure: dict[str, Any],
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    language_instruction = build_language_instruction(generation_language)
    user_prompt = f"""
{language_instruction}

Gere um material complementar para o curso inteiro.

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
  "complementary_material": {{
    "course_title": "",
    "material_title": "",
    "material_type": "study_guide",
    "overview": "",
    "key_concepts": [
      {{
        "concept": "",
        "explanation": ""
      }}
    ],
    "practical_applications": [],
    "reflection_exercises": [],
    "recommended_next_steps": []
  }}
}}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
