# VVE-0010 — Technical Roadmap
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define a ordem técnica de construção do Virtus et Veritas Engine.

O objetivo é evitar confusão, reduzir retrabalho e permitir que o projeto evolua de forma organizada, começando como ferramenta interna da Virtus et Veritas Academy e futuramente podendo se tornar um SaaS comercial.

## 2. Princípio de Execução

O projeto será desenvolvido por blocos.

Cada bloco deve:

1. ter objetivo claro;
2. entregar algo funcional ou documentado;
3. ser testável;
4. não tentar resolver problemas de fases futuras;
5. preservar a arquitetura modular;
6. manter foco na entrega de conhecimento de qualidade.

## 3. Estratégia de Validação

O Virtus et Veritas Engine será validado prioritariamente direto na VPS usando Docker Compose.

Embora o projeto possa rodar localmente, a validação principal será feita no servidor, aproximando o ambiente de teste do ambiente real de produção.

Motivos:

- o usuário já possui VPS disponível;
- evita dependência de configuração local;
- reduz diferenças entre desenvolvimento e produção;
- permite testar Docker, portas, variáveis, domínio, SSL e persistência desde cedo;
- prepara o projeto para funcionar como produto real.

## 4. Status Geral

Fase atual:

- Documentação e arquitetura inicial.

Status:

- Em andamento.

## 5. Fase 1 — Documentação e Arquitetura

Objetivo:

Definir claramente visão, requisitos, arquitetura, banco, API, IA, frontend, backend e deploy.

Arquivos:

- docs/01-product-vision.md
- docs/02-requirements.md
- docs/03-architecture.md
- docs/04-database.md
- docs/05-api.md
- docs/06-ai-orchestrator.md
- docs/07-frontend.md
- docs/08-backend.md
- docs/09-deployment.md
- docs/10-roadmap.md
- docs/11-decisions.md

Critério de conclusão:

- Todos os documentos iniciais preenchidos.
- Decisões principais registradas.
- Pronto para iniciar implementação técnica.

Status:

- Quase concluída.

## 6. Fase 2 — Fundação Técnica do Repositório

Objetivo:

Criar a base real do sistema com frontend, backend, Docker e estrutura de pastas.

Entregas:

1. Criar frontend Next.js em apps/frontend.
2. Criar backend FastAPI em apps/backend.
3. Criar docker-compose.yml.
4. Atualizar .env.example completo.
5. Criar health check do backend.
6. Criar página inicial simples do frontend.
7. Subir tudo na VPS com Docker Compose.

Critério de conclusão:

- docker compose up -d --build sobe frontend e backend na VPS.
- Frontend acessível pelo IP ou domínio configurado da VPS.
- Backend acessível pelo IP ou domínio configurado da VPS em /health.
- Containers principais sobem corretamente na VPS.
- Nenhuma integração com IA ainda.

Observação:

Embora o projeto possa rodar localmente, a validação principal será feita diretamente na VPS, usando Docker Compose, para aproximar o ambiente de teste do ambiente real de produção.

## 7. Fase 3 — Banco de Dados e Autenticação

Objetivo:

Implementar PostgreSQL, models principais, migrations e login básico.

Entregas:

1. Configurar SQLAlchemy.
2. Configurar Alembic.
3. Criar models:
   - organizations
   - users
   - projects
   - project_files
   - generated_contents
   - processing_jobs
   - processing_logs
   - ai_providers
   - ai_requests
4. Criar migrations iniciais.
5. Criar seed inicial:
   - Virtus et Veritas Academy
   - usuário administrador
   - provedor OpenAI
6. Implementar login com e-mail e senha.
7. Implementar hash seguro de senha.
8. Implementar JWT.
9. Implementar /auth/me.
10. Proteger rotas internas.

Critério de conclusão:

- Usuário administrador consegue fazer login.
- Token é emitido.
- /auth/me retorna usuário e organização.
- Banco sobe com migrations.
- Seed inicial funciona.
- Autenticação validada na VPS.

## 8. Fase 4 — Dashboard e Projetos

Objetivo:

Permitir que o usuário autenticado visualize dashboard e crie projetos.

Entregas:

1. Criar layout autenticado no frontend.
2. Criar tela de login.
3. Criar dashboard.
4. Criar lista de projetos.
5. Criar formulário de novo projeto.
6. Criar endpoints:
   - GET /projects
   - POST /projects
   - GET /projects/{id}
   - PATCH /projects/{id}
   - DELETE /projects/{id}
7. Integrar frontend com API.

Critério de conclusão:

- Usuário faz login.
- Usuário acessa dashboard.
- Usuário cria projeto do tipo course.
- Usuário lista projetos.
- Usuário abre detalhes do projeto.
- Fluxo validado direto na VPS.

## 9. Fase 5 — Upload de PDF e Storage

Objetivo:

Permitir envio e armazenamento de PDFs vinculados ao projeto.

Entregas:

1. Configurar storage local ou MinIO.
2. Criar File Service.
3. Criar endpoint:
   - POST /projects/{project_id}/files
4. Criar endpoint:
   - GET /projects/{project_id}/files
5. Validar:
   - extensão PDF
   - MIME type
   - tamanho máximo
6. Salvar arquivo no storage.
7. Registrar metadados em project_files.
8. Criar tela de upload no frontend.

Critério de conclusão:

- Usuário envia PDF.
- Arquivo é salvo.
- Metadados aparecem no banco.
- Arquivo aparece listado no projeto.
- Upload validado direto na VPS.

## 10. Fase 6 — Extração de Texto e Jobs

Objetivo:

Criar o primeiro processamento assíncrono real.

Entregas:

1. Configurar Redis.
2. Configurar worker.
3. Criar processing_jobs.
4. Criar endpoint:
   - POST /projects/{project_id}/process
5. Criar endpoint:
   - GET /projects/{project_id}/status
6. Implementar extração de texto do PDF.
7. Salvar texto extraído.
8. Atualizar status do projeto.
9. Registrar logs de processamento.
10. Criar tela de processamento no frontend.

Critério de conclusão:

- Usuário inicia processamento.
- Job é criado.
- Worker extrai texto do PDF.
- Status muda durante o processamento.
- Logs são registrados.
- Projeto chega ao status de texto extraído ou erro claro.
- Processamento validado direto na VPS.

## 11. Fase 7 — AI Orchestrator V1

Objetivo:

Transformar o texto extraído em estrutura educacional com IA.

Entregas:

1. Criar AI Provider base.
2. Criar OpenAI Provider.
3. Criar prompts versionados:
   - document_analysis_v1
   - course_structure_v1
4. Criar AI Orchestrator Service.
5. Registrar ai_requests.
6. Gerar análise do documento.
7. Gerar estrutura do curso.
8. Salvar em generated_contents.
9. Exibir estrutura no frontend.

Critério de conclusão:

- PDF processado gera análise do documento.
- PDF processado gera estrutura de curso.
- Estrutura aparece na tela de revisão.
- Chamadas de IA ficam registradas.
- Fluxo de IA validado direto na VPS.

## 12. Fase 8 — Roteiros, Quizzes e Materiais

Objetivo:

Gerar o pacote textual completo do curso.

Entregas:

1. Criar prompt lesson_script_v1.
2. Criar prompt quiz_v1.
3. Criar prompt materials_v1.
4. Criar prompt marketing_v1.
5. Gerar roteiros aula por aula.
6. Gerar quizzes por módulo.
7. Gerar materiais complementares.
8. Gerar textos simples de divulgação.
9. Salvar tudo em generated_contents.
10. Criar abas de revisão no frontend:
    - Estrutura
    - Roteiros
    - Quizzes
    - Materiais
    - Marketing

Critério de conclusão:

- Um PDF gera curso estruturado completo.
- Usuário consegue revisar o conteúdo na interface.
- Conteúdos ficam separados por tipo.
- Status final fica completed.
- Pacote textual validado direto na VPS.

## 13. Fase 9 — Exportações

Objetivo:

Permitir baixar o conteúdo gerado.

Entregas:

1. Exportar JSON.
2. Exportar DOCX.
3. Exportar ZIP.
4. Criar Export Service.
5. Criar endpoints:
   - GET /projects/{project_id}/export/json
   - GET /projects/{project_id}/export/docx
   - GET /projects/{project_id}/export/zip
6. Criar tela de exportação no frontend.
7. Salvar exportações no storage.

Critério de conclusão:

- Usuário baixa JSON.
- Usuário baixa DOCX.
- Usuário baixa ZIP.
- ZIP contém arquivos organizados do projeto.
- Exportações validadas direto na VPS.

## 14. Fase 10 — Endurecimento de Produção na VPS

Objetivo:

Transformar o ambiente já validado na VPS em um ambiente mais seguro e preparado para uso real.

A VPS será usada desde as fases iniciais. Portanto, esta fase não representa o primeiro deploy, mas sim o endurecimento de produção.

Entregas:

1. Configurar docker-compose para produção.
2. Revisar .env de produção.
3. Configurar Nginx.
4. Configurar SSL.
5. Configurar domínio ou subdomínio.
6. Configurar firewall.
7. Garantir que Postgres não esteja público.
8. Garantir que Redis não esteja público.
9. Garantir que MinIO esteja protegido.
10. Rodar migrations.
11. Rodar seed.
12. Validar login.
13. Validar upload.
14. Validar processamento.
15. Validar exportação.
16. Configurar backup inicial.
17. Registrar checklist de produção.

Critério de conclusão:

- Sistema acessível via domínio.
- HTTPS funcionando.
- Login funcionando.
- PDF vira curso estruturado.
- Exportação funcionando.
- Dados persistem após reinício.
- Containers reiniciam corretamente.
- Backup inicial definido.
- Ambiente pronto para uso interno real da Virtus et Veritas Academy.

## 15. Fase 11 — Media Engine V1

Objetivo:

Adicionar produção audiovisual.

Entregas futuras:

1. Gerar outline de slides.
2. Gerar slides.
3. Gerar narração.
4. Integrar ElevenLabs ou outro provedor de voz.
5. Integrar HeyGen, Tavus ou Synthesia para avatar.
6. Gerar pacote de vídeos.
7. Organizar arquivos para Greenn.

Critério de conclusão:

- Curso textual vira pacote audiovisual inicial.
- O conteúdo gerado pode ser usado para antecipar a produção dos cursos da Virtus et Veritas Academy.

## 16. Fase 12 — Knowledge Base

Objetivo:

Criar memória permanente do conhecimento da Virtus et Veritas Academy.

Entregas futuras:

1. Adicionar Qdrant.
2. Criar coleções de conhecimento.
3. Indexar PDFs.
4. Indexar cursos gerados.
5. Criar busca semântica.
6. Permitir geração de novos produtos usando acervo interno.

Critério de conclusão:

- Sistema consulta conhecimento interno antes de gerar novos produtos.
- A Virtus et Veritas Academy começa a formar uma biblioteca intelectual própria e reutilizável.

## 17. Fase 13 — SaaS Comercial

Objetivo:

Preparar o VVE Engine para clientes externos.

Entregas futuras:

1. Multiempresa real.
2. Convites de usuários.
3. Planos.
4. Limites.
5. Billing.
6. Painel administrativo.
7. Métricas de consumo.
8. White label.
9. Onboarding.
10. Termos de uso e privacidade.
11. Política de uso aceitável.
12. Controle de custos por organização.

Critério de conclusão:

- Plataforma pronta para receber clientes externos.
- Uso interno da Virtus et Veritas Academy validou o produto.
- Arquitetura preparada para comercialização.

## 18. Ordem Imediata de Execução

A ordem imediata após a documentação será:

1. Finalizar docs/10-roadmap.md.
2. Atualizar docs/11-decisions.md.
3. Criar frontend e backend mínimos.
4. Criar Docker Compose.
5. Subir health check na VPS.
6. Implementar banco e autenticação.
7. Implementar projetos.
8. Implementar upload.
9. Implementar processamento.
10. Implementar IA.

## 19. Regra de Ouro

Não avançar para produção audiovisual antes de o núcleo textual estar funcionando muito bem.

O avatar só fará sentido quando o conteúdo gerado já tiver qualidade suficiente para representar a Virtus et Veritas Academy.

## 20. Diretrizes de Segurança Durante as Fases Iniciais

Mesmo em fase inicial, o projeto deverá seguir cuidados mínimos:

1. Não versionar .env.
2. Não expor chaves de IA.
3. Não deixar Postgres público.
4. Não deixar Redis público.
5. Usar senhas fortes.
6. Proteger rotas internas assim que autenticação for criada.
7. Usar firewall na VPS.
8. Ativar SSL antes de uso real.
9. Manter backups assim que dados reais forem inseridos.
10. Não usar materiais sensíveis em testes públicos.

## 21. Diretriz Final

O roadmap deve manter o projeto sob controle.

O VVE Engine deve entregar valor rápido para a Virtus et Veritas Academy, sem perder a arquitetura necessária para virar produto comercial no futuro.

A prioridade é criar primeiro um núcleo textual excelente:

PDF → estrutura educacional → roteiros → quizzes → materiais → exportação.

Depois disso, avançar para:

slides → voz → avatar → vídeo → publicação → SaaS comercial.
