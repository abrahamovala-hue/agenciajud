# AgentHandoff — Contrato de Comunicação Estruturada

> Formaliza o "formato padrão de mensagem entre agentes" já usado no protocolo V1
> (seção "Como os Agentes Conversam Entre Si"), como um contrato de campos nomeados
> e estáveis. **Isto é um padrão conceitual de documentação/comunicação, não uma
> infraestrutura distribuída** — não há fila, broker ou API implementados nesta etapa.
> Na prática, cada `AgentHandoff` hoje é a saída estruturada de um Agent do Agno
> (markdown ou, futuramente, `output_schema` tipado).

---

## Estrutura

```
AgentHandoff
├── from                  — agente que está entregando
├── to                    — agente que recebe (ou "Judith" na etapa final)
├── workflow              — qual workflow (ver workflows/WORKFLOWS_V2_INDEX.md)
├── task_id               — identificador único da execução do workflow
├── objective             — objetivo desta etapa (herdado do CMO/etapa anterior)
├── context               — o que foi recebido do agente/etapa anterior
├── evidence              — quais documentos/dados foram consultados (Knowledge citada)
├── decision              — a decisão/output desta etapa
├── output                — o conteúdo real produzido (roteiro, hook, análise, resposta etc.)
├── confidence            — alto / médio / baixo (o quão certo o agente está do próprio output)
├── risks                 — riscos ou dúvidas identificados nesta etapa
├── references             — documentos específicos citados como evidência
├── recommended_next      — para qual agente isso deveria ir e por quê
└── timestamp             — quando esta etapa foi concluída
```

## Exemplo preenchido

```yaml
AgentHandoff:
  from: hook_finder
  to: script_writer
  workflow: CREATE_REEL
  task_id: reel-2026-08-22-ruby-launch
  objective: "Gerar 3-10 hooks para o reel de lançamento do Chocolate Ruby"
  context: "Brand Architect definiu ângulo educativo: técnica de fermentação"
  evidence:
    - AUDIENCE.md (linguagem: 'raro', 'técnica', 'fermentação')
    - CONTENT_PILLARS.md (pilar: Educação)
  decision: "Hook 1 recomendado: maior potencial de curiosidade + alinhado ao pilar"
  output: |
    Hook 1: "Esse chocolate é ROSA e é real..."
    Hook 2: "A técnica de fermentação que torna o chocolate rosa"
    Hook 3: "Só 5 unidades por semana... e vão acabar"
  confidence: alto
  risks: []
  references:
    - AUDIENCE.md
    - CONTENT_PILLARS.md
    - VOICE.md
  recommended_next: "script_writer, com Hook 1"
  timestamp: "2026-08-22T14:32:00-03:00"
```

## Regras de preenchimento

- `evidence`/`references` nunca ficam vazios quando a decisão envolve julgamento de marca/produto — se não há evidência a citar, isso é sinal de que o agente está decidindo "no feeling", o que viola a Regra 5 do protocolo.
- `confidence: baixo` **exige** que `risks` não esteja vazio — baixa confiança sem risco declarado é uma inconsistência que o Quality Control Agent deve pegar.
- `recommended_next` nunca é "Judith" a menos que o workflow realmente termine ali — pular direto para Judith sem passar por Brand Reviewer/Quality Control viola a Regra 1 do protocolo (nenhum pulo de etapa).

## Relação com Agno

Quando um agente V2 for implementado como `Agent` do Agno com `output_schema` (Pydantic), o `AgentHandoff` é o candidato natural a esse schema — mas isso é uma decisão de implementação por agente, não coberta nesta etapa (ver "Classificação Agno" no relatório de entrega). Hoje, o `AgentHandoff` é produzido como texto estruturado (igual ao formato V1), não como objeto tipado em runtime.

---

*Versão: 2.0*
*Formaliza: o formato de mensagem já usado informalmente no protocolo V1*
