# VVE-0006 — AI Orchestrator Document
## Virtus et Veritas Engine

## 1. Objetivo

Este documento define a arquitetura conceitual e funcional do AI Orchestrator do Virtus et Veritas Engine.

O AI Orchestrator será o componente responsável por transformar conhecimento bruto em produtos educacionais estruturados.

Ele não deve ser apenas uma chamada simples para uma IA.

Ele deverá coordenar etapas, selecionar prompts, validar respostas, padronizar saídas, registrar uso e preservar qualidade didática.

## 2. Princípio Central

O AI Orchestrator existe para responder à pergunta:

Como transformar este conhecimento em uma experiência educacional clara, útil, envolvente e aplicável?

A IA não deve apenas resumir conteúdo.

Ela deve:

- compreender;
- organizar;
- didatizar;
- adaptar ao público;
- transformar em roteiro;
- criar materiais;
- gerar experiência de aprendizagem.

## 3. Responsabilidades do AI Orchestrator

O AI Orchestrator será responsável por:

1. Receber conteúdo extraído de documentos.
2. Limpar e preparar o conteúdo.
3. Identificar tema central.
4. Identificar público adequado.
5. Sugerir formato educacional.
6. Definir estrutura do curso.
7. Criar módulos.
8. Criar aulas.
9. Criar objetivos de aprendizagem.
10. Criar roteiros.
11. Criar quizzes.
12. Criar materiais complementares.
13. Criar textos de marketing.
14. Validar consistência das respostas.
15. Registrar chamadas aos provedores de IA.
16. Controlar versões de prompts.
17. Permitir reprocessamento.
18. Padronizar saída em JSON estruturado.

## 4. O AI Orchestrator Não Deve Fazer

O AI Orchestrator não deve:

- salvar arquivos físicos diretamente;
- autenticar usuários;
- lidar com interface;
- conhecer detalhes do frontend;
- depender diretamente de um único provedor de IA;
- gerar vídeos diretamente;
- publicar em plataformas externas;
- executar pagamentos;
- misturar responsabilidades de banco, storage e mídia.

Essas tarefas pertencem a outros módulos.

## 5. Fluxo Geral da Primeira Versão

Fluxo V1:

1. Receber texto extraído do PDF.
2. Normalizar texto.
3. Dividir texto em blocos se necessário.
4. Criar análise inicial do documento.
5. Gerar estrutura do curso.
6. Gerar roteiros das aulas.
7. Gerar quizzes por módulo.
8. Gerar materiais complementares.
9. Gerar textos simples de divulgação.
10. Retornar tudo em JSON estruturado.
11. Registrar uso de IA.
12. Salvar resultados via backend/worker.

## 6. Etapas do Pipeline

## 6.1 Document Analysis

Objetivo:

Entender o conteúdo de entrada.

Entrada:

- texto extraído do PDF
- nome do projeto
- público-alvo informado
- tom de voz
- duração desejada
- descrição opcional

Saída esperada:

- tema central
- subtemas
- complexidade
- público recomendado
- tipo de produto recomendado
- lacunas percebidas
- riscos didáticos
- oportunidades de melhoria
- sugestão de estrutura

Formato de saída:

```json
{
  "document_analysis": {
    "main_theme": "",
    "subthemes": [],
    "complexity_level": "beginner | intermediate | advanced",
    "recommended_audience": "",
    "recommended_product_type": "course",
    "didactic_risks": [],
    "opportunities": [],
    "suggested_approach": ""
  }
}
```

## 6.2 Course Structure Generation

Objetivo:

Transformar a análise em estrutura de curso.

Saída esperada:

```json
{
  "course": {
    "title": "",
    "promise": "",
    "description": "",
    "target_audience": "",
    "learning_objectives": [],
    "modules": [
      {
        "module_number": 1,
        "title": "",
        "description": "",
        "learning_goal": "",
        "lessons": [
          {
            "lesson_number": 1,
            "title": "",
            "summary": "",
            "estimated_duration_minutes": 10,
            "learning_objective": ""
          }
        ]
      }
    ]
  }
}
```

## 6.3 Script Generation

Objetivo:

Criar roteiros didáticos e envolventes para cada aula.

Cada roteiro deve conter:

- abertura forte
- conexão com o aluno
- explicação principal
- exemplos
- analogias
- transições
- chamada para reflexão
- resumo
- encerramento

Formato:

```json
{
  "lesson_script": {
    "module_number": 1,
    "lesson_number": 1,
    "title": "",
    "estimated_duration_minutes": 10,
    "opening": "",
    "main_script": "",
    "examples": [],
    "reflection_prompt": "",
    "closing": ""
  }
}
```

## 6.4 Quiz Generation

Objetivo:

Criar perguntas para fixação.

Formato:

```json
{
  "quiz": {
    "module_number": 1,
    "questions": [
      {
        "question": "",
        "type": "multiple_choice",
        "options": [],
        "correct_answer": "",
        "explanation": ""
      }
    ]
  }
}
```

## 6.5 Complementary Materials Generation

Objetivo:

Criar materiais de apoio para o aluno.

Materiais possíveis:

- resumo do módulo
- checklist
- exercícios práticos
- perguntas de reflexão
- sugestões de leitura
- plano de ação

Formato:

```json
{
  "complementary_material": {
    "module_number": 1,
    "summary": "",
    "checklist": [],
    "practical_exercises": [],
    "reflection_questions": [],
    "suggested_readings": [],
    "action_plan": []
  }
}
```

## 6.6 Marketing Copy Generation

Objetivo:

Criar textos simples para divulgação do curso.

Formato:

```json
{
  "marketing": {
    "short_description": "",
    "long_description": "",
    "instagram_post": "",
    "whatsapp_message": "",
    "sales_points": []
  }
}
```

## 7. Prompt Strategy

Os prompts deverão ser versionados.

Exemplo de versões:

- prompt_document_analysis_v1
- prompt_course_structure_v1
- prompt_lesson_script_v1
- prompt_quiz_v1
- prompt_materials_v1
- prompt_marketing_v1

Cada prompt deverá ter:

- nome
- versão
- objetivo
- entrada esperada
- saída esperada
- critérios de qualidade

## 8. Critérios de Qualidade

Toda saída da IA deverá buscar:

1. Clareza.
2. Profundidade adequada.
3. Linguagem compatível com o público-alvo.
4. Coerência entre módulos e aulas.
5. Progressão didática.
6. Aplicabilidade prática.
7. Tom inspirador quando adequado.
8. Ausência de excesso de jargão.
9. Respeito ao conteúdo original.
10. Estrutura exportável.

## 9. Tom de Voz Padrão da Virtus et Veritas Academy

Quando o projeto for da Virtus et Veritas Academy, o tom padrão deverá ser:

- inspirador;
- elegante;
- profundo;
- claro;
- humano;
- filosófico;
- prático;
- transformador;
- sem arrogância;
- sem linguagem rasa;
- sem promessas milagrosas.

A linguagem deve transmitir evolução, virtude, verdade, disciplina, consciência, liderança e transformação humana.

## 10. Regras de Segurança e Qualidade

O AI Orchestrator deverá:

- evitar inventar fontes não presentes;
- sinalizar lacunas do conteúdo;
- evitar promessas absolutas;
- evitar linguagem sensacionalista;
- preservar contexto;
- respeitar o material enviado;
- gerar conteúdo revisável;
- permitir edição humana;
- registrar erros;
- não expor chaves ou informações sensíveis.

## 11. AI Provider Interface

O sistema deverá ter uma interface abstrata de provedor de IA.

Conceito:

AIProvider.generate_text(request)

Entrada conceitual:

```json
{
  "provider": "openai",
  "model": "model-name",
  "prompt_name": "prompt_course_structure_v1",
  "system_prompt": "",
  "user_prompt": "",
  "input_data": {},
  "temperature": 0.4,
  "response_format": "json"
}
```

Saída conceitual:

```json
{
  "success": true,
  "content": {},
  "raw_response": {},
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "estimated_cost": 0
  }
}
```

O backend não deve depender diretamente da OpenAI em todos os pontos.

Deve depender de uma interface interna que possa futuramente chamar OpenAI, Claude, Gemini ou modelos locais.

## 12. Modelos Recomendados

Na primeira versão, usar OpenAI para:

- análise de documento
- estrutura de curso
- roteiros
- quizzes
- materiais complementares
- marketing copy

Futuramente, avaliar:

- Claude para escrita longa
- Gemini para grandes contextos
- modelos locais para tarefas simples
- ElevenLabs para voz
- HeyGen/Tavus/Synthesia para avatar
- Runway/Pika para mídia complementar

## 13. Estratégia para PDFs Grandes

Se o PDF for pequeno:

- enviar texto completo para análise.

Se o PDF for grande:

1. dividir em chunks;
2. resumir cada chunk;
3. gerar mapa geral do conteúdo;
4. criar estrutura a partir do mapa;
5. usar chunks relevantes para criar roteiros.

O sistema deverá evitar enviar documentos muito grandes sem preparação.

## 14. Validação de JSON

Toda resposta estruturada deverá ser validada.

Se a IA retornar JSON inválido:

1. tentar corrigir automaticamente;
2. solicitar nova resposta ao provedor;
3. registrar erro;
4. marcar job como failed se exceder tentativas.

## 15. Reprocessamento

O sistema deverá permitir reprocessar:

- apenas análise;
- apenas estrutura;
- apenas roteiros;
- apenas quizzes;
- apenas materiais;
- tudo.

Isso permitirá melhorar o conteúdo sem reenviar o PDF.

## 16. Registro de Uso

Cada chamada de IA deverá registrar:

- projeto
- job
- provedor
- modelo
- tipo de requisição
- versão do prompt
- tokens de entrada
- tokens de saída
- custo estimado
- status
- erro, se houver

Esses dados serão úteis para controle de custo e futura comercialização SaaS.

## 17. Saída Final Esperada da V1

Ao final do processamento, o AI Orchestrator deverá produzir um pacote estruturado contendo:

- análise do documento
- estrutura do curso
- roteiros das aulas
- quizzes
- materiais complementares
- textos simples de divulgação

Esse pacote deverá ser salvo no banco e preparado para exportação.

## 18. Futuro: Media Orchestration

Na segunda versão, o AI Orchestrator deverá se comunicar com o Media Engine para:

- criar outline dos slides;
- gerar narração;
- gerar avatar;
- sincronizar roteiro, voz, slides e vídeo.

Mas a geração audiovisual não pertence à V1.

## 19. Futuro: Knowledge Base

Na terceira versão, o AI Orchestrator deverá consultar a base permanente de conhecimento da Virtus et Veritas Academy.

Isso permitirá criar novos produtos usando:

- PDFs antigos
- cursos já criados
- roteiros aprovados
- materiais próprios
- bibliografia autorizada
- biblioteca filosófica e de liderança

## 20. Diretriz Final

O AI Orchestrator é o coração intelectual do VVE Engine.

Ele deve ser projetado para produzir conteúdo educacional excelente, não apenas respostas rápidas.

Na primeira versão, deve ser simples o suficiente para funcionar.

No longo prazo, deve evoluir para um verdadeiro sistema de produção intelectual com memória, qualidade, curadoria e capacidade de escala.
