# Knowledge Refresh Policy — V2

> Define a política de atualização (freshness) por tipo de dado. **Nenhum scheduler foi
> criado nesta etapa** — isto é documentação da política, para implementar depois.
> O Knowledge Manager (agente 18) é o dono conceitual de aplicar/sinalizar esta política.

---

| Tipo de dado | Freshness | Fonte | Status de integração |
|---|---|---|---|
| Brand / Voice | On change (evento, não tempo) | `BRAND.md`, `VOICE.md` | Manual — Judith edita, Knowledge Manager sinaliza a mudança |
| Products / Offers | On change | `PRODUCTS.md`, `OFFERS.md` | Manual |
| Instagram metrics | Diária | Instagram Insights | **TOOL PLANNED** — sem integração hoje |
| Sales / Kiwify | Diária | Kiwify | **TOOL PLANNED** — sem integração hoje |
| DMs / comentários | Contínua ou agendada | Instagram | **TOOL PLANNED** — sem integração hoje |
| Trend research | Recorrente (a cada nova pesquisa disparada) | Market & Trend Intelligence Agent | Manual (sem Apify ainda, ver `agents/05-market-trend-intelligence.md`) |
| Customer Insights | Diária/semanal (agregação) | Customer Insights Agent | Manual — depende de volume de conversa real |
| Evals | Após interações suficientes (não por tempo fixo) | AI Performance & Evals Agent | Conceitual — ver `models/LEARNING_EVALS_MODEL.md` |
| Weekly report | Semanal | Analytics & BI Agent | Manual |

---

## Por que "on change" em vez de tempo fixo para Brand/Products/Offers

Esses documentos são fonte de verdade transacional (preço errado publicado é um erro de negócio real, não cosmético). Uma política de "revisar a cada X dias" criaria uma janela de dado desatualizado sem necessidade — o correto é o dado mudar exatamente quando o fato muda, e o Knowledge Manager sinalizar a mudança para quem depende dela (ex.: Offer & Funnel Strategist, Brand Reviewer).

## O que "vencido" significa na prática (hoje)

Sem scheduler, "vencido" é hoje um conceito que o Knowledge Manager aplica quando **consultado** (ex.: um agente relata inconsistência, ou alguém pergunta diretamente) — não uma varredura automática periódica. Isso é uma limitação explícita, não uma decisão de design permanente.

---

*Versão: 2.0*
*Nenhum scheduler/cron implementado — política documentada para implementação futura.*
