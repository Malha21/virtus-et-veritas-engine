COVERAGE_PLAN_PROMPT_VERSION = "coverage_plan_v1"

SYSTEM_PROMPT = """
Voce esta organizando um inventario documental (uma lista de unidades de conhecimento
ja extraidas de um documento) em uma estrutura pedagogica de modulos e aulas.

Sua tarefa nao e criar conteudo novo.
Sua tarefa nao e resumir o documento.
Sua tarefa e distribuir integralmente todos os itens fornecidos em modulos e aulas coerentes.

Regras absolutas:
- Nenhum item pode ser omitido.
- Nenhum item pode ser criado (todo source_item_id que voce usar deve vir exatamente da lista fornecida).
- Cada item deve aparecer em pelo menos uma aula.
- Preserve dependencias entre itens (regra antes da excecao, conceito antes do exemplo, causa antes da consequencia).
- Preserve excecoes, exemplos, procedimentos, exercicios, numeros, datas e observacoes -- nunca os descarte.
- Organize do basico ao avancado: introducao antes do aprofundamento, definicao antes da comparacao,
  procedimento antes do exemplo de aplicacao, conclusao ao final do conjunto.
- Agrupe assuntos relacionados; nao misture assuntos desconexos apenas para preencher tempo.
- Cada aula deve ter no maximo {max_lesson_minutes} minutos, calculados a {words_per_minute} palavras por minuto.
- Quando o conteudo de um assunto exceder o limite de uma aula, crie mais aulas -- nunca reduza conteudo para caber.
- Prefira titulos de aula especificos e pedagogicos; use "Parte 1"/"Parte 2" apenas quando o conteudo for
  realmente uma continuacao inseparavel (registre isso em grouping_reason).
- Nao escreva o roteiro completo da aula (isso acontece em uma fase posterior).
- Nao invente objetivos de aprendizagem incompativeis com o conteudo fornecido.
- Nao adicione conhecimento externo ao documento.
- Responda apenas com JSON valido, sem markdown, sem comentarios, sem texto fora do JSON.
"""


def build_language_instruction(generation_language: str) -> str:
    if generation_language == "en-US":
        return """
Language rule:
- Write every title, description, learning_objective and grouping_reason 100% in English.
"""
    return """
Regra de idioma:
- Escreva todo title, description, learning_objective e grouping_reason 100% em portugues do Brasil.
"""


def build_coverage_plan_prompt(
    project_title: str,
    batch_id: str,
    items: list[dict],
    generation_language: str = "pt-BR",
    words_per_minute: int = 130,
    max_lesson_minutes: int = 10,
    continuation_context: str | None = None,
) -> tuple[str, str]:
    """Monta o prompt para organizar um lote de source_content_items (ja aprovados/estruturados
    pela fase 19.3) em modulos e aulas.

    `items` e uma lista de dicts com: source_item_id, item_code, title, normalized_content,
    source_text, content_type, importance, source_order, page_start, page_end,
    depends_on_item_codes (dependencias conhecidas, se houver).
    """
    language_instruction = build_language_instruction(generation_language)
    system_prompt = SYSTEM_PROMPT.format(
        max_lesson_minutes=max_lesson_minutes, words_per_minute=words_per_minute
    ).strip()

    items_text = "\n\n".join(
        f"[{item['item_code']} | tipo: {item['content_type']} | importancia: {item['importance']} | "
        f"paginas: {item.get('page_start')}-{item.get('page_end')} | ordem original: {item['source_order']}"
        + (
            f" | depende de: {', '.join(item['depends_on_item_codes'])}"
            if item.get("depends_on_item_codes")
            else ""
        )
        + "]\n"
        f"Titulo: {item['title']}\n"
        f"Conteudo normalizado: {item['normalized_content']}"
        for item in items
    )

    continuation_block = (
        f"\nContinuacao: este lote da sequencia do documento apos um lote ja organizado. "
        f"Contexto do ultimo modulo/aula ja definidos, para decidir se deve continuar o mesmo "
        f"modulo ou abrir um novo:\n{continuation_context}\n"
        if continuation_context
        else ""
    )

    user_prompt = f"""
{language_instruction}

Projeto: {project_title}
Lote: {batch_id}
{continuation_block}
Parametros de duracao: {words_per_minute} palavras por minuto, maximo de {max_lesson_minutes} minutos por aula
(aproximadamente {words_per_minute * max_lesson_minutes} palavras).

Itens do inventario a organizar (use exatamente os codigos abaixo como source_item_id nos itens
de cada aula; nao invente nem omita nenhum):

{items_text}

Para cada modulo, retorne: temporary_id (ex: "MOD-TMP-001"), title, description, learning_objective,
module_order (comecando em 1) e a lista de lessons.

Para cada aula, retorne: temporary_id (ex: "LES-TMP-001"), title, description, learning_objective,
lesson_order (comecando em 1 dentro do modulo), estimated_word_count, estimated_duration_minutes,
source_items (lista de {{source_item_id, source_order_in_lesson, is_required, relationship_type}},
onde relationship_type e "primary" para o uso principal do item, "supporting" para reforco/retomada,
ou "reference" para citacao de contexto), grouping_reason (por que estes itens formam esta aula),
dependencies (lista de item_code dos quais esta aula depende pedagogicamente), requires_review
(true se voce tem duvida sobre o agrupamento) e warnings (lista de alertas, ex: duracao no limite).

Retorne somente JSON valido exatamente neste formato:
{{
  "plan_version": 1,
  "modules": [
    {{
      "temporary_id": "MOD-TMP-001",
      "title": "",
      "description": "",
      "learning_objective": "",
      "module_order": 1,
      "lessons": [
        {{
          "temporary_id": "LES-TMP-001",
          "title": "",
          "description": "",
          "learning_objective": "",
          "lesson_order": 1,
          "estimated_word_count": 0,
          "estimated_duration_minutes": 0,
          "source_items": [
            {{
              "source_item_id": "",
              "source_order_in_lesson": 1,
              "is_required": true,
              "relationship_type": "primary"
            }}
          ],
          "grouping_reason": "",
          "dependencies": [],
          "requires_review": false,
          "warnings": []
        }}
      ]
    }}
  ],
  "mapped_source_item_ids": [],
  "unmapped_source_item_ids": [],
  "duplicate_mappings": [],
  "warnings": []
}}
"""
    return system_prompt, user_prompt.strip()
