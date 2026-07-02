from app.models.project import Project

DOCUMENT_ANALYSIS_PROMPT_VERSION = "document_analysis_v1"

SYSTEM_PROMPT = """
Voce e um especialista em design educacional, filosofia pratica e analise de conhecimento.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Nao invente fontes, nao acrescente referencias inexistentes e preserve o conteudo original.
Use um tom inspirador, claro, filosofico e pratico quando aplicavel.
Evite promessas milagrosas.
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

Retorne somente JSON valido exatamente neste formato:
{{
  "document_analysis": {{
    "main_theme": "",
    "subthemes": [],
    "complexity_level": "beginner | intermediate | advanced",
    "recommended_audience": "",
    "recommended_product_type": "course",
    "didactic_risks": [],
    "opportunities": [],
    "suggested_approach": ""
  }}
}}

Texto extraido:
{extracted_text}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()
