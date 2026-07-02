# VVE-0005 — API Design Document
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define o design inicial da API do Virtus et Veritas Engine.

A API será responsável por conectar o frontend, o banco de dados, o storage, a fila de processamento, o AI Orchestrator e os serviços de exportação.

A primeira versão usará uma API REST construída com FastAPI.

## 2. Princípios da API

A API deverá seguir os seguintes princípios:

1. Clareza nos endpoints.
2. Separação por domínio.
3. Autenticação obrigatória nas rotas internas.
4. Respostas em JSON.
5. Tratamento consistente de erros.
6. Validação forte de entrada.
7. Padrão previsível de paginação.
8. Compatibilidade futura com SaaS multiempresa.
9. Não exposição de chaves sensíveis.
10. Preparação para tarefas assíncronas.

## 3. Prefixo da API

Todas as rotas da aplicação deverão usar o prefixo:

/api/v1

Exemplo:

/api/v1/projects

## 4. Autenticação

A primeira versão deverá usar autenticação com e-mail e senha.

Opções aceitas:

- JWT com access token
- sessão HTTP segura

Recomendação inicial:

- JWT no backend
- token armazenado com cuidado no frontend
- rotas protegidas por dependência de autenticação no FastAPI

## 5. Padrão de Resposta

Resposta de sucesso simples:

```json
{
  "success": true,
  "data": {}
}
```

Resposta de erro:

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

## 6. Códigos HTTP

Padrões:

- 200 OK
- 201 Created
- 202 Accepted
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 409 Conflict
- 422 Validation Error
- 500 Internal Server Error

## 7. Paginação

Rotas de listagem deverão suportar:

- page
- page_size
- sort
- order

Exemplo:

GET /api/v1/projects?page=1&page_size=20&sort=created_at&order=desc

Resposta paginada:

```json
{
  "success": true,
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

## 8. Health Check

### GET /health

Endpoint público para verificar se o backend está online.

Resposta:

```json
{
  "status": "ok",
  "service": "vve-engine"
}
```

## 9. Auth Endpoints

### POST /api/v1/auth/login

Realiza login do usuário.

Body:

```json
{
  "email": "admin@example.com",
  "password": "senha"
}
```

Resposta:

```json
{
  "success": true,
  "data": {
    "access_token": "token",
    "token_type": "bearer",
    "user": {
      "id": "uuid",
      "name": "Leonardo Elias",
      "email": "email",
      "role": "admin"
    }
  }
}
```

### POST /api/v1/auth/logout

Encerra sessão do usuário.

Na primeira versão, pode apenas responder sucesso caso JWT stateless seja usado.

Resposta:

```json
{
  "success": true,
  "data": {
    "message": "Logout realizado com sucesso"
  }
}
```

### GET /api/v1/auth/me

Retorna dados do usuário autenticado.

Resposta:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Leonardo Elias",
    "email": "email",
    "role": "admin",
    "organization": {
      "id": "uuid",
      "name": "Virtus et Veritas Academy",
      "slug": "virtus-et-veritas-academy"
    }
  }
}
```

## 10. Project Endpoints

### GET /api/v1/projects

Lista projetos da organização do usuário autenticado.

Query params:

- page
- page_size
- status
- product_type
- processing_status
- search

Resposta:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "Curso de Liderança",
        "product_type": "course",
        "status": "active",
        "processing_status": "completed",
        "created_at": "datetime",
        "updated_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

### POST /api/v1/projects

Cria novo projeto.

Body:

```json
{
  "title": "Curso de Liderança Filosófica",
  "product_type": "course",
  "target_audience": "Líderes e empreendedores",
  "tone_of_voice": "inspirador e didático",
  "desired_duration": "6 horas",
  "description": "Curso sobre liderança baseada em virtudes."
}
```

Resposta:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "Curso de Liderança Filosófica",
    "product_type": "course",
    "status": "draft",
    "processing_status": "draft"
  }
}
```

### GET /api/v1/projects/{project_id}

Retorna detalhes de um projeto.

Resposta:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "Curso de Liderança Filosófica",
    "product_type": "course",
    "target_audience": "Líderes e empreendedores",
    "tone_of_voice": "inspirador e didático",
    "desired_duration": "6 horas",
    "description": "Curso sobre liderança baseada em virtudes.",
    "status": "active",
    "processing_status": "completed",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
}
```

### PATCH /api/v1/projects/{project_id}

Atualiza metadados do projeto.

Body:

```json
{
  "title": "Novo título",
  "target_audience": "Novo público",
  "tone_of_voice": "tom atualizado",
  "desired_duration": "8 horas",
  "description": "Nova descrição"
}
```

Resposta:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "Novo título"
  }
}
```

### DELETE /api/v1/projects/{project_id}

Arquiva um projeto.

A primeira versão não deve apagar fisicamente o projeto.

Resposta:

```json
{
  "success": true,
  "data": {
    "message": "Projeto arquivado com sucesso"
  }
}
```

## 11. File Endpoints

### POST /api/v1/projects/{project_id}/files

Faz upload de arquivo para o projeto.

Na primeira versão, aceitar apenas PDF.

Content-Type:

multipart/form-data

Campos:

- file

Resposta:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "project_id": "uuid",
    "file_type": "source_pdf",
    "original_filename": "arquivo.pdf",
    "status": "uploaded"
  }
}
```

### GET /api/v1/projects/{project_id}/files

Lista arquivos do projeto.

Resposta:

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "file_type": "source_pdf",
      "original_filename": "arquivo.pdf",
      "mime_type": "application/pdf",
      "file_size": 123456,
      "status": "uploaded",
      "created_at": "datetime"
    }
  ]
}
```

## 12. Processing Endpoints

### POST /api/v1/projects/{project_id}/process

Inicia o processamento do projeto.

O backend deverá criar jobs assíncronos para:

- extração de texto
- análise do documento
- geração de estrutura
- geração de roteiros
- geração de quizzes
- geração de materiais

Resposta:

```json
{
  "success": true,
  "data": {
    "project_id": "uuid",
    "processing_status": "queued",
    "message": "Processamento iniciado"
  }
}
```

### GET /api/v1/projects/{project_id}/status

Retorna status atual do processamento.

Resposta:

```json
{
  "success": true,
  "data": {
    "project_id": "uuid",
    "processing_status": "generating_scripts",
    "progress": 60,
    "current_step": "Gerando roteiros das aulas",
    "updated_at": "datetime"
  }
}
```

### POST /api/v1/projects/{project_id}/reprocess

Reprocessa um projeto em caso de erro ou nova versão.

Body opcional:

```json
{
  "scope": "all"
}
```

Scopes possíveis:

- all
- structure
- scripts
- materials
- exports

Resposta:

```json
{
  "success": true,
  "data": {
    "project_id": "uuid",
    "processing_status": "queued",
    "message": "Reprocessamento iniciado"
  }
}
```

## 13. Content Endpoints

### GET /api/v1/projects/{project_id}/contents

Lista conteúdos gerados do projeto.

Query params:

- content_type
- status

Resposta:

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "content_type": "course_structure",
      "title": "Estrutura do curso",
      "version": 1,
      "status": "generated",
      "created_at": "datetime"
    }
  ]
}
```

### GET /api/v1/projects/{project_id}/contents/{content_id}

Retorna conteúdo específico.

Resposta:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "content_type": "course_structure",
    "title": "Estrutura do curso",
    "version": 1,
    "language": "pt-BR",
    "content_json": {},
    "content_text": null,
    "status": "generated"
  }
}
```

### PATCH /api/v1/projects/{project_id}/contents/{content_id}

Atualiza um conteúdo gerado após revisão humana.

Body:

```json
{
  "title": "Título atualizado",
  "content_json": {},
  "content_text": "Texto atualizado",
  "status": "reviewed"
}
```

Resposta:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "reviewed",
    "updated_at": "datetime"
  }
}
```

### POST /api/v1/projects/{project_id}/contents/{content_id}/approve

Aprova um conteúdo.

Resposta:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "approved"
  }
}
```

## 14. Export Endpoints

### GET /api/v1/projects/{project_id}/export/json

Exporta projeto em JSON.

Resposta:

Arquivo .json para download.

### GET /api/v1/projects/{project_id}/export/docx

Exporta roteiros e materiais em DOCX.

Resposta:

Arquivo .docx para download.

### GET /api/v1/projects/{project_id}/export/zip

Exporta pacote completo em ZIP.

Resposta:

Arquivo .zip para download.

## 15. Logs Endpoints

### GET /api/v1/projects/{project_id}/logs

Lista logs de processamento do projeto.

Query params:

- level
- job_id

Resposta:

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "level": "info",
      "message": "Processamento iniciado",
      "context_json": {},
      "created_at": "datetime"
    }
  ]
}
```

## 16. Admin Endpoints — Futuro

Rotas futuras:

- GET /api/v1/admin/users
- POST /api/v1/admin/users
- PATCH /api/v1/admin/users/{user_id}
- GET /api/v1/admin/organizations
- GET /api/v1/admin/ai-requests
- GET /api/v1/admin/usage

Não serão implementadas na primeira versão, exceto se necessário para seed/admin interno.

## 17. Validações Importantes

A API deverá validar:

- arquivo deve ser PDF na primeira versão
- limite de tamanho do PDF
- projeto deve pertencer à organização do usuário
- usuário deve estar autenticado
- campos obrigatórios
- product_type deve ser válido
- status deve seguir enum definido
- conteúdo não deve ser exportado se o projeto não tiver conteúdo gerado

## 18. Segurança da API

A API deverá garantir:

- rotas privadas protegidas
- senha nunca retornada
- password_hash nunca exposto
- chaves de IA nunca expostas
- arquivos acessíveis apenas ao usuário autorizado
- validação de MIME type
- logs sem dados sensíveis
- CORS configurado apenas para domínios permitidos

## 19. Versionamento

A API usará versionamento por URL:

/api/v1

Mudanças futuras incompatíveis deverão usar:

/api/v2

## 20. Diretriz Final

A API deve ser simples, previsível e fácil de consumir pelo frontend.

A primeira versão deve priorizar o fluxo principal:

login → criar projeto → upload PDF → processar → revisar → exportar.
