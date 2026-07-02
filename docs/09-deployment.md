# VVE-0009 — Deployment & Infrastructure Document
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define a estratégia inicial de infraestrutura, deploy e operação do Virtus et Veritas Engine.

O sistema será inicialmente hospedado em VPS própria, usando Docker e Docker Compose.

O objetivo é permitir uma implantação simples, segura, reproduzível e preparada para evolução futura.

## 2. Ambiente Inicial

Ambiente de execução inicial:

- VPS Linux
- Ubuntu Server recomendado
- Docker
- Docker Compose
- Nginx
- Certbot ou proxy com SSL
- domínio ou subdomínio próprio

Subdomínio sugerido:

- engine.vvacademy.com.br

Alternativas:

- vve.seudominio.com.br
- app.virtusetveritas.com.br
- engine.virtusetveritas.com.br

## 3. Containers da Primeira Versão

A primeira versão deverá usar os seguintes containers:

- frontend
- backend
- worker
- postgres
- redis
- minio

Futuramente:

- nginx
- qdrant
- monitoring
- backup
- media-worker

## 4. Responsabilidade dos Containers

## 4.1 frontend

Responsável por servir a aplicação Next.js.

Porta interna sugerida:

- 3000

## 4.2 backend

Responsável por servir a API FastAPI.

Porta interna sugerida:

- 8000

## 4.3 worker

Responsável por executar tarefas assíncronas.

Exemplos:

- extração de texto de PDF
- chamadas ao AI Orchestrator
- geração de roteiros
- exportações

## 4.4 postgres

Banco principal da aplicação.

Porta padrão:

- 5432

Volume persistente obrigatório.

## 4.5 redis

Fila/cache para processamento assíncrono.

Porta padrão:

- 6379

## 4.6 minio

Storage de arquivos.

Responsável por armazenar:

- PDFs originais
- textos extraídos
- exportações JSON
- DOCX
- ZIP
- futuramente imagens, áudios e vídeos

Portas sugeridas:

- 9000 API
- 9001 Console

Volume persistente obrigatório.

## 5. Docker Compose

A primeira versão deverá usar Docker Compose para subir todos os serviços.

Arquivo esperado:

- docker-compose.yml

Futuro:

- docker-compose.prod.yml
- docker-compose.dev.yml

## 6. Volumes Persistentes

Volumes necessários:

- postgres_data
- minio_data
- redis_data opcional

Nunca armazenar dados importantes apenas dentro do container sem volume.

## 7. Variáveis de Ambiente

O arquivo .env deverá conter:

Aplicação:

- APP_NAME=Virtus et Veritas Engine
- APP_ENV=production
- API_PREFIX=/api/v1

Banco:

- POSTGRES_DB=vve_engine
- POSTGRES_USER=vve_user
- POSTGRES_PASSWORD=senha_segura
- DATABASE_URL=postgresql+psycopg://vve_user:senha_segura@postgres:5432/vve_engine

Redis:

- REDIS_URL=redis://redis:6379/0

Storage:

- STORAGE_DRIVER=minio
- STORAGE_PATH=/storage
- MINIO_ENDPOINT=minio:9000
- MINIO_PUBLIC_ENDPOINT=https://storage.seudominio.com.br
- MINIO_ACCESS_KEY=definir
- MINIO_SECRET_KEY=definir
- MINIO_BUCKET=vve-engine

Autenticação:

- JWT_SECRET=definir_chave_muito_segura
- JWT_EXPIRES_MINUTES=1440

IA:

- OPENAI_API_KEY=definir
- OPENAI_DEFAULT_MODEL=definir

Upload:

- MAX_UPLOAD_SIZE_MB=100

Frontend:

- NEXT_PUBLIC_API_URL=https://engine.seudominio.com.br/api/v1

CORS:

- CORS_ORIGINS=https://engine.seudominio.com.br

Seed inicial:

- SEED_ADMIN_NAME=Leonardo Elias
- SEED_ADMIN_EMAIL=definir
- SEED_ADMIN_PASSWORD=definir
- SEED_ORGANIZATION_NAME=Virtus et Veritas Academy
- SEED_ORGANIZATION_SLUG=virtus-et-veritas-academy

## 8. Segurança Inicial

Medidas mínimas:

1. Usar HTTPS.
2. Não expor Postgres publicamente.
3. Não expor Redis publicamente.
4. Não expor MinIO sem controle.
5. Usar senhas fortes.
6. Usar JWT secret forte.
7. Restringir CORS.
8. Não versionar .env.
9. Não colocar chaves de IA no frontend.
10. Manter backups.
11. Atualizar VPS regularmente.
12. Usar firewall.

## 9. Firewall

Portas públicas recomendadas:

- 80 HTTP
- 443 HTTPS
- 22 SSH, preferencialmente restrita

Portas internas não devem ficar públicas:

- 5432 PostgreSQL
- 6379 Redis
- 9000 MinIO API
- 9001 MinIO Console
- 8000 Backend direto
- 3000 Frontend direto

O acesso externo deverá passar pelo Nginx/proxy.

## 10. Nginx

O Nginx deverá atuar como reverse proxy.

Rotas sugeridas:

- / → frontend
- /api → backend
- /health → backend health check

MinIO poderá usar subdomínio próprio futuramente:

- storage.vvacademy.com.br

Na primeira versão, MinIO pode ser usado apenas internamente.

## 11. SSL

Usar certificado SSL.

Opções:

- Certbot com Let's Encrypt
- Cloudflare Proxy
- Traefik
- Caddy

Recomendação inicial:

- Nginx + Certbot ou Cloudflare + Nginx

## 12. Backups

Backups mínimos:

- banco PostgreSQL
- volume do MinIO
- arquivo .env guardado com segurança
- repositório Git

Estratégia inicial:

- backup diário do PostgreSQL
- backup semanal do MinIO
- retenção mínima de 7 dias

Futuro:

- backup automático para storage externo
- backup criptografado
- monitoramento de falhas de backup

## 13. Deploy Inicial

Fluxo de deploy recomendado:

1. Acessar VPS via SSH.
2. Instalar Docker e Docker Compose.
3. Clonar repositório.
4. Criar arquivo .env.
5. Rodar docker compose up -d --build.
6. Rodar migrations.
7. Rodar seed inicial.
8. Verificar backend /health.
9. Acessar frontend.
10. Configurar domínio e SSL.

## 14. Ambientes

Primeira versão:

- production

Futuro:

- development
- staging
- production

Recomendação:

Mesmo em VPS única, manter clareza entre ambiente local e produção.

## 15. Logs

Logs deverão ser acessíveis via:

- docker logs
- logs da aplicação
- processing_logs no banco

Futuro:

- Grafana
- Loki
- Prometheus
- Sentry

## 16. Monitoramento

Monitoramento inicial:

- health check do backend
- uso de CPU/RAM da VPS
- uso de disco
- tamanho do banco
- tamanho do MinIO
- falhas no worker

Futuro:

- alertas por e-mail/Telegram/WhatsApp
- painel de observabilidade
- métricas de IA
- custo por projeto

## 17. Requisitos Mínimos da VPS

Para desenvolvimento e primeira versão interna:

- 2 vCPU
- 4 GB RAM
- 50 GB SSD

Recomendado:

- 4 vCPU
- 8 GB RAM
- 100 GB SSD

Para geração audiovisual futura, avaliar serviços externos ou workers dedicados.

## 18. Cuidados com Custos

Custos principais:

- VPS
- OpenAI API
- storage
- avatar/voz no futuro
- backups
- domínio
- Cloudflare opcional

O sistema deverá registrar uso de IA desde cedo para permitir controle de custo.

## 19. Estratégia para Crescimento

Quando virar SaaS comercial, considerar:

- separar banco em serviço gerenciado
- usar S3 compatível para storage
- usar workers escaláveis
- usar CDN
- usar observabilidade completa
- criar ambientes separados
- criar CI/CD
- implementar billing
- aplicar limites por organização

## 20. CI/CD Futuro

Na primeira versão, deploy manual via SSH é aceitável.

Futuro:

- GitHub Actions
- build automático
- testes antes do deploy
- deploy para staging
- aprovação manual para produção
- rollback

## 21. Checklist de Produção

Antes de expor publicamente:

- HTTPS ativo
- .env fora do Git
- senhas fortes
- backups funcionando
- firewall configurado
- CORS restrito
- Postgres sem acesso público
- Redis sem acesso público
- MinIO protegido
- health check funcionando
- seed admin alterada após primeiro login
- logs funcionando
- upload limitado
- domínio apontado corretamente

## 22. Fora do Escopo da Infraestrutura V1

Não implementar inicialmente:

- Kubernetes
- autoscaling
- multi-região
- CDN avançada
- banco gerenciado obrigatório
- CI/CD obrigatório
- observabilidade completa
- cluster de workers
- renderização local pesada de vídeo

## 23. Diretriz Final

A infraestrutura inicial deve ser simples, segura e controlável.

O objetivo é colocar o VVE Engine em produção na VPS própria de forma estável, sem complexidade desnecessária.

A arquitetura deve permitir evolução, mas a primeira entrega deve privilegiar funcionamento, segurança básica e facilidade de manutenção.
