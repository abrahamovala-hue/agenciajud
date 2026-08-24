# Autonomy Model — V2

> Define os 4 níveis de autonomia pedidos e qual agente/ação cai em cada um.
> Regra que nunca muda, herdada do protocolo V1: **nenhum conteúdo público sem aprovação da Judith.**

---

## Os 4 níveis

### LOW RISK
FAQ factual e consultas internas. Reversível, sem compromisso com cliente ou marca.
**Pode, futuramente, responder automaticamente** (hoje ainda passa por revisão, mas é o nível mais próximo de autonomia real).

**Exemplos de ação neste nível:**
- Community & DM Agent respondendo pergunta coberta por `sources/COMMENTS_FAQ.md`.
- Analytics & BI Agent gerando relatório.
- Market & Trend Intelligence Agent pesquisando tendência.
- Quality Control Agent validando checklist de processo.
- Customer Insights Agent agregando padrão.
- Knowledge Manager sinalizando documento vencido.

### COMMERCIAL
Venda, recomendação, criação de conteúdo dentro de diretrizes. Regras estritas + logging obrigatório. Não é autônomo para publicar/enviar.

**Exemplos de ação neste nível:**
- Sales & Conversion Agent recomendando produto/respondendo objeção.
- Hook Finder/Script Writer/Caption Writer/Visual Creative criando peça.
- Offer & Funnel Strategist escrevendo copy.
- CMO aprovando objetivo/priorizando recursos.
- CRM & Lifecycle Agent registrando estágio/propondo follow-up (a execução do follow-up ainda passa por canal apropriado).

### SENSITIVE
Reembolso fora de política, conflito, jurídico, reclamação séria, caso incerto, mudança de preço, promoção de versão de agente. **Sempre humano.**

**Exemplos de ação neste nível:**
- Qualquer exceção de política de reembolso (Customer Support Agent).
- Qualquer mudança de preço/oferta (Offer & Funnel Strategist → Judith).
- Qualquer promoção de versão de agente (AI Performance & Evals Agent → Judith, sem exceção).
- Reclamação com tom hostil/ameaça (Community & DM Agent → Judith).
- Decisão estratégica com risco financeiro/legal/reputacional (CMO → Judith).
- Disparo de mensagem em massa (CRM & Lifecycle Agent → Judith).

### PUBLICATION
Nenhum conteúdo público sem aprovação da Judith — sem exceção, independente do nível de autonomia da criação em si.

**Aplica-se a:** todo output de Hook Finder, Script Writer, Caption Writer, Visual Creative, Video Editor, Offer & Funnel Strategist (copy pública), Marketing Director (campanha) — a *criação* pode ser COMMERCIAL, mas a *publicação* é sempre gate humano, passando por Brand Reviewer + Quality Control antes.

---

## Tabela de referência rápida por agente

| Agente | Nível dominante | Exceções |
|---|---|---|
| CMO | COMMERCIAL | SENSITIVE para risco financeiro/legal |
| Brand Architect | COMMERCIAL | — |
| Marketing Director | COMMERCIAL | — |
| Social Media Manager | LOW RISK (roteamento) / COMMERCIAL (calendário) | — |
| Market & Trend Intelligence | LOW RISK | — |
| Hook Finder / Script Writer / Caption Writer / Visual Creative | COMMERCIAL | PUBLICATION sempre humana |
| Video Editor | COMMERCIAL | PUBLICATION sempre humana |
| Offer & Funnel Strategist | COMMERCIAL | SENSITIVE para preço |
| Sales & Conversion | COMMERCIAL | SENSITIVE para desconto fora de `OFFERS.md` |
| CRM & Lifecycle | COMMERCIAL | SENSITIVE para disparo em massa |
| Community & DM | LOW RISK (FAQ) | SENSITIVE para reclamação séria |
| Customer Support | LOW RISK (troubleshooting padrão) | SENSITIVE para exceção de política |
| Analytics & BI | LOW RISK | — |
| Customer Insights | LOW RISK | — |
| Knowledge Manager | LOW RISK | — |
| AI Performance & Evals | LOW RISK (detecção/relatório) | SENSITIVE para promoção de versão (sempre) |
| Brand Reviewer | COMMERCIAL | Não é a aprovação final |
| Quality Control | LOW RISK | — |

---

*Versão: 2.0*
