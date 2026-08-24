# Agent Competency & Knowledge Matrix

> **GERADO A PARTIR DO CODIGO** por `scripts/generate_foundation_docs.py`.
> Nao edite a mao: rode o script apos mudar `knowledge_policies.py` ou `capabilities.py`.

Fonte: `agents/knowledge_policies.py` (Knowledge) e `agents/capabilities.py` (Capabilities).

## `ai-performance-evals-agent`

**MISSION** — Avalia comportamento e propoe melhoria.

**GENERAL_DOMAIN_COMPETENCIES** — rubrica, gold set, regressao, taxonomia de falha
**CRAFT KNOWLEDGE (geral)** — EVALUATION
**JUDITH_SPECIFIC + SHARED CORE** — EVALS_README, LEARNING_EVALS_MODEL, AUTONOMY_MODEL, ORCHESTRATION_V2, HANDOFF_CONTRACT, HANDOFF_EXAMPLES, STATUS_V2, AGENT_ROSTER, BUSINESS_RULES
**FICHAS DE AGENTE** — 21 (papel transversal)
**FONTES TEMPLATE (nao validadas)** — —
**FONTES COM RESSALVA** — —
**DYNAMIC_DATA_REQUIRED** — GOLD_DATASET, METRICAS_INSTAGRAM, EXEMPLOS_APROVADOS, HISTORICO_POSTS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — InstagramInsightsReader

**CAPABILITIES_ALLOWED** — CREATE_REPORT, PROPOSE_AGENT_IMPROVEMENT, READ_ANALYTICS, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — PROMOTE_AGENT_VERSION
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — nao aplicavel
**WORKFLOWS** — —
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/ai-performance-evals-agent/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `analytics-bi-agent`

**MISSION** — Le e reporta performance. Nunca fabrica dataset.

**GENERAL_DOMAIN_COMPETENCIES** — KPI, funil, coorte, atribuicao, variancia, qualidade de dado
**CRAFT KNOWLEDGE (geral)** — ANALYTICS
**JUDITH_SPECIFIC + SHARED CORE** — PLAYBOOK_METRICS, INSTAGRAM_AUDIT, WEBSITE_AUDIT, PRODUCT_PAGES_AUDIT, PRODUCTS, OFFERS, CONTENT_PILLARS, STATUS_V2, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — INSTAGRAM_AUDIT, PRODUCT_PAGES_AUDIT, CONTENT_PILLARS
**FONTES COM RESSALVA** — PRODUCTS, OFFERS
**DYNAMIC_DATA_REQUIRED** — METRICAS_INSTAGRAM, VENDAS_KIWIFY, CRM_PIPELINE, DATA_DICTIONARY, HISTORICO_POSTS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — InstagramInsightsReader, KiwifySalesReader

**CAPABILITIES_ALLOWED** — CREATE_REPORT, READ_ANALYTICS, READ_BUSINESS_DATA, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — todo numero reportado
**WORKFLOWS** — WEEKLY_BUSINESS_REVIEW
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/analytics-bi-agent/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `WAITING_FOR_DATA` (funcao depende de integracao inexistente)

---

## `brand-architect`

**MISSION** — Define e corrige direcao de marca. Nao aprova peca final.

**GENERAL_DOMAIN_COMPETENCIES** — posicionamento, diferenciacao, hierarquia de mensagem, voz
**CRAFT KNOWLEDGE (geral)** — BRAND
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, VOICE, AUDIENCE, CONTENT_PILLARS, VISUAL_IDENTITY, PRODUCTS, COMPETITORS, BUSINESS_RULES, COLLABORATION_PROTOCOL_V2, AGENT_ROSTER
**FONTES TEMPLATE (nao validadas)** — VOICE, AUDIENCE, CONTENT_PILLARS, VISUAL_IDENTITY
**FONTES COM RESSALVA** — PRODUCTS
**DYNAMIC_DATA_REQUIRED** — EXEMPLOS_APROVADOS_REJEITADOS, DECISOES_ESTRATEGICAS, PERFORMANCE_POR_PILAR, RECEITA, TENDENCIAS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — —

**CAPABILITIES_ALLOWED** — PROPOSE_STRATEGY, READ_KNOWLEDGE, REVIEW_CONTENT
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — PUBLISH_CONTENT · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — direcao e correcao de marca
**WORKFLOWS** — CREATE_REEL
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/brand-architect/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (refinado individualmente e testado)

---

## `brand-reviewer`

**MISSION** — Revisa a peca final contra a direcao de marca.

**GENERAL_DOMAIN_COMPETENCIES** — revisao editorial, verificacao de claim, consistencia
**CRAFT KNOWLEDGE (geral)** — BRAND, COPY
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, VOICE, AUDIENCE, CONTENT_PILLARS, VISUAL_IDENTITY, PRODUCTS, OFFERS, PLAYBOOK_BRAND_REVIEW, BUSINESS_RULES, COLLABORATION_PROTOCOL_V1
**FONTES TEMPLATE (nao validadas)** — VOICE, AUDIENCE, CONTENT_PILLARS, VISUAL_IDENTITY
**FONTES COM RESSALVA** — PRODUCTS, OFFERS
**DYNAMIC_DATA_REQUIRED** — EXEMPLOS_APROVADOS, METRICAS_INSTAGRAM

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — —

**CAPABILITIES_ALLOWED** — READ_KNOWLEDGE, REVIEW_CONTENT
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — PUBLISH_CONTENT · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — aprovacao/reprovacao por regra de marca
**WORKFLOWS** — CREATE_REEL
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/brand-reviewer/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `caption-writer`

**MISSION** — Escreve legenda, CTA e hashtags.

**GENERAL_DOMAIN_COMPETENCIES** — estrutura de legenda, legibilidade, CTA, copy educativa
**CRAFT KNOWLEDGE (geral)** — COPY
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, VOICE, AUDIENCE, CONTENT_PILLARS, PRODUCTS, OFFERS, PLAYBOOK_CAPTION, COMMENTS_FAQ, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — VOICE, AUDIENCE, CONTENT_PILLARS
**FONTES COM RESSALVA** — PRODUCTS, OFFERS, COMMENTS_FAQ
**DYNAMIC_DATA_REQUIRED** — EXEMPLOS_APROVADOS, HISTORICO_POSTS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — —

**CAPABILITIES_ALLOWED** — CREATE_CONTENT, EDIT_CONTENT, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — preco/link citado em legenda
**WORKFLOWS** — CREATE_REEL
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/caption-writer/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `cmo`

**MISSION** — Aprova objetivo, prioriza, resolve conflito, escala para a Judith.

**GENERAL_DOMAIN_COMPETENCIES** — estrategia, KPI design, priorizacao, trade-off, leitura de evidencia
**CRAFT KNOWLEDGE (geral)** — STRATEGY
**JUDITH_SPECIFIC + SHARED CORE** — PRD, STATUS, STATUS_V2, BRAND, VOICE, AUDIENCE, PRODUCTS, OFFERS, CONTENT_PILLARS, BUSINESS_RULES, COLLABORATION_PROTOCOL_V2, AGENT_ROSTER, INSTAGRAM_AUDIT, WEBSITE_AUDIT, COMMENTS_FAQ, COMPETITORS
**FONTES TEMPLATE (nao validadas)** — INSTAGRAM_AUDIT
**FONTES COM RESSALVA** — —
**DYNAMIC_DATA_REQUIRED** — KPIS_ATUAIS, RECEITA, CAMPANHAS_ATIVAS, CUSTOMER_INSIGHTS_LIVE, TREND_INTELLIGENCE, CRM_PIPELINE, DECISOES_ANTERIORES

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — CrmCampaignSender, InstagramInsightsReader, InstagramPublishTool, PriceUpdateTool

**CAPABILITIES_ALLOWED** — CREATE_REPORT, PROPOSE_STRATEGY, READ_ANALYTICS, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — CHANGE_PRICE, PROPOSE_OFFER, PUBLISH_CONTENT, SEND_CAMPAIGN
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — aprovacao de objetivo e decisao de conflito
**WORKFLOWS** — CREATE_REEL, WEEKLY_BUSINESS_REVIEW
**ESCALATES_TO** — judith
**EVAL_REQUIREMENTS** — `evals/cmo/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (refinado individualmente e testado)

---

## `community-dm-agent`

**MISSION** — Classifica intencao e conversa socialmente.

**GENERAL_DOMAIN_COMPETENCIES** — conversa, classificacao de intencao, de-escalation, roteamento
**CRAFT KNOWLEDGE (geral)** — CONVERSATION
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, VOICE, AUDIENCE, PRODUCTS, OFFERS, COMMENTS_FAQ, AGENT_ROSTER, COLLABORATION_PROTOCOL_V2, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — VOICE, AUDIENCE
**FONTES COM RESSALVA** — PRODUCTS, OFFERS, COMMENTS_FAQ
**DYNAMIC_DATA_REQUIRED** — HISTORICO_DM, EXEMPLOS_APROVADOS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — CrmContactReader

**CAPABILITIES_ALLOWED** — ANSWER_CUSTOMER, READ_CUSTOMER_DATA, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — qualquer claim de produto/oferta/politica
**WORKFLOWS** — ANSWER_DM
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/community-dm-agent/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `crm-lifecycle-agent`

**MISSION** — Redige follow-up e cuida do ciclo de vida.

**GENERAL_DOMAIN_COMPETENCIES** — lifecycle, segmentacao, reativacao, consentimento
**CRAFT KNOWLEDGE (geral)** — CONVERSATION
**JUDITH_SPECIFIC + SHARED CORE** — PRODUCTS, OFFERS, AUDIENCE, VOICE, BUSINESS_RULES, COLLABORATION_PROTOCOL_V2
**FONTES TEMPLATE (nao validadas)** — AUDIENCE, VOICE
**FONTES COM RESSALVA** — PRODUCTS, OFFERS
**DYNAMIC_DATA_REQUIRED** — CRM_PIPELINE, VENDAS_KIWIFY, HISTORICO_DM

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — CrmCampaignSender, CrmContactReader

**CAPABILITIES_ALLOWED** — CREATE_FOLLOW_UP, READ_CUSTOMER_DATA, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — SEND_CAMPAIGN
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — nao aplicavel
**WORKFLOWS** — ANSWER_DM, WEEKLY_BUSINESS_REVIEW
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/crm-lifecycle-agent/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `WAITING_FOR_DATA` (funcao depende de integracao inexistente)

---

## `customer-insights-agent`

**MISSION** — Extrai dor, motivacao e objecao do que o publico diz.

**GENERAL_DOMAIN_COMPETENCIES** — pesquisa qualitativa, analise tematica, voice-of-customer
**CRAFT KNOWLEDGE (geral)** — RESEARCH
**JUDITH_SPECIFIC + SHARED CORE** — AUDIENCE, COMMENTS_FAQ, PRODUCTS, COMPETITORS, WEBSITE_AUDIT, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — AUDIENCE
**FONTES COM RESSALVA** — COMMENTS_FAQ, PRODUCTS
**DYNAMIC_DATA_REQUIRED** — HISTORICO_DM, VENDAS_KIWIFY, CRM_PIPELINE

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — CrmContactReader

**CAPABILITIES_ALLOWED** — CREATE_REPORT, READ_CUSTOMER_DATA, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — frequencia de tema
**WORKFLOWS** — WEEKLY_BUSINESS_REVIEW
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/customer-insights-agent/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `WAITING_FOR_DATA` (funcao depende de integracao inexistente)

---

## `customer-support-agent`

**MISSION** — Resolve problema pos-venda dentro da politica.

**GENERAL_DOMAIN_COMPETENCIES** — troubleshooting, classificacao, escalada, expectativa
**CRAFT KNOWLEDGE (geral)** — CONVERSATION
**JUDITH_SPECIFIC + SHARED CORE** — PRODUCTS, OFFERS, COMMENTS_FAQ, WEBSITE_AUDIT, VOICE, BUSINESS_RULES, COLLABORATION_PROTOCOL_V2
**FONTES TEMPLATE (nao validadas)** — VOICE
**FONTES COM RESSALVA** — PRODUCTS, OFFERS, COMMENTS_FAQ
**DYNAMIC_DATA_REQUIRED** — CASOS_SUPORTE, VENDAS_KIWIFY, CRM_PIPELINE

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — CrmContactReader, KiwifyRefundTool

**CAPABILITIES_ALLOWED** — ANSWER_CUSTOMER, PREPARE_SUPPORT_RESPONSE, READ_CUSTOMER_DATA, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — GRANT_REFUND
**CAPABILITIES_DENIED (declaradas)** — CHANGE_POLICY · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — politica, prazo, garantia, acesso
**WORKFLOWS** — ANSWER_DM
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/customer-support-agent/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `WAITING_FOR_KNOWLEDGE` (conteudo real dos ebooks ausente)

---

## `hook-finder`

**MISSION** — Encontra o angulo que segura atencao nos primeiros segundos.

**GENERAL_DOMAIN_COMPETENCIES** — atencao, curiosidade, lacuna de informacao, taxonomia de hook
**CRAFT KNOWLEDGE (geral)** — SHORTFORM
**JUDITH_SPECIFIC + SHARED CORE** — VOICE, AUDIENCE, CONTENT_PILLARS, PLAYBOOK_HOOK, COMMENTS_FAQ, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — VOICE, AUDIENCE, CONTENT_PILLARS
**FONTES COM RESSALVA** — COMMENTS_FAQ
**DYNAMIC_DATA_REQUIRED** — METRICAS_INSTAGRAM, EXEMPLOS_APROVADOS, HISTORICO_POSTS, TENDENCIAS_ATUAIS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — —

**CAPABILITIES_ALLOWED** — CREATE_CONTENT, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — nao aplicavel
**WORKFLOWS** — CREATE_REEL
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/hook-finder/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `knowledge-manager`

**MISSION** — Governa fontes. Nao decide verdade de negocio.

**GENERAL_DOMAIN_COMPETENCIES** — proveniencia, autoridade, frescor, conflito, versionamento
**CRAFT KNOWLEDGE (geral)** — KNOWLEDGE_GOVERNANCE
**JUDITH_SPECIFIC + SHARED CORE** — KNOWLEDGE_REFRESH_POLICY, MEMORY_MODEL, LEARNING_EVALS_MODEL, AUTONOMY_MODEL, BUSINESS_RULES, COLLABORATION_PROTOCOL_V1, COLLABORATION_PROTOCOL_V2, HANDOFF_CONTRACT, AGENT_ROSTER, STATUS, STATUS_V2, PRD, ORCHESTRATION_V2, WORKFLOWS_V2_INDEX, BRAND, VOICE, AUDIENCE, CONTENT_PILLARS, VISUAL_IDENTITY, PRODUCTS, OFFERS
**FICHAS DE AGENTE** — 21 (papel transversal)
**FONTES TEMPLATE (nao validadas)** — VOICE, AUDIENCE, CONTENT_PILLARS, VISUAL_IDENTITY
**FONTES COM RESSALVA** — MEMORY_MODEL, PRODUCTS, OFFERS
**DYNAMIC_DATA_REQUIRED** — DECISOES_ESTRATEGICAS, EXEMPLOS_APROVADOS, METRICAS_INSTAGRAM, VENDAS_KIWIFY

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — —

**CAPABILITIES_ALLOWED** — CREATE_REPORT, MANAGE_KNOWLEDGE_SOURCES, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — CHANGE_POLICY · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — estado de qualquer fonte
**WORKFLOWS** — —
**ESCALATES_TO** — judith
**EVAL_REQUIREMENTS** — `evals/knowledge-manager/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `market-trend-intelligence`

**MISSION** — Contextualiza com tendencia e concorrencia.

**GENERAL_DOMAIN_COMPETENCIES** — ciclo de tendencia, sinal vs ruido, analise competitiva
**CRAFT KNOWLEDGE (geral)** — RESEARCH
**JUDITH_SPECIFIC + SHARED CORE** — AUDIENCE, CONTENT_PILLARS, PRODUCTS, COMPETITORS, INSTAGRAM_AUDIT, WEBSITE_AUDIT, PLAYBOOK_TREND, PLAYBOOK_VIRAL, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — AUDIENCE, CONTENT_PILLARS, INSTAGRAM_AUDIT
**FONTES COM RESSALVA** — PRODUCTS
**DYNAMIC_DATA_REQUIRED** — TENDENCIAS_ATUAIS, METRICAS_INSTAGRAM, HISTORICO_POSTS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — —

**CAPABILITIES_ALLOWED** — CREATE_REPORT, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — toda tendencia afirmada
**WORKFLOWS** — CREATE_REEL, WEEKLY_BUSINESS_REVIEW
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/market-trend-intelligence/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `marketing-director`

**MISSION** — Planeja campanha, mix de conteudo e alocacao.

**GENERAL_DOMAIN_COMPETENCIES** — campanha, funil, lancamento, distribuicao, medicao
**CRAFT KNOWLEDGE (geral)** — STRATEGY, OFFER_FUNNEL, ANALYTICS
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, AUDIENCE, PRODUCTS, OFFERS, CONTENT_PILLARS, PLAYBOOK_MARKETING_DIRECTOR, WORKFLOW_CREATE_CAMPAIGN, WORKFLOWS_V1, BUSINESS_RULES, AGENT_ROSTER
**FONTES TEMPLATE (nao validadas)** — AUDIENCE, CONTENT_PILLARS
**FONTES COM RESSALVA** — PRODUCTS, OFFERS
**DYNAMIC_DATA_REQUIRED** — CALENDARIO_EDITORIAL, HISTORICO_POSTS, METRICAS_INSTAGRAM, VENDAS_KIWIFY, DECISOES_ESTRATEGICAS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — CrmCampaignSender, InstagramInsightsReader, InstagramPublishTool

**CAPABILITIES_ALLOWED** — CREATE_REPORT, PROPOSE_STRATEGY, READ_ANALYTICS, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — PROPOSE_OFFER, PUBLISH_CONTENT, SEND_CAMPAIGN
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — nao aplicavel
**WORKFLOWS** — —
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/marketing-director/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `offer-funnel-strategist`

**MISSION** — Desenha oferta e funil. Propoe, nao aplica preco.

**GENERAL_DOMAIN_COMPETENCIES** — design de oferta, precificacao, etapas de funil, friccao
**CRAFT KNOWLEDGE (geral)** — OFFER_FUNNEL, ANALYTICS
**JUDITH_SPECIFIC + SHARED CORE** — PRODUCTS, OFFERS, AUDIENCE, BRAND, WEBSITE_AUDIT, PRODUCT_PAGES_AUDIT, COMMENTS_FAQ, PLAYBOOK_PRODUCT_MARKETING, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — AUDIENCE, PRODUCT_PAGES_AUDIT
**FONTES COM RESSALVA** — PRODUCTS, OFFERS, COMMENTS_FAQ
**DYNAMIC_DATA_REQUIRED** — VENDAS_KIWIFY, METRICAS_INSTAGRAM, CRM_PIPELINE, HISTORICO_DM

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — InstagramInsightsReader, PriceUpdateTool

**CAPABILITIES_ALLOWED** — PROPOSE_OFFER, READ_ANALYTICS, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — CHANGE_PRICE, GRANT_DISCOUNT
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — preco e condicao de oferta
**WORKFLOWS** — —
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/offer-funnel-strategist/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `sales-conversion-agent`

**MISSION** — Responde intencao de compra com dado verificado.

**GENERAL_DOMAIN_COMPETENCIES** — descoberta, qualificacao, objecao, persuasao etica
**CRAFT KNOWLEDGE (geral)** — CONVERSATION
**JUDITH_SPECIFIC + SHARED CORE** — PRODUCTS, OFFERS, AUDIENCE, VOICE, COMMENTS_FAQ, WEBSITE_AUDIT, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — AUDIENCE, VOICE
**FONTES COM RESSALVA** — PRODUCTS, OFFERS, COMMENTS_FAQ
**DYNAMIC_DATA_REQUIRED** — VENDAS_KIWIFY, CRM_PIPELINE, HISTORICO_DM

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — CrmContactReader

**CAPABILITIES_ALLOWED** — ANSWER_CUSTOMER, PREPARE_SALES_RESPONSE, READ_CUSTOMER_DATA, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — GRANT_DISCOUNT
**CAPABILITIES_DENIED (declaradas)** — CHANGE_PRICE · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — preco, oferta, desconto, conteudo de produto
**WORKFLOWS** — ANSWER_DM, WEEKLY_BUSINESS_REVIEW
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/sales-conversion-agent/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `script-writer`

**MISSION** — Escreve o roteiro do video curto.

**GENERAL_DOMAIN_COMPETENCIES** — storytelling, estrutura, ritmo, open loop, clareza didatica
**CRAFT KNOWLEDGE (geral)** — SHORTFORM, COPY
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, VOICE, AUDIENCE, CONTENT_PILLARS, PRODUCTS, OFFERS, PLAYBOOK_SCRIPT, WORKFLOW_CREATE_REEL, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — VOICE, AUDIENCE, CONTENT_PILLARS
**FONTES COM RESSALVA** — PRODUCTS, OFFERS
**DYNAMIC_DATA_REQUIRED** — EXEMPLOS_APROVADOS, HISTORICO_POSTS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — —

**CAPABILITIES_ALLOWED** — CREATE_CONTENT, EDIT_CONTENT, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — afirmacao sobre produto no roteiro
**WORKFLOWS** — CREATE_REEL
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/script-writer/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `social-media-manager`

**MISSION** — Calendario editorial, formato e cadencia.

**GENERAL_DOMAIN_COMPETENCIES** — planejamento editorial, formatos, cadencia, repurposing
**CRAFT KNOWLEDGE (geral)** — COPY, SHORTFORM, ANALYTICS
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, VOICE, AUDIENCE, CONTENT_PILLARS, PLAYBOOK_SOCIAL, INSTAGRAM_AUDIT, WORKFLOWS_V1, BUSINESS_RULES, AGENT_ROSTER
**FONTES TEMPLATE (nao validadas)** — VOICE, AUDIENCE, CONTENT_PILLARS, INSTAGRAM_AUDIT
**FONTES COM RESSALVA** — —
**DYNAMIC_DATA_REQUIRED** — CALENDARIO_EDITORIAL, HISTORICO_POSTS, METRICAS_INSTAGRAM, TENDENCIAS_ATUAIS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — InstagramInsightsReader, InstagramPublishTool

**CAPABILITIES_ALLOWED** — CREATE_CONTENT, READ_ANALYTICS, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — PUBLISH_CONTENT
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — nao aplicavel
**WORKFLOWS** — —
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/social-media-manager/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (opera sem o dado dinamico; a lacuna e declarada)

---

## `video-editor`

**MISSION** — Especifica a edicao (cortes, ritmo, legendas, trilha).

**GENERAL_DOMAIN_COMPETENCIES** — timeline, ritmo, B-roll, legenda, continuidade
**CRAFT KNOWLEDGE (geral)** — VISUAL, SHORTFORM
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, VOICE, VISUAL_IDENTITY, VIDEO_ENGINE_PLAN, VIDEO_EDIT_SPEC, PLAYBOOK_VIDEO, CONTENT_PILLARS, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — VOICE, VISUAL_IDENTITY, CONTENT_PILLARS
**FONTES COM RESSALVA** — VIDEO_ENGINE_PLAN
**DYNAMIC_DATA_REQUIRED** — EXEMPLOS_APROVADOS, METRICAS_INSTAGRAM

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — RemotionRenderTool

**CAPABILITIES_ALLOWED** — CREATE_VIDEO_SPEC, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — RENDER_VIDEO
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — nao aplicavel
**WORKFLOWS** — CREATE_REEL
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/video-editor/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `WAITING_FOR_TOOL` (Remotion Tool nao conectada)

---

## `visual-creative`

**MISSION** — Cria o briefing visual da peca.

**GENERAL_DOMAIN_COMPETENCIES** — hierarquia, composicao, legibilidade, consistencia visual
**CRAFT KNOWLEDGE (geral)** — VISUAL
**JUDITH_SPECIFIC + SHARED CORE** — BRAND, VISUAL_IDENTITY, CONTENT_PILLARS, PLAYBOOK_VISUAL, PRODUCTS, BUSINESS_RULES
**FONTES TEMPLATE (nao validadas)** — VISUAL_IDENTITY, CONTENT_PILLARS
**FONTES COM RESSALVA** — PRODUCTS
**DYNAMIC_DATA_REQUIRED** — EXEMPLOS_APROVADOS

**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`
**TOOLS_FUTURE** — —

**CAPABILITIES_ALLOWED** — CREATE_CONTENT, READ_KNOWLEDGE
**CAPABILITIES_HUMAN_REQUIRED** — —
**CAPABILITIES_DENIED (declaradas)** — — · *todo o resto tambem e DENIED por omissao*

**EVIDENCE_REQUIRED_FOR** — nao aplicavel
**WORKFLOWS** — CREATE_REEL
**ESCALATES_TO** — cmo
**EVAL_REQUIREMENTS** — `evals/visual-creative/cases.yaml` (estrutura existe, gold set vazio)
**READINESS** — `READY_FOR_EVALS` (fundacao completa)

---
