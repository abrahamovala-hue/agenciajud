# 🔗 Agent Workflow Connections — Conexões Oficiais

> Define exatamente quais agentes participam de cada workflow, quem lidera, ordem de execução, skills usadas e aprovação humana.

**Versão:** 1.0  
**Data:** 07 de Agosto de 2026  
**Status:** ✅ Oficial (Antes de testar workflows reais)

---

## 📋 Regra Fundamental

**Nenhum teste de workflow real será executado antes desta documentação estar 100% completa.**

Cada workflow tem:
- ✅ Agente Líder definido
- ✅ Sequência exata de execução
- ✅ Skills mapeadas por agente
- ✅ Pontos de aprovação definidos
- ✅ Regra de consenso em caso de conflito
- ✅ Aprovação humana de Judith garantida

---

## 🎬 WORKFLOW 1: `/judith-create-reel`

### Objetivo
Criar 1 reel profissional completo (roteiro + caption + visual brief) em 2-3 horas.

### Agente Líder
**Brand Architect** (coordena e valida estratégia)

### Sequência de Execução

| Etapa | Agente | Skill | Entrada | Saída | Duração |
|-------|--------|-------|---------|-------|---------|
| 1 | **CMO** | — | Objetivo do reel | Aprovação de objetivo | 5 min |
| 2 | **Brand Architect** | `/content-strategy` + `/competitor-profiling` | Objetivo + CONTENT_PILLARS.md | Estratégia (angle, tone, messaging) | 10 min |
| 3 | **Trend Research** | `/analytics` + `/competitor-profiling` | Tema + Audience | Trends contexto + referencias | 10 min |
| 4 | **Hook Finder** | `/marketing-psychology` + `/customer-research` | Tema + Estratégia + Trends | 3-5 Hooks irresistíveis | 15 min |
| 5 | **Script Writer** | `/copywriting` + `/marketing-psychology` + `/customer-research` | Hook escolhida + Estratégia | Roteiro 30-60s (com pacing) | 15 min |
| 6 | **Caption Writer** | `/copywriting` + `/copy-editing` + `/social` | Script + Produto | Caption + Hashtags + CTA | 15 min |
| 7 | **Visual Creative** | `/ad-creative` + `/marketing-psychology` | Script + Tone + Brand colors | Visual brief (shots, colors, music, pacing) | 15 min |
| 8 | **Video Editor** (opcional) | `/content-strategy` + `/copy-editing` | Visual brief + Script | Timeline com timing otimizado | 20 min |
| 9 | **Brand Reviewer** | `/copy-editing` + `/content-strategy` | Tudo acima | ✅ APROVADO ou 🔄 REVISÃO | 10 min |
| 10 | **Quality Control** | Protocol check | Documentação completa | ✅ PROCESSO VALIDADO | 5 min |
| 11 | **Judith** | Human decision | Recomendação final | ✅ PUBLICAR ou ❌ REJEITAR | 10 min |

**Tempo Total:** 2-3 horas

### Skills Necessários
```
✅ /content-strategy (Brand Architect, Video Editor)
✅ /competitor-profiling (Brand Architect, Trend Research)
✅ /analytics (Trend Research)
✅ /marketing-psychology (Hook Finder, Script Writer, Visual Creative)
✅ /customer-research (Hook Finder, Script Writer)
✅ /copywriting (Script Writer, Caption Writer)
✅ /copy-editing (Caption Writer, Brand Reviewer, Video Editor)
✅ /social (Caption Writer)
✅ /ad-creative (Visual Creative)
```

### Fluxo de Comunicação

```
CMO: "Cria reel de [TEMA]. Objetivo: [OBJETIVO]"
  ↓
Brand Architect: "📤 ENTREGA" [Estratégia]
  ↓
Trend Research: "📤 ENTREGA" [Trends]
  ↓
Hook Finder: "📤 ENTREGA" [3 Hooks]
  ↓
Script Writer: "📤 ENTREGA" [Script 45s]
  ↓
Caption Writer: "📤 ENTREGA" [Caption final]
  ↓
Visual Creative: "📤 ENTREGA" [Visual brief]
  ↓
[Video Editor opcional]
  ↓
Brand Reviewer: "✅ APROVADO" ou "🔄 REVISÃO: [FEEDBACK]"
  ↓
Quality Control: "✅ PROCESSO VALIDADO"
  ↓
Judith: "✅ APROVO" ou "❌ REJEITO"
```

### Pontos de Aprovação
1. **CMO** → Valida objetivo
2. **Brand Architect** → Valida estratégia
3. **Brand Reviewer** → Valida conteúdo
4. **Quality Control** → Valida processo
5. **Judith** → Aprovação final

### Resolução de Conflitos

**Cenário 1: Hook Finder vs Brand Architect**
- Tema: Hook muito ousada vs marca conservadora
- Escalada: **CMO** (decisão final)
- Critério: Consulta VOICE.md + AUDIENCE.md

**Cenário 2: Caption Writer vs Social Media Manager** (não está no workflow, mas se surgir questão)
- Tema: Timing ou hashtags
- Escalada: **Social Media Manager** (expert)

**Cenário 3: Brand Reviewer rejeita**
- Retorna para: Agente específico (Script Writer, Caption Writer, Visual Creative)
- Prazo para revisar: Indicado por Brand Reviewer

### Saída Final Esperada

```
✅ Reel Completo
├─ Roteiro (45s com beats de pacing)
├─ Caption (com hashtags e CTA)
├─ Visual Brief (shots list, colors, music, pacing)
├─ Aprovação Brand Reviewer
├─ Validação Quality Control
└─ Aprovação Judith (pronto para publicar)
```

---

## 🎬 WORKFLOW 2: `/judith-create-reel-full`

### Objetivo
Criar reel + editar vídeo (versão completa com edição).

### Agente Líder
**Brand Architect** (coordena) + **Video Editor** (executa edição)

### Diferença vs `/judith-create-reel`

| Aspecto | create-reel | create-reel-full |
|---------|------------|------------------|
| Duração | 2-3h | 4-5h |
| Video Editor | Opcional | Obrigatório |
| Saída | Brief + Script | Vídeo editado pronto |
| Timeline | Conceitual | Detalhada com timing |

### Sequência
**Mesmo que `/judith-create-reel` (etapas 1-7), mais:**

| Etapa | Agente | Skill | Entrada | Saída |
|-------|--------|-------|---------|-------|
| 8 | **Video Editor** | `/content-strategy` + `/copy-editing` | Visual brief + Script | Timeline completo (cuts, transitions, timing) |
| 9 | **Brand Reviewer** | `/copy-editing` | Timeline + Script | ✅ APROVADO ou 🔄 REVISÃO |
| 10 | **Quality Control** | Protocol check | Documentação + Video | ✅ PROCESSO VALIDADO |
| 11 | **Judith** | Human decision | Video final | ✅ PUBLICAR ou ❌ REJEITAR |

**Duração Total:** 4-5 horas

### Skills Necessários
```
[Mesmos de /judith-create-reel] +
✅ Video Editor tem /content-strategy + /copy-editing
```

### Saída Final Esperada
```
✅ Reel Completo + Video Editado
├─ Roteiro (45s com beats)
├─ Caption (com hashtags e CTA)
├─ Visual Brief (shots, colors, music)
├─ Timeline (cuts, transitions, timing)
├─ Video Final (pronto para publicar ou posterizar)
├─ Aprovação Brand Reviewer
├─ Validação Quality Control
└─ Aprovação Judith
```

---

## 📅 WORKFLOW 3: `/judith-create-campaign`

### Objetivo
Criar campanha 7 dias integrada (mix de conteúdo: reels + stories + carousels + posts).

### Agente Líder
**Marketing Director** (coordena) + **Social Media Manager** (otimiza)

### Sequência de Execução

| Etapa | Agente | Skill | Entrada | Saída | Duração |
|-------|--------|-------|---------|-------|---------|
| 1 | **CMO** | — | Objetivo campanha | Aprovação | 5 min |
| 2 | **Brand Architect** | `/content-strategy` + `/marketing-psychology` | Objetivo + PRODUCTS.md | Estratégia geral (4 pillars, messaging) | 15 min |
| 3 | **Marketing Director** | `/marketing-psychology` + `/pricing` + `/ads` | Estratégia | Plano 7 dias (mix, budget, KPIs) | 20 min |
| 4 | **Social Media Manager** | `/social` + `/content-strategy` | Plano | Calendário otimizado (timing, plataforma) | 15 min |
| 5 | **Trend Research** (paralelo) | `/analytics` + `/competitor-profiling` | Tema | Trends do período | 15 min |
| 5 | **Hook Finder** (paralelo) | `/marketing-psychology` + `/customer-research` | Tema + Trends | 7 Hooks (um por dia) | 20 min |
| 5 | **Script Writer** (paralelo) | `/copywriting` + `/marketing-psychology` | Hooks | 7 Scripts (um por dia) | 25 min |
| 5 | **Caption Writer** (paralelo) | `/copywriting` + `/copy-editing` + `/social` | Scripts | 7 Captions (um por dia) | 25 min |
| 6 | **Metrics Analyst** | `/analytics` + `/cro` | Calendário | KPI Setup + Predictions | 15 min |
| 7 | **Brand Reviewer** | `/copy-editing` + `/content-strategy` | Calendário completo (7 dias) | ✅ APROVADO ou 🔄 REVISÃO | 20 min |
| 8 | **Quality Control** | Protocol check | Documentação | ✅ PROCESSO VALIDADO | 5 min |
| 9 | **Judith** | Human decision | Calendário + Recommendations | ✅ PUBLICAR ou ❌ REJEITAR | 10 min |

**Tempo Total:** 5-10 horas (paralelo acelerá)

### Skills Necessários
```
✅ /content-strategy (Brand Architect, Social Media Manager)
✅ /marketing-psychology (Brand Architect, Marketing Director, Hook Finder, Script Writer)
✅ /competitor-profiling (Trend Research)
✅ /analytics (Trend Research, Metrics Analyst)
✅ /customer-research (Hook Finder)
✅ /copywriting (Script Writer, Caption Writer)
✅ /copy-editing (Caption Writer, Brand Reviewer)
✅ /social (Social Media Manager, Caption Writer)
✅ /pricing (Marketing Director)
✅ /ads (Marketing Director) — se usar paid ads
✅ /cro (Metrics Analyst) — para conversion goals
```

### Fluxo Paralelo

```
CMO aprova objetivo
  ↓
Brand Architect define estratégia
  ↓
Marketing Director plano
  ↓
Social Media Manager calendário
  ↓
[PARALELO - 15 min]
├─ Trend Research → trends
├─ Hook Finder → 7 hooks
├─ Script Writer → 7 scripts
└─ Caption Writer → 7 captions
  ↓
Metrics Analyst → KPI setup
  ↓
Brand Reviewer → valida calendário
  ↓
Quality Control → valida processo
  ↓
Judith → aprovação final
```

### Pontos de Aprovação
1. **CMO** → Objetivo
2. **Brand Architect** → Estratégia
3. **Marketing Director** → Plano tático
4. **Brand Reviewer** → Calendário final
5. **Quality Control** → Processo
6. **Judith** → Publicação

### Saída Final Esperada
```
✅ Campanha 7 Dias Completa
├─ Estratégia (4 pillars, messaging)
├─ Plano (mix, timing, budget)
├─ Calendário (7 dias com conteúdo)
├─ Scripts (7 roteiros)
├─ Captions (7 legendas com hashtags/CTAs)
├─ KPIs (targets e predictions)
├─ Aprovação Brand Reviewer
├─ Validação Quality Control
└─ Aprovação Judith (pronto para publicar 7 dias)
```

---

## 📅 WORKFLOW 4: `/judith-create-campaign-full`

### Objetivo
Criar campanha 7 dias com videos editados (versão completa).

### Agente Líder
**Marketing Director** (coordena) + **Video Editor** (edita)

### Diferença vs `/judith-create-campaign`

| Aspecto | create-campaign | create-campaign-full |
|---------|-----------------|----------------------|
| Duração | 5-10h | 8-15h |
| Video Editor | Não | Obrigatório para cada vídeo |
| Saída | Scripts + Captions | Vídeos editados prontos |

### Sequência
**Mesmo que `/judith-create-campaign`, mais:**

Após etapa 5 (Caption Writer finaliza), adiciona:

| Etapa | Agente | Skill | Entrada | Saída |
|-------|--------|-------|---------|-------|
| 6 | **Visual Creative** | `/ad-creative` + `/marketing-psychology` | Scripts | 7 Visual Briefs (um por dia) |
| 7 | **Video Editor** (paralelo x7) | `/content-strategy` + `/copy-editing` | Visual briefs | 7 Videos editados |
| 8 | **Metrics Analyst** | `/analytics` + `/cro` | Calendário video | KPI Setup + Predictions |
| 9 | **Brand Reviewer** | `/copy-editing` | Videos + Captions | ✅ APROVADO |
| 10 | **Quality Control** | Protocol check | Documentação | ✅ PROCESSO VALIDADO |
| 11 | **Judith** | Human decision | Videos finais | ✅ PUBLICAR |

**Duração Total:** 8-15 horas

### Saída Final Esperada
```
✅ Campanha 7 Dias Completa + Videos
├─ Estratégia (4 pillars)
├─ Plano (mix, timing, budget)
├─ Calendário (7 dias)
├─ Scripts (7 roteiros)
├─ Captions (7 legendas)
├─ Visual Briefs (7 briefs)
├─ Videos Editados (7 vídeos prontos)
├─ KPIs (targets e predictions)
├─ Aprovação Brand Reviewer
├─ Validação Quality Control
└─ Aprovação Judith (pronto para publicar)
```

---

## 🔄 WORKFLOW 5: `/judith-repurpose-content`

### Objetivo
Converter 1 vídeo em 6 formatos diferentes (stories + carousel + email + blog + tiktok).

### Agente Líder
**Brand Architect** (coordena) + **Social Media Manager** (otimiza por formato)

### Sequência de Execução

| Etapa | Agente | Skill | Entrada | Saída | Formatos |
|-------|--------|-------|---------|-------|----------|
| 1 | **CMO** | — | Vídeo + Objetivo | Aprovação | — |
| 2 | **Brand Architect** | `/content-strategy` | Vídeo | Estratégia repurposing | — |
| 3 | **Social Media Manager** | `/social` + `/content-strategy` | Vídeo + Estratégia | Specs por formato | 6 formatos |
| 4 | **Script Writer** (x5 paralelo) | `/copywriting` | Vídeo + Specs | Scripts para cada formato | Stories, Carousel, Email, Blog, TikTok |
| 5 | **Caption Writer** (x5 paralelo) | `/copywriting` + `/copy-editing` + `/social` | Scripts | Captions para cada formato | Idem |
| 6 | **Visual Creative** | `/ad-creative` + `/marketing-psychology` | Scripts | Visual specs por formato | Idem |
| 7 | **Metrics Analyst** | `/analytics` | 6 Formatos | Performance predictions | Idem |
| 8 | **Brand Reviewer** | `/copy-editing` + `/content-strategy` | Tudo acima | ✅ APROVADO | Idem |
| 9 | **Quality Control** | Protocol check | Documentação | ✅ PROCESSO VALIDADO | — |
| 10 | **Judith** | Human decision | 6 Conteúdos | ✅ PUBLICAR | — |

**Tempo Total:** 3-5 horas

### Skills Necessários
```
✅ /content-strategy (Brand Architect, Social Media Manager)
✅ /social (Social Media Manager, 5x Caption Writers)
✅ /copywriting (5x Script Writers, 5x Caption Writers)
✅ /copy-editing (5x Caption Writers, Brand Reviewer)
✅ /ad-creative (Visual Creative)
✅ /marketing-psychology (Visual Creative)
✅ /analytics (Metrics Analyst)
```

### Saída Final Esperada
```
✅ 6 Conteúdos Diferentes
├─ Stories (3-5 slides com cliffhangers)
├─ Carousel (5-9 slides otimizado)
├─ Email (texto longo com CTA)
├─ Blog Post (artigo completo)
├─ TikTok (versão curta 15-60s)
├─ Specs por formato (visual, timing, tone)
├─ Performance predictions
├─ Aprovação Brand Reviewer
├─ Validação Quality Control
└─ Aprovação Judith (pronto para publicar em 6 plataformas)
```

---

## ✅ WORKFLOW 6: `/judith-review-content`

### Objetivo
Revisar conteúdo criado vs brand guidelines antes de publicar.

### Agente Líder
**Brand Reviewer** (valida)

### Sequência de Execução

| Etapa | Agente | Skill | Entrada | Saída | Duração |
|-------|--------|-------|---------|-------|---------|
| 1 | **Brand Reviewer** | `/copy-editing` + `/content-strategy` + `/marketing-psychology` | Conteúdo final | ✅ APROVADO ou 🔄 REVISÃO | 15-30 min |
| 2 | Se rejeitar: Retorna para agente específico com feedback | — | — | — | — |
| 3 | Se aprovado: **Quality Control** | Protocol check | Documentação | ✅ PROCESSO VALIDADO | 5 min |
| 4 | **Judith** | Human decision | Conteúdo revisado | ✅ PUBLICAR ou ❌ REJEITAR | 10 min |

**Tempo Total:** 30-45 minutos

### Skills Necessários
```
✅ /copy-editing (Brand Reviewer)
✅ /content-strategy (Brand Reviewer)
✅ /marketing-psychology (Brand Reviewer) — opcional para análise profunda
```

### Validações da Brand Reviewer

```
Checklist:
- [ ] Ton alinhado com VOICE.md?
- [ ] Linguagem correta de AUDIENCE.md?
- [ ] Segue CONTENT_PILLARS.md?
- [ ] Sem typos ou erros gramaticais?
- [ ] CTAs funcionam?
- [ ] Imagens/vídeos com specs corretos?
- [ ] Alinhado com histórico de conteúdo?
```

### Saída Final Esperada
```
✅ Conteúdo Revisado
├─ Validação contra brand guidelines
├─ Feedback se precisa revisão (com detalhes)
├─ Aprovação Brand Reviewer
├─ Validação Quality Control
└─ Aprovação Judith (pronto para publicar)
```

---

## 📊 Tabela Cruzada: Agentes x Workflows

| Agente | create-reel | create-reel-full | create-campaign | create-campaign-full | repurpose | review |
|--------|------------|-----------------|-----------------|----------------------|-----------|--------|
| **CMO** | 1 (aprova) | 1 (aprova) | 1 (aprova) | 1 (aprova) | 1 (aprova) | — |
| **Brand Architect** | LIDERA | LIDERA | 2 (estratégia) | 2 (estratégia) | LIDERA | — |
| **Marketing Director** | — | — | LIDERA | LIDERA | — | — |
| **Social Media Manager** | — | — | 4 (calendário) | 4 (calendário) | 3 (specs) | — |
| **Trend Research** | 3 | 3 | 5 (paralelo) | 5 (paralelo) | — | — |
| **Hook Finder** | 4 | 4 | 5 (paralelo) | 5 (paralelo) | — | — |
| **Script Writer** | 5 | 5 | 5 (paralelo) | 5 (paralelo) | 4 (x5 paralelo) | — |
| **Caption Writer** | 6 | 6 | 5 (paralelo) | 5 (paralelo) | 5 (x5 paralelo) | — |
| **Visual Creative** | 7 | 7 | — | 6 (paralelo x7) | 6 | — |
| **Video Editor** | 8 (opt) | 8 (obrig) | — | 7 (paralelo x7) | — | — |
| **Product Marketing** | — | — | — | — | — | — |
| **Metrics Analyst** | — | — | 6 | 8 | 7 | — |
| **Brand Reviewer** | 9 | 9 | 7 | 9 | 8 | 1 (LIDERA) |
| **Quality Control** | 10 | 10 | 8 | 10 | 9 | 3 |
| **Judith** | 11 | 11 | 9 | 11 | 10 | 4 |

**Legenda:**
- Número = Ordem de execução (etapa)
- LIDERA = Agente principal do workflow
- Opt = Opcional
- Obrig = Obrigatório
- (x5 paralelo) = Múltiplas instâncias em paralelo

---

## 🔐 Regras Vinculantes

### Regra 1: Nenhum Workflow Sem CMO
Toda execução começa com **CMO aprova objetivo.**

### Regra 2: Nenhum Workflow Sem Brand Reviewer
Toda saída é revisada por **Brand Reviewer** antes de Judith.

### Regra 3: Nenhum Workflow Sem Judith
**Judith** faz aprovação final de QUALQUER conteúdo.

### Regra 4: Nenhum Pulo de Etapa
Não é permitido pular agentes na sequência.

**Proibido:** Hook Finder → Judith (pulou Script Writer)  
**Correto:** Hook Finder → Script Writer → Caption Writer → Brand Reviewer → Judith

### Regra 5: Documentação Obrigatória
Cada agente documenta sua entrega no formato estruturado (AGENT_COLLABORATION_PROTOCOL.md).

### Regra 6: Escalada em Conflito
Se 2 agentes discordam → Escalada para **CMO** (decisão final).

---

## ✅ Checklist: Antes de Testar Workflow Real

- [ ] Lido AGENT_COLLABORATION_PROTOCOL.md (entendo regras)
- [ ] Entendo sequência exata do workflow que vou testar
- [ ] Sei quem é agente líder
- [ ] Sei quais skills são necessários
- [ ] Sei quem revisa
- [ ] Sei que Judith faz aprovação final
- [ ] Entendo pontos de conflito e escalada
- [ ] Tenho acesso a documentação de brand (VOICE.md, AUDIENCE.md, etc)

---

## 🚀 Status: Pronto para Testar

**Agora podemos:**

1. ✅ Escolher um workflow (recomendado: `/judith-create-reel`)
2. ✅ Executar de verdade com os agentes
3. ✅ Validar se fluxo funciona na prática
4. ✅ Ajustar se necessário
5. ✅ Documentar aprendizados

**Workflows estão 100% conectados e documentados.**

---

*Document: Agent Workflow Connections*  
*Project: Judith AI Creative Team*  
*Brand: Bem me Qué*  
*Version: 1.0 Official*
