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
Para PDFs entre 50 e 80 paginas, gere preferencialmente entre 7 e 10 modulos e entre 24 e 40 aulas.
Quando houver sumario, capitulos ou secoes principais identificaveis, use essa sequencia como guia principal.
Nao gere apenas 1 modulo quando o documento tiver multiplos capitulos claros.
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
- Se o documento tiver entre 50 e 80 paginas, gere preferencialmente entre 7 e 10 modulos e entre 24 e 40 aulas.
- Para documentos medios ou grandes, menos de 5 modulos ou menos de 15 aulas e considerado superficial e insuficiente.
- Quando existir sumario, capitulos numerados ou uma sequencia clara de secoes, use essa ordem como guia principal dos modulos.
- Introducao pode virar modulo introdutorio.
- Capitulos numerados devem virar modulos, ou blocos centrais com varios modulos, quando forem extensos.
- Secoes finais como oracoes, conclusao, posfacio, apendices ou sobre o autor podem virar modulo final, aula final ou material complementar, conforme a relevancia didatica.
- Cada modulo deve corresponder a um grande tema, capitulo ou bloco conceitual do documento.
- Cada modulo deve ter de 3 a 5 aulas, salvo excecao justificada pelo conteudo.
- Para obras com multiplos capitulos claros, nao agrupe todo o documento em um unico modulo.
- A divisao deve seguir a logica pedagogica do documento, nao apenas a contagem de paginas.
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


def build_course_structure_expansion_prompt(
    project: Project,
    document_analysis: dict[str, Any],
    extracted_text: str,
    previous_structure: dict[str, Any],
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    language_instruction = build_language_instruction(generation_language)
    analysis_json = json.dumps(document_analysis, ensure_ascii=False, indent=2)
    previous_json = json.dumps(previous_structure, ensure_ascii=False, indent=2)
    user_prompt = f"""
{language_instruction}

A estrutura anterior ficou superficial e não cobriu o documento inteiro. Gere uma estrutura completa, cobrindo todos os capítulos e seções principais do documento.

Projeto:
- Titulo: {project.title}
- Tipo de produto: {project.product_type}
- Publico-alvo: {project.target_audience or "nao informado"}
- Tom de voz: {project.tone_of_voice or "claro, inspirador e pratico"}
- Duracao desejada: {project.desired_duration or "nao informada"}
- Descricao: {project.description or "nao informada"}

Analise do documento:
{analysis_json}

Estrutura anterior insuficiente:
{previous_json}

Regras obrigatorias para a nova estrutura:
- Use o document_analysis como fonte principal quando existir.
- Use o sumario, capitulos numerados e secoes principais como guia central.
- Para PDFs entre 50 e 80 paginas, gere preferencialmente entre 7 e 10 modulos e entre 24 e 40 aulas.
- Nao gere menos de 5 modulos nem menos de 15 aulas para documento medio ou grande.
- Cada capitulo ou grande tema deve aparecer como modulo, ou como parte claramente identificada de um modulo.
- Cada modulo deve ter de 3 a 5 aulas, salvo excecao justificada pelo conteudo.
- Nao invente conteudo externo.
- Cubra introducao, capitulos centrais e secoes finais relevantes.
- Preserve a ordem pedagogica e a ordem natural do documento sempre que fizer sentido.

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
