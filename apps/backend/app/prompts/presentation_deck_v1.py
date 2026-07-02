import json
from typing import Any

from app.models.project import Project

PRESENTATION_DECK_PROMPT_VERSION = "presentation_deck_v1"

SYSTEM_PROMPT = """
Voce e um designer instrucional e estrategista de apresentacoes premium.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Crie uma apresentacao clara, didatica e pronta para uso em aula, palestra, treinamento, workshop ou apresentacao online.
Evite slides longos. Cada slide deve ter no maximo 5 bullets, com frases curtas e objetivas.
As notas do apresentador devem ser uteis, especificas e acionaveis, nunca genericas.
As sugestoes visuais devem ser adequadas ao tema, sem depender de uma imagem real pronta.
"""


def build_language_instruction(generation_language: str) -> str:
    if generation_language == "en-US":
        return """
Language rule:
- Respond 100% in English.
- Do not write Portuguese in titles, bullets, speaker notes, visual suggestions or interaction questions.
- Even if the original document is in Portuguese, translate and adapt the output to English.
"""
    return """
Regra de idioma:
- Responda 100% em portugues do Brasil.
- Nao use ingles em titulos, bullets, notas do apresentador, sugestoes visuais ou perguntas de interacao.
- Mesmo que o documento original esteja em ingles, traduza e adapte a saida para portugues do Brasil.
- Mantenha termos tecnicos em ingles apenas quando forem nomes proprios, siglas ou expressoes consagradas.
"""


def build_presentation_deck_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    course_structure: dict[str, Any],
    course_summaries: list[dict[str, Any]],
    lesson_scripts: list[dict[str, Any]],
    complementary_materials: list[dict[str, Any]],
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    language_instruction = build_language_instruction(generation_language)
    user_prompt = f"""
{language_instruction}

Gere uma apresentacao pronta a partir dos conteudos educacionais disponiveis.

Projeto:
- Titulo: {project.title}
- Publico-alvo: {project.target_audience or "nao informado"}
- Objetivo educacional / descricao: {project.description or "nao informado"}
- Tom de voz: {project.tone_of_voice or "claro, inspirador e pratico"}
- Duracao desejada: {project.desired_duration or "nao informada"}

Analise do documento:
{json.dumps(document_analysis, ensure_ascii=False, indent=2)}

Estrutura do curso:
{json.dumps(course_structure, ensure_ascii=False, indent=2)}

Resumos do curso disponiveis:
{json.dumps(course_summaries, ensure_ascii=False, indent=2)}

Roteiros de aula disponiveis:
{json.dumps(lesson_scripts, ensure_ascii=False, indent=2)}

Materiais complementares disponiveis:
{json.dumps(complementary_materials, ensure_ascii=False, indent=2)}

Regras de conteudo:
- Responda em JSON valido.
- Adapte a quantidade de slides ao tamanho do curso.
- Para cursos curtos, gere entre 8 e 12 slides.
- Para cursos medios, gere entre 12 e 20 slides.
- Para cursos longos, gere entre 20 e 30 slides.
- Cada slide deve ter no maximo 5 bullets.
- Prefira frases curtas, claras e objetivas.
- Inclua perguntas de interacao quando fizer sentido para engajar a audiencia.
- Use speaker_notes para orientar exatamente como conduzir o slide.

Retorne somente JSON valido exatamente neste formato:
{{
  "presentation_title": "",
  "target_audience": "",
  "estimated_duration": "",
  "visual_style": "",
  "presentation_objective": "",
  "slides": [
    {{
      "slide_number": 1,
      "title": "",
      "subtitle": "",
      "bullets": [],
      "speaker_notes": "",
      "visual_suggestion": "",
      "interaction_question": ""
    }}
  ],
  "closing_message": ""
}}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
