# Knowledge Gap Registry

> **GERADO A PARTIR DO CODIGO** (as lacunas ja declaradas) + auditoria manual da Fase 4.

Serve para sabermos exatamente o que pedir a Judith e o que depende de integracao.

## MISSING_JUDITH_SOURCE — precisa de material que so a Judith tem

A auditoria procurou conteudo tecnico real no repositorio (temperagem, ganache, caramelo,
casquinha, drageado, praline, validade, armazenamento, ingredientes, equipamentos).
**Os termos aparecem como topico; nao ha nenhum conteudo tecnico** — zero temperatura,
zero gramatura, zero passo-a-passo. Os ebooks nao estao no projeto e **nao foram
reconstruidos de memoria**.

| Item | Por que precisamos | Quem fica bloqueado |
|---|---|---|
| Conteudo real dos ebooks | responder o que o produto ensina, sem inventar | customer-support, sales, script-writer |
| Receitas e tecnicas | conteudo educativo fiel | script-writer, caption-writer, hook-finder |
| Troubleshooting real | resolver duvida tecnica de cliente | customer-support |
| FAQ com respostas aprovadas | responder no padrao da Judith | community-dm, customer-support |
| Politicas completas (acesso, entrega, troca) | hoje so a garantia de 7 dias esta documentada | customer-support |

## TO_VALIDATE_WITH_JUDITH — existe, mas nao esta validado

| Fonte | Estado | Impacto |
|---|---|---|
| `VOICE` | TEMPLATE | tom da marca inferido do site, nao confirmado |
| `AUDIENCE` | TEMPLATE | personas inferidas |
| `CONTENT_PILLARS` | TEMPLATE | pilares e proporcoes propostos |
| `VISUAL_IDENTITY` | TEMPLATE | cores e fontes inferidas do CSS |
| `INSTAGRAM_AUDIT` | TEMPLATE | pede analise manual, nao preenchida |
| `PRODUCT_PAGES_AUDIT` | TEMPLATE | template sem conclusao |
| `OFFERS` (colecao completa) | A_VERIFICAR | preco da colecao nao confirmado |
| `PRODUCTS` (produtos futuros) | A_VERIFICAR | secao marcada 'a preencher com Judith' |

## WAITING_FOR_INTEGRATION — depende de sistema externo

| Lacuna | Integracao | Agentes que dependem |
|---|---|---|
| `CALENDARIO_EDITORIAL` | Nao existe arquivo de calendario no repo — CONTENT_PILLARS traz apenas uma proporcao semanal sugerida. | marketing-director, social-media-manager |
| `CASOS_SUPORTE` | Nao ha base de tickets ou casos resolvidos documentados. | customer-support-agent |
| `CRM_PIPELINE` | CRM externo nao esta conectado (TOOL PLANNED). | analytics-bi-agent, cmo, crm-lifecycle-agent, customer-insights-agent, customer-support-agent, offer-funnel-strategist, sales-conversion-agent |
| `DATA_DICTIONARY` | Nao existe data dictionary nem documento de definicao de KPI no repo. | analytics-bi-agent |
| `DECISOES_ESTRATEGICAS` | Business Memory nao esta implementada — decisoes passadas nao sobrevivem entre sessoes. | brand-architect, knowledge-manager, marketing-director |
| `EXEMPLOS_APROVADOS` | Nenhum historico de aprovacao/rejeicao e persistido — nao ha exemplo real para calibrar. | ai-performance-evals-agent, brand-reviewer, caption-writer, community-dm-agent, hook-finder, knowledge-manager, script-writer, video-editor, visual-creative |
| `GOLD_DATASET` | evals/*/cases.yaml existem, mas nao ha gold dataset preenchido nem pipeline de regressao rodando. | ai-performance-evals-agent |
| `HISTORICO_DM` | Nenhum fluxo de DM/comentario esta conectado. COMMENTS_FAQ e um retrato manual antigo. | community-dm-agent, crm-lifecycle-agent, customer-insights-agent, offer-funnel-strategist, sales-conversion-agent |
| `HISTORICO_POSTS` | Nao ha base de posts publicados; o Instagram nao esta conectado. | ai-performance-evals-agent, analytics-bi-agent, caption-writer, hook-finder, market-trend-intelligence, marketing-director, script-writer, social-media-manager |
| `METRICAS_INSTAGRAM` | Instagram Insights nao esta conectado (TOOL PLANNED). INSTAGRAM_AUDIT e levantamento manual, nao metrica. | ai-performance-evals-agent, analytics-bi-agent, brand-reviewer, hook-finder, knowledge-manager, market-trend-intelligence, marketing-director, offer-funnel-strategist, social-media-manager, video-editor |
| `TENDENCIAS_ATUAIS` | Nenhuma fonte externa de tendencia esta conectada (Apify/scraping sao TOOL PLANNED). | hook-finder, market-trend-intelligence, social-media-manager |
| `VENDAS_KIWIFY` | Integracao Kiwify nao existe (TOOL PLANNED). Nenhum numero de venda esta disponivel no sistema. | analytics-bi-agent, crm-lifecycle-agent, customer-insights-agent, customer-support-agent, knowledge-manager, marketing-director, offer-funnel-strategist, sales-conversion-agent |

## WAITING_FOR_REAL_EXAMPLES — comportamento, nao fato

Pecas aprovadas e rejeitadas, correcoes da Judith, respostas de DM reais, conversas que
converteram, casos de suporte resolvidos. Alimentam o gold set do `ai-performance-evals-agent`
e calibram os agentes criativos. **Nada disso e persistido hoje.**

## WAITING_FOR_METRICS

Instagram (alcance, retencao, salvamentos) e Kiwify (vendas, receita, reembolso).
Sem eles, toda afirmacao de performance e hipotese — e os agentes sao obrigados a dizer isso.

## COMPLETE_ENOUGH_FOR_V1

| Camada | Estado |
|---|---|
| Craft knowledge (11 documentos de oficio) | completo para os 20 papeis |
| Posicionamento e diferenciais (`BRAND`) | vigente |
| Catalogo e precos individuais (`PRODUCTS`, `OFFERS`) | vigente |
| Garantia de 7 dias | vigente |
| Regras de negocio (`BUSINESS_RULES`) | vigente |
| Protocolo de colaboracao | vigente |
| Capability Policy | completa, 20 agentes |
