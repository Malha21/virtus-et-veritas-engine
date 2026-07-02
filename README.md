# Virtus et Veritas Engine

O Virtus et Veritas Engine, também chamado internamente de VVE Engine, é uma plataforma de inteligência artificial para transformar conhecimento em produtos educacionais.

O primeiro uso será interno na Virtus et Veritas Academy, com foco em transformar conhecimento bruto em cursos, roteiros, materiais e experiências educacionais.

## Status

Fase 6: extração de texto e jobs.

Esta fase entrega:

- frontend Next.js inicial;
- login no frontend;
- dashboard e projetos;
- upload de PDF vinculado ao projeto;
- extração síncrona de texto do PDF;
- registros em `processing_jobs`;
- registros em `processing_logs`;
- tela de processamento;
- storage local persistido via volume Docker;
- PostgreSQL via Docker Compose;
- migrations Alembic.

Ainda não há IA, Redis, MinIO, worker separado, exportação, slides, voz, avatar, Nginx ou SSL.

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

## Pré-requisitos

Para validação na VPS:

- VPS Linux, preferencialmente Ubuntu Server;
- Docker instalado;
- Docker Compose instalado;
- porta `3000` liberada para o frontend nesta fase;
- porta `8000` liberada para o backend nesta fase.

O PostgreSQL roda apenas na rede interna do Docker Compose.

## Configuração

Crie o arquivo `.env` a partir do exemplo, caso ainda não exista:

```bash
cp .env.example .env
```

Edite o `.env` antes de usar em VPS:

- troque `POSTGRES_PASSWORD`;
- troque `JWT_SECRET`;
- troque `SEED_ADMIN_EMAIL`;
- troque `SEED_ADMIN_PASSWORD`;
- ajuste `NEXT_PUBLIC_API_URL` para o IP ou domínio da VPS;
- ajuste `CORS_ORIGINS` para o IP ou domínio do frontend;
- mantenha `STORAGE_DRIVER=local`;
- mantenha `STORAGE_PATH=/app/storage`.

## Subir na VPS com Docker Compose

Na raiz do repositório:

```bash
git pull
docker compose up -d --build
```

Se o arquivo `.env` ainda não existir:

```bash
cp .env.example .env
nano .env
```

## Rodar Migrations

```bash
docker compose exec backend alembic upgrade head
```

## Rodar Seed Inicial

```bash
docker compose exec backend python -m app.scripts.seed
```

## Testar Pelo Frontend

1. Acesse `http://IP_DA_VPS:3000`.
2. Faça login com o administrador.
3. Crie ou abra um projeto.
4. Clique em `Enviar PDF`.
5. Envie um arquivo PDF.
6. Clique em `Iniciar processamento`.
7. Confira a tela de processamento e os logs.

O texto extraído será salvo no storage local em uma estrutura como:

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

Health check público:

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

## Testar Projetos

Criar projeto:

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_AQUI" \
  -d '{"title":"Curso de Liderança Filosófica","product_type":"course"}'
```

Listar projetos:

```bash
curl http://IP_DA_VPS:8000/api/v1/projects \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Parar Containers

```bash
docker compose down
```

Para remover também o volume do banco, use apenas quando tiver certeza:

```bash
docker compose down -v
```

## Próximas Fases

A próxima fase técnica deve implementar o AI Orchestrator V1, conforme `docs/10-roadmap.md`.
