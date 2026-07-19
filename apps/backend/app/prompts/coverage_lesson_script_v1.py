COVERAGE_LESSON_SCRIPT_PROMPT_VERSION = "coverage_lesson_script_v1"

SYSTEM_PROMPT = """
Voce esta criando o roteiro completo de UMA UNICA aula educacional, a partir
exclusivamente das fontes fornecidas (itens do inventario documental ja
vinculados a esta aula pelo Plano de Cobertura). Esta chamada produz sempre
uma unica aula -- nunca um modulo inteiro, nunca o curso inteiro.

A aula deve ser autoral em sua redacao e organizacao didatica, mas
integralmente fundamentada no conteudo fornecido.

Voce pode:
- reorganizar a redacao e melhorar a sequencia didatica;
- criar introducao baseada no tema da aula e transicoes entre os itens;
- transformar listas em explicacoes fluidas;
- simplificar frases dificeis e explicar melhor conteudos ja presentes;
- conectar itens relacionados e produzir um encerramento coerente;
- evitar copiar a estrutura sintatica literal do documento.

Voce NUNCA pode:
- inventar fatos, exemplos, historias, dados, pesquisas, citacoes, aplicacoes
  ou definicoes que nao estejam nas fontes fornecidas;
- usar qualquer conhecimento externo as fontes fornecidas;
- completar lacunas do documento ou corrigir o autor;
- alterar numeros, datas, nomes, regras ou definicoes;
- omitir excecoes, ressalvas, exemplos, procedimentos ou observacoes presentes;
- generalizar detalhes importantes para simplificar;
- mencionar como fato algo que nao esta nas fontes;
- eliminar conteudo apenas para caber no limite de duracao.

Todos os itens marcados como obrigatorios (is_required=true) devem ser
efetivamente ensinados no roteiro, nao apenas citados de passagem. Itens
complementares tambem devem aparecer, respeitando o coverage_type indicado.

Estrutura obrigatoria do roteiro: abertura objetiva, contextualizacao,
desenvolvimento didatico cobrindo todos os itens na ordem indicada, transicoes
naturais, explicacoes claras, preservacao de todos os detalhes, encerramento
coerente.

A abertura pode apresentar o tema e indicar o que sera aprendido, mas nunca
pode inventar uma historia, pergunta retorica baseada em fato externo,
estatistica ou cenario que nao esteja nas fontes; nunca promete conteudo que
nao esta nesta aula.

O encerramento pode recapitular e reforcar os pontos principais, mas nunca
antecipa conteudo de outra aula sem base nas fontes e nunca usa uma chamada
motivacional generica desconectada do material.

Nunca mencione, na narracao do roteiro: "o PDF", "o documento enviado", "a
fonte diz", codigos SRC, nomes de blocos/paginas do sistema, instrucoes
internas, marcacoes tecnicas, JSON, comentarios sobre limitacoes ou qualquer
metadado do processo de geracao. O texto deve soar como uma aula gravada, nao
como um relatorio sobre um documento.

Estilo de redacao: claro, didatico, natural, profissional, autoral, fluido,
adequado para narracao em audio/video, sem linguagem robotica, sem repeticao
desnecessaria, sem frases excessivamente longas, sem estrutura de artigo
academico (salvo exigencia do proprio material), sem marcacoes de slide, sem
codigos internos.

A aula deve respeitar a duracao-alvo, calculada a {words_per_minute} palavras
por minuto, com no maximo {max_lesson_minutes} minutos. Se o conteudo,
tratado com fidelidade total (sem cortes, sem omissoes, sem resumo excessivo),
nao couber dentro desse limite, NAO COMPRIMA e NAO OMITA NADA: retorne
generation_status="requires_split", explique em split_reason quais itens
causam o excesso, e ainda assim preencha script/opening/development/closing
com o melhor roteiro fiel possivel (sera usado apenas como referencia; a aula
sera dividida no Plano de Cobertura). Nunca gere uma aula incompleta.

Responda apenas com JSON valido, sem markdown, sem comentarios, sem texto
fora do JSON.
"""


def build_language_instruction(generation_language: str) -> str:
    if generation_language == "en-US":
        return """
Language rule:
- Write lesson_title, learning_objective, opening, development, closing, script,
  summary and key_points 100% in English.
"""
    return """
Regra de idioma:
- Escreva lesson_title, learning_objective, opening, development, closing, script,
  summary e key_points 100% em portugues do Brasil.
"""


def _format_item(item: dict) -> str:
    header_parts = [
        f"codigo: {item['item_code']}",
        f"tipo: {item['content_type']}",
        f"importancia: {item['importance']}",
        f"obrigatorio: {'sim' if item.get('is_required', True) else 'nao'}",
        f"cobertura planejada: {item.get('coverage_type', 'planned_primary')}",
        f"ordem nesta aula: {item.get('source_order_in_lesson', 0)}",
        f"paginas: {item.get('page_start')}-{item.get('page_end')}",
    ]
    if item.get("block_codes"):
        header_parts.append(f"blocos: {', '.join(item['block_codes'])}")
    if item.get("depends_on_item_codes"):
        header_parts.append(f"depende de: {', '.join(item['depends_on_item_codes'])}")
    if item.get("requires_review"):
        header_parts.append("ALERTA: item pendente de revisao no inventario -- use com cautela redobrada")

    text = f"[{' | '.join(header_parts)}]\nTitulo: {item['title']}\n"
    normalized = item.get("normalized_content") or ""
    source_text = item.get("source_text") or ""
    text += f"Conteudo normalizado: {normalized}\n"
    if source_text and source_text.strip() != normalized.strip():
        text += f"Texto original da fonte (preserve todos os detalhes que aparecem aqui): {source_text}\n"
    return text.strip()


def build_coverage_lesson_script_prompt(
    project_title: str,
    module_title: str,
    module_objective: str,
    lesson_title: str,
    lesson_description: str,
    lesson_objective: str,
    target_duration_minutes: float,
    max_lesson_minutes: int,
    words_per_minute: int,
    items: list[dict],
    generation_language: str = "pt-BR",
    feedback: str | None = None,
    repair_notes: str | None = None,
    missing_item_codes: list[str] | None = None,
) -> tuple[str, str]:
    """Monta o prompt para gerar o roteiro completo de UMA aula do Plano de Cobertura.

    `items` e a lista ordenada (source_order_in_lesson) dos source_content_items
    vinculados a esta aula (LessonSourceItem.coverage_plan_lesson_id), cada um com:
    source_item_id/item_code, title, normalized_content, source_text, content_type,
    importance, source_order_in_lesson, coverage_type, is_required, page_start,
    page_end, block_codes, depends_on_item_codes, requires_review.
    """
    language_instruction = build_language_instruction(generation_language)
    system_prompt = SYSTEM_PROMPT.format(
        max_lesson_minutes=max_lesson_minutes, words_per_minute=words_per_minute
    ).strip()

    items_text = "\n\n".join(_format_item(item) for item in items)
    item_codes = [item["item_code"] for item in items]
    required_codes = [item["item_code"] for item in items if item.get("is_required", True)]

    feedback_block = ""
    if feedback:
        feedback_block = f"""
Instrucao de regeneracao (aplique sem violar nenhuma das fontes ou regras acima):
{feedback}
"""

    repair_block = ""
    if repair_notes or missing_item_codes:
        missing_list = ", ".join(missing_item_codes or [])
        repair_block = f"""
Esta e uma correcao de uma versao anterior que deixou de cobrir efetivamente os
seguintes itens obrigatorios: {missing_list}.
Preserve todo o restante do roteiro ja aprovado como referencia e incorpore
esses itens de forma completa, sem remover nenhum conteudo ja coberto.
Notas da revisao: {repair_notes or ''}
"""

    user_prompt = f"""
{language_instruction}

Projeto: {project_title}
Modulo: {module_title}
Objetivo do modulo: {module_objective}

Aula: {lesson_title}
Descricao da aula: {lesson_description}
Objetivo de aprendizagem da aula: {lesson_objective}

Parametros de duracao: {words_per_minute} palavras por minuto, duracao-alvo de
{target_duration_minutes} minutos, maximo absoluto de {max_lesson_minutes} minutos.
{feedback_block}{repair_block}
Itens do inventario vinculados a esta aula, na ordem em que devem ser ensinados
(use exatamente os codigos abaixo como source_item_id em covered_source_items;
nao invente nem omita nenhum item obrigatorio):

{items_text}

Todos os itens obrigatorios desta aula ({', '.join(required_codes)}) devem
aparecer em covered_source_items ao final, com coverage_type refletindo o uso
real que voce deu ao item no roteiro (full = ensinado integralmente, partial =
mencionado parcialmente, reference = apenas citado). Todos os codigos
fornecidos ({', '.join(item_codes)}) devem ser considerados; se algum nao puder
ser efetivamente coberto sem violar as regras, liste-o em uncovered_source_items
e explique em warnings.

Retorne somente JSON valido exatamente neste formato:
{{
  "lesson_title": "",
  "learning_objective": "",
  "generation_status": "completed",
  "target_duration_minutes": {target_duration_minutes},
  "estimated_duration_minutes": 0,
  "word_count": 0,
  "opening": "",
  "development": "",
  "closing": "",
  "script": "",
  "summary": "",
  "key_points": [],
  "covered_source_items": [
    {{
      "source_item_id": "",
      "coverage_description": "",
      "coverage_type": "full"
    }}
  ],
  "uncovered_source_items": [],
  "source_pages": [],
  "source_block_codes": [],
  "unsupported_claims_declared": [],
  "requires_split": false,
  "split_reason": null,
  "warnings": []
}}
"""
    return system_prompt, user_prompt.strip()
