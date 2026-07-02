# Virtus et Veritas Engine

O Virtus et Veritas Engine, tambem chamado internamente de VVE Engine, e uma plataforma de inteligencia artificial para transformar conhecimento em produtos educacionais.

O primeiro uso sera interno na Virtus et Veritas Academy, com foco em transformar conhecimento bruto em cursos, roteiros, materiais e experiencias educacionais.

## Status

Fase 8: geracao de roteiros, quizzes e materiais.

Esta fase entrega:

- frontend Next.js inicial;
- login no frontend;
- dashboard e projetos;
- upload de PDF vinculado ao projeto;
- extracao sincrona de texto do PDF;
- OpenAI Provider para geracao textual;
- AI Orchestrator V1;
- prompts versionados;
- geracao de analise do documento;
- geracao de estrutura inicial de curso;
- geracao de roteiro por aula;
- geracao de quizzes por modulo;
- geracao de material complementar;
- geracao de resumo executivo do curso;
- registros em `generated_contents`;
- registros em `ai_requests`;
- registros em `processing_jobs`;
- registros em `processing_logs`;
- tela de processamento;
- tela de revisao da estrutura;
- tela de revisao de conteudos educacionais;
- storage local persistido via volume Docker;
- PostgreSQL via Docker Compose;
- migrations Alembic.

Ainda nao ha exportacao PDF/DOCX/PPTX, slides, voz, avatar, Redis, MinIO ou worker separado.

## Estrutura

```text
docs/
infra/
apps/
  frontend/
  backend/
storage/
docker-compose.yml
.env.example
```

## Pre-requisitos

Para validacao na VPS:

- VPS Linux, preferencialmente Ubuntu Server;
- Docker instalado;
- Docker Compose instalado;
- porta `3000` liberada para o frontend nesta fase;
- porta `8000` liberada para o backend nesta fase.

O PostgreSQL roda apenas na rede interna do Docker Compose.

## Configuracao

Crie o arquivo `.env` a partir do exemplo, caso ainda nao exista:

```bash
cp .env.example .env
```

Edite o `.env` antes de usar em VPS:

- troque `POSTGRES_PASSWORD`;
- troque `JWT_SECRET`;
- troque `SEED_ADMIN_EMAIL`;
- troque `SEED_ADMIN_PASSWORD`;
- ajuste `NEXT_PUBLIC_API_URL` para o IP ou dominio da VPS;
- ajuste `CORS_ORIGINS` para o IP ou dominio do frontend;
- configure `OPENAI_API_KEY` com a chave real apenas no `.env` da VPS;
- mantenha `OPENAI_DEFAULT_MODEL=gpt-4.1-mini`, salvo necessidade especifica;
- mantenha `STORAGE_DRIVER=local`;
- mantenha `STORAGE_PATH=/app/storage`.

## Subir na VPS com Docker Compose

Na raiz do repositorio:

```bash
git pull
docker compose up -d --build
```

Se o arquivo `.env` ainda nao existir:

```bash
cp .env.example .env
nano .env
```

## Rodar Migrations

```bash
docker compose exec backend alembic upgrade head
```

Para a Fase 7, garanta que a migration `0005_ai_content` seja aplicada.

## Rodar Seed Inicial

```bash
docker compose exec backend python -m app.scripts.seed
```

## Testar Pelo Frontend

1. Acesse `http://IP_DA_VPS:3000`.
2. Faca login com o administrador.
3. Crie ou abra um projeto.
4. Clique em `Enviar PDF`.
5. Envie um arquivo PDF.
6. Clique em `Iniciar processamento`.
7. Confira a tela de processamento e os logs.
8. Quando o status estiver `text_extracted`, clique em `Gerar estrutura com IA`.
9. Revise a analise do documento e a estrutura do curso em `Revisar estrutura`.
10. Clique em `Gerar conteudos educacionais`.
11. Revise roteiros, quizzes, materiais e resumo em `/educational-content`.

O texto extraido sera salvo no storage local em uma estrutura como:

```text
storage/organizations/{organization_id}/projects/{project_id}/extracted/extracted_text.txt
```

## Verificar Containers

```bash
docker compose ps
```

Para ver logs:

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

## Testar Backend

Health check publico:

```bash
curl http://IP_DA_VPS:8000/health
```

Health check versionado:

```bash
curl http://IP_DA_VPS:8000/api/v1/health
```

## Testar Login

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"change_me_admin_password"}'
```

A resposta retorna um `access_token`.

## Testar Upload de PDF

Substitua `TOKEN_AQUI`, `PROJECT_ID` e o caminho do arquivo:

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/files \
  -H "Authorization: Bearer TOKEN_AQUI" \
  -F "file=@/caminho/para/arquivo.pdf;type=application/pdf"
```

## Listar Arquivos do Projeto

```bash
curl http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/files \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Iniciar Processamento

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/process \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Consultar Status

```bash
curl http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/status \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Consultar Logs

```bash
curl http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/logs \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Gerar Estrutura com IA

Antes de gerar a estrutura, o projeto precisa ter um PDF ja processado com status `text_extracted`.

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/generate-structure \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Listar Conteudos Gerados

```bash
curl http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/contents \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Gerar Conteudos Educacionais

Antes de gerar os conteudos educacionais, o projeto precisa ter uma estrutura de curso ja gerada com status `ai_structure_generated`.

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/generate-educational-content \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Listar Conteudos Educacionais

```bash
curl http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/educational-content \
  -H "Authorization: Bearer TOKEN_AQUI"
```

Filtrar por tipo de conteudo:

```bash
curl "http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID/contents?content_type=course_structure" \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Testar Projetos

Criar projeto:

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_AQUI" \
  -d '{"title":"Curso de Lideranca Filosofica","product_type":"course"}'
```

Listar projetos:

```bash
curl http://IP_DA_VPS:8000/api/v1/projects \
  -H "Authorization: Bearer TOKEN_AQUI"
```

Arquivar projeto:

```bash
curl -X DELETE http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Limpeza de Projetos Expirados

Projetos novos recebem uma janela inicial de retencao de 10 dias. O botao comum de exclusao apenas arquiva o projeto; ele nao remove arquivos fisicos imediatamente.

Comando manual de limpeza:

```bash
docker compose exec backend python -m app.scripts.cleanup_expired_projects
```

Sugestao futura de cron: rodar o comando uma vez por dia.

## Fluxo de Atualizacao da Fase 8 na VPS

```bash
git pull
nano .env
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

Nao ha migration nova especifica para a Fase 8, pois os tipos de conteudo e de requisicao de IA usam strings livres. O `alembic upgrade head` continua sendo seguro para manter a VPS atualizada.

No `.env`, garanta `OPENAI_API_KEY` com a chave real. Depois, garanta que a estrutura do curso ja foi gerada, clique em `Gerar conteudos educacionais` e revise a tela `/educational-content`.

## Parar Containers

```bash
docker compose down
```

Para remover tambem o volume do banco, use apenas quando tiver certeza:

```bash
docker compose down -v
```

## Proximas Fases

A proxima fase tecnica deve implementar exportacao e formatos de entrega, conforme `docs/10-roadmap.md`.
