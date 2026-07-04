from app.models.project import Project

DOCUMENT_ANALYSIS_PROMPT_VERSION = "document_analysis_v1"

SYSTEM_PROMPT = """
Voce e um especialista em design educacional, leitura analitica e transformacao fiel de conhecimento em produtos educacionais.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Use exclusivamente o conteudo do documento enviado.
Nao use conhecimento externo.
Nao invente nomes, datas, fatos, eventos, conceitos ou conclusoes.
Quando o documento nao trouxer informacao suficiente, informe a limitacao.
Reescreva com linguagem propria, preservando o sentido original.
Nao copie paragrafos longos literalmente.
Nao reduza demais o documento.
Cubra todos os topicos relevantes presentes no material.
Respeite a ordem natural do documento sempre que ela fizer sentido.
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


def build_document_analysis_prompt(
    project: Project,
    extracted_text: str,
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    language_instruction = build_language_instruction(generation_language)
    user_prompt = f"""
{language_instruction}

Analise o texto extraido do documento para o projeto abaixo.

Projeto:
- Titulo: {project.title}
- Tipo de produto: {project.product_type}
- Publico-alvo: {project.target_audience or "nao informado"}
- Tom de voz: {project.tone_of_voice or "claro, inspirador e pratico"}
- Duracao desejada: {project.desired_duration or "nao informada"}
- Descricao: {project.description or "nao informada"}

Regras obrigatorias:
- O PDF e a fonte de verdade.
- Interprete, reorganize, explique e reescreva com linguagem propria.
- Nao acrescente informacoes externas ao documento.
- Nao complete lacunas com conhecimento geral.
- Nao altere o sentido do material enviado.
- Sinalize limitacoes quando o documento nao oferecer informacao suficiente.
- A analise deve ser mais completa que um resumo curto.
- A analise deve apoiar a criacao futura de estrutura de curso e aulas profundas.

Retorne somente JSON valido exatamente neste formato:
{{
  "document_analysis": {{
    "document_title": "",
    "source_overview": "",
    "authorial_summary": "",
    "central_ideas": [],
    "key_concepts": [],
    "document_sequence": [
      {{
        "order": 1,
        "topic": "",
        "summary": "",
        "didactic_relevance": ""
      }}
    ],
    "suggested_course_path": [
      {{
        "module_title": "",
        "reason": "",
        "possible_lessons": []
      }}
    ],
    "coverage_notes": "",
    "limitations": [],
    "fidelity_rules": [
      "Usar apenas informacoes presentes no documento.",
      "Nao acrescentar fatos externos.",
      "Sinalizar lacunas quando o documento nao trouxer informacao suficiente."
    ],
    "originality_strategy": {{
      "rewrite_guidance": "",
      "tone": "",
      "what_to_avoid": []
    }}
  }}
}}

Texto extraido:
{extracted_text}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
