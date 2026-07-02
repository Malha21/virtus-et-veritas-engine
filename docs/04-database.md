# VVE-0004 — Database Design Document
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define o modelo inicial de banco de dados do Virtus et Veritas Engine.

O objetivo é criar uma base simples, consistente e preparada para evoluir de uma ferramenta interna da Virtus et Veritas Academy para uma plataforma SaaS multiempresa.

## 2. Banco Principal

O banco principal será PostgreSQL.

Ele armazenará:

- usuários
- organizações
- projetos
- arquivos
- conteúdos gerados
- jobs de processamento
- logs
- configurações
- provedores de IA

Arquivos grandes, como PDFs, DOCX, ZIP, imagens, áudios e vídeos, não devem ser salvos diretamente no PostgreSQL.

Esses arquivos devem ser salvos no storage, inicialmente MinIO ou armazenamento local, mantendo apenas referências no banco.

## 3. Princípios de Modelagem

A modelagem deverá seguir estes princípios:

1. Usar UUID como identificador principal.
2. Usar timestamps em todas as tabelas principais.
3. Separar metadados de arquivos físicos.
4. Preparar desde cedo a estrutura para organizações.
5. Evitar acoplamento direto com provedores de IA.
6. Registrar status de processamento.
7. Permitir reprocessamento de projetos.
8. Manter histórico de logs e erros.
9. Permitir expansão para múltiplos tipos de produto.
10. Evitar armazenar arquivos binários no banco.

## 4. Entidades Principais

A primeira versão terá as seguintes entidades:

- organizations
- users
- projects
- project_files
- generated_contents
- processing_jobs
- processing_logs
- ai_providers
- ai_requests

## 5. Tabela: organizations

Representa uma organização ou cliente.

Na primeira versão, existirá apenas a organização interna da Virtus et Veritas Academy.

No futuro, cada cliente SaaS poderá ser uma organização.

Campos:

- id: UUID, primary key
- name: string, required
- slug: string, unique, required
- status: string, default active
- created_at: timestamp
- updated_at: timestamp

Status possíveis:

- active
- inactive
- suspended

## 6. Tabela: users

Representa os usuários do sistema.

Campos:

- id: UUID, primary key
- organization_id: UUID, foreign key organizations.id
- name: string, required
- email: string, unique, required
- password_hash: string, required
- role: string, required
- status: string, default active
- last_login_at: timestamp, nullable
- created_at: timestamp
- updated_at: timestamp

Roles iniciais:

- admin
- editor
- viewer

Status possíveis:

- active
- inactive
- invited

## 7. Tabela: projects

Representa um projeto de produção intelectual.

Na primeira versão, o tipo principal será Curso.

Campos:

- id: UUID, primary key
- organization_id: UUID, foreign key organizations.id
- owner_id: UUID, foreign key users.id
- title: string, required
- slug: string, required
- product_type: string, required
- target_audience: text, nullable
- tone_of_voice: string, nullable
- desired_duration: string, nullable
- description: text, nullable
- status: string, required
- processing_status: string, nullable
- created_at: timestamp
- updated_at: timestamp
- completed_at: timestamp, nullable

Product types futuros:

- course
- lesson
- workshop
- lecture
- ebook
- podcast
- reels
- training
- mentoring
- landing_page
- campaign

Status possíveis:

- draft
- active
- archived

Processing status possíveis:

- draft
- uploaded
- queued
- extracting_text
- analyzing
- generating_structure
- generating_scripts
- generating_materials
- completed
- failed

## 8. Tabela: project_files

Representa arquivos vinculados a um projeto.

Campos:

- id: UUID, primary key
- project_id: UUID, foreign key projects.id
- organization_id: UUID, foreign key organizations.id
- file_type: string, required
- original_filename: string, required
- storage_path: string, required
- mime_type: string, nullable
- file_size: integer, nullable
- checksum: string, nullable
- status: string, required
- extracted_text_path: string, nullable
- created_at: timestamp
- updated_at: timestamp

File types:

- source_pdf
- extracted_text
- generated_docx
- generated_zip
- generated_pdf
- slide_deck
- audio
- video
- thumbnail
- other

Status:

- uploaded
- processed
- failed
- deleted

## 9. Tabela: generated_contents

Representa conteúdos gerados pela IA.

Campos:

- id: UUID, primary key
- project_id: UUID, foreign key projects.id
- organization_id: UUID, foreign key organizations.id
- content_type: string, required
- title: string, nullable
- version: integer, default 1
- language: string, default pt-BR
- content_json: jsonb, nullable
- content_text: text, nullable
- status: string, required
- created_by_ai_provider_id: UUID, nullable, foreign key ai_providers.id
- created_at: timestamp
- updated_at: timestamp

Content types:

- course_structure
- module
- lesson
- script
- quiz
- summary
- checklist
- exercise
- marketing_copy
- export_manifest

Status:

- draft
- generated
- reviewed
- approved
- rejected
- archived

Observação:
Na primeira versão, conteúdos estruturados devem ser salvos preferencialmente em content_json.

Textos longos também podem ser salvos em content_text quando necessário.

## 10. Tabela: processing_jobs

Representa tarefas assíncronas.

Campos:

- id: UUID, primary key
- project_id: UUID, foreign key projects.id
- organization_id: UUID, foreign key organizations.id
- job_type: string, required
- status: string, required
- attempts: integer, default 0
- max_attempts: integer, default 3
- error_message: text, nullable
- payload_json: jsonb, nullable
- result_json: jsonb, nullable
- started_at: timestamp, nullable
- finished_at: timestamp, nullable
- created_at: timestamp
- updated_at: timestamp

Job types:

- extract_pdf_text
- analyze_document
- generate_course_structure
- generate_scripts
- generate_quizzes
- generate_materials
- export_json
- export_docx
- export_zip

Status:

- pending
- running
- completed
- failed
- cancelled

## 11. Tabela: processing_logs

Representa logs de processamento.

Campos:

- id: UUID, primary key
- project_id: UUID, nullable, foreign key projects.id
- job_id: UUID, nullable, foreign key processing_jobs.id
- organization_id: UUID, nullable, foreign key organizations.id
- level: string, required
- message: text, required
- context_json: jsonb, nullable
- created_at: timestamp

Levels:

- debug
- info
- warning
- error
- critical

## 12. Tabela: ai_providers

Representa provedores de IA configurados.

Campos:

- id: UUID, primary key
- name: string, required
- provider_type: string, required
- status: string, required
- config_json: jsonb, nullable
- created_at: timestamp
- updated_at: timestamp

Provider types:

- openai
- anthropic
- google
- local
- elevenlabs
- heygen
- runway
- other

Status:

- active
- inactive
- deprecated

Observação:
Chaves sensíveis não devem ser salvas diretamente no banco em texto aberto.

Devem preferencialmente ficar em variáveis de ambiente ou em um secret manager no futuro.

## 13. Tabela: ai_requests

Representa chamadas feitas para provedores de IA.

Campos:

- id: UUID, primary key
- project_id: UUID, nullable, foreign key projects.id
- job_id: UUID, nullable, foreign key processing_jobs.id
- provider_id: UUID, foreign key ai_providers.id
- request_type: string, required
- model_name: string, nullable
- prompt_version: string, nullable
- input_tokens: integer, nullable
- output_tokens: integer, nullable
- estimated_cost: decimal, nullable
- status: string, required
- error_message: text, nullable
- created_at: timestamp

Request types:

- analyze_document
- generate_course_structure
- generate_script
- generate_quiz
- generate_material
- generate_marketing_copy
- generate_slide_outline
- generate_voice
- generate_avatar_video

Status:

- success
- failed
- cancelled

## 14. Relacionamentos Principais

Relacionamentos:

- organization has many users
- organization has many projects
- user has many projects
- project has many project_files
- project has many generated_contents
- project has many processing_jobs
- project has many processing_logs
- processing_job has many processing_logs
- ai_provider has many ai_requests
- project has many ai_requests
- processing_job has many ai_requests

## 15. Índices Recomendados

Índices iniciais:

- users.email
- users.organization_id
- projects.organization_id
- projects.owner_id
- projects.product_type
- projects.processing_status
- project_files.project_id
- generated_contents.project_id
- generated_contents.content_type
- processing_jobs.project_id
- processing_jobs.status
- processing_logs.project_id
- processing_logs.job_id
- ai_requests.project_id
- ai_requests.provider_id

## 16. Dados Iniciais

A primeira versão deverá criar via seed:

Organização:

- name: Virtus et Veritas Academy
- slug: virtus-et-veritas-academy
- status: active

Usuário administrador:

- name: Leonardo Elias
- email: definir via variável de ambiente
- password: definir via variável de ambiente
- role: admin
- status: active

Provedor inicial de IA:

- name: OpenAI
- provider_type: openai
- status: active

## 17. Considerações para SaaS Futuro

A modelagem já inclui organization_id nas principais tabelas para facilitar evolução futura para multiempresa.

Na primeira versão, haverá apenas uma organização.

No futuro, será possível adicionar:

- planos
- assinaturas
- limites de uso
- billing
- convites
- times
- permissões avançadas
- auditoria
- white label

## 18. Considerações para Banco Vetorial

A primeira versão não implementará banco vetorial.

Futuramente, poderá ser adicionado Qdrant para:

- indexar PDFs
- criar biblioteca de conhecimento
- buscar conteúdos por significado
- reutilizar conhecimento da Virtus et Veritas Academy
- permitir geração de novos produtos com base no acervo interno

Entidades futuras possíveis:

- knowledge_collections
- knowledge_documents
- knowledge_chunks
- embeddings
- semantic_search_logs

## 19. Diretriz Final

O banco de dados deve começar simples, mas não ingênuo.

Ele deve atender a primeira versão sem complexidade excessiva, mas já estar preparado para expansão futura como SaaS modular e multiempresa.
