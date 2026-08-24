# Exemplos reais de AgentHandoff

> Capturados de execuções reais dos workflows (com LLM de verdade), não escritos à mão.
> Truncados para legibilidade; o objeto completo é serializável via `.model_dump_json()`.

---

## ANSWER_DM — cadeia completa de 2 handoffs

Mensagem de entrada: `"Qual ebook e melhor pra quem ta comecando do zero?"`
Resultado: `route_to=sales-conversion-agent`, `status=completed`, `QC=PROCESSO_VALIDADO`

### Handoff 1 — classificação

```json
{
  "from_agent": "community-dm-agent",
  "to_agent": "sales-conversion-agent",
  "workflow": "ANSWER_DM",
  "task_id": "f5b26390-fb69-4aba-ac75-5d42873dceba",
  "objective": "Classificar mensagem recebida e rotear para o especialista certo",
  "context": "Mensagem recebida via Instagram: 'Qual ebook e melhor pra quem ta comecando do zero?'",
  "evidence": [],
  "decision": "Usuário pergunta qual eBook é melhor para começar do zero — é uma decisão de compra, encaminhar para Sales & Conversion Agent.",
  "output": "Intenção identificada: seleção/recomendação de compra...\nAgente de destino: sales-conversion-agent.\nPor quê: a pergunta é uma comparação/recomendação de produto — enquadra-se em decisão de compra...",
  "confidence": "alto",
  "recommended_next": "sales-conversion-agent"
}
```

Note que `to_agent` foi corrigido de `"pending-route"` para o destino real assim que o `Router` decidiu — o handoff registrado reflete a rota que de fato aconteceu.

### Handoff 2 — especialista responde

```json
{
  "from_agent": "sales-conversion-agent",
  "to_agent": "crm-lifecycle-agent",
  "workflow": "ANSWER_DM",
  "task_id": "f5b26390-fb69-4aba-ac75-5d42873dceba",
  "objective": "Responder intencao de compra",
  "context": "Community & DM classificou como intencao de compra. Mensagem original: '...'",
  "decision": "Recomendei um ebook de introdução à chocolataria com conteúdos práticos (temperagem, ganaches, trufas, equipamentos) e pedi mais contexto para indicar o produto exato e checar preços.",
  "confidence": "alto"
}
```

**Comportamento correto observado:** o Sales & Conversion **não inventou preço nem link** — pediu o dado real antes de indicar produto específico, exatamente como manda `BUSINESS_RULES.md`. Isso acontece porque não há Knowledge/RAG conectada, e o agente foi instruído a não preencher a lacuna com invenção.

O `task_id` é o mesmo nos dois handoffs — toda a cadeia é rastreável como uma execução só.

---

## CREATE_REEL — handoff no meio do pipeline

Do pipeline de 9 agentes (`cmo → brand-architect → market-trend-intelligence → hook-finder → script-writer → caption-writer → visual-creative → video-editor → brand-reviewer`):

```json
{
  "from_agent": "hook-finder",
  "to_agent": "script-writer",
  "workflow": "CREATE_REEL",
  "task_id": "cd5c4d69-0c5e-407e-92b2-55c51fb7c51d",
  "objective": "Gerar hooks para o reel",
  "context": "Contexto de tendencia: Forneci um briefing estratégico e de tendências...",
  "evidence": [
    "Brief do usuário (Resumo executivo e estrutura do Reel fornecidos)",
    "Barry Callebaut — press release de lançamento do Ruby (2017)",
    "Revisões científicas sobre fermentação do cacau (ex.: trabalhos/reviews de De Vuyst et al.)"
  ],
  "decision": "Apresentei 3 hooks curtos e alinhados ao tom premium/educador; recomendo o primeiro como vencedor por ser surpreendente e fiel ao conteúdo.",
  "output": "1) (Declaração chocante) \"Essa cor rosa não vem de corante — ela nasce na fermentação do cacau.\"\n2) (Curiosidade) ...\n3) (Tutorial direto) ...\n\nVencedor recomendado: #1 ...",
  "confidence": "alto",
  "recommended_next": "script-writer"
}
```

O campo `context` carrega o resumo da decisão da etapa anterior — cada agente recebe o contexto do handoff que o precedeu, não a conversa inteira.

---

## WEEKLY_BUSINESS_REVIEW — relatório estruturado do CMO

Saída do `WeeklyReportDecision` (fan-out de 5 especialistas → CMO), sobre fixtures marcadas TEST DATA:

```
kpis: [
  "Alcance total 12.400 (+23% vs 10.100) — analytics-bi-agent",
  "Engajamento médio 4,2% (semana anterior 3,8%) — analytics-bi-agent",
  "Top post: Reel 'Técnica de Temperagem' — 2.100 likes, 340 comments — analytics-bi-agent",
  "7 conversas com intenção de compra (3 menções de preço) — sales-conversion-agent",
  "4 novos leads qualificados + 2 qualificados sem follow-up — crm-lifecycle-agent"
]
insights: [
  "Reels técnicos/educacionais geraram maior alcance e engajamento que carrosséis institucionais nesta semana.",
  "Temperagem é uma barreira técnica percebida; conteúdo didático pode reduzir fricção de compra."
]
alerts: [
  "2 leads da semana anterior sem follow-up — contatar em até 48h.",
  "3/7 leads mencionaram preço como objeção — não oferecer desconto sem aprovação humana (escalar se solicitado)."
]
```

Cada KPI vem **com atribuição ao agente de origem**. No cenário "nenhuma fonte disponível", o mesmo relatório reporta zeros explicitamente marcados `(TEST DATA)` e vira alerta — nenhum número inventado para preencher espaço.

---

*Capturado em: 2026-08-23*
