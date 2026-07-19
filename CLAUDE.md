
# VVE Engine — Direção para Claude Code

## Projeto
Repositório: https://github.com/Malha21/virtus-et-veritas-engine  
VPS: /opt/virtus-et-veritas-engine  
Domínio: http://engine.vvacademy.com.br

## Stack
Backend FastAPI: apps/backend  
Frontend Next.js: apps/frontend  
Postgres Docker  
Containers: vve-backend, vve-frontend, vve-postgres

## Regras obrigatórias
- Nunca usar git add .
- Usar git add seletivo.
- Nunca comitar .env, chaves, storage, áudios ou vídeos gerados.
- Nunca adicionar dashboardaaes-main/ nem lms-premium/.
- Antes de commit rodar:
  git status --short
  git diff --stat
  git diff --check
- Não sobrescrever docker-compose.yml sem autorização se ele estiver modificado localmente.

## Fases concluídas
17.1 Documento Base como fonte da verdade.
17.2 Estrutura do curso baseada na análise do PDF.
17.3 Roteiros profundos por aula.
17.4 Narração fiel ao roteiro.
17.5 Narração por aula e módulo.
17.6 Biblioteca de áudios.
17.7 Exportação ZIP por aula/módulo.
18.0 Base de vídeo/avatar por aula.

## Problema atual prioritário
PDF de 69 páginas está gerando somente:
- Módulo 1
- Aula 1
- Aula 2
- Aula 3

Isso está errado.

Arquivo de teste:
os-4-compromissos.pdf

O PDF tem sumário com:
- Introdução
- 1 Domesticação e o sonho do planeta
- 2 O primeiro compromisso
- 3 O segundo compromisso
- 4 O terceiro compromisso
- 5 O quarto compromisso
- 6 O caminho tolteca para a liberdade
- 7 O novo sonho
- Orações
- Sobre o autor

Resultado esperado:
mínimo 7 módulos e 21 aulas.
Ideal 8 a 9 módulos e 28 a 35 aulas.

## Tarefa atual
Não corrigir no escuro. Primeiro investigar onde ocorre o truncamento:
1. extração do PDF;
2. document_analysis;
3. prompt de course_structure;
4. resposta bruta da IA;
5. parser;
6. salvamento no banco;
7. exibição no frontend.

Arquivos prováveis:
- apps/backend/app/prompts/course_structure_v1.py
- apps/backend/app/prompts/document_analysis_v1.py
- apps/backend/app/services/
- apps/backend/app/api/v1/educational_content.py
- apps/frontend/app/projects/[id]/educational-content/page.tsx
- apps/frontend/lib/api.ts

Entregar primeiro diagnóstico, depois pedir autorização para implementar.
