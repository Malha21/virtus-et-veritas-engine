import json
from typing import Any

from app.models.project import Project

MODULE_QUIZ_PROMPT_VERSION = "module_quiz_v1"

SYSTEM_PROMPT = """
Voce e um designer instrucional especializado em avaliacao de aprendizagem.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Gere preferencialmente 5 questoes por modulo.
As perguntas devem avaliar compreensao real, evitando obviedades.
As alternativas devem ser plausiveis e a explicacao deve ensinar.
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


def build_module_quiz_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    course_structure: dict[str, Any],
    module: dict[str, Any],
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    language_instruction = build_language_instruction(generation_language)
    user_prompt = f"""
{language_instruction}

Gere um quiz para o modulo indicado.

Projeto:
- Titulo: {project.title}
- Publico-alvo: {project.target_audience or "nao informado"}

Analise do documento:
{json.dumps(document_analysis, ensure_ascii=False, indent=2)}

Estrutura do curso:
{json.dumps(course_structure, ensure_ascii=False, indent=2)}

Modulo:
{json.dumps(module, ensure_ascii=False, indent=2)}

Retorne somente JSON valido exatamente neste formato:
{{
  "module_quiz": {{
    "course_title": "",
    "module_number": 1,
    "module_title": "",
    "questions": [
      {{
        "question_number": 1,
        "question": "",
        "options": [
          {{"letter": "A", "text": ""}},
          {{"letter": "B", "text": ""}},
          {{"letter": "C", "text": ""}},
          {{"letter": "D", "text": ""}}
        ],
        "correct_answer": "A",
        "explanation": ""
      }}
    ]
  }}
}}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
