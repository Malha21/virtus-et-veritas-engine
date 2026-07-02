# VVE-0003 — System Architecture Document
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define a arquitetura inicial do Virtus et Veritas Engine.

O objetivo é construir uma plataforma modular, segura, escalável e preparada para evoluir de uma ferramenta interna da Virtus et Veritas Academy para um SaaS comercial.

## 2. Princípios Arquiteturais

A arquitetura deverá seguir os seguintes princípios:

1. Modularidade
2. Separação clara de responsabilidades
3. Baixo acoplamento entre módulos
4. Facilidade de manutenção
5. Preparação para SaaS multiempresa no futuro
6. Execução em VPS própria com Docker
7. Possibilidade de troca de provedores de IA
8. Processamento assíncrono para tarefas longas
9. Segurança desde a primeira versão
10. Qualidade do conhecimento como critério principal

## 3. Visão Geral da Arquitetura

O sistema será composto inicialmente por:

- Frontend Web
- Backend API
- Banco de dados PostgreSQL
- Storage de arquivos
- Fila de processamento
- Worker de IA
- Camada de provedores de IA
- Serviço de exportação

Arquitetura conceitual:

Usuário
↓
Frontend Next.js
↓
Backend FastAPI
↓
PostgreSQL
↓
Storage / MinIO
↓
Redis Queue
↓
AI Worker
↓
AI Providers
↓
Export Engine

## 4. Stack Tecnológica Inicial

### 4.1 Frontend

Tecnologias:

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query

Responsabilidades:

- login
- dashboard
- criação de projetos
- upload de PDF
- acompanhamento de status
- visualização dos conteúdos gerados
- exportação dos arquivos

### 4.2 Backend

Tecnologias:

- FastAPI
- Python
- SQLAlchemy
- Alembic
- Pydantic

Responsabilidades:

- autenticação
- autorização
- gerenciamento de usuários
- gerenciamento de projetos
- upload de arquivos
- extração de texto
- orquestração de tarefas
- comunicação com banco
- comunicação com storage
- endpoints da aplicação

### 4.3 Banco de Dados

Tecnologia:

- PostgreSQL

Responsabilidades:

- usuários
- organizações
- projetos
- arquivos
- status de processamento
- conteúdos gerados
- logs
- configurações

### 4.4 Storage

Primeira versão:

- armazenamento local ou MinIO

Versão recomendada:

- MinIO

Responsabilidades:

- PDFs originais
- arquivos processados
- exportações
- DOCX
- ZIP
- futuramente áudios, imagens, slides e vídeos

### 4.5 Fila

Tecnologia:

- Redis

Responsabilidades:

- enfileirar processamento de PDF
- enfileirar geração de estrutura
- enfileirar geração de roteiros
- enfileirar exportações
- evitar travamento da interface

### 4.6 Worker

Tecnologia:

- Python worker

Responsabilidades:

- executar tarefas longas
- extrair texto do PDF
- chamar AI Orchestrator
- gerar estrutura
- gerar roteiros
- gerar quizzes
- gerar materiais complementares
- atualizar status do projeto

### 4.7 IA

Primeira versão:

- OpenAI API

Arquitetura futura:

- OpenAI
- Claude
- Gemini
- modelos locais
- ElevenLabs
- HeyGen
- Runway
- outros provedores

A aplicação não deve depender diretamente de um provedor específico.

Deverá existir uma interface interna chamada AI Provider.

## 5. Módulos do Sistema

## 5.1 Identity Engine

Responsável por:

- login
- senha
- usuários
- permissões
- sessão
- futura estrutura multiempresa

Primeira versão:

- um administrador
- login com e-mail e senha
- senha com hash seguro
- JWT ou sessão segura

## 5.2 Project Engine

Responsável por:

- criar projeto
- listar projetos
- abrir projeto
- atualizar informações do projeto
- controlar status
- armazenar metadados

Tipos futuros de projeto:

- Curso
- Aula
- Workshop
- Palestra
- Ebook
- Podcast
- Reels
- Treinamento
- Mentoria
- Landing Page

Primeira versão:

- Curso

## 5.3 Knowledge Engine

Responsável por:

- receber documentos
- extrair texto
- limpar texto
- dividir texto em partes
- preparar conteúdo para IA
- futuramente indexar conhecimento em banco vetorial

## 5.4 AI Orchestrator

Responsável por:

- decidir como transformar o conteúdo
- selecionar prompts
- chamar provedores de IA
- validar respostas
- padronizar saídas
- preservar coerência didática

Primeira versão:

- geração de estrutura de curso
- geração de roteiro
- geração de quiz
- geração de materiais complementares

## 5.5 Course Engine

Responsável por:

- transformar conhecimento em curso
- organizar módulos
- organizar aulas
- definir objetivos
- gerar roteiros
- gerar materiais por módulo
- preparar exportações educacionais

## 5.6 Export Engine

Responsável por:

- exportar JSON
- exportar DOCX
- exportar ZIP
- futuramente exportar PDF
- organizar arquivos por pasta

## 5.7 Media Engine

Responsável futuramente por:

- voz
- avatar
- vídeo
- thumbnail
- slides narrados

Não será implementado na primeira versão.

## 5.8 Publishing Engine

Responsável futuramente por:

- organizar pacote para Greenn
- integração com Hotmart
- integração com Kiwify
- integração com MemberKit
- publicação manual ou semi-automática

Não será implementado na primeira versão.

## 5.9 Marketing Engine

Responsável futuramente por:

- posts
- reels
- shorts
- copy
- e-mails
- WhatsApp
- landing pages
- campanhas

Na primeira versão, poderá gerar textos simples de divulgação como parte dos materiais complementares.

## 6. Fluxo Principal da Versão 1

1. Usuário faz login.
2. Usuário cria novo projeto do tipo Curso.
3. Usuário envia PDF.
4. Backend salva PDF no storage.
5. Backend cria job de processamento.
6. Worker extrai texto do PDF.
7. Worker envia texto ao AI Orchestrator.
8. AI Orchestrator gera estrutura do curso.
9. Worker salva estrutura no banco.
10. AI Orchestrator gera roteiros.
11. Worker salva roteiros no banco.
12. AI Orchestrator gera quizzes e materiais.
13. Worker salva materiais no banco.
14. Projeto muda status para concluído.
15. Usuário revisa o conteúdo.
16. Usuário exporta JSON, DOCX ou ZIP.

## 7. Estados de Processamento

Os projetos poderão ter os seguintes status:

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

## 8. Organização Inicial do Repositório

Estrutura desejada:

/docs
/infra
/apps
  /frontend
  /backend

/apps/frontend
  Next.js app

/apps/backend
  FastAPI app

/infra
  docker
  nginx
  scripts

## 9. Comunicação entre Frontend e Backend

O frontend se comunicará com o backend via API REST.

Padrão inicial de endpoints:

- POST /auth/login
- POST /auth/logout
- GET /auth/me
- GET /projects
- POST /projects
- GET /projects/{id}
- POST /projects/{id}/upload
- POST /projects/{id}/process
- GET /projects/{id}/status
- GET /projects/{id}/content
- GET /projects/{id}/export/json
- GET /projects/{id}/export/docx
- GET /projects/{id}/export/zip
- GET /health

## 10. Segurança

A primeira versão deverá incluir:

- autenticação obrigatória
- hash seguro de senha
- proteção de rotas internas
- validação de upload
- limite de tamanho de arquivo
- proteção básica contra arquivos inválidos
- variáveis sensíveis em .env
- não expor chaves de IA no frontend

## 11. Estratégia de Deploy

Primeira versão:

- VPS própria
- Docker Compose
- containers:
  - frontend
  - backend
  - postgres
  - redis
  - minio
  - worker

Futuro:

- Nginx
- SSL
- backups automáticos
- observabilidade
- monitoramento
- separação de ambientes staging e produção

## 12. Estratégia de Escalabilidade

A arquitetura deverá permitir:

- mover storage local para MinIO/S3
- escalar workers separadamente
- trocar provedores de IA
- adicionar banco vetorial
- adicionar organizações
- adicionar planos
- adicionar billing
- adicionar múltiplos usuários

## 13. Decisões Técnicas Iniciais

1. Usar Next.js no frontend.
2. Usar FastAPI no backend.
3. Usar PostgreSQL como banco principal.
4. Usar Redis para fila.
5. Usar MinIO para storage.
6. Usar Docker Compose na VPS.
7. Usar OpenAI API como primeiro provedor textual.
8. Criar camada AI Provider para evitar dependência direta.
9. Implementar primeiro apenas projetos do tipo Curso.
10. Deixar Media Engine para segunda fase.

## 14. Fora do Escopo da Arquitetura Inicial

Não será implementado inicialmente:

- pagamento
- multiempresa real
- área de alunos
- certificados
- marketplace
- publicação automática
- avatar
- vídeo
- slides automáticos
- mobile app

## 15. Diretriz Final

A arquitetura deve ser simples o suficiente para entregar a primeira versão rapidamente, mas organizada o bastante para permitir crescimento.

O VVE Engine deve nascer como ferramenta interna da Virtus et Veritas Academy, mas com base técnica preparada para evoluir para um SaaS comercial.
