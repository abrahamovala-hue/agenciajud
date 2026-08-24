# Status V2 — Documentação vs Implementação Agno

> Atualizado nesta etapa (2ª rodada de implementação). Ver relatório de entrega da
> conversa para o racional completo da classificação Agno (Agent vs Team vs Workflow
> vs Tool).

---

## Classificação Agno por agente

Critério (mesmo usado na análise de arquitetura anterior desta sessão, aplicado aos 21 papéis V2): papéis com **julgamento criativo/analítico genuíno** → `Agent`. Papéis de **checklist/gate puramente determinístico** → lógica de Workflow, não LLM próprio.

Nota sobre a evolução desta classificação: na 1ª rodada, o CMO tinha ficado fora por causa da confusão entre duas coisas diferentes — "CMO deveria orquestrar dinamicamente quem chamar" (não deveria — isso é ordem fixa de Workflow) vs. "CMO deveria ter julgamento próprio pra aprovar objetivo/resolver conflito citando evidência" (deveria — isso é comportamento de `Agent` legítimo). Corrigido nesta rodada.

| # | Agente | Classificação | Implementado? |
|---|---|---|---|
| 01 | CMO | `Agent` | ✅ `agents/judith_team/cmo.py` |
| 02 | Brand Architect | `Agent` | ✅ `agents/judith_team/brand_architect.py` |
| 03 | Marketing Director | `Agent` | ✅ `agents/judith_team/marketing_director.py` |
| 04 | Social Media Manager | `Agent` (roteamento; sem Instagram API real ainda) | ✅ `agents/judith_team/social_media_manager.py` |
| 05 | Market & Trend Intelligence | `Agent` | ✅ `agents/judith_team/market_trend_intelligence.py` |
| 06 | Hook Finder | `Agent` | ✅ `agents/judith_team/hook_finder.py` |
| 07 | Script Writer | `Agent` | ✅ `agents/judith_team/script_writer.py` |
| 08 | Caption Writer | `Agent` | ✅ `agents/judith_team/caption_writer.py` |
| 09 | Visual Creative | `Agent` | ✅ `agents/judith_team/visual_creative.py` |
| 10 | Video Editor | `Agent` (decisão editorial; sem Remotion Tool ainda) | ✅ `agents/judith_team/video_editor.py` |
| 11 | Offer & Funnel Strategist | `Agent` | ✅ `agents/judith_team/offer_funnel_strategist.py` |
| 12 | Sales & Conversion | `Agent` (sem Customer Memory real ainda) | ✅ `agents/judith_team/sales_conversion_agent.py` |
| 13 | CRM & Lifecycle | `Agent` (sem integração Kiwify/CRM ainda) | ✅ `agents/judith_team/crm_lifecycle_agent.py` |
| 14 | Community & DM | `Agent` (sem Instagram API ainda) | ✅ `agents/judith_team/community_dm_agent.py` |
| 15 | Customer Support | `Agent` (sem Kiwify API ainda) | ✅ `agents/judith_team/customer_support_agent.py` |
| 16 | Analytics & BI | `Agent` (sem Instagram Insights/Kiwify ainda) | ✅ `agents/judith_team/analytics_bi_agent.py` |
| 17 | Customer Insights | `Agent` (sem volume real de conversa ainda) | ✅ `agents/judith_team/customer_insights_agent.py` |
| 18 | Knowledge Manager | `Agent` (papel atípico — transversal, não conversacional de negócio) | ✅ `agents/judith_team/knowledge_manager.py` |
| 19 | AI Performance & Evals | `Agent` — raciocínio/proposta; sem pipeline automático de regressão (não é feature nativa do Agno, ver nota abaixo) | ✅ `agents/judith_team/ai_performance_evals_agent.py` |
| 20 | Brand Reviewer | `Agent` | ✅ `agents/judith_team/brand_reviewer.py` |
| 21 | Quality Control | Lógica de Workflow (checklist determinístico, zero julgamento criativo) | ❌ Documentação apenas (decisão de design, não pendência) |

**Resumo: 20 de 21 papéis implementados como `Agent` real do Agno.** O único que ficou de fora — Quality Control — ficou de fora por design (é uma checagem determinística de "documentação existe? sim/não", não um caso de uso de LLM), não por falta de tempo.

---

## Decisão explicitamente não inventada (AI Performance & Evals)

A skill Agno carregada nesta sessão (`agents.md`, `teams.md`, `workflows.md`, `learning.md`, `tools.md`, `mcp.md`, `models.md`) **não documenta um módulo nativo de comparação de versão/regressão de agente**. O agente `ai-performance-evals-agent` foi implementado como `Agent` capaz de fazer o *raciocínio* (detectar padrão, propor mudança, comparar candidata vs atual quando os dados forem fornecidos) — mas a *execução automatizada* de um pipeline de regressão não existe como infraestrutura, e as instructions do agente deixam isso explícito para quem conversar com ele.

## O que está genuinamente funcional em Agno hoje

- **21 agentes rodando no AgentOS** (`Jud` + os 20 do time V2), confirmado via:
  - `docker compose logs` — todos os 21 registrados sem erro, reload limpo.
  - `GET /agents` — lista os 21 ids.
  - Smoke tests reais via `POST /agents/<id>/runs` em 4 agentes distintos (hook-finder, cmo, customer-support-agent, knowledge-manager), todos com comportamento condizente com a ficha — incluindo os casos mais delicados (CMO recusando aprovar objetivo sem KPI, Customer Support escalando exceção de reembolso, Knowledge Manager recusando decidir conflito de preço sozinho).
- Guardrail de segurança (`ContentSafetyGuardrail` + `enforce_safe_output`) reutilizado pelos 20 agentes novos, sem duplicar lógica (Jud continua com a variante WhatsApp-específica).
- 20 testes automatizados passando (`pytest tests/`), incluindo verificação de que os 20 ids são únicos e cada agente carrega guardrail.

## Camada de orquestração (implementada — ver `ORCHESTRATION_V2.md`)

- **`AgentHandoff` é código**, não mais texto: modelo Pydantic tipado, preenchido via `output_schema` por chamada em `Agent.run()`.
- **Agent Registry** (`orchestration/registry.py`): `agent_id -> Agent`, 21 ids únicos.
- **Quality Control determinístico** (`orchestration/quality_control.py`): sem LLM, valida etapas/ordem/aprovações/evidência/pulos proibidos.
- **3 Workflows Agno reais**: `ANSWER_DM`, `CREATE_REEL`, `WEEKLY_BUSINESS_REVIEW`.
- **Execution Log** (`orchestration/execution_log.py`): rastro completo por execução, serializável.
- **Learning loop** (`orchestration/learning_loop.py`): estrutura de proposta, com teste que impede a adição de qualquer função de mutação.

## Knowledge — 20 de 20 agentes de negócio conectados

Todo agente de negócio consulta documentos reais do repositório sob demanda. `jud` (tira-dúvidas de Agno no WhatsApp) fica fora por não ser agente de negócio.

Mecanismo (verificado em `agno/agent/_tools.py`): o Agno registra a tool nativa `search_knowledge_base` quando `knowledge_retriever is not None and search_knowledge` — **não** é obrigatório ter `Knowledge`/pgvector. Isso deu grounding real ao time sem criar tabela, gerar embedding ou mudar o banco.

| Camada | Arquivo | Papel |
|---|---|---|
| Leitura, busca, provenance | `agents/knowledge_sources.py` | `DocumentSource`, `MissingSource`, busca lexical por seção, `FONTE_NAO_DISPONIVEL`. Uma implementação, não 20. |
| Whitelist por agente | `agents/knowledge_policies.py` | `KNOWLEDGE_POLICIES: agent_id -> AgentKnowledgePolicy` + fábrica de retriever/tools. |

Cada agente enxerga **só a sua whitelist** — de 6 a 42 documentos, nunca o catálogo inteiro (68 fontes). Um agente não consegue abrir documento de outro: `ler_documento` só conhece as chaves da própria política.

### Evidência verificada, não declarada

`AgentHandoff` carrega dois campos distintos:

| Campo | Origem | Serve para |
|---|---|---|
| `references` | texto do LLM | o que o agente **diz** ter consultado |
| `sources_opened` | tool calls do runtime | o que ele **de fato** abriu |

O Quality Control compara os dois. Citar fonte sem ter aberto documento vira `citations_without_source` e reprova o processo — sem precisar de LLM para julgar. Chamar `listar_fontes_disponiveis` não conta como consultar, de propósito. O marcador honesto "nenhuma fonte consultada" é filtrado antes da comparação, para não punir quem foi transparente.

O Brand Reviewer tem um terceiro estado além de aprovar/reprovar: `needs_evidence=true` quando não há base documental para decidir. Isso não é rejeição de conteúdo — é ausência de base, e o QC reporta como tal.

### Evidence Gate do ANSWER_DM (`orchestration/evidence_gate.py`)

Aplicado à **resposta final** que iria para a cliente, não a cada etapa interna. Classificar uma intenção não exige abrir `OFFERS`; informar um preço exige.

| Estado | Quando | O que a cliente recebe |
|---|---|---|
| `PASS` | sem claim factual, ou claim sustentado por fonte aberta | a resposta do agente (saneada) |
| `NEEDS_EVIDENCE` | há claim e falta consulta que o sustente | "Deixa eu confirmar essa informação certinho…" |
| `HUMAN_REQUIRED` | exceção de política, escalação, ou claim comercial só com fonte TEMPLATE | "Prefiro confirmar direto com a Judith…" |
| `REJECTED` | citou fonte que não abriu | "Deixa eu conferir na fonte oficial…" |

Claim comercial (preço, desconto, política, acesso, conteúdo, disponibilidade) exige `OFFERS` ou `PRODUCTS` aberto — `BUSINESS_RULES` regras 4 e 10. Reembolso fora do prazo é sempre `HUMAN_REQUIRED`, regra 11, mesmo com a fonte certa aberta.

**UX:** a cliente nunca vê nome de arquivo, status do gate nem vocabulário interno. `strip_internal_references()` remove citação de documento da prosa de forma determinística; a evidência continua inteira em `references`/`sources_opened` no log.

### Níveis de proveniência

| Nível | Significado |
|---|---|
| `vigente` | Documento de referência estável. |
| `snapshot` | Retrato de um momento — não é dado ao vivo. |
| `template` | O próprio arquivo se declara não validado pela Judith. |
| `ressalva` | Ressalva pontual dentro de um documento vigente (ex.: "A VERIFICAR" em `OFFERS.md`). |
| `FONTE_NAO_DISPONIVEL` | A fonte não existe; vem com o agente responsável e a integração que falta. |

**Achado importante:** 4 dos 5 documentos centrais de marca (`VOICE`, `AUDIENCE`, `CONTENT_PILLARS`, `VISUAL_IDENTITY`) e mais `INSTAGRAM_AUDIT` se declaram `STATUS: TEMPLATE — precisa validação da Judith`. Os agentes são obrigados a repassar essa ressalva ao citá-los.

## Refinamento individual de agentes (2 de 21)

| Agente | Status | O que mudou |
|---|---|---|
| CMO | ✅ refinado (v2.1) | Instructions em 13 seções, 6 casos reais, 3 defeitos corrigidos. |
| Brand Architect | ✅ refinado (v2.1) | Instructions em 14 seções, 6 casos reais, 4 defeitos corrigidos em 4 iterações. |
| Os outros 18 | ⏳ com Knowledge, sem refinamento de persona | Ganharam consulta real e a regra de evidência; as instructions ainda são as da rodada de implementação. |

## O que ainda é apenas documentação/não implementado

- Quality Control Agent como LLM (por design — é validação determinística, ver acima).
- RAG vetorial (`create_knowledge()` + pgvector): nenhum agente usa. A busca é **lexical** sobre markdown — suficiente e auditável neste corpus, mas não semântica.
- Memory (Session/Customer/Business/Agent Performance) — modelo conceitual documentado (`models/MEMORY_MODEL.md`), nada implementado.
- Learning/Evals — o ciclo tem estrutura de dados pronta, mas **nenhuma persistência em banco** do Execution Log e **nenhum pipeline de regressão automatizado**.
- Os outros 21 workflows documentados em `workflows/WORKFLOWS_V2_INDEX.md` (só 3 foram implementados nesta etapa, deliberadamente).

## Integrações futuras (nenhuma implementada — todas TOOL PLANNED)

Instagram API, Kiwify API, Apify (Market & Trend Intelligence), Remotion Tool (Video Editor), CRM externo.

---

*Versão: 2.1 — 20/21 agentes implementados como Agno Agent*
