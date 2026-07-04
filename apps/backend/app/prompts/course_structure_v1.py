import json
from typing import Any

from app.models.project import Project

COURSE_STRUCTURE_PROMPT_VERSION = "course_structure_v1"

SYSTEM_PROMPT = """
Voce e um arquiteto de cursos premium da Virtus et Veritas Academy.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
O PDF e a fonte da verdade.
Use a analise inteligente do documento base como referencia principal quando ela estiver disponivel.
Nao use conhecimento externo.
Nao invente fatos, nomes, datas, conceitos, leis, eventos ou conclusoes que nao estejam no documento.
Reescreva com linguagem propria, mas mantenha fidelidade substancial ao conteudo.
Nao comprima demais o documento.
Nao force uma quantidade pequena de modulos ou aulas.
Crie uma progressao didatica coerente, fiel, profunda, com tom inspirador, claro, filosofico e pratico.
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
    analysis_available = bool(document_analysis and document_analysis.get("document_analysis"))
    user_prompt = f"""
{language_instruction}

Crie a estrutura completa de um curso a partir da analise inteligente do documento base e do texto extraido.

Projeto:
- Titulo: {project.title}
- Tipo de produto: {project.product_type}
- Publico-alvo: {project.target_audience or "nao informado"}
- Tom de voz: {project.tone_of_voice or "claro, inspirador e pratico"}
- Duracao desejada: {project.desired_duration or "nao informada"}
- Descricao: {project.description or "nao informada"}

Analise do documento:
{analysis_json}

Status da analise do documento base:
{"A analise do documento base esta disponivel e deve orientar a estrutura." if analysis_available else "A analise do documento base nao estava disponivel. Use o texto extraido diretamente, mantendo o comportamento antigo, sem quebrar a geracao."}

Regras de fidelidade e profundidade:
- Use a analise do documento base como referencia principal quando disponivel.
- Use especialmente: document_title, source_overview, central_ideas, key_concepts, document_sequence, suggested_course_path, coverage_notes, limitations, originality_strategy e fidelity_rules.
- O PDF continua sendo a fonte de verdade.
- Nao use conhecimento externo.
- Nao invente fatos, nomes, datas, conceitos, leis, eventos ou conclusoes.
- Cubra todos os temas relevantes identificados na analise do documento base.
- Mantenha a ordem natural do documento sempre que fizer sentido.
- Reorganize a ordem apenas quando houver justificativa didatica clara.
- Nao transforme capitulos ou blocos complexos inteiros em uma unica aula.
- Divida assuntos complexos em aulas separadas.
- Crie modulos suficientes para cobrir a complexidade real do documento.
- Se um ponto do PDF for introdutorio, complementar ou repetitivo, indique isso honestamente no campo fidelity_note ou covered_document_points.
- Cada modulo deve ter um proposito claro.
- Cada aula deve representar um recorte real do conteudo do PDF.
- A estrutura deve permitir gerar depois roteiros profundos, quizzes, materiais, apresentacao, narracao e video.
- Use linguagem autoral e didatica, sem copiar grandes trechos do PDF.

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
            "learning_objective": "",
            "key_topics": [],
            "covered_document_points": [],
            "fidelity_note": ""
          }}
        ],
        "covered_document_points": [],
        "fidelity_note": ""
      }}
    ]
  }}
}}

Texto extraido:
{extracted_text}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
