import json
from typing import Any

from app.models.project import Project

LESSON_SCRIPT_PROMPT_VERSION = "lesson_script_v1"

SYSTEM_PROMPT = """
Voce e um roteirista educacional premium da Virtus et Veritas Academy.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
O PDF e a fonte da verdade.
Use a estrutura do curso como espinha dorsal obrigatoria dos roteiros.
Use a analise inteligente do documento base como apoio para fidelidade, cobertura e ordem logica quando ela estiver disponivel.
Nao use conhecimento externo.
Nao invente fatos, nomes, datas, conceitos, leis, eventos ou conclusoes que nao estejam no documento.
Reescreva com linguagem propria, mas mantenha fidelidade substancial ao conteudo.
Nao copie grandes trechos do PDF.
Nao gere roteiro raso, generico ou apenas resumido.
A linguagem deve ser clara, didatica, inspiradora, filosofica e pratica quando aplicavel.
O roteiro deve parecer pronto para teleprompter, narracao, audio e gravacao.
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

Regras obrigatorias para esta aula:
- Respeite exatamente o modulo e a aula informados acima.
- Nao crie aulas soltas fora da estrutura.
- A estrutura do curso e a espinha dorsal: use titulo, objetivo, topicos, pontos cobertos e nota de fidelidade da aula quando existirem.
- Use a analise do documento base como apoio, especialmente document_title, source_overview, central_ideas, key_concepts, document_sequence, suggested_course_path, coverage_notes, limitations, originality_strategy e fidelity_rules.
- O PDF continua sendo a fonte da verdade.
- Nao use conhecimento externo.
- Nao invente nomes, datas, eventos, conceitos, leis ou conclusoes.
- Nao copie paragrafos longos literalmente.
- Desenvolva a aula como uma aula real, com abertura, introducao, desenvolvimento, exemplos baseados no documento, atividade quando fizer sentido e fechamento.
- Nao transforme a aula em um resumo curto.
- Desenvolva conceitos passo a passo.
- Explique por que o tema importa dentro do modulo e do curso.
- Conecte com a aula anterior e a proxima quando isso for possivel pela estrutura.
- Inclua transicoes naturais.
- Inclua orientacoes para o instrutor.
- O texto deve ser adequado para ser lido em voz alta.
- Evite frases genericas, topicos curtos e repeticao artificial.
- Se houver lacuna no documento, sinalize em fidelity_notes.
- Cada roteiro deve indicar claramente quais topicos da estrutura e do documento foram cobertos.
- Use script_text e narration_text como texto completo de fala da aula, nao como resumo.

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
    "introduction": "",
    "learning_objective": "",
    "script_text": "",
    "narration_text": "",
    "development": "",
    "main_script": [
      {{
        "section_title": "",
        "narration": "",
        "teaching_notes": "",
        "visual_suggestion": ""
      }}
    ],
    "practical_example": "",
    "practical_activity": "",
    "reflection_question": "",
    "closing": "",
    "call_to_action": "",
    "instructor_notes": "",
    "covered_structure_topics": [],
    "covered_document_topics": [],
    "fidelity_notes": ""
  }}
}}

Trecho do texto extraido:
{extracted_text_excerpt}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
