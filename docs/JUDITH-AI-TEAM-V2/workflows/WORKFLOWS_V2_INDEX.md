# Workflows V2 — Índice

> Documenta todos os workflows pedidos para V2. Não reimplementa os workflows de conteúdo
> já detalhados em V1 (`docs/JUDITH-AI-TEAM/workflows/CREATE_REEL_FULL.md` etc.) — referencia-os
> e mostra como os novos tiers (Growth, Customer Experience, Intelligence) se conectam.
> Nenhuma integração externa (Instagram API, Kiwify) está implementada — onde um workflow
> depende de uma delas, isso está marcado como **TOOL PLANNED**.

---

## Routing por Intenção (como o sistema decide quem chamar)

O sistema **não** aciona todos os 21 agentes em toda tarefa. O Social Media Manager (ou, para pedidos diretos da Judith, o CMO) classifica a intenção e roteia só para quem é necessário.

| Pedido | Rota |
|---|---|
| "Não consigo baixar meu ebook" | Community/Router → Customer Support |
| "Qual ebook é melhor pra mim?" | Community → Sales & Conversion |
| "Quanto vendemos essa semana?" | Analytics & BI → (Kiwify/Data Tool, **TOOL PLANNED**) |
| "Crie campanha de 7 dias" | CMO → Brand Architect → Marketing Director → especialistas necessários → Brand Reviewer → Quality Control → Judith |
| "Edite esse Reel" | Video Editor → (Remotion Tool, **TOOL PLANNED**) → Brand Reviewer → Judith |

---

## Content & Social

### CREATE_REEL
Já documentado em detalhe no V1 (`workflows/CREATE_REEL_FULL.md`, 13 etapas — não reescrito). Em V2: mesma cadeia, com o Video Editor preparado (não implementado) para futuramente emitir `VideoEditSpec`.
**Participantes:** CMO → Brand Architect → Market & Trend Intelligence → Hook Finder → Script Writer → Brand Reviewer (pré-check) → Visual Creative → Video Editor → Caption Writer → Brand Reviewer → Quality Control → Judith.

### CREATE_CAMPAIGN
Já documentado em V1 (`workflows/CREATE_CAMPAIGN.md`). Em V2, o Offer & Funnel Strategist entra quando a campanha envolve produto/oferta.
**Participantes:** CMO → Brand Architect → Marketing Director → Social Media Manager → [paralelo: Market & Trend Intelligence, Hook Finder, Script Writer, Caption Writer] → Offer & Funnel Strategist (se aplicável) → Analytics & BI (KPI setup) → Brand Reviewer → Quality Control → Judith.

### CREATE_STORY / CREATE_CAROUSEL
Mesma cadeia reduzida de `CREATE_REEL`, sem a etapa de vídeo (Video Editor não participa).

### REPURPOSE_CONTENT
Já documentado em V1 (`workflows/REPURPOSE_CONTENT.md`). Sem mudança estrutural em V2.

---

## Customer Experience

### ANSWER_DM / ANSWER_COMMENT
**Participantes:** Social Media Manager (roteamento) → Community & DM Agent (resposta ou sub-roteamento) → [Sales & Conversion | Customer Support | Judith, conforme intenção].
**Regra:** Community & DM nunca inventa resposta fora de `sources/COMMENTS_FAQ.md`/`VOICE.md` — se não sabe, roteia ou escala.

### CUSTOMER_SUPPORT
**Participantes:** Social Media Manager → Community & DM Agent → Customer Support Agent → [resolve, ou escala para Judith se for exceção de política].

---

## Growth & Sales

### QUALIFY_LEAD
**Participantes:** Social Media Manager/Community & DM (identifica intenção de compra) → Sales & Conversion Agent (qualifica) → CRM & Lifecycle Agent (registra estágio).

### CONVERT_LEAD
**Participantes:** Sales & Conversion Agent (recomendação/objeção) → CRM & Lifecycle Agent (registro) → [conversão real acontece fora do sistema, no Kiwify — **TOOL PLANNED** para confirmação automática].

### FOLLOW_UP_LEAD
**Participantes:** CRM & Lifecycle Agent (decide follow-up) → Sales & Conversion Agent ou Community & DM (executa no canal).
**Regra:** nenhum follow-up sem base de consentimento (`BUSINESS_RULES.md` regra 12).

---

## Intelligence

### ANALYZE_CONTENT / ANALYZE_SALES / ANALYZE_FUNNEL
**Participantes:** Analytics & BI Agent (lidera) → relatório entregue ao CMO/Marketing Director/Offer & Funnel Strategist conforme o domínio.
**Limitação atual:** sem integração real com Instagram Insights/Kiwify (**TOOL PLANNED**) — hoje roda só sobre dado reportado manualmente; o agente declara "sem dados suficientes" quando aplicável.

### RESEARCH_TRENDS
**Participantes:** Market & Trend Intelligence Agent (lidera) → Brand Architect (valida compatibilidade com posicionamento).

### CUSTOMER_INSIGHTS
**Participantes:** Customer Insights Agent (lidera, agrega DMs/comentários/reviews) → Offer & Funnel Strategist / Brand Architect / Script Writer (consomem o padrão identificado).

---

## Governança / Revisão de Negócio

### WEEKLY_BUSINESS_REVIEW
**Participantes:** Analytics & BI Agent (relatório) → CMO (leitura estratégica) → Judith.
**Cadência:** semanal (ver `models/KNOWLEDGE_REFRESH_POLICY.md`).

### MONTHLY_STRATEGY
**Participantes:** CMO → Brand Architect → Marketing Director, com insumo de Analytics & BI e Customer Insights.
**Cadência:** mensal.

### OPTIMIZE_OFFER
**Participantes:** Offer & Funnel Strategist (lidera, com insumo de Customer Insights) → CMO valida → **Judith aprova qualquer mudança de preço** (sempre SENSITIVE).

### OPTIMIZE_LANDING_PAGE
**Participantes:** Offer & Funnel Strategist (lidera) → Brand Reviewer (valida tom/compliance) → Judith.

---

## AI Performance & Evals

### AGENT_EVALUATION
**Participantes:** AI Performance & Evals Agent (lidera todo o ciclo) → Judith (aprovação final de qualquer versão nova).
**Detalhe completo do ciclo:** ver `models/LEARNING_EVALS_MODEL.md`.

---

*Versão: 2.0*
*Não implementa nenhuma integração externa — todo ponto que dependeria de Instagram API, Kiwify API ou CRM está marcado TOOL PLANNED.*
