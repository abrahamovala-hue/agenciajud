# Workflow Orchestrator — Orquestração de Agentes

Define como os 12 agentes executam em cada workflow.

## 🎬 CREATE_REELS Pipeline

```
1. BRAND_STRATEGIST
   └─ Input: tema do reel
   └─ Output: estratégia, positioning, messaging

2. TREND_RESEARCH
   └─ Input: tema, audience
   └─ Output: trends atuais, referencias

3. HOOK_FINDER
   └─ Input: tema, trends, audience
   └─ Output: 3-5 hooks irresistíveis

4. SCRIPT_WRITER
   └─ Input: hook escolhido, estratégia, products
   └─ Output: roteiro completo (0-60s)

5. CAPTION_WRITER
   └─ Input: script, hook, products
   └─ Output: caption + hashtags + CTA

6. VISUAL_CREATIVE
   └─ Input: script, tone, visual identity
   └─ Output: visual brief detalhado

7. BRAND_REVIEWER
   └─ Input: tudo acima
   └─ Output: aprovação/revisões

8. VIDEO_EDITOR (opcional)
   └─ Input: visual brief
   └─ Output: timeline, cuts, transitions
```

## 📅 CREATE_CAMPAIGN Pipeline

```
1. BRAND_STRATEGIST
   └─ Input: tema, objetivo
   └─ Output: posicionamento, messaging, KPIs

2. MARKETING_DIRECTOR
   └─ Input: estratégia, objetivo
   └─ Output: plano 7 dias, formato mix

3. SOCIAL_MEDIA_MANAGER
   └─ Input: plano, audience, trends
   └─ Output: calendário otimizado, timing

4. TREND_RESEARCH (paralelo)
   └─ Input: tema, público-alvo
   └─ Output: insights de trending topics

5. HOOK_FINDER (paralelo)
   └─ Input: tema, trends, cada dia
   └─ Output: hooks para cada piece

6. SCRIPT_WRITER (paralelo)
   └─ Input: hooks, estratégia
   └─ Output: roteiros para cada dia

7. CAPTION_WRITER (paralelo)
   └─ Input: scripts
   └─ Output: captions + CTAs

8. METRICS_ANALYST
   └─ Input: calendário, histórico
   └─ Output: KPIs esperados, benchmarks

9. BRAND_REVIEWER
   └─ Input: calendário completo
   └─ Output: aprovação/revisões
```

## 🔄 REPURPOSE_CONTENT Pipeline

```
1. BRAND_STRATEGIST
   └─ Input: reel original
   └─ Output: key messages, core value

2. CONTENT_STRATEGIST
   └─ Input: reel, platforms target
   └─ Output: estratégia de repurposing

3. SCRIPT_WRITER (5 threads paralelas)
   ├─ Stories: quebra em 3-5 momentos
   ├─ Carousel: estrutura para 5 slides
   ├─ Email: formato longo
   ├─ Blog: artigo completo
   └─ TikTok: versão curta

4. CAPTION_WRITER (5 threads paralelas)
   ├─ Escreve caption para cada formato
   └─ Otimiza para cada plataforma

5. VISUAL_CREATIVE
   └─ Input: cada formato
   └─ Output: visual specs para cada um

6. METRICS_ANALYST
   └─ Input: 6 formatos
   └─ Output: performance predictions

7. BRAND_REVIEWER
   └─ Input: tudo repurposed
   └─ Output: aprovação final
```

## 💡 Padrão de Execução

### Sequential (padrão)
```
Agent 1 → Agent 2 → Agent 3 → ... → Agent N
```

### Parallel (quando possível)
```
Agent 1 → [Agent 2a || Agent 2b || Agent 2c] → Agent 3
```

### Fallback (se um falha)
```
Agent 1 → [Agent 2 FAIL] → Agent 2 Alternative → Agent 3
```

## 🔌 Integração com MCP

Cada workflow invoca a MCP assim:

```typescript
// Inicia workflow
start_workflow({
  type: "reel|campaign|repurpose",
  title: "Nome do workflow",
  context: {
    agentPipeline: [...],
    inputs: {...}
  }
})

// Valida resultado
validate_against_brand({
  content: resultado_final
})

// Salva se aprovado
save_content({
  format: "reel|campaign|repurpose",
  data: {...}
})
```

## 📊 Status de Execução

Cada workflow reporta:
- ✅ Completed — Pronto para publish
- ⏳ Processing — Aguardando agentes
- 📝 Needs Review — Aguardando aprovação
- ❌ Failed — Erro em um agente
- 🔄 Revision — Aguardando revisão

## 🎯 Próximos Steps

1. [ ] Integrar com Claude API para invocar agentes
2. [ ] Criar sistema de fallback se agente falha
3. [ ] Adicionar retry logic com delays
4. [ ] Dashboard para monitorar execução
5. [ ] Webhook para notificações de completion
