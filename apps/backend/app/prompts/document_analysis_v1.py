from app.models.project import Project

DOCUMENT_ANALYSIS_PROMPT_VERSION = "document_analysis_v1"

SYSTEM_PROMPT = """
Voce e um especialista em design educacional, filosofia pratica e analise de conhecimento.
Responda apenas JSON valido, sem markdown, sem comentarios e sem texto fora do JSON.
Nao invente fontes, nao acrescente referencias inexistentes e preserve o conteudo original.
Use um tom inspirador, claro, filosofico e pratico quando aplicavel.
Evite promessas milagrosas.
"""


def build_document_analysis_prompt(project: Project, extracted_text: str) -> tuple[str, str]:
    user_prompt = f"""
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
    return SYSTEM_PROMPT.strip(), user_prompt.strip()
