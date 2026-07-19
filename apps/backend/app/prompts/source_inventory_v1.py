SOURCE_INVENTORY_PROMPT_VERSION = "source_inventory_v1"

SYSTEM_PROMPT = """
Voce esta analisando exclusivamente um trecho de um documento enviado pelo usuario.
Sua tarefa nao e resumir.
Sua tarefa e identificar todas as unidades de conhecimento existentes no trecho.

Considere como unidades de conhecimento: conceitos, definicoes, explicacoes, argumentos,
fatos, datas, numeros, procedimentos, etapas, regras, excecoes, exemplos, casos, listas,
classificacoes, comparacoes, distincoes, causas, consequencias, observacoes, alertas,
recomendacoes, citacoes, conclusoes, exercicios, perguntas, referencias internas,
descricoes de tabelas, legendas e informacoes complementares relevantes.

Regras absolutas:
- Nao elimine conteudo por parecer secundario, repetitivo, complementar, introdutorio ou dificil de classificar.
- Nao utilize conhecimento externo.
- Nao complete informacoes ausentes.
- Nao invente explicacoes, exemplos ou definicoes.
- Nao corrija o documento.
- Nao altere datas, numeros, nomes ou definicoes.
- Nao transforme o texto em aula.
- Nao crie modulos.
- Nao crie titulos pedagogicos genericos.
- Cada informacao relevante do trecho deve aparecer em pelo menos um item.
- Se o trecho estiver incompleto (comeca ou termina no meio de uma ideia), marque possible_fragment=true.
- Se um item parecer repetir algo ja comum no documento (cabecalho, rodape, citacao repetida), marque possible_duplicate=true e ainda assim retorne o item.
- Nao retorne conteudo que nao esteja presente no trecho.
- Responda apenas com JSON valido, sem markdown, sem comentarios, sem texto fora do JSON.
"""


def build_language_instruction(generation_language: str) -> str:
    if generation_language == "en-US":
        return """
Language rule:
- Write title, normalized_content and review_reason 100% in English.
- source_text must remain exactly as it appears in the original excerpt, regardless of language.
"""
    return """
Regra de idioma:
- Escreva title, normalized_content e review_reason 100% em portugues do Brasil.
- source_text deve permanecer exatamente como aparece no trecho original, independentemente do idioma.
"""


CONTENT_TYPES = (
    "concept, definition, explanation, fact, procedure, step, rule, exception, example, "
    "case, list, classification, comparison, distinction, cause, consequence, argument, "
    "conclusion, observation, warning, recommendation, exercise, question, table, "
    "image_caption, quotation, reference, other"
)

IMPORTANCE_LEVELS = "essential, relevant, complementary"


def build_source_inventory_chunk_prompt(
    project_title: str,
    chunk_id: str,
    page_start: int,
    page_end: int,
    blocks: list[dict],
    generation_language: str = "pt-BR",
) -> tuple[str, str]:
    """Monta o prompt para um chunk (conjunto de blocos de paginas consecutivas).

    `blocks` e uma lista de dicts com: block_code, block_type, page_number, source_text.
    """
    language_instruction = build_language_instruction(generation_language)

    blocks_text = "\n\n".join(
        f"[{block['block_code']} | pagina {block['page_number']} | tipo heuristico: {block['block_type']}]\n"
        f"{block['source_text']}"
        for block in blocks
    )

    user_prompt = f"""
{language_instruction}

Projeto: {project_title}
Chunk: {chunk_id}
Paginas cobertas neste trecho: {page_start} a {page_end}

Tipos de conteudo permitidos (content_type): {CONTENT_TYPES}
Niveis de importancia permitidos (importance): {IMPORTANCE_LEVELS}

Trecho do documento, dividido em blocos com codigo, pagina e tipo heuristico ja identificados
pela extracao estrutural (fase anterior). Use esses codigos de bloco para referenciar a origem
de cada item que voce identificar:

{blocks_text}

Para cada unidade de conhecimento identificada, retorne um item com:
- temporary_id: identificador temporario unico dentro deste chunk (ex: "TMP-0001");
- title: titulo descritivo e fiel (nao pedagogico, nao generico);
- normalized_content: descricao normalizada e fiel, semanticamente equivalente ao trecho, sem eliminar detalhes;
- source_text: trecho original exato correspondente (copie do texto acima, nao parafraseie aqui);
- content_type: um dos tipos permitidos acima;
- importance: um dos niveis permitidos acima;
- page_start: primeira pagina onde este item aparece;
- page_end: ultima pagina onde este item aparece;
- source_block_codes: lista dos codigos de bloco (dos blocos acima) que originaram este item;
- source_order: posicao inteira deste item na ordem de leitura deste chunk, comecando em 1;
- depends_on_temporary_ids: lista de temporary_id de outros itens deste mesmo chunk dos quais este item depende (ex: uma excecao depende de uma regra), ou lista vazia;
- possible_duplicate: true se este conteudo parece repetir algo comum no documento (cabecalho, rodape, citacao repetida) ou algo que provavelmente ja apareceu antes;
- possible_fragment: true se este item parece comecar ou terminar de forma incompleta (continuacao provavel no proximo trecho);
- requires_review: true se voce tem duvida sobre classificacao, limites ou completude deste item;
- review_reason: motivo da duvida quando requires_review=true, ou null.

Retorne somente JSON valido exatamente neste formato:
{{
  "chunk_id": "{chunk_id}",
  "items": [
    {{
      "temporary_id": "TMP-0001",
      "title": "",
      "normalized_content": "",
      "source_text": "",
      "content_type": "",
      "importance": "",
      "page_start": {page_start},
      "page_end": {page_start},
      "source_block_codes": [],
      "source_order": 1,
      "depends_on_temporary_ids": [],
      "possible_duplicate": false,
      "possible_fragment": false,
      "requires_review": false,
      "review_reason": null
    }}
  ],
  "chunk_warnings": [],
  "unprocessed_content": []
}}
"""
    return f"{SYSTEM_PROMPT.strip()}\n\n{language_instruction.strip()}", user_prompt.strip()


COVERAGE_CHECK_PROMPT_VERSION = "source_inventory_coverage_check_v1"

COVERAGE_CHECK_SYSTEM_PROMPT = """
Compare o texto-fonte de um trecho de documento com a lista de itens de inventario ja
identificados a partir dele.
Liste qualquer conceito, fato, definicao, procedimento, exemplo, regra, excecao, numero,
data, observacao ou argumento presente no texto-fonte e ausente nos itens.
Nao crie conteudo externo.
Retorne apenas lacunas verificaveis, com o trecho exato que fundamenta cada lacuna.
Responda apenas com JSON valido, sem markdown, sem comentarios.
"""


def build_coverage_check_prompt(chunk_id: str, source_text: str, items_summary: str) -> tuple[str, str]:
    user_prompt = f"""
Chunk: {chunk_id}

Texto-fonte do trecho:
{source_text}

Itens ja identificados neste trecho (titulo e resumo normalizado):
{items_summary}

Retorne somente JSON valido exatamente neste formato:
{{
  "chunk_id": "{chunk_id}",
  "coverage_status": "complete",
  "missing_content": [
    {{
      "excerpt": "trecho exato do texto-fonte que nao esta representado",
      "reason": "por que este trecho parece nao coberto pelos itens existentes"
    }}
  ],
  "warnings": []
}}

coverage_status deve ser "complete" quando missing_content estiver vazio, ou "incomplete" caso contrario.
"""
    return COVERAGE_CHECK_SYSTEM_PROMPT.strip(), user_prompt.strip()
