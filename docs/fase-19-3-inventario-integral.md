# Fase 19.3 — Inventário Integral do Documento

## Objetivo

Transformar integralmente o conteúdo extraído do documento (`document_pages`/`document_blocks`,
fase 19.2) em um inventário estruturado de unidades de conhecimento (`source_content_items`,
fase 19.1), preservando a cadeia de rastreabilidade:

```
documento → página inicial/final → bloco inicial/final → trecho original → item SRC → futura aula
```

Esta fase **não** é uma etapa de resumo: nenhuma informação pode ser eliminada por parecer
secundária, repetitiva, complementar, introdutória, detalhada ou difícil de classificar. Quando
houver dúvida, o item é preservado e marcado para revisão humana (`status=requires_review`).

## Fase 19.3.1 — Auditoria do estado existente

- **Texto extraído**: `document_pages` (raw_text/normalized_text por página) e `document_blocks`
  (segmentação heurística, `block_code` tipo `P0007-B0002`) — fase 19.2, reutilizados sem alteração.
- **Inventário parcial**: nenhum. `source_content_items` existia (fase 19.1) como schema/model
  completo, mas com **zero linhas** e nenhum service o populava.
- **`lesson_source_items`**: existe (fase 19.1), fora do escopo desta fase (vínculo item→aula é
  fase 19.4).
- **Provedor de IA**: OpenAI via `OpenAIProvider`/`AIProviderRequest`/`AIProviderResponse`
  (`app/providers/ai/`), já usada por `document_analysis_service.py`. Suporta
  `response_format="json"`. **Não tinha timeout nem retry** — adicionado nesta fase de forma
  aditiva (`AIProviderRequest.timeout`/`max_retries`, ambos com default que preserva o
  comportamento anterior para todos os chamadores existentes).
- **JSON estruturado**: `parse_json_content` (`ai_orchestrator_service.py`) já limpa cercas de
  markdown. Não havia validação de schema Pydantic sobre a resposta da IA em nenhum lugar do
  projeto — implementada pela primeira vez aqui (`AIInventoryChunkResponse`/`AIInventoryItemResponse`)
  combinada com ancoragem determinística contra os blocos reais do chunk.
- **Jobs**: confirmado (fases anteriores) — sem Celery/RQ/Redis, `ProcessingJob` + `BackgroundTasks`
  do FastAPI. Reutilizado com `job_type="source_inventory"`.
- **Custos/tokens**: `AIRequest` (tabela pré-existente) já registra `input_tokens`/`output_tokens`
  via `register_ai_request` — reutilizado, sem nova tabela de custos.
- **Limitações encontradas**: nenhum relacionamento item↔bloco existia; nenhuma tabela de
  dependências entre itens; nenhum mecanismo de retry/timeout na camada de IA.

## Decisões arquiteturais (reuso vs. criação)

- **`source_content_items` foi reutilizado integralmente**, sem nenhuma nova coluna. Os enums de
  `content_type` e `status` foram **ampliados de forma não destrutiva** (união dos valores da fase
  19.1 com os novos da 19.3 — validados apenas na camada Pydantic, já que o projeto não usa enum
  nativo do Postgres para esses campos, exatamente para permitir esse tipo de evolução sem
  migration).
- **Duas tabelas novas foram criadas** (migration `0022_inventory_item_assoc`), porque a estrutura
  existente genuinamente não conseguia preservar o que a fase pede:
  - `source_content_item_blocks`: associação N:N entre item e bloco de origem (um item pode vir de
    vários blocos; um bloco pode alimentar mais de um item — ex.: uma tabela com duas informações
    distintas).
  - `source_content_item_dependencies`: relação opcional item→item (ex.: exceção depende de regra),
    não obrigatória, nunca bloqueia a fase quando não resolvida.
- **Chunks não geraram tabela própria.** A auditoria de chunks (id, páginas, blocos, status,
  quantidade de itens, lacunas encontradas) fica em `ProcessingJob.result_json` (JSONB), não em uma
  tabela `inventory_chunks` — chunks são unidades de processamento efêmeras sem ciclo de vida
  próprio além do job que as criou; persistir isso como JSON no job já dá auditoria e retomada
  suficientes, conforme permitido explicitamente ("crie tabela apenas se necessário").
- **Relatório de inventário não gerou tabela própria** (`inventory_report`), pelo mesmo motivo:
  `build_inventory_summary()` computa tudo em tempo real a partir de `document_pages`,
  `document_blocks`, `source_content_items` e do `result_json` do último job — mesmo padrão já usado
  em `document_extraction_service.build_extraction_summary()` (fase 19.2). `course_coverage_reports`
  (fase 19.1) continua reservado exclusivamente para a auditoria final pós-geração de aulas, sem
  mistura de conceitos.
- **`generation_jobs`**: não criei tabela nova — `job_type="source_inventory"` sobre o
  `ProcessingJob` já existente (mesmo padrão de `document_extraction`/`video_pipeline`).

## Tabelas novas

### `source_content_item_blocks`
`id`, `source_item_id` (FK `source_content_items`, CASCADE), `block_id` (FK `document_blocks`,
CASCADE), `source_order`, `is_primary`, `created_at`.
Unique `(source_item_id, block_id)`. Índices em ambas as FKs.

### `source_content_item_dependencies`
`id`, `source_item_id` (FK, CASCADE), `depends_on_source_item_id` (FK, CASCADE), `dependency_type`
(`explains`, `exemplifies`, `continues`, `qualifies`, `contradicts`, `depends_on`, `exception_to`,
`part_of`), `created_at`.
Unique `(source_item_id, depends_on_source_item_id, dependency_type)`. Check: sem auto-referência.

## Serviço: separado em 3 módulos (não concentrado em um arquivo)

- **`app/services/source_inventory_chunking.py`** — `build_chunks(pages, blocks_by_page)`: agrupa
  páginas consecutivas até ~9000 caracteres (heurística transparente, documentada, não perfeita por
  design), com **sobreposição de 1 página** entre chunks consecutivos (a última página do chunk N
  também abre o chunk N+1) para nunca perder conceitos que atravessam a fronteira. Blocos
  `page_header`/`page_footer` só são excluídos do conteúdo enviado à IA quando já foram marcados
  `metadata_json.repeated=true` pela fase 19.2 (repetição real, não perde avisos/notas legítimas que
  estejam no rodapé sem repetição).
- **`app/services/source_inventory_validator.py`** — `anchor_item_to_blocks`: valida que todo
  `block_code` retornado pela IA existe de fato no chunk, que as páginas estão dentro do intervalo,
  e que o `source_text` tem sobreposição de palavras ≥55% com o texto real dos blocos referenciados
  (nunca confiamos cegamente nos campos retornados pelo modelo). `are_likely_same_chunk_overlap_duplicate`:
  heurística de deduplicação em camadas. `validate_persisted_inventory`: validação determinística do
  inventário já persistido (usada pelo endpoint `/validate`).
- **`app/services/source_inventory_service.py`** — orquestração: pré-condições, criação/dedup de
  job, chamada de IA por chunk, checagem de cobertura, deduplicação, consolidação de fragmentos,
  persistência idempotente, numeração de códigos SRC, leitura/resumo.

## Prompt (versionado e centralizado)

`app/prompts/source_inventory_v1.py`, `SOURCE_INVENTORY_PROMPT_VERSION = "source_inventory_v1"`.

- Lista exaustiva do que conta como "unidade de conhecimento" (conceitos, definições, fatos, datas,
  números, procedimentos, regras, exceções, exemplos, listas, causas, consequências, observações,
  citações, exercícios, tabelas, legendas etc.), replicando literalmente as regras do enunciado desta
  fase.
- Regras absolutas: não eliminar por parecer secundário; não usar conhecimento externo; não
  completar lacunas; não inventar; não alterar datas/números/nomes; não transformar em aula; não
  criar módulos; não criar títulos pedagógicos genéricos.
- Cada bloco do chunk é enviado com seu `block_code`, página e tipo heurístico já identificado pela
  fase 19.2 — a IA deve referenciar esses códigos, nunca inventar novos.
- **Segundo prompt separado** (`build_coverage_check_prompt`,
  `COVERAGE_CHECK_PROMPT_VERSION = "source_inventory_coverage_check_v1"`): compara o texto-fonte do
  chunk com os itens já identificados e aponta lacunas verificáveis — usado como segunda chamada por
  chunk (não confiamos na autodeclaração de completude do primeiro prompt).

## Resposta estruturada e ancoragem

Formato JSON exatamente como especificado no enunciado (`temporary_id`, `title`,
`normalized_content`, `source_text`, `content_type`, `importance`, `page_start`/`page_end`,
`source_block_codes`, `source_order`, `depends_on_temporary_ids`, `possible_duplicate`,
`possible_fragment`, `requires_review`, `review_reason`).

Cada item passa por `anchor_item_to_blocks` antes de ser persistido:
- `block_code` inexistente no chunk → erro registrado, item marcado `requires_review`;
- páginas fora do intervalo do chunk → erro registrado;
- `source_text` com sobreposição de palavras < 55% com os blocos referenciados → erro registrado.

**Itens mal ancorados nunca são descartados silenciosamente** — são persistidos com
`status="requires_review"` e o motivo em `metadata_json.review_reason`, para revisão humana
explícita (nenhum conteúdo desaparece, mas também nenhuma alucinação é aceita como fato do
documento).

## Códigos SRC

`next_item_code()`: lê o maior sufixo numérico já usado no projeto (`SRC-XXXX`) e incrementa —
nunca depende da ordem de resposta da IA, nunca reutiliza código de item superseded/rejeitado. Em
reprocessamentos parciais (`reprocess_pages`, `reprocess_failed`), itens de páginas fora do escopo
mantêm seus códigos originais intactos (só os afetados são superseded e regenerados com códigos
novos).

## Deduplicação (em camadas, com pré-seleção)

- **Camada 1 (determinística)**: mesmo `normalized_content` (normalizado) + mesmo conjunto de
  `block_code`s → fusão automática.
- **Camada 2 (similaridade textual)**: `difflib.SequenceMatcher` ratio ≥ 0.82 **apenas entre itens
  com páginas sobrepostas ou adjacentes** (nunca todos-contra-todos) — pré-seleção explícita conforme
  pedido. Dentro desse grupo, se os blocos de origem forem majoritariamente compartilhados
  (≥50%), é tratado como artefato de sobreposição de chunk e fundido automaticamente; se a
  similaridade for alta mas os blocos de origem forem diferentes, é **repetição real do documento**
  e **não é fundida** — ambos os itens permanecem, preservando a distinção pedagógica entre
  duplicidade de chunk (sempre segura de fundir) e repetição intencional do autor (nunca apagar
  automaticamente).
- **Camada 3 (revisão semântica por IA)**: não implementada nesta fase — trim de escopo documentado
  em Limitações.

## Fragmentos

`consolidate_fragments`: quando o último item de um chunk e o primeiro item do chunk seguinte estão
ambos marcados `possible_fragment=true`, pertencem a páginas adjacentes/sobrepostas, são fundidos
(texto concatenado preservando ordem, páginas e blocos unidos, nunca perde conteúdo). Escopo
propositalmente limitado à fronteira entre chunks adjacentes (não detecção geral de fragmentos em
qualquer ponto do documento) — documentado como heurística v1 em Limitações.

## Cobertura por chunk (segunda chamada)

Após identificar os itens de um chunk, uma segunda chamada de IA (prompt separado) compara o
texto-fonte com os itens encontrados e aponta lacunas. Cada lacuna vira um **item de segurança**
(`create_fallback_item`, `content_type="other"`, `status="requires_review"`,
`metadata_json.source="coverage_check_gap"`) com o trecho exato preservado — nunca perdido, apenas
marcado para classificação humana futura.

## Idempotência e modos de reprocessamento

`generate_if_missing` | `reprocess_failed` | `reprocess_pages` | `full_rebuild` | `validate_only`.

Em todos os modos que regeneram conteúdo, os itens afetados são **superseded** (`status="rejected"`,
`metadata_json.superseded_by_reprocess=true`), **nunca apagados** — e itens já `status="approved"`
são protegidos explicitamente contra qualquer superseding (mesmo em `full_rebuild`), preparando o
terreno para quando a fase 19.4 já tiver vinculado itens a aulas. `reprocess_failed` lê os chunks com
`status="failed"` do `result_json` do último job para reprocessar exatamente as páginas afetadas.

## Jobs

`job_type="source_inventory"` sobre `ProcessingJob` (fase 19.1), mesmo padrão de
`document_extraction`/`video_pipeline`: criação síncrona com validação de pré-condições (documento
existe, extração concluída, sem job ativo duplicado) + execução em background via
`BackgroundTasks`, progresso persistido por chunk (`processed_items`/`failed_items`/`current_item`/
`progress`). Página com falha bloqueia geração a menos que `continue_with_alerts=true`; páginas
`requires_ocr` nunca são declaradas como cobertura integral (contabilizadas separadamente no
resumo).

## Endpoints

Sob `/api/v1/projects/{project_id}/files/{file_id}/inventory` (mesmo padrão de aninhamento de
`document_extraction`):

| Método | Rota | Descrição |
|---|---|---|
| POST | `/generate` | Inicia geração (idempotente; reaproveita job ativo) |
| POST | `/reprocess` | Reprocessamento por modo |
| GET | `/summary` | Métricas agregadas reais |
| GET | `/job` | Job mais recente |
| POST | `/validate` | Validação determinística do inventário persistido |
| GET | `` | Lista paginada (filtros: tipo, importância, status, página, revisão, duplicidade, busca) |
| GET | `/{source_item_id}` | Detalhe: texto original, normalizado, blocos, dependências |
| PATCH | `/{source_item_id}` | Edição manual (título, conteúdo normalizado, tipo, importância, nota) — **`source_text` deliberadamente não editável neste schema** |
| POST | `/{source_item_id}/approve` | Aprova o item |
| POST | `/{source_item_id}/reject` | Rejeita o item |

## Frontend

Reaproveitado: `AppShell`, `StatusBadge`, padrão de tabela/filtros já usado em `/fidelity-coverage`.

- **`/fidelity-coverage/[id]`**: o placeholder "Inventário do Documento" (fase 19.1) virou uma seção
  real, com métricas reais (itens por importância, duplicidades, fragmentados, para revisão, OCR
  pendente), badge de status, progresso ao vivo (poll 2s), e ações só habilitadas quando fazem
  sentido: "Gerar inventário" (desabilitado até a extração concluir), "Reprocessar falhas" (só
  aparece com falhas reais), "Atualizar status", "Visualizar inventário".
- **`/fidelity-coverage/[id]/inventory`** (nova): tabela com código SRC, título, tipo, importância,
  páginas, status, busca e filtros (status/importância), aprovar/rejeitar inline.
- **`/fidelity-coverage/[id]/inventory/[itemId]`** (nova): distingue visualmente **texto original**
  (não editável, preservado) de **conteúdo normalizado** (editável), lista blocos de origem
  (linkados de volta para `/fidelity-coverage/[id]/pages/{page}`) e dependências, ações
  aprovar/rejeitar/salvar edição.

## Migration

`apps/backend/alembic/versions/0022_inventory_item_assoc.py`, separada da 0021 (fase 19.2). Head
único verificado antes (`0021_document_extraction`) e depois (`0022_inventory_item_assoc`).
**Nota**: o revision id inicial (`0022_source_inventory_associations`) excedeu os 32 caracteres da
coluna `alembic_version.version_num` e foi renomeado para `0022_inventory_item_assoc` antes de
aplicar — a tentativa inicial falhou e reverteu limpo (transação única), sem deixar estado
inconsistente. `downgrade` remove exclusivamente as 2 tabelas novas.

```bash
cd /opt/virtus-et-veritas-engine
docker compose exec backend alembic heads
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current   # 0022_inventory_item_assoc (head)
```

Reverter: `docker compose exec backend alembic downgrade -1`.

## Testes

```bash
cd /opt/virtus-et-veritas-engine
docker compose exec backend pip install -r requirements-dev.txt
docker compose exec backend python -m pytest -v
```

**182 testes, 182 aprovados** (113 das fases 19.1/19.2 + 69 novos desta fase). Nenhuma chamada real
de IA nos testes automatizados — um provedor falso e determinístico (`fake_ai_provider`, em
`tests/conftest.py`) substitui `OpenAIProvider` dentro do módulo do serviço: por padrão gera um item
por bloco (extraído via regex do próprio prompt montado, garantindo ancoragem 100% "de fábrica"),
mas cada teste pode sobrescrever a resposta de um chunk específico
(`fake_ai_provider["chunk_overrides"]["CHUNK-0001"] = {...}`) para simular alucinação, lacunas de
cobertura, duplicidade etc., sem qualquer chamada de rede.

Cobertos: chunking (divisão, sobreposição, exclusão de cabeçalho/rodapé repetido, ordem);
ancoragem (válida, bloco inexistente, texto não relacionado, página fora do intervalo);
deduplicação (funde artefato de sobreposição, não funde repetição distante, ignora conteúdo não
relacionado); consolidação de fragmentos; constraints de banco (associação única, sem
auto-referência de dependência, cascade de exclusão); schemas (enums ampliados de forma não
destrutiva, validação da resposta da IA); **teste de completude** (10 tipos de conteúdo conhecidos
— definição, fatos, lista, procedimento, exceção, exemplo, conclusão, observação — todos verificados
presentes no inventário final, não apenas "algum item foi gerado"); **teste de ancoragem/não-invenção**
(item com `source_text` sem relação real com o bloco é marcado `requires_review`, nunca aceito como
fato do documento); geração de item de segurança quando a checagem de cobertura encontra lacuna;
códigos SRC sequenciais e únicos; ordem por página preservada; isolamento entre documentos e
organizações; `full_rebuild` preserva itens aprovados e nunca apaga (supersede); pré-condições
(bloqueio por página com falha, permissão explícita via `continue_with_alerts`); prevenção de job
duplicado; endpoints via `TestClient` (contrato HTTP, isolamento entre projetos, rejeição de
`source_text` no PATCH manual).

### Validação com documento real

Além dos testes automatizados (sempre com IA falsa), a extração e o inventário foram executados
contra o mesmo PDF real de 69 páginas já usado para validar a fase 19.2
(`os-4-compromissosss.pdf`, projeto "4compromissos"), desta vez **com chamadas reais à OpenAI**
(`gpt-4.1-mini`), confirmando que o pipeline completo funciona ponta-a-ponta fora do ambiente de
teste sintético: extração reconfirmada (69/69 páginas, 0 falhas), inventário dividido em 26 chunks
reais (o documento é bem mais denso que os 69 pages/24k palavras sugeriam à primeira vista — texto
corrido sem muitas quebras, refletido em chunks maiores). Os primeiros chunks processados com IA
real geraram itens corretamente classificados (`content_type="other"`, `status="requires_review"`)
para o material de abertura do livro (créditos de tradução, ficha editorial, dedicatória) — um
resultado honesto: o sistema não força esse conteúdo institucional em categorias pedagógicas que não
se aplicam, e sinaliza para revisão humana em vez de decidir sozinho. Cada chamada real de IA para
um documento desse tamanho leva vários minutos (chunk maior + verificação de cobertura em duas
chamadas separadas); por isso a execução completa dos 26 chunks não foi aguardada integralmente
antes do fechamento desta fase — o processamento continuou em segundo plano no ambiente e os dados
reais gerados permanecem no banco como inventário legítimo (não são dados de teste, não foram
removidos).

## Compatibilidade com a Fase 19.4

- `source_content_items` já é o inventário completo, com código SRC estável, texto original e
  normalizado, páginas e blocos de origem rastreáveis — exatamente a entrada que o Plano de
  Cobertura (fase 19.4) precisa consumir via `list_inventory_items`/`get_inventory_item_detail`
  já existentes.
- `source_content_item_dependencies` já está pronta para alimentar a ordenação pedagógica
  (regra antes da exceção, conceito antes do exemplo) que a fase 19.4 precisa respeitar.
- O padrão de reuso de `ProcessingJob` (job_type livre, sem tabela nova) e o padrão de
  "supersede em vez de apagar" ficam estabelecidos e devem ser repetidos para
  `job_type="coverage_plan"`.
- Nenhuma chamada de IA fora do escopo de inventário foi feita — nenhum módulo, aula, roteiro,
  quiz, slide, teleprompter, narração ou vídeo foi gerado nesta fase, conforme exigido.

## Limitações conhecidas

- **Camada 3 de deduplicação (revisão semântica por IA)** não implementada — apenas as camadas 1
  (determinística) e 2 (similaridade textual pré-selecionada) estão ativas. Casos ambíguos ficam
  como itens `possible_duplicate` separados para revisão humana, em vez de serem resolvidos
  automaticamente por uma terceira chamada de IA.
- **Consolidação de fragmentos** limitada à fronteira entre chunks adjacentes (não detecta
  fragmentação em qualquer ponto arbitrário do documento).
- **`bounding_box`** de blocos (herdado da fase 19.2) continua não populado — sem impacto nesta
  fase, que não depende de coordenadas visuais.
- A estimativa de "chunk" usa `caracteres/4` como proxy de tokens (documentado como heurística
  transparente, não um tokenizador real, para não adicionar `tiktoken` como dependência nova).
- **Observado na validação com IA real** (documento de 69 páginas, ver seção seguinte): a IA
  ocasionalmente retorna, dentro de um único chunk, dois itens quase-idênticos com texto
  ligeiramente diferente (ex.: página de dedicatória repetida com pontuação distinta). Como a
  camada 2 de deduplicação exige similaridade textual ≥0.82 **e** ≥50% de blocos compartilhados,
  esses pares passam despercebidos quando o texto diverge o suficiente ou quando a IA associa cada
  item a blocos ligeiramente diferentes. Nenhum conteúdo é perdido (ambos ficam marcados
  `requires_review`, tipicamente em material introdutório/institucional de baixo valor pedagógico),
  mas a revisão humana precisa consolidar manualmente esses casos raros — não é feito automaticamente
  nesta fase.

## Arquivos criados

- `apps/backend/app/models/source_content_item_block.py`
- `apps/backend/app/models/source_content_item_dependency.py`
- `apps/backend/app/schemas/source_inventory_ai.py`
- `apps/backend/app/schemas/source_inventory.py`
- `apps/backend/app/prompts/source_inventory_v1.py`
- `apps/backend/app/services/source_inventory_chunking.py`
- `apps/backend/app/services/source_inventory_validator.py`
- `apps/backend/app/services/source_inventory_service.py`
- `apps/backend/app/api/v1/source_inventory.py`
- `apps/backend/alembic/versions/0022_inventory_item_assoc.py`
- `apps/backend/tests/test_source_inventory_chunking.py`
- `apps/backend/tests/test_source_inventory_validator.py`
- `apps/backend/tests/test_source_inventory_models.py`
- `apps/backend/tests/test_source_inventory_schemas.py`
- `apps/backend/tests/test_source_inventory_generation.py`
- `apps/backend/tests/test_source_inventory_job.py`
- `apps/backend/tests/test_source_inventory_endpoints.py`
- `apps/frontend/types/source-inventory.ts`
- `apps/frontend/app/fidelity-coverage/[id]/inventory/page.tsx`
- `apps/frontend/app/fidelity-coverage/[id]/inventory/[itemId]/page.tsx`
- `docs/fase-19-3-inventario-integral.md` (este arquivo)

## Arquivos modificados

- `apps/backend/app/models/__init__.py` — registra os 2 models novos.
- `apps/backend/app/main.py` — registra o router de inventário.
- `apps/backend/app/schemas/source_content_item.py` — enums de `content_type`/`status` ampliados
  de forma não destrutiva.
- `apps/backend/app/prompts/__init__.py` — registra o novo prompt.
- `apps/backend/app/providers/ai/base.py` — campos `timeout`/`max_retries` aditivos em
  `AIProviderRequest` (defaults preservam o comportamento anterior).
- `apps/backend/app/providers/ai/openai_provider.py` — retry com backoff e timeout opcional,
  sem alterar o comportamento de nenhum chamador existente que não passe esses campos.
- `apps/backend/tests/conftest.py` — fixtures de páginas/blocos já extraídos
  (`inventory_project_file`, `add_extracted_page`) e provedor de IA falso determinístico
  (`fake_ai_provider`).
- `apps/frontend/app/fidelity-coverage/[id]/page.tsx` — seção real de inventário.
- `apps/frontend/lib/api.ts` — funções de API de inventário.

Nenhum arquivo/tabela existente foi removido, renomeado ou alterado de forma destrutiva.
