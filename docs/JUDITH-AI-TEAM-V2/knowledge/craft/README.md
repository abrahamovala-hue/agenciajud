# Craft Knowledge — conhecimento GERAL de ofício

> **Natureza:** `GENERAL / REUSABLE`. Nada aqui é fato sobre a Bem me Qué.

## O que é isto

Os agentes precisam de duas coisas diferentes:

| Camada | Responde | Onde vive |
|---|---|---|
| **Craft knowledge** (esta pasta) | como o ofício funciona | `knowledge/craft/` |
| **Judith-specific knowledge** | o que o negócio da Judith afirma | `brand/`, `sources/` |

Antes desta rodada só existia a segunda. Os playbooks V1 (`docs/JUDITH-AI-TEAM/agents/*.md`) descrevem **papel e formato de saída** — úteis, mas não ensinam o ofício.

## O que estes documentos são — e o que não são

**São:** princípios de trabalho e checklists que este projeto adota, escritos para serem consultáveis por agente.

**Não são:**
- "best practices oficiais" de nenhuma autoridade externa — não citamos fonte que não temos;
- cópia de material protegido;
- enciclopédia. Cada documento é curto de propósito: o que não é acionável não entra;
- fato sobre a Judith. Se um agente precisa de preço, público ou produto, isso vem de `brand/`, nunca daqui.

## Como um agente deve tratar isto

Craft knowledge orienta **julgamento profissional**. Não serve como evidência de afirmação factual sobre o negócio.

Ou seja: `SCRIPT_CRAFT` justifica *por que* um roteiro abre daquele jeito. **Não** justifica dizer que um ebook custa R$ 47 — isso exige `OFFERS`.

O Evidence Gate continua exigindo `OFFERS`/`PRODUCTS` para claim comercial, independente do craft aberto.

## Índice

| Documento | Ofício | Agentes servidos |
|---|---|---|
| `SHORTFORM_CRAFT.md` | atenção, hook, retenção, estrutura de vídeo curto | hook-finder, script-writer, video-editor |
| `COPY_CRAFT.md` | legenda, legibilidade, CTA, copy educativa | caption-writer, social-media-manager |
| `BRAND_CRAFT.md` | posicionamento, diferenciação, coerência, revisão editorial | brand-architect, brand-reviewer |
| `CONVERSATION_CRAFT.md` | descoberta, objeção, de-escalation, roteamento, suporte | sales, support, community-dm, crm |
| `OFFER_FUNNEL_CRAFT.md` | oferta, precificação, etapas de funil, fricção | offer-funnel-strategist, marketing-director |
| `ANALYTICS_CRAFT.md` | KPI, funil, coorte, atribuição, variância | analytics-bi, cmo, marketing-director |
| `RESEARCH_CRAFT.md` | pesquisa qualitativa, sinal vs ruído, tendência | customer-insights, market-trend-intelligence |
| `VISUAL_CRAFT.md` | hierarquia, composição, legibilidade, continuidade | visual-creative, video-editor |
| `KNOWLEDGE_GOVERNANCE_CRAFT.md` | proveniência, frescor, conflito, versionamento | knowledge-manager |
| `EVALUATION_CRAFT.md` | rubrica, gold set, regressão, taxonomia de falha | ai-performance-evals-agent |
| `STRATEGY_CRAFT.md` | objetivo, priorização, trade-off, decisão sob incerteza | cmo, marketing-director |

*Versão: 1.0 — Agent Foundation V2*
