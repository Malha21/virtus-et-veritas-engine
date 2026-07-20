# VVE-0000 — Fluxo de Uso do Engine
## Virtus et Veritas Engine

## Objetivo

Este documento existe porque o produto hoje tem **dois caminhos de geração de conteúdo
coexistindo no mesmo projeto**: o fluxo antigo (Fase 8, geração direta) e o fluxo novo
(Fase 19+, Motor de Fidelidade e Cobertura). A tela `/projects/[id]` oferece os dois
botões lado a lado, o que gera confusão sobre qual caminho seguir.

Este guia define a ordem numerada e oficial de uso do engine. Para novos projetos,
siga apenas os passos marcados como caminho atual. Os passos marcados como legado
existem no código por compatibilidade, mas não devem ser usados para novos projetos.

## Configuração inicial (uma vez, antes de criar projetos)

1. Login — `/login`
2. *(opcional)* Configurar sua própria chave de IA — `/account/api-keys`
3. *(opcional)* Criar perfil do instrutor — `/instructor-profile` (persona usada na narração/vídeo)
4. *(opcional)* Cadastrar avatares de vídeo na biblioteca de avatares

## Caminho atual — Motor de Fidelidade e Cobertura (Fase 19+)

5. Criar projeto — `/projects/new`
6. Enviar PDF/EPUB — `/projects/[id]/upload`
7. Processar/extrair o documento — `/projects/[id]/processing`
   (extração em páginas/blocos, Fase 19.2 — `document_extraction`)
8. Conferir páginas extraídas — `/fidelity-coverage/[id]/pages`
9. Gerar inventário integral de conteúdo — `/fidelity-coverage/[id]/inventory`
   (Fase 19.3 — `source_content_items`; nada é descartado, tudo vira item rastreável;
   itens duvidosos ficam marcados como `requires_review`)
10. Gerar plano de cobertura (mapeamento de itens de conhecimento → aulas) —
    `/fidelity-coverage/[id]/coverage-plan`
11. Gerar roteiros de aula a partir do plano (mesma tela) e aprovar/rejeitar cada aula
    (`lesson_generation`)
12. Gerar áudio narrado por aula
13. Configurar vídeo do projeto e gerar vídeo com avatar
    (`project_video_settings` → pipeline de vídeo)
14. Exportar curso completo em ZIP — `course_exports` (exportação nova, assíncrona)

Rastreabilidade garantida neste caminho:
```
documento → página inicial/final → bloco inicial/final → trecho original → item SRC → aula
```

## Caminho antigo (Fase 8) — legado, não usar em projetos novos

- ⚠️ `/projects/[id]/educational-content` — geração direta (analisa documento → gera
  estrutura de curso → gera todo o conteúdo de uma vez, sem inventário nem plano de
  cobertura). É o fluxo com o bug conhecido registrado no `CLAUDE.md` (trunca PDFs
  grandes, gerando só 1 módulo / 3 aulas quando deveria gerar 7+ módulos / 21+ aulas).
  A Fase 19 (Motor de Fidelidade e Cobertura) foi criada justamente para substituir
  este caminho.
- ⚠️ `/projects/[id]/review` — tela de revisão do fluxo antigo
- ⚠️ Rota `/exports` (`exports.py`) — exportação PDF antiga por aula/módulo, substituída
  por `course_exports`

## Referência cruzada com a documentação existente

- `docs/01-product-vision.md` a `docs/11-decisions.md` — documentos fundacionais de
  produto/arquitetura, ainda válidos como visão geral, mas não descrevem o Motor de
  Fidelidade e Cobertura (posterior a eles).
- `docs/fase-19-1-motor-fidelidade-cobertura.md` — fundação de banco/models/schemas do
  motor novo (passos 8–11 acima).
- `docs/fase-19-2-extracao-estruturada.md` — detalha o passo 7.
- `docs/fase-19-3-inventario-integral.md` — detalha o passo 9.
- `README.md` — atenção: seu conteúdo ainda descreve o estado da **Fase 8** (setup e
  fluxo antigo). Use este documento (`00-fluxo-de-uso.md`) como referência de fluxo
  atual até o README ser atualizado.
