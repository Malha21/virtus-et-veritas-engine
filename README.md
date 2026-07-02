# Virtus et Veritas Engine

O Virtus et Veritas Engine, também chamado internamente de VVE Engine, é uma plataforma de inteligência artificial para transformar conhecimento em produtos educacionais.

O primeiro uso será interno na Virtus et Veritas Academy, com foco em transformar conhecimento bruto em cursos, roteiros, materiais e experiências educacionais.

## Status

Fase 2: fundação técnica do repositório.

Esta fase cria apenas a base mínima:

- frontend Next.js;
- backend FastAPI;
- Dockerfiles;
- Docker Compose com `frontend` e `backend`;
- health checks públicos.

Ainda não há banco de dados, autenticação, upload, IA, Redis, MinIO, Nginx ou SSL.

## Estrutura

```text
docs/
infra/
apps/
  frontend/
  backend/
docker-compose.yml
.env.example
```

## Pré-requisitos

Para validação na VPS:

- VPS Linux, preferencialmente Ubuntu Server;
- Docker instalado;
- Docker Compose instalado;
- porta `3000` liberada para o frontend;
- porta `8000` liberada para o backend nesta fase inicial.

## Configuração

Crie o arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

Valores padrão:

```env
APP_NAME=Virtus et Veritas Engine
APP_ENV=development
API_PREFIX=/api/v1
FRONTEND_PORT=3000
BACKEND_PORT=8000
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
CORS_ORIGINS=http://localhost:3000
```

Na VPS, ajuste `NEXT_PUBLIC_API_URL` e `CORS_ORIGINS` para o IP ou domínio configurado.

## Subir na VPS com Docker Compose

Na raiz do repositório:

```bash
docker compose up -d --build
```

## Verificar Containers

```bash
docker compose ps
```

Para ver logs:

```bash
docker compose logs -f frontend
docker compose logs -f backend
```

## Acessar Frontend

Com os valores padrão:

```text
http://IP_DA_VPS:3000
```

Se houver domínio configurado, use o domínio apontando para a VPS.

## Testar Backend

Health check público:

```bash
curl http://IP_DA_VPS:8000/health
```

Resposta esperada:

```json
{
  "status": "ok",
  "service": "vve-engine"
}
```

Health check versionado:

```bash
curl http://IP_DA_VPS:8000/api/v1/health
```

Resposta esperada:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "vve-engine",
    "version": "0.1.0"
  }
}
```

## Parar Containers

```bash
docker compose down
```

## Próximas Fases

A próxima fase técnica deve adicionar PostgreSQL, models, migrations, seed inicial e autenticação básica, conforme `docs/10-roadmap.md`.
