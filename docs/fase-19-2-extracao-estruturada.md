# Fase 19.2 — Extração Estruturada do Documento

## Objetivo

Garantir que qualquer PDF enviado seja extraído integralmente e transformado em uma
representação estruturada, rastreável e persistida no banco, preservando:

```
documento → página → bloco → texto original
```

Sem criar módulos, aulas ou roteiros (isso fica para fases futuras). Sem inventar,
resumir ou remover conteúdo silenciosamente.

## Fase 19.2.1 — Auditoria da extração existente (antes de alterar código)

- **Biblioteca de PDF**: `pypdf` 5.1.0, já usada apenas para extração de texto simples
  (`app/services/pdf_service.py`). Confirmado (via teste direto no container) que essa
  versão suporta `extract_text(visitor_text=...)` (posição/tamanho de fonte por trecho)
  e `page.images` (detecção de imagens embutidas) — **nenhuma dependência nova foi
  necessária**.
- **Onde o texto era salvo**: um único arquivo `.txt` por documento
  (`ProjectFile.extracted_text_path`), sem separação por página.
- **Numeração de páginas**: não era preservada — `pdf_service.extract_text_from_pdf`
  descartava páginas sem texto ao concatenar (`if cleaned: page_texts.append(...)`),
  desalinhando a numeração real.
- **Layout**: totalmente perdido (sem posição, sem fonte).
- **Tabelas**: não detectadas.
- **Imagens**: ignoradas.
- **OCR**: inexistente (sem `pytesseract`/`pdf2image`/`Pillow` no projeto).
- **PDFs escaneados**: causavam falha total do job (`PDFTextExtractionError`), sem
  granularidade por página.
- **Tratamento de erros**: tudo-ou-nada, um erro qualquer falhava o documento inteiro.
- **Retomada**: inexistente — reprocessar reescrevia o único arquivo de texto do zero.
- **Padrão de jobs confirmado**: sem Celery/RQ/Dramatiq/Redis. O projeto usa
  `ProcessingJob` (fase 19.1) + `BackgroundTasks` do FastAPI — a rota cria o job
  sincronamente e agenda a execução real via `background_tasks.add_task(...)`, que abre
  uma `SessionLocal()` própria e processa item a item, commitando progresso
  incrementalmente (padrão maduro já usado em `video_pipeline_service.py`). **Reutilizado
  integralmente**, nenhum mecanismo de fila novo foi criado.
- **Checksum**: já existia (`ProjectFile.checksum`, SHA-256, calculado no upload) —
  reutilizado, não duplicado.

## Arquitetura implementada

### Tabelas novas

#### `document_pages`
Uma linha por página extraída de um documento (`project_files`).

Campos: `id`, `project_file_id` (FK `project_files`, CASCADE), `page_number`,
`raw_text` (preservado, nunca sobrescrito), `normalized_text` (só transformações
seguras), `character_count`, `word_count`, `extraction_status`, `extraction_method`,
`has_text`, `requires_ocr`, `metadata_json` (JSONB — ex.: `has_images`), `created_at`,
`updated_at`.

- Unique: `(project_file_id, page_number)`.
- Check: `page_number > 0`.
- Índices: `project_file_id`, `page_number`, `extraction_status`.
- `extraction_status` ∈ {pending, processing, extracted, empty, failed, requires_ocr,
  reviewed}.

#### `document_blocks`
Segmentação heurística de cada página em blocos, na ordem de leitura.

Campos: `id`, `project_file_id` (FK, CASCADE), `page_id` (FK `document_pages`,
CASCADE), `block_code` (ex.: `P0007-B0002`), `block_type`, `block_order`, `source_text`,
`normalized_text`, `bounding_box` (JSONB, hoje não populado — pypdf não expõe bbox por
trecho de forma confiável), `confidence_score` (Numeric 5,2), `metadata_json` (JSONB —
ex.: `table_rows`, `repeated`), `created_at`, `updated_at`.

- Unique: `(project_file_id, block_code)` e `(page_id, block_order)`.
- Check: `block_order >= 0`; `confidence_score` entre 0 e 100.
- Índices: `project_file_id`, `page_id`, `block_type`.
- `block_type` ∈ {title, heading, paragraph, list_item, table, table_row,
  image_caption, footnote, quotation, page_header, page_footer, unknown}.

### `processing_jobs` (reutilizado, não duplicado)

`job_type="document_extraction"`. Usa as colunas já adicionadas na fase 19.1
(`project_file_id`, `total_items`, `processed_items`, `failed_items`, `current_item`,
`progress`, `status`, `error_message`, `started_at`, `finished_at`, `payload_json`,
`result_json`). O `payload_json` guarda `{project_file_id, scope, page_number,
checksum}` para permitir retomada/reprocessamento com contexto.

## Serviço: `app/services/document_extraction_service.py`

Responsabilidades separadas em funções puras/testáveis (não uma classe monolítica):

- **Extração por página** (`extract_page_raw`): `pypdf` com `visitor_text` capturando
  `(texto, tamanho_de_fonte)` por trecho, e `page.images` para detectar imagens
  embutidas.
- **Normalização** (`normalize_text`): apenas transformações seguras — junta palavras
  quebradas por hífen entre linhas, colapsa espaços/tabs duplicados, remove caracteres
  de controle invisíveis, padroniza quebras de parágrafo. **Nunca** resume, reescreve,
  remove frases ou altera números/datas/nomes. `raw_text` é sempre preservado à parte,
  nunca sobrescrito.
- **Segmentação heurística** (`segment_page_blocks` + `classify_chunk`): divide a
  página em blocos por linhas em branco, com heurísticas **sem IA** (conforme exigido
  nesta fase):
  - marcadores de lista (`-`, `•`, `1.`, `(a)`) → `list_item`, um bloco por item;
  - linhas com ≥2 colunas separadas por espaços largos, repetido em ≥2 linhas →
    `table` (linhas/colunas preservadas em `metadata_json.table_rows`);
  - `Figura/Tabela/Quadro N:` → `image_caption`;
  - linha numerada curta ou nota de rodapé (`(1)`, `Nota:`) → `footnote`;
  - texto entre aspas/aspas angulares → `quotation`;
  - texto curto em CAIXA ALTA, numeração de capítulo (`1.2 Título`), ou fonte ≥15%
    maior que a fonte dominante da página (via `visitor_text`) → `title`/`heading`;
  - restante → `paragraph`.
- **Cabeçalhos/rodapés repetidos** (`detect_repeated_edges` +
  `finalize_header_footer_detection`): após extrair todas as páginas, compara o
  primeiro e o último bloco de cada página; se um texto (normalizado, com números
  substituídos por `#`) se repete em ≥40% das páginas (mínimo 3), os blocos
  correspondentes são reclassificados como `page_header`/`page_footer` com
  `metadata_json.repeated=true`. **O conteúdo nunca é apagado do `raw_text`** — apenas
  reclassificado, para que fases futuras decidam se entra no inventário.
- **Detecção de `requires_ocr`**: página sem texto e com imagem → `requires_ocr`;
  página sem texto e sem imagem → `empty` (não confundido com falha); pouco texto
  (<10 caracteres) com imagem → `requires_ocr`. **Nenhum OCR foi instalado ou
  executado** — apenas marcação, conforme instruído (o projeto não tinha
  infraestrutura de OCR).
- **Idempotência**: `upsert_page` (get-or-create por `project_file_id`+`page_number`,
  depois atualiza em vez de duplicar) e `replace_page_blocks` (apaga só os blocos
  *daquela página* antes de recriar — nunca afeta outras páginas ou documentos).
  Reprocessar o mesmo documento não cria linhas duplicadas.
- **Falha granular por página**: cada página é processada dentro de seu próprio
  `try/except`; uma falha marca aquela página como `failed` (com o erro em
  `metadata_json`) e o job continua para as demais — uma página ruim nunca aborta o
  documento inteiro (só uma falha ao *abrir* o PDF, ou arquivo ausente, é fatal para o
  job).

## Jobs (retomável, persistente)

`create_extraction_job` cria o `ProcessingJob` e impede duplicação: se já existe um job
`pending/queued/processing` para o mesmo documento, ele é reaproveitado em vez de criar
um novo (endpoint idempotente para chamadas concorrentes). `run_document_extraction` é
a função de background (mesmo padrão de `video_pipeline_service.run_video_pipeline_job`):
abre `SessionLocal()` própria, processa, e nunca deixa o job "preso" — qualquer exceção
não tratada marca o job como `failed` com a mensagem de erro.

Progresso é persistido a cada página (`update_job_progress`): `processed_items`,
`failed_items`, `current_item`, `progress` (%). Como tudo fica no banco, o estado
sobrevive a um reinício do backend — só a *continuação automática* de um job travado a
meio caminho não é feita (não existe supervisor/watchdog no projeto); o usuário pode
disparar reprocessamento (`scope=failed`) manualmente a qualquer momento.

## Reprocessamento

`POST .../extraction/reprocess` aceita `scope`:
- `all`: reextrai o documento inteiro;
- `failed`: só páginas com `extraction_status=failed` (exige extração prévia);
- `requires_ocr`: só páginas marcadas `requires_ocr` (exige extração prévia);
- `page`: uma página específica (`page_number` obrigatório, precisa já existir).

## Endpoints criados

Todos sob `/api/v1/projects/{project_id}/files/{file_id}` (mesmo padrão de
`files.py`, que já usa `project_id` + `file_id` aninhados):

| Método | Rota | Descrição |
|---|---|---|
| POST | `/extraction` | Inicia extração (idempotente; reaproveita job ativo) |
| GET | `/extraction` | Resumo/métricas agregadas |
| GET | `/extraction/job` | Job mais recente |
| POST | `/extraction/reprocess` | Reprocessamento por escopo |
| GET | `/pages` | Lista paginada (filtros: `extraction_status`, `requires_ocr`) |
| GET | `/pages/{page_number}` | Detalhe: `raw_text`, `normalized_text`, blocos |
| GET | `/blocks` | Lista (filtros: `page_number`, `block_type`) |

Todos validam acesso via `get_project_by_id` (organização) antes de tocar no documento;
`get_project_file_for_extraction` também rejeita arquivos não-PDF. Nenhum stack trace ou
caminho interno de servidor é retornado ao cliente.

## Frontend

Reaproveitado: `AppShell`, `StatusBadge`, `EmptyState`, padrão de tabela/filtros já
usado em `/fidelity-coverage`. Nenhum componente duplicado.

- **`/fidelity-coverage/[id]`**: nova seção "Extração do Documento" (primeira etapa,
  acima dos placeholders "Em breve" de inventário/cobertura/auditoria/aprovação
  criados na fase 19.1) com métricas reais, badge de status (Não iniciado / Na fila /
  Processando / Concluído / Concluído com alertas / Falhou), barra de progresso durante
  o processamento (poll a cada 2s reaproveitando o padrão já usado em
  `projects/[id]/page.tsx`), e ações **só habilitadas quando o endpoint existe de
  fato**: "Iniciar extração", "Reprocessar falhas" (só aparece se `failed_pages > 0`),
  "Atualizar status", "Visualizar páginas".
- **`/fidelity-coverage/[id]/pages`** (nova): tabela de páginas com status, palavras,
  caracteres, blocos, método, `requer OCR`, filtros por status e por OCR.
- **`/fidelity-coverage/[id]/pages/[pageNumber]`** (nova): alterna entre texto
  normalizado e texto bruto (`<pre>` com `whitespace-pre-wrap`, sem
  `dangerouslySetInnerHTML`), e lista os blocos na ordem de leitura com tipo e código.

Tipos novos: `apps/frontend/types/document-extraction.ts`. `types/processing.ts`
(`ProcessingJob`) ganhou os campos `project_file_id`, `total_items`, `processed_items`,
`failed_items`, `current_item` (já existentes no backend desde a fase 19.1, agora
expostos no frontend).

## Migration

`apps/backend/alembic/versions/0021_document_extraction.py`, separada da 0020 (fase
19.1). Head único verificado antes (`0020_fidelity_coverage_engine`) e depois
(`0021_document_extraction`). `downgrade` remove exclusivamente as 2 tabelas novas,
sem tocar em nenhuma tabela pré-existente. Testado manualmente: `downgrade -1` →
`upgrade head`, sem erros.

```bash
cd /opt/virtus-et-veritas-engine
docker compose exec backend alembic heads
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current   # 0021_document_extraction (head)
```

Reverter:
```bash
docker compose exec backend alembic downgrade -1
```

## Testes

`pytest` não é instalado na imagem de produção (mantém a imagem enxuta); instalar a
partir de `requirements-dev.txt` só para rodar a suíte:

```bash
cd /opt/virtus-et-veritas-engine
docker compose exec backend pip install -r requirements-dev.txt
docker compose exec backend python -m pytest -v
```

Todos os testes rodam contra o Postgres real via `docker-compose`, dentro de uma
transação com `SAVEPOINT` revertida ao final (`tests/conftest.py`, herdado da fase
19.1) — nenhum dado de teste é persistido. Os PDFs de teste são gerados de verdade via
`reportlab` (já era dependência do projeto) e escritos em disco durante o teste
(`tests/conftest.py::written_pdf_files` garante a limpeza dos arquivos ao final, mesmo
em caso de falha).

**Resultado: 113 testes, 113 aprovados** (38 da fase 19.1 + 75 novos desta fase),
cobrindo:
- normalização (junção de hífen, colapso de espaços, preservação de números/datas/
  acentos/marcadores de lista);
- segmentação heurística (listas, legendas, tabelas, classificação de heading/
  paragraph);
- detecção de cabeçalho/rodapé repetido;
- extração ponta-a-ponta com PDF real gerado via `reportlab` (4 páginas, incluindo uma
  em branco), verificando: uma linha por página, ordem preservada, página vazia
  detectada corretamente, `raw_text` e `normalized_text` preservados separadamente,
  blocos na ordem de leitura, detecção de `list_item`/`image_caption`;
- **idempotência**: reprocessar o mesmo documento não duplica páginas nem blocos;
- **isolamento entre documentos**: extrair um documento não cria páginas em outro;
- **PDF corrompido** e **arquivo inexistente** → `DocumentExtractionError`, sem
  derrubar o processo;
- **job duplicado**: chamar `create_extraction_job` duas vezes seguidas reaproveita o
  mesmo job ativo;
- reprocessamento por escopo (`all`/`failed`/`requires_ocr`/`page`), incluindo rejeição
  quando não há extração prévia ou a página não existe;
- constraints de banco: `page_number` único por documento (mas repetível entre
  documentos), `page_number > 0`, `block_code` único por documento, `(page_id,
  block_order)` único, `block_order >= 0`, `confidence_score` entre 0–100;
- cascade de exclusão (`project_file` → `document_pages` → `document_blocks`);
- validações Pydantic (status/tipo inválidos, `scope=page` exige `page_number`);
- **teste de não-perda** (`test_document_extraction_no_loss.py`): PDF com números,
  datas, título, nome próprio e itens de lista conhecidos — verifica que todos os
  valores sobrevivem tanto no `raw_text` quanto no `normalized_text`, e que a ordem de
  leitura é preservada;
- endpoints via `TestClient` (contrato HTTP, códigos de status, isolamento entre
  organizações/projetos, validação de payload) — os testes de `POST` substituem a
  função de background por um dublê para nunca escrever na base real fora da
  transação revertida do teste (o job real usa `SessionLocal()` própria, fora da
  transação de teste, então executá-lo de verdade commitaria dados permanentes).

### Validação com documento real

Além dos testes automatizados, a extração foi executada diretamente contra um PDF real
já presente no sistema (`os-4-compromissosss.pdf`, projeto "4compromissos"): **69
páginas, 0 falhas, 6.14s**, batendo exatamente com o número de páginas descrito no
`CLAUDE.md`. Detectou corretamente 1 página vazia e 1 página `requires_ocr` (a capa,
provavelmente uma imagem sem texto), gerando 112 blocos classificados em 5 tipos. Essa
extração real permanece no banco (não é dado de teste — é o resultado legítimo da
funcionalidade para um projeto real). Confirmado visualmente no navegador (login real,
screenshots das 3 telas novas, sem erros de console).

## Compatibilidade com a Fase 19.3

- `document_blocks.source_text`/`normalized_text` + `block_type` são exatamente a
  matéria-prima que o inventário (fase 19.3, com IA) vai ler para gerar
  `source_content_items` (fase 19.1) — a rastreabilidade
  `documento → página → bloco` já está pronta para ganhar o próximo elo,
  `bloco → item do inventário`.
- `metadata_json` de blocos e páginas já comporta os sinais que a fase 19.3 vai
  precisar (`repeated`, `has_images`, `table_rows`) sem precisar de migration nova.
- Nenhuma chamada de IA, prompt ou classificação semântica foi implementada nesta
  fase — escopo mantido estritamente em extração estrutural/heurística, conforme
  solicitado.

## Limitações conhecidas

- `bounding_box` existe no schema mas não é populado: `pypdf` não expõe coordenadas
  de bloco de forma confiável via `visitor_text` (só posição de texto corrido); ficaria
  fora do escopo "sem nova biblioteca" tentar reconstruir isso agora.
- Detecção de tabela é heurística (colunas por espaçamento), não uma extração
  estrutural real (exigiria `camelot`/`pdfplumber`, não instalados, conforme
  instruído).
- OCR não foi implementado (infraestrutura inexistente no projeto) — páginas
  `requires_ocr` ficam marcadas para processamento manual/futuro.
- A retomada automática após reinício do backend não existe (nenhum
  supervisor/watchdog no projeto); o usuário precisa disparar reprocessamento
  manualmente via `scope=failed`.

## Arquivos criados

- `apps/backend/app/models/document_page.py`
- `apps/backend/app/models/document_block.py`
- `apps/backend/app/schemas/document_page.py`
- `apps/backend/app/schemas/document_block.py`
- `apps/backend/app/schemas/document_extraction.py`
- `apps/backend/app/services/document_extraction_service.py`
- `apps/backend/app/api/v1/document_extraction.py`
- `apps/backend/alembic/versions/0021_document_extraction.py`
- `apps/backend/tests/test_document_extraction_service.py`
- `apps/backend/tests/test_document_extraction_models.py`
- `apps/backend/tests/test_document_extraction_schemas.py`
- `apps/backend/tests/test_document_extraction_job.py`
- `apps/backend/tests/test_document_extraction_no_loss.py`
- `apps/backend/tests/test_document_extraction_endpoints.py`
- `apps/frontend/types/document-extraction.ts`
- `apps/frontend/app/fidelity-coverage/[id]/pages/page.tsx`
- `apps/frontend/app/fidelity-coverage/[id]/pages/[pageNumber]/page.tsx`
- `docs/fase-19-2-extracao-estruturada.md` (este arquivo)

## Arquivos modificados

- `apps/backend/app/models/__init__.py` — registra `DocumentPage`/`DocumentBlock`.
- `apps/backend/app/main.py` — registra o router de extração.
- `apps/backend/tests/conftest.py` — fixtures de PDF real (`reportlab`),
  `real_project_file`, `corrupted_project_file`, `current_user`.
- `apps/frontend/app/fidelity-coverage/[id]/page.tsx` — nova seção "Extração do
  Documento" com dados/ações reais.
- `apps/frontend/lib/api.ts` — funções de API de extração.
- `apps/frontend/types/processing.ts` — campos novos em `ProcessingJob`.

Nenhum arquivo/tabela existente foi removido, renomeado ou alterado de forma
destrutiva. `apps/backend/app/services/pdf_service.py` e
`apps/backend/app/services/processing_service.py` (extração legada, usada pelo fluxo
`/projects/{id}/process` que gera `ai_structure`) foram deixados intactos — o fluxo
legado continua funcionando exatamente como antes; a extração estruturada desta fase é
aditiva e independente, acessível pela nova área "Fidelidade e Cobertura".
