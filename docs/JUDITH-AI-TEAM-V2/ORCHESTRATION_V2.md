# Orquestração V2 — o que virou código

> Esta etapa transformou o protocolo de colaboração (antes só documentação)
> em código executável. Fonte da verdade da implementação: `orchestration/`.

---

## Camadas implementadas

| Camada | Arquivo | O que é |
|---|---|---|
| **AgentHandoff** | `orchestration/handoff.py` | Contrato tipado (Pydantic) com os 14 campos do `AGENT_HANDOFF_CONTRACT.md`. Comunicação crítica não depende mais de texto livre. |
| **Agent Registry** | `orchestration/registry.py` | `agent_id -> Agent`, 21 ids únicos (Jud + 20 do time). Erro claro para id inexistente. |
| **Execution Log** | `orchestration/execution_log.py` | Rastro completo de cada execução (task_id, agentes chamados, handoffs, escalações, feedback humano, status). |
| **Quality Control** | `orchestration/quality_control.py` | Validação **100% determinística, sem LLM**. |
| **Step helper** | `orchestration/step_helpers.py` | Único ponto que chama um Agent e produz um `AgentHandoff`. |
| **Learning loop** | `orchestration/learning_loop.py` | Estrutura para propostas de melhoria — **sem nenhuma função de mutação**. |
| **Workflows** | `orchestration/workflows/` | Os 3 primeiros, como `agno.workflow.Workflow` reais. |

---

## Como o AgentHandoff é preenchido (decisão de arquitetura)

O `AgentHandoff` tem dois tipos de campo, preenchidos por fontes diferentes:

- **Envelope** (`from_agent`, `to_agent`, `workflow`, `task_id`, `objective`, `context`, `timestamp`): preenchido pelo **orquestrador** (código determinístico). Ele já sabe essa informação — não faz sentido pedir ao LLM.
- **Decisão** (`decision`, `output`, `confidence`, `risks`, `references`, `recommended_next`): preenchido pelo **próprio agente**, via `agent.run(message, output_schema=AgentStepDecision)`.

Achado técnico que viabilizou isso sem tocar nos 20 agentes: `Agent.run()` do Agno 2.6.4 aceita `output_schema` **por chamada**, não só na construção do `Agent`. Verificado no código-fonte instalado, não presumido.

Subclasses especializadas em `handoff.py`: `RoutingDecision` (+`route_to`), `ReviewDecision` (+`approved`), `WeeklyReportDecision` (+`kpis`/`insights`/`alerts`/`opportunities`/`recommended_plan`).

---

## Quality Control determinístico

`validate_workflow(log, spec) -> QualityControlResult`. Verifica, sem nenhuma chamada de LLM:

1. Agentes obrigatórios participaram (`required_agents_in_order` + `required_agents_unordered`).
2. Ordem respeitada — **só entre os agentes ordenados**. Agentes dentro de um `Parallel` vão em `required_agents_unordered`, porque a ordem de conclusão entre eles não é determinística (exigir ordem ali gerava falso positivo).
3. Brand Reviewer aprovou quando exigido — via o campo booleano `approved` de `ReviewDecision`, nunca parseando texto.
4. Referências obrigatórias presentes (handoff sem `references` **e** sem `risks` = decisão "no feeling", proibida pela Regra 5 do protocolo).
5. Nenhuma aresta proibida (`forbidden_direct_edges`) — ex.: `script-writer -> judith` pularia o Brand Reviewer.
6. Aprovação humana: detecta o caso crítico de um workflow marcado `completed` sem nunca ter passado por `pending_human_approval`.

---

## Os 3 Workflows

### ANSWER_DM (`orchestration/workflows/answer_dm.py`)
`Community & DM` classifica (`RoutingDecision`) → `Router` do Agno escolhe **um** destino: Customer Support, Sales & Conversion, CRM & Lifecycle, ou escalação humana. Chama 2 agentes por execução, nunca os 20.

### CREATE_REEL (`orchestration/workflows/create_reel.py`)
Gate do CMO (fora do pipeline — rejeita brief incompleto sem gastar o resto) → pipeline sequencial de 8 agentes → Brand Reviewer → **Quality Control determinístico** (`StepOutput(stop=True)` se incompleto) → **`HumanReview(requires_output_review=True)`**, que faz o workflow **pausar de verdade** (`RunStatus.paused`).

Nenhum conteúdo é publicado. Nenhuma chamada ao motor Remotion — o Video Editor produz a especificação de edição em texto; a integração Agno→Remotion não existe e não foi improvisada.

### WEEKLY_BUSINESS_REVIEW (`orchestration/workflows/weekly_business_review.py`)
`Parallel` com 5 especialistas → CMO sintetiza em `WeeklyReportDecision` estruturado. Todo dado vem de `orchestration/fixtures/`, marcado `[TEST DATA]` **dentro da própria mensagem enviada ao agente** — nenhum agente é induzido a tratar fixture como dado real.

---

## Learning loop — o que existe e o que é proibido

**Existe:** `attach_human_feedback()`, `collect_for_evaluation()`, e o modelo `ImprovementProposal` (com `requires_human_approval: Literal[True]` e `applied: Literal[False]` — imutáveis por tipo).

**Não existe, por design:** nenhuma função que edite prompt/instructions/código/tools/guardrails/knowledge, e nenhuma função de "promover versão". Há um teste automatizado (`test_learning_loop_module_exposes_no_mutation_function`) que falha se alguém adicionar uma.

---

*Versão: 2.2 — camada de orquestração implementada*
