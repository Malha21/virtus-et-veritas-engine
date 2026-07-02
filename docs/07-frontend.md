# VVE-0007 — Frontend Design Document
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define a arquitetura, a experiência do usuário e a direção visual inicial do frontend do Virtus et Veritas Engine.

O frontend será a interface principal entre o usuário e o motor de produção intelectual.

Ele deve ser simples, elegante, premium e focado em transformar conhecimento bruto em produtos educacionais completos.

## 2. Princípios de Experiência

O frontend deverá seguir os seguintes princípios:

1. Simplicidade.
2. Clareza.
3. Aparência premium.
4. Baixa fricção.
5. Orientação por etapas.
6. Feedback visual constante.
7. Sensação de controle.
8. Foco na criação de conhecimento.
9. Evitar aparência técnica demais.
10. Facilitar revisão humana.

## 3. Stack do Frontend

Tecnologias recomendadas:

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- Zod
- React Hook Form
- Motion

## 4. Identidade Visual

A identidade visual do VVE Engine deverá transmitir:

- sofisticação;
- autoridade;
- tecnologia;
- clareza;
- confiança;
- profundidade intelectual;
- produto SaaS premium.

## 5. Paleta de Cores

Paleta inicial sugerida:

### Cores principais

- Navy profundo: #07111F
- Azul escuro: #0B1B33
- Dourado premium: #C8A24A
- Dourado claro: #E4C766
- Branco: #FFFFFF
- Cinza claro: #E5E7EB
- Cinza texto: #94A3B8
- Grafite: #111827

### Uso recomendado

- Fundo principal: navy profundo
- Cards: azul escuro
- Destaques: dourado premium
- Texto principal: branco
- Texto secundário: cinza claro
- Bordas discretas: rgba(255,255,255,0.08)

## 6. Tipografia

Direção tipográfica:

- Títulos: fonte elegante, moderna e forte
- Texto: fonte limpa, legível e profissional

Sugestões:

- Inter
- Geist
- Manrope
- Playfair Display para detalhes editoriais opcionais

Na primeira versão, usar uma fonte moderna e simples, como Inter ou Geist.

## 7. Layout Geral

O layout interno deverá usar:

- sidebar lateral
- topo com usuário e organização
- área principal com cards
- botões claros
- estados de loading
- mensagens de erro amigáveis
- design responsivo para desktop

A primeira versão será otimizada para desktop.

Mobile será considerado futuramente.

## 8. Rotas Principais

Rotas iniciais:

- /login
- /dashboard
- /projects
- /projects/new
- /projects/[id]
- /projects/[id]/upload
- /projects/[id]/processing
- /projects/[id]/review
- /projects/[id]/export
- /settings

## 9. Tela de Login

Objetivo:

Permitir acesso seguro ao sistema.

Elementos:

- logo ou nome VVE Engine
- subtítulo: Inteligência para produção de conhecimento
- campo e-mail
- campo senha
- botão Entrar
- mensagem de erro
- fundo escuro premium
- detalhe visual em dourado

Texto sugerido:

Virtus et Veritas Engine  
Inteligência para produção de conhecimento.

Campos:

- E-mail
- Senha

Botão:

Entrar

## 10. Dashboard

Objetivo:

Dar visão geral do sistema após login.

Elementos:

- saudação ao usuário
- cards de indicadores
- botão Novo Projeto
- lista de projetos recentes
- status dos processamentos

Cards iniciais:

- Projetos criados
- Cursos concluídos
- Em processamento
- Exportações geradas

Ações principais:

- Novo Projeto
- Ver Projetos
- Continuar último projeto

## 11. Lista de Projetos

Objetivo:

Permitir encontrar e acompanhar projetos.

Elementos:

- tabela ou cards de projetos
- busca
- filtro por status
- filtro por tipo
- status visual de processamento
- data de criação
- botão abrir

Campos exibidos:

- título
- tipo de produto
- status
- processamento
- atualizado em
- ação

## 12. Novo Projeto

Objetivo:

Criar um novo projeto de produção intelectual.

Fluxo em etapas:

### Etapa 1 — Tipo de Produto

Na primeira versão, apenas Curso estará habilitado.

Tipos futuros visíveis, porém bloqueados opcionalmente:

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
- Campanha

### Etapa 2 — Informações do Projeto

Campos:

- nome do projeto
- público-alvo
- tom de voz
- duração desejada
- descrição opcional

### Etapa 3 — Material de Entrada

Upload do PDF.

### Etapa 4 — Revisão da Configuração

Resumo antes de iniciar.

Botão final:

Criar Projeto

## 13. Upload de PDF

Objetivo:

Permitir envio do material-base.

Elementos:

- área drag and drop
- botão selecionar arquivo
- limite de tamanho visível
- validação de PDF
- nome do arquivo enviado
- status do upload
- botão iniciar processamento

Mensagens amigáveis:

- Envie o material que servirá como base para o curso.
- O VVE Engine irá analisar, organizar e transformar este conhecimento em uma estrutura educacional.

## 14. Tela de Processamento

Objetivo:

Mostrar ao usuário o andamento da geração.

Etapas visuais:

1. Recebendo arquivo
2. Extraindo texto
3. Analisando conhecimento
4. Criando estrutura
5. Gerando roteiros
6. Criando quizzes
7. Preparando materiais
8. Finalizando pacote

Elementos:

- barra de progresso
- etapa atual
- status detalhado
- tempo aproximado opcional
- logs resumidos
- aviso para não fechar a página se necessário

Observação:
Mesmo que o processamento continue em background, a interface deve transmitir confiança e clareza.

## 15. Tela de Revisão

Objetivo:

Permitir revisar o conteúdo gerado antes da exportação.

Organização:

- visão geral do curso
- módulos
- aulas
- roteiros
- quizzes
- materiais complementares
- textos de divulgação

Layout sugerido:

- sidebar interna com navegação do conteúdo
- área principal com editor/visualizador
- botões de aprovar, editar e salvar

Abas:

- Estrutura
- Roteiros
- Quizzes
- Materiais
- Marketing

## 16. Tela de Exportação

Objetivo:

Permitir baixar os arquivos finais.

Opções:

- Exportar JSON
- Exportar DOCX
- Exportar ZIP

Futuro:

- Exportar PDF
- Gerar slides
- Gerar pacote para Greenn
- Gerar vídeo com avatar

Elementos:

- resumo do projeto
- status de aprovação
- botões de download
- histórico de exportações

## 17. Componentes Principais

Componentes iniciais:

- AppShell
- Sidebar
- Topbar
- StatCard
- ProjectCard
- ProjectTable
- StatusBadge
- ProgressSteps
- FileUploader
- EmptyState
- ErrorState
- LoadingState
- ContentViewer
- ContentEditor
- ExportCard
- PrimaryButton
- SecondaryButton

## 18. Estados Visuais

Estados obrigatórios:

- loading
- empty
- error
- success
- disabled
- processing
- completed
- failed

O usuário nunca deve ficar sem resposta visual.

## 19. Linguagem da Interface

A linguagem deve ser clara, elegante e humana.

Evitar termos excessivamente técnicos.

Exemplos:

Em vez de:
- Job iniciado

Usar:
- Seu conteúdo entrou na fila de processamento.

Em vez de:
- Parsing PDF

Usar:
- Estamos lendo o material enviado.

Em vez de:
- AI response failed

Usar:
- Não conseguimos gerar esta etapa. Você pode tentar novamente.

## 20. Experiência Premium

O frontend deve parecer uma ferramenta de alto padrão.

Elementos desejados:

- cards com profundidade sutil
- bordas discretas
- animações suaves
- ícones elegantes
- muito espaço em branco ou respiro visual
- tipografia bem hierarquizada
- botões com destaque dourado
- fundos escuros sofisticados
- interface limpa, sem poluição

## 21. Acessibilidade

Requisitos básicos:

- contraste adequado
- foco visível em inputs
- labels em formulários
- botões com texto claro
- mensagens de erro legíveis
- navegação por teclado sempre que possível

## 22. Integração com API

O frontend deverá consumir a API REST em:

/api/v1

Principais integrações:

- login
- usuário atual
- listar projetos
- criar projeto
- upload de arquivo
- iniciar processamento
- consultar status
- listar conteúdos
- revisar conteúdo
- exportar arquivos

## 23. Gerenciamento de Estado

Recomendação:

- TanStack Query para dados vindos da API
- React Hook Form para formulários
- Zod para validação
- estado local apenas para UI

## 24. Estrutura Recomendada de Pastas

Estrutura sugerida:

/apps/frontend
  /app
    /login
    /dashboard
    /projects
      /new
      /[id]
        /upload
        /processing
        /review
        /export
  /components
    /layout
    /ui
    /projects
    /upload
    /content
    /export
  /lib
    api.ts
    auth.ts
    utils.ts
  /hooks
  /types
  /styles

## 25. Fora do Escopo da Primeira Versão

Não implementar inicialmente:

- aplicativo mobile
- modo claro
- edição colaborativa em tempo real
- comentários
- marketplace
- área do aluno
- player de vídeo
- editor avançado de slides
- billing
- página pública de vendas

## 26. Critério de Sucesso do Frontend V1

A interface será considerada bem-sucedida quando o usuário conseguir:

1. fazer login
2. visualizar dashboard
3. criar projeto
4. enviar PDF
5. iniciar processamento
6. acompanhar status
7. revisar conteúdo gerado
8. exportar arquivos

Tudo isso com clareza, segurança visual e aparência premium.

## 27. Diretriz Final

O frontend do VVE Engine deve fazer o usuário sentir que está controlando uma fábrica de conhecimento sofisticada, e não apenas preenchendo formulários.

A interface deve ser simples, mas transmitir grandeza.

O usuário deve perceber que está diante de uma plataforma capaz de transformar conhecimento em produtos educacionais de alto nível.
