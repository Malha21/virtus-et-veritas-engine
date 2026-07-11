# Fase 19.1 — Banco de Dados, Models e Schemas do Motor de Fidelidade e Cobertura

## Objetivo

Preparar a fundação de banco de dados, models e schemas necessária para que, em fases futuras, todo PDF
enviado possa ser inventariado, dividido em unidades de conhecimento rastreáveis, relacionado a aulas,
auditado quanto a cobertura e fidelidade, e processado por jobs longos e retomáveis.

Esta fase **não** implementa chamadas de IA, prompts, geração de inventário/módulos/aulas, auditoria
semântica ou alterações visuais no frontend. Apenas a fundação estrutural.

## Arquitetura real encontrada (antes de qualquer alteração)

O projeto **não possui tabelas `courses`, `modules` ou `lessons`**. O mapeamento real é:

| Conceito do enunciado | Entidade real do projeto              |
|------------------------|----------------------------------------|
| Curso                  | `Project` (`projects`)                 |
| Documento enviado      | `ProjectFile` (`project_files`)        |
| Módulo/Aula            | `GeneratedContent` (`generated_contents`, `content_type='lesson_script'`), identificado por `module_index`/`lesson_index`. O `id` dessa linha já é usado como "lesson id" em `video_pipeline_jobs.lesson_id` e `video_pipeline_job_items.lesson_content_id` — convenção reaproveitada aqui. |
| Sistema de jobs        | `ProcessingJob` (`processing_jobs`), genérico (project_id, job_type string, status, attempts/max_attempts, progress, payload_json, result_json) — **estendido** nesta fase em vez de duplicado. |

Padrões confirmados e seguidos:
- SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Python 3.12, FastAPI 0.115, Pydantic 2.13, psycopg3.
- Todas as PKs são `UUID` (`postgresql.UUID(as_uuid=True)`), geradas em Python (`uuid.uuid4`).
- Sem `Enum` nativo do Postgres: status/tipo são `String` validados na camada Pydantic.
- JSONB para dados livres/estruturados (`content_json`, `payload_json`, `report_data` etc.).
- Tabelas "filhas" recentes (`course_exports`, `video_pipeline_jobs`) não replicam `organization_id`;
  o escopo por organização é feito via join com `projects.organization_id`. Seguido aqui.
- `relationship()` do ORM só é usado em `Organization`/`User`; as demais tabelas usam apenas FKs +
  índices e consultas explícitas com `select()`. Seguido aqui (sem `relationship()` novo).
- Migrations Alembic manuais e sequenciais (`0001` ... `0019`), sem uso de autogenerate.

## Decisão arquitetural: reuso em vez de duplicação

- **Não foi criada uma tabela `generation_jobs`**. `ProcessingJob` já cobria quase todos os requisitos
  (job_type livre, status, progress, payload/result JSONB, retries via `attempts`/`max_attempts`). Foram
  adicionadas apenas as colunas que faltavam: `project_file_id`, `lesson_content_id`, `total_items`,
  `processed_items`, `failed_items`, `current_item`. Os `job_type` desta fase (`document_extraction`,
  `source_inventory`, `coverage_plan`, `lesson_generation`, `course_audit`, `content_repair`) são apenas
  valores de string aceitos pela coluna já existente, sem necessidade de enum ou tabela nova.
- **Não foram criadas tabelas `courses`/`modules`/`lessons`**. `lesson_id` do enunciado foi mapeado para
  `lesson_content_id`, FK para `generated_contents.id`, mesma convenção já usada por
  `video_pipeline_jobs`/`video_pipeline_job_items`.
- **`course_id`/`document_id`** do enunciado foram mapeados para `project_id`/`project_file_id`.

## Tabelas criadas

### `source_content_items`
Unidades de conhecimento inventariadas a partir de um documento (`project_file`).

Campos principais: `id`, `project_id` (FK `projects`, CASCADE), `project_file_id` (FK `project_files`,
CASCADE), `item_code`, `title`, `source_text`, `normalized_content`, `content_type`, `page_start`,
`page_end`, `source_order`, `importance`, `status`, `metadata_json` (JSONB), `created_at`, `updated_at`.

- Unique: `(project_id, item_code)` — `item_code` único por curso, permitido repetir entre cursos.
- Índices: `project_id`, `project_file_id`, `content_type`, `source_order`, `status`.
- Valores esperados: `content_type` ∈ {concept, definition, explanation, procedure, example, list,
  argument, conclusion, observation, exercise, table, image_caption, quotation, other};
  `importance` ∈ {essential, relevant, complementary};
  `status` ∈ {pending, mapped, reviewed, approved, rejected} (validados em `SourceContentItemBase`).

### `lesson_source_items`
Relaciona um `source_content_item` a uma aula (`generated_contents.id`, `lesson_content_id`).

Campos: `id`, `lesson_content_id` (FK `generated_contents`, CASCADE), `source_item_id` (FK
`source_content_items`, CASCADE), `coverage_type`, `coverage_notes`, `coverage_score` (Numeric 5,2),
`source_order_in_lesson`, `is_required`, `created_at`, `updated_at`.

- Unique: `(lesson_content_id, source_item_id)` — impede duplicidade; um mesmo item pode aparecer em
  várias aulas (linhas diferentes), atendendo ao requisito pedagógico.
- Índices: `lesson_content_id`, `source_item_id`, `coverage_type`.
- Valores esperados: `coverage_type` ∈ {planned, full, partial, missing, supplemental}.

### `lesson_generations`
Versões *append-only* de conteúdo gerado para uma aula.

Campos: `id`, `lesson_content_id` (FK `generated_contents`, CASCADE), `version`, `generated_content`,
`structured_content` (JSONB), `word_count`, `estimated_duration_seconds`, `source_item_count`,
`generation_status`, `validation_status`, `model_name`, `prompt_version`, `error_message`,
`created_at`, `updated_at`.

- Unique: `(lesson_content_id, version)` — versões nunca são sobrescritas; a mais recente é obtida via
  `MAX(version)` filtrando por `lesson_content_id`.
- Índices: `lesson_content_id`, `generation_status`, `validation_status`.
- Valores esperados: `generation_status` ∈ {pending, processing, completed, failed, cancelled};
  `validation_status` ∈ {pending, valid, invalid, requires_review, approved}.

### `course_coverage_reports`
Relatórios *append-only* de auditoria de cobertura/fidelidade por curso.

Campos: `id`, `project_id` (FK `projects`, CASCADE), `version`, `total_source_items`, `covered_items`,
`partially_covered_items`, `uncovered_items`, `coverage_percentage` (Numeric 5,2), `unsupported_claims`,
`duration_violations`, `duplicate_content_count`, `fidelity_score` (Numeric 5,2), `report_data` (JSONB),
`status`, `created_at`, `updated_at`.

- Unique: `(project_id, version)` — relatórios anteriores nunca são sobrescritos.
- Índices: `project_id`, `status`.
- Valores esperados: `status` ∈ {pending, processing, passed, failed, requires_review,
  approved_with_exceptions}.

### `processing_jobs` (extensão, não nova tabela)
Colunas adicionadas: `project_file_id` (FK `project_files`, SET NULL), `lesson_content_id` (FK
`generated_contents`, SET NULL), `total_items`, `processed_items`, `failed_items`, `current_item`.
Índices novos: `project_file_id`, `lesson_content_id`. `retry_count`/`max_retries` do enunciado já
existiam como `attempts`/`max_attempts`; `progress_percentage` já existia como `progress` (0-100).

## Rastreabilidade obtida

```
project_file (documento) → source_content_items (página/bloco/item)
                              → lesson_source_items → generated_contents (aula)
                                                          → lesson_generations (geração versionada)
project (curso) → course_coverage_reports (auditoria)
project/project_file/generated_contents → processing_jobs (job persistente e retomável)
```

## Arquivos criados

- `apps/backend/app/models/source_content_item.py`
- `apps/backend/app/models/lesson_source_item.py`
- `apps/backend/app/models/lesson_generation.py`
- `apps/backend/app/models/course_coverage_report.py`
- `apps/backend/app/schemas/source_content_item.py`
- `apps/backend/app/schemas/lesson_source_item.py`
- `apps/backend/app/schemas/lesson_generation.py`
- `apps/backend/app/schemas/course_coverage_report.py`
- `apps/backend/alembic/versions/0020_fidelity_coverage_engine.py`
- `apps/backend/requirements-dev.txt` (dependência de teste `pytest`, não instalada na imagem de produção)
- `apps/backend/pytest.ini`
- `apps/backend/tests/conftest.py`
- `apps/backend/tests/test_source_content_item.py`
- `apps/backend/tests/test_lesson_source_item.py`
- `apps/backend/tests/test_lesson_generation.py`
- `apps/backend/tests/test_course_coverage_report.py`
- `apps/backend/tests/test_processing_job_extension.py`
- `apps/backend/tests/test_foreign_key_integrity.py`
- `docs/fase-19-1-motor-fidelidade-cobertura.md` (este arquivo)

## Arquivos modificados

- `apps/backend/app/models/processing_job.py` — novas colunas (ver acima).
- `apps/backend/app/models/__init__.py` — registra os 4 novos models.
- `apps/backend/app/schemas/processing.py` — `ProcessingJobResponse` ganhou os novos campos;
  adicionado `ProcessingJobProgressUpdate` (valida `processed_items <= total_items`, `progress` 0-100,
  contadores não-negativos) para uso pelas próximas fases ao atualizar progresso de jobs.

Nenhum arquivo/tabela existente foi removido ou renomeado. Nenhuma funcionalidade em produção foi
alterada.

## Como executar a migration

```bash
cd /opt/virtus-et-veritas-engine
docker compose exec backend alembic heads      # confirmar head único antes de gerar/aplicar
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current     # confirmar 0020_fidelity_coverage_engine (head)
```

## Como reverter

```bash
docker compose exec backend alembic downgrade -1
```

O `downgrade` remove exclusivamente as 4 tabelas novas e as 6 colunas adicionadas a `processing_jobs`
(com seus índices). Não afeta dados de nenhuma tabela pré-existente. Testado manualmente nesta fase
(`downgrade -1` seguido de `upgrade head`, sem erros).

## Como executar os testes

Os testes rodam contra o Postgres real do `docker-compose` (não há banco de testes separado), mas cada
teste roda dentro de uma transação com `SAVEPOINT` que é revertida ao final (`tests/conftest.py`), então
nenhum dado de teste é persistido. `pytest` não é instalado na imagem de produção (mantém a imagem
enxuta); instale a partir de `requirements-dev.txt` apenas quando for rodar a suíte:

```bash
cd /opt/virtus-et-veritas-engine
docker compose exec backend pip install -r requirements-dev.txt
docker compose exec backend python -m pytest -v
```

### Resultado obtido nesta fase

38 testes, 38 aprovados. Cobrem: criação das 4 entidades, unicidade de `item_code` por curso (e reuso
permitido entre cursos), prevenção de duplicidade em `lesson_source_items` (e reuso do mesmo item em
aulas diferentes), versionamento append-only de `lesson_generations` e `course_coverage_reports`,
extensão de `ProcessingJob` (criação, retomada após falha, filtros por curso/documento/aula/tipo),
validações Pydantic (páginas, percentuais, contadores, status), integridade de FK e cascade de exclusão.

Verificado após a execução que as 4 novas tabelas permanecem com `count(*) = 0` no banco real — nenhum
dado de teste vazou.

## Compatibilidade com as próximas fases

- `structured_content` (JSONB) de `lesson_generations` está pronto para receber objetivo, roteiro,
  resumo, tópicos, páginas e IDs de `source_content_items` cobertos, quando a geração por IA for
  implementada (fase seguinte).
- `report_data` (JSONB) de `course_coverage_reports` está pronto para detalhamento por item/aula da
  auditoria semântica futura.
- `ProcessingJobProgressUpdate` já valida a semântica de progresso que os jobs `source_inventory`,
  `coverage_plan`, `lesson_generation`, `course_audit` e `content_repair` vão usar.
- Nenhuma chamada de IA, prompt ou rota de API nova foi criada nesta fase — escopo mantido estritamente
  em banco/models/schemas, conforme solicitado.

## Pendências para fases seguintes

- Endpoints REST (`api/v1`) e services para CRUD/consulta das 4 novas entidades ainda não existem —
  propositalmente fora do escopo desta fase.
- Job de inventário automático do PDF (`source_inventory`) ainda não lê nem popula
  `source_content_items` — apenas a estrutura está pronta.
- `docs/04-database.md` (documento de referência de banco já existente no projeto) pode ser atualizado
  em uma fase futura para incluir estas tabelas no diagrama geral, se desejado.
