# VVE-0008 — Backend Design Document
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define a arquitetura inicial do backend do Virtus et Veritas Engine.

O backend será responsável por autenticação, autorização, gerenciamento de projetos, upload de arquivos, processamento assíncrono, integração com IA, exportação de conteúdos e comunicação com banco de dados, storage e fila.

A primeira versão será construída com FastAPI e Python.

## 2. Princípios do Backend

O backend deverá seguir os seguintes princípios:

1. Organização modular.
2. Separação entre API, domínio, serviços e infraestrutura.
3. Segurança desde a primeira versão.
4. Baixo acoplamento com provedores externos.
5. Processamento assíncrono para tarefas longas.
6. Validação forte de dados.
7. Logs claros.
8. Facilidade de testes.
9. Preparação para SaaS multiempresa.
10. Simplicidade suficiente para entregar rapidamente.

## 3. Stack Recomendada

Tecnologias principais:

- Python
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic
- PostgreSQL
- Redis
- MinIO
- Uvicorn
- PyJWT ou python-jose
- Passlib ou Argon2
- python-multipart
- pypdf ou pymupdf
- python-docx
- zipfile nativo
- Anthropic SDK (provedor de IA padrão)
- OpenAI SDK (TTS e provedor de IA secundário/legado)

## 4. Responsabilidades do Backend

O backend será responsável por:

- expor API REST;
- autenticar usuários;
- validar permissões;
- gerenciar organizações;
- gerenciar usuários;
- gerenciar projetos;
- receber upload de PDFs;
- armazenar metadados no banco;
- salvar arquivos no storage;
- criar jobs de processamento;
- executar ou acionar workers;
- extrair texto de PDFs;
- chamar o AI Orchestrator;
- salvar conteúdos gerados;
- exportar JSON, DOCX e ZIP;
- registrar logs;
- registrar chamadas de IA;
- retornar status ao frontend.

## 5. Estrutura Recomendada de Pastas

Estrutura sugerida:

/apps/backend
  /app
    /api
      /v1
        auth.py
        projects.py
        files.py
        processing.py
        contents.py
        exports.py
        logs.py
        health.py
    /core
      config.py
      security.py
      database.py
      logging.py
      errors.py
    /models
      organization.py
      user.py
      project.py
      project_file.py
      generated_content.py
      processing_job.py
      processing_log.py
      ai_provider.py
      ai_request.py
    /schemas
      auth.py
      user.py
      project.py
      file.py
      content.py
      processing.py
      export.py
      common.py
    /services
      auth_service.py
      user_service.py
      project_service.py
      file_service.py
      pdf_service.py
      processing_service.py
      ai_orchestrator_service.py
      export_service.py
      storage_service.py
      logging_service.py
    /providers
      /ai
        base.py
        anthropic_provider.py
        openai_provider.py
      /storage
        base.py
        local_storage.py
        minio_storage.py
    /workers
      worker.py
      tasks.py
    /prompts
      document_analysis_v1.py
      course_structure_v1.py
      lesson_script_v1.py
      quiz_v1.py
      materials_v1.py
      marketing_v1.py
    /utils
      ids.py
      slug.py
      files.py
      json.py
    main.py
  /alembic
  requirements.txt
  Dockerfile

## 6. Camadas do Backend

## 6.1 API Layer

Responsável por:

- receber requisições HTTP;
- validar entrada com Pydantic;
- verificar autenticação;
- chamar services;
- retornar respostas padronizadas.

A API não deve conter regra de negócio complexa.

## 6.2 Service Layer

Responsável por:

- regras de negócio;
- criação de projetos;
- upload;
- processamento;
- exportação;
- chamadas ao AI Orchestrator;
- validações internas.

## 6.3 Model Layer

Responsável por:

- representação das tabelas do banco;
- relacionamentos;
- constraints;
- enums quando aplicável.

## 6.4 Provider Layer

Responsável por abstrair serviços externos.

Exemplos:

- OpenAI;
- MinIO;
- storage local;
- futuramente Claude, Gemini, ElevenLabs, HeyGen.

## 6.5 Worker Layer

Responsável por tarefas longas.

Exemplos:

- extrair texto do PDF;
- gerar estrutura;
- gerar roteiros;
- gerar quizzes;
- gerar materiais;
- exportar arquivos.

## 7. Autenticação

A primeira versão deverá implementar:

- login com e-mail e senha;
- hash seguro de senha;
- JWT access token;
- endpoint /auth/me;
- proteção das rotas internas.

Regras:

- senha nunca deve ser retornada;
- password_hash nunca deve ser exposto;
- usuário inativo não deve logar;
- token deve conter user_id e organization_id;
- rotas devem filtrar dados por organization_id.

## 8. Organizações

Mesmo na primeira versão, o sistema terá tabela organizations.

Na V1, haverá apenas:

- Virtus et Veritas Academy

Isso prepara a plataforma para SaaS futuro.

Toda entidade principal deverá carregar organization_id quando aplicável.

## 9. Projetos

O Project Service deverá permitir:

- criar projeto;
- listar projetos;
- buscar projeto por ID;
- atualizar projeto;
- arquivar projeto;
- alterar status de processamento;
- validar se o projeto pertence à organização do usuário.

Na primeira versão, product_type principal:

- course

## 10. Upload de Arquivos

O File Service deverá:

- aceitar apenas PDF na V1;
- validar MIME type;
- validar extensão;
- validar tamanho máximo;
- calcular checksum opcional;
- salvar arquivo no storage;
- registrar metadados em project_files;
- associar arquivo ao projeto.

Storage inicial:

- local ou MinIO.

Preferência:

- MinIO, com fallback para local em desenvolvimento.

## 11. Extração de Texto

O PDF Service deverá:

- abrir PDF;
- extrair texto;
- lidar com PDFs sem texto extraível;
- salvar texto extraído em arquivo ou banco;
- registrar falhas;
- retornar texto limpo para o pipeline.

Ferramentas possíveis:

- pypdf;
- pymupdf.

Na primeira versão, começar com uma solução simples e evoluir se necessário.

## 12. Processamento Assíncrono

Processamentos longos não devem travar a API.

A API deverá:

1. receber pedido de processamento;
2. criar registro em processing_jobs;
3. colocar tarefa na fila;
4. retornar resposta 202 Accepted ou success com status queued;
5. worker executa a tarefa;
6. worker atualiza status.

Fila recomendada:

- Redis.

Worker:

- Python worker separado.

Bibliotecas possíveis:

- RQ;
- Celery;
- Dramatiq.

Recomendação inicial:

- RQ pela simplicidade.

## 13. AI Orchestrator Service

O AI Orchestrator Service deverá coordenar:

- análise do documento;
- geração da estrutura do curso;
- geração dos roteiros;
- geração dos quizzes;
- geração dos materiais complementares;
- geração de textos simples de marketing.

Ele deverá usar a camada AI Provider.

Não deve chamar o provedor de IA diretamente em múltiplos pontos do sistema.

## 14. AI Provider

Interface conceitual:

```python
class AIProvider:
    def generate_text(self, request):
        pass
```

`AnthropicProvider` (padrão, `AI_PROVIDER=anthropic`) e `OpenAIProvider`
(secundário/legado, também usado para TTS) implementam essa interface. Os
serviços não instanciam nenhum dos dois diretamente — consomem
`get_ai_provider(settings)`, que resolve a implementação ativa.

Entradas importantes:

- prompt_name;
- prompt_version;
- system_prompt;
- user_prompt;
- input_data;
- temperature;
- response_format.

Saída esperada:

- success;
- content;
- raw_response;
- usage;
- error.

## 15. Prompts

Os prompts deverão ficar versionados na pasta:

/app/prompts

Prompts iniciais:

- document_analysis_v1
- course_structure_v1
- lesson_script_v1
- quiz_v1
- materials_v1
- marketing_v1

Cada prompt deverá ter:

- objetivo;
- instruções do sistema;
- formato de entrada;
- formato de saída;
- critérios de qualidade.

## 16. Conteúdos Gerados

O Generated Content Service deverá:

- salvar conteúdos em generated_contents;
- usar content_json para estruturas;
- usar content_text para textos longos;
- controlar versionamento;
- permitir revisão humana;
- permitir aprovação.

Content types iniciais:

- document_analysis
- course_structure
- lesson_script
- quiz
- complementary_material
- marketing_copy

## 17. Exportações

O Export Service deverá permitir:

- exportar JSON;
- exportar DOCX;
- exportar ZIP.

Na V1:

- JSON deve conter todo o projeto estruturado;
- DOCX deve conter estrutura, roteiros, quizzes e materiais;
- ZIP deve conter JSON, DOCX e arquivos auxiliares.

Futuro:

- PDF;
- slides;
- pacote Greenn;
- vídeos;
- thumbnails.

## 18. Logs

O backend deverá registrar logs em duas camadas:

1. logs técnicos da aplicação;
2. processing_logs no banco para o usuário acompanhar.

Logs de processamento devem incluir:

- início de etapa;
- conclusão de etapa;
- erro;
- retry;
- status.

## 19. Tratamento de Erros

Erros devem seguir padrão consistente:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Mensagem amigável",
    "details": {}
  }
}
```

Erros comuns:

- AUTH_INVALID_CREDENTIALS
- AUTH_UNAUTHORIZED
- PROJECT_NOT_FOUND
- FILE_INVALID_TYPE
- FILE_TOO_LARGE
- PDF_TEXT_EXTRACTION_FAILED
- AI_PROVIDER_ERROR
- PROCESSING_FAILED
- EXPORT_FAILED

## 20. Configurações

Configurações via .env:

- APP_NAME
- APP_ENV
- API_PREFIX
- DATABASE_URL
- REDIS_URL
- STORAGE_DRIVER
- STORAGE_PATH
- MINIO_ENDPOINT
- MINIO_ACCESS_KEY
- MINIO_SECRET_KEY
- MINIO_BUCKET
- JWT_SECRET
- JWT_EXPIRES_MINUTES
- AI_PROVIDER (anthropic | openai; padrão: anthropic)
- ANTHROPIC_API_KEY
- ANTHROPIC_MODEL
- ANTHROPIC_MAX_TOKENS
- ANTHROPIC_TIMEOUT_SECONDS
- OPENAI_API_KEY (TTS e provedor de IA secundário/legado)
- OPENAI_DEFAULT_MODEL
- MAX_UPLOAD_SIZE_MB
- CORS_ORIGINS

## 21. Seed Inicial

O backend deverá permitir seed inicial de:

Organização:

- Virtus et Veritas Academy

Usuário administrador:

- nome definido por env;
- e-mail definido por env;
- senha definida por env;
- role admin.

Provedor IA:

- Anthropic (provedor ativo padrão, `AI_PROVIDER=anthropic`)
- active

## 22. Testes

Testes recomendados:

- health check;
- login;
- criar projeto;
- upload PDF inválido;
- upload PDF válido;
- listar projetos;
- status do projeto;
- export JSON;
- permissões por organização;
- AI Provider mockado.

Na primeira versão, implementar testes básicos após o MVP funcional.

## 23. Fora do Escopo do Backend V1

Não implementar inicialmente:

- pagamento;
- multiempresa real com billing;
- certificados;
- área de alunos;
- publicação automática;
- avatar;
- vídeos;
- slides;
- marketplace;
- notificações complexas;
- webhooks externos.

## 24. Diretriz Final

O backend deve ser simples, modular e confiável.

Ele deve entregar o fluxo principal:

login → projeto → upload PDF → processamento IA → revisão → exportação.

Ao mesmo tempo, deve nascer com organização suficiente para evoluir para uma plataforma SaaS comercial.
