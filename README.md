# Virtus et Veritas Engine

O Virtus et Veritas Engine, também chamado internamente de VVE Engine, é uma plataforma de inteligência artificial para transformar conhecimento em produtos educacionais.

O primeiro uso será interno na Virtus et Veritas Academy, com foco em transformar conhecimento bruto em cursos, roteiros, materiais e experiências educacionais.

## Status

Fase 4: dashboard e projetos.

Esta fase entrega:

- frontend Next.js inicial;
- login no frontend;
- persistência de token JWT em `localStorage`;
- consulta `/api/v1/auth/me`;
- layout autenticado;
- dashboard;
- lista de projetos;
- criação de projeto;
- detalhe de projeto;
- backend FastAPI com CRUD inicial de projetos;
- PostgreSQL via Docker Compose;
- migrations Alembic.

Ainda não há upload de PDF, processamento, IA, Redis, MinIO, worker, exportação, Nginx ou SSL.

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
- ajuste `CORS_ORIGINS` para o IP ou domínio do frontend.

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

O seed cria, de forma idempotente:

- organização `Virtus et Veritas Academy`;
- usuário administrador;
- provedor `OpenAI`.

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

## Acessar Frontend

Com os valores padrão:

```text
http://IP_DA_VPS:3000
```

Depois de acessar:

1. entre com o usuário administrador definido no `.env`;
2. abra o dashboard;
3. crie um projeto;
4. confira a lista de projetos;
5. abra o detalhe do projeto.

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

Use o e-mail e a senha definidos em `.env`:

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"change_me_admin_password"}'
```

A resposta retorna um `access_token`.

## Testar Usuário Atual

Substitua `TOKEN_AQUI` pelo token retornado no login:

```bash
curl http://IP_DA_VPS:8000/api/v1/auth/me \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Testar Projetos

Criar projeto:

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_AQUI" \
  -d '{
    "title": "Curso de Liderança Filosófica",
    "product_type": "course",
    "target_audience": "Líderes e empreendedores",
    "tone_of_voice": "inspirador e didático",
    "desired_duration": "6 horas",
    "description": "Curso sobre liderança baseada em virtudes."
  }'
```

Listar projetos:

```bash
curl http://IP_DA_VPS:8000/api/v1/projects \
  -H "Authorization: Bearer TOKEN_AQUI"
```

Buscar projeto:

```bash
curl http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID \
  -H "Authorization: Bearer TOKEN_AQUI"
```

Atualizar projeto:

```bash
curl -X PATCH http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_AQUI" \
  -d '{"title":"Novo título"}'
```

Arquivar projeto:

```bash
curl -X DELETE http://IP_DA_VPS:8000/api/v1/projects/PROJECT_ID \
  -H "Authorization: Bearer TOKEN_AQUI"
```

## Logout

```bash
curl -X POST http://IP_DA_VPS:8000/api/v1/auth/logout
```

Na V1, o logout apenas retorna sucesso porque o token JWT é stateless.

## Parar Containers

```bash
docker compose down
```

Para remover também o volume do banco, use apenas quando tiver certeza:

```bash
docker compose down -v
```

## Próximas Fases

A próxima fase técnica deve implementar upload de PDF e storage, conforme `docs/10-roadmap.md`.
