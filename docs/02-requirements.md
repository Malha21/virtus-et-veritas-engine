# VVE-0002 — Requirements Document
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define os requisitos funcionais e não funcionais do Virtus et Veritas Engine.

O objetivo é orientar o desenvolvimento da primeira versão funcional da plataforma, mantendo visão de longo prazo para evolução como SaaS.

## 2. Escopo da Primeira Versão

A primeira versão será uma aplicação interna para uso da Virtus et Veritas Academy.

Ela deverá permitir que um usuário autenticado envie um PDF e receba uma estrutura educacional completa, incluindo módulos, aulas, roteiros, quizzes e materiais complementares.

## 3. Requisitos Funcionais — Versão 1

### RF-001 — Autenticação

O sistema deve permitir login com e-mail e senha.

### RF-002 — Usuário administrador inicial

O sistema deve permitir a criação de um usuário administrador inicial por seed ou comando interno.

### RF-003 — Dashboard

O sistema deve exibir um dashboard após o login com visão geral dos projetos criados.

### RF-004 — Criar projeto

O usuário deve conseguir criar um novo projeto.

Campos mínimos:

- nome do projeto
- tipo de produto
- público-alvo
- tom de voz
- duração desejada
- descrição opcional

Na primeira versão, o tipo de produto principal será Curso.

### RF-005 — Upload de PDF

O usuário deve conseguir enviar um arquivo PDF para o projeto.

### RF-006 — Armazenamento do PDF

O sistema deve armazenar o PDF original em storage próprio.

Na primeira versão, pode ser armazenamento local ou MinIO.

### RF-007 — Extração de texto

O backend deve extrair o texto do PDF enviado.

### RF-008 — Registro do conteúdo extraído

O sistema deve salvar o texto extraído ou uma referência processável no banco de dados.

### RF-009 — Análise do documento

O sistema deve enviar o conteúdo extraído para o AI Orchestrator analisar.

### RF-010 — Estrutura do curso

O sistema deve gerar uma estrutura inicial contendo:

- nome sugerido do curso
- promessa do curso
- descrição
- público-alvo
- objetivos de aprendizagem
- módulos
- aulas
- resumo de cada aula

### RF-011 — Roteiros

O sistema deve gerar roteiros completos para cada aula.

Cada roteiro deve conter:

- abertura
- explicação principal
- exemplos
- transições
- chamada para reflexão
- encerramento

### RF-012 — Quizzes

O sistema deve gerar perguntas de fixação para cada módulo.

### RF-013 — Materiais complementares

O sistema deve gerar materiais complementares, como:

- resumo do módulo
- checklist
- exercícios
- sugestões de leitura
- texto de apoio

### RF-014 — Revisão humana

O sistema deve permitir que o usuário visualize o conteúdo gerado antes de exportar.

### RF-015 — Exportação JSON

O sistema deve permitir exportar o projeto em JSON.

### RF-016 — Exportação DOCX

O sistema deve permitir exportar roteiros e materiais em DOCX.

### RF-017 — Exportação ZIP

O sistema deve permitir baixar um pacote ZIP com os arquivos gerados.

### RF-018 — Status de processamento

O sistema deve exibir status do processamento:

- aguardando
- extraindo texto
- analisando
- gerando estrutura
- gerando roteiros
- gerando materiais
- concluído
- erro

### RF-019 — Histórico de projetos

O sistema deve listar os projetos já criados.

### RF-020 — Visualizar projeto

O usuário deve conseguir abrir um projeto e visualizar sua estrutura, roteiros e materiais.

## 4. Requisitos Funcionais — Versão 2

### RF-021 — Geração de slides

O sistema deverá gerar slides para cada aula.

### RF-022 — Geração de narração

O sistema deverá gerar narração por IA.

### RF-023 — Integração com avatar

O sistema deverá integrar com uma ferramenta de avatar, como HeyGen, Synthesia ou Tavus.

### RF-024 — Geração de vídeo

O sistema deverá gerar ou organizar vídeos finais das aulas.

### RF-025 — Thumbnails

O sistema deverá criar thumbnails para aulas e cursos.

### RF-026 — Pacote para Greenn

O sistema deverá organizar os arquivos em uma estrutura adequada para publicação manual ou semi-automática na Greenn.

## 5. Requisitos Funcionais — Versão 3

### RF-027 — Base de conhecimento

O sistema deverá permitir criar uma biblioteca permanente de conhecimento.

### RF-028 — Busca semântica

O sistema deverá permitir buscar conteúdos por significado, não apenas por palavras-chave.

### RF-029 — Reaproveitamento de conteúdos

O sistema deverá permitir criar novos produtos usando materiais já existentes.

### RF-030 — Multiempresa

O sistema deverá evoluir para múltiplas organizações no modelo SaaS.

### RF-031 — Planos e limites

O sistema deverá permitir planos de uso, limites e controle de consumo.

## 6. Requisitos Não Funcionais

### RNF-001 — Segurança

O sistema deve proteger rotas internas com autenticação.

### RNF-002 — Senhas seguras

As senhas devem ser armazenadas com hash seguro.

### RNF-003 — Modularidade

O sistema deve ser construído de forma modular, separando frontend, backend, banco, storage, fila e provedores de IA.

### RNF-004 — Escalabilidade

A arquitetura deve permitir evolução futura para SaaS multiusuário e multiempresa.

### RNF-005 — Observabilidade

O sistema deve registrar logs de processamento e erros.

### RNF-006 — Reprocessamento

O sistema deve permitir reprocessar um projeto em caso de erro.

### RNF-007 — Portabilidade

O sistema deve rodar em VPS própria usando Docker.

### RNF-008 — Substituição de provedores

O sistema deve permitir trocar provedores de IA sem reescrever o núcleo da aplicação.

### RNF-009 — Qualidade do conteúdo

O conteúdo gerado deve ser estruturado, claro, didático e adequado ao público-alvo informado.

### RNF-010 — Performance

Processamentos longos devem ser executados em background, sem travar a interface.

### RNF-011 — Manutenibilidade

O código deve ser organizado, documentado e fácil de evoluir.

### RNF-012 — Experiência premium

A interface deve transmitir sofisticação, clareza, confiança e simplicidade.

## 7. Fora do Escopo da Primeira Versão

A primeira versão não incluirá:

- pagamento
- marketplace
- área de alunos
- certificados automáticos
- aplicativo mobile
- afiliados
- publicação automática na Greenn
- múltiplas empresas
- edição avançada de vídeo
- comunidade interna

## 8. Critério de Sucesso da Primeira Versão

A primeira versão será considerada bem-sucedida quando o usuário conseguir:

1. fazer login
2. criar um projeto
3. enviar um PDF
4. gerar uma estrutura de curso
5. gerar roteiros
6. gerar quizzes e materiais
7. revisar o conteúdo
8. exportar o pacote final

## 9. Diretriz Final

A primeira versão deve ser simples, estável e útil.

Não devemos tentar construir todas as funcionalidades de uma vez.

O foco inicial é criar o núcleo de transformação:

Conhecimento bruto → estrutura educacional → roteiro → materiais → exportação.
