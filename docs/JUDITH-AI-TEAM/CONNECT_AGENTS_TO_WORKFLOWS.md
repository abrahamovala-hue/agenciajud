# 🔗 Conectar Agentes aos Workflows — Planejamento Detalhado

> Documento planejando como conectar cada agente aos workflows principais, definindo liderança, sequência, skills, revisão e aprovação.

**Data:** 07 de Agosto de 2026  
**Status:** 📋 Planejamento  
**Próximo Passo:** Executar conexões

---

## 📊 Objetivo

Para cada workflow principal, definir:

1. **Quem lidera** (qual agente coordena)
2. **Quais agentes participam** (lista completa)
3. **Em que ordem trabalham** (sequência)
4. **Qual skill cada agente usa** (referência a SKILLS_USAGE_MAP.md)
5. **Quem revisa** (pontos de validação)
6. **Quem decide consenso** (se houver divergência)
7. **Onde entra aprovação da Judith** (último passo)

---

## 🎯 Workflows a Conectar

### Principais (Priority 1)
1. **CREATE_REELS** — Gerar 1 reel profissional completo
2. **CREATE_CAMPAIGN** — Campanha 7 dias integrada
3. **REPURPOSE_CONTENT** — Multiplica 1 vídeo em 6 formatos

### Secundários (Priority 2)
4. **CREATE_STORIES** — Gerar 3-5 stories
5. **CREATE_CAROUSEL** — Gerar carousel 5-9 slides
6. **LAUNCH_DIGITAL_PRODUCT** — Lançar ebook/curso
7. **REVIEW_CONTENT** — Validar vs brand
8. **ANALYZE_METRICS** — Analisar performance

---

## 🎬 WORKFLOW 1: CREATE_REELS

### Estrutura de Liderança

```
👑 CMO (aprova objetivo)
  ↓
🏛️ Brand Architect (LIDERA estratégia)
  ↓
[Agentes Criativos em Sequência]
  ↓
✅ Brand Reviewer (aprova conteúdo)
  ↓
🔍 Quality Control (valida processo)
  ↓
👩‍💼 Judith (aprovação humana final)
```

### Sequência Completa

| Etapa | Agente Líder | Agentes Participantes | Skill Principal | Output | Próximo |
|-------|-------------|----------------------|-----------------|--------|---------|
| 1 | CMO | — | — | Aprova objetivo | Brand Architect |
| 2 | Brand Architect | — | `/content-strategy` | Estratégia + Positioning | Trend Research |
| 3 | Trend Research | — | `/analytics` + `/competitor-profiling` | Contexto + Trends | Hook Finder |
| 4 | Hook Finder | — | `/marketing-psychology` + `/customer-research` | 3-5 Hooks | Script Writer |
| 5 | Script Writer | — | `/copywriting` + `/marketing-psychology` | Roteiro 30-60s | Caption Writer |
| 6 | Caption Writer | — | `/copywriting` + `/copy-editing` + `/social` | Caption + Hashtags + CTA | Visual Creative |
| 7 | Visual Creative | — | `/ad-creative` + `/marketing-psychology` | Visual Brief (shots, colors, music) | Brand Reviewer |
| 8 | Video Editor | — | `/content-strategy` + `/copy-editing` | Timeline otimizado (opcional) | Brand Reviewer |
| 9 | Brand Reviewer | — | `/copy-editing` + `/content-strategy` | ✅ APROVADO ou 🔄 PRECISA REVISÃO | Quality Control ou Agente |
| 10 | Quality Control | — | Protocol check | ✅ PROCESSO VALIDADO | Judith |
| 11 | Judith | — | Human decision | ✅ APROVADO ou ❌ REJEITADO | Publicar |

### Decisões de Consenso

**Se Hook Finder e Brand Reviewer discordam sobre hook:**
→ Escalada para **CMO** (decisão final)

**Se Script Writer discorda de Hook Finder:**
→ Retorna para **Hook Finder** para explicação

**Se Brand Reviewer rejeita conteúdo:**
→ Retorna para **agente específico** com feedback

### Skills Necessários

```
✅ /content-strategy (Brand Architect, Video Editor)
✅ /marketing-psychology (Hook Finder, Script Writer, Visual Creative)
✅ /customer-research (Hook Finder)
✅ /copywriting (Script Writer, Caption Writer)
✅ /copy-editing (Caption Writer, Brand Reviewer, Video Editor)
✅ /social (Caption Writer)
✅ /ad-creative (Visual Creative)
✅ /analytics (Trend Research)
✅ /competitor-profiling (Trend Research)
```

### Pontos de Aprovação

1. **CMO** → Objetivo
2. **Brand Architect** → Estratégia
3. **Brand Reviewer** → Conteúdo final
4. **Quality Control** → Processo
5. **Judith** → Publicação

---

## 📅 WORKFLOW 2: CREATE_CAMPAIGN

### Estrutura de Liderança

```
👑 CMO (aprova objetivo)
  ↓
🏛️ Brand Architect (LIDERA estratégia)
  ↓
📈 Marketing Director (coordena execução)
  ↓
[Agentes Criativos em PARALELO para 7 dias]
  ↓
✅ Brand Reviewer (aprova calendário)
  ↓
🔍 Quality Control (valida processo)
  ↓
👩‍💼 Judith (aprovação humana final)
```

### Sequência (Sequential + Parallel)

| Etapa | Agente Líder | Participa | Skill | Output | Timing |
|-------|-------------|-----------|-------|--------|--------|
| 1 | CMO | — | — | Aprova objetivos da campanha | Minuto 0 |
| 2 | Brand Architect | — | `/content-strategy` + `/marketing-psychology` | Estratégia geral (4 pillars, messaging) | Minuto 5 |
| 3 | Marketing Director | — | `/marketing-psychology` + `/pricing` + `/ads` | Plano 7 dias (mix, budget, KPIs) | Minuto 15 |
| 4 | Social Media Manager | — | `/social` + `/content-strategy` | Calendário otimizado (timing, plataforma) | Minuto 25 |
| **5-7 (PARALELO)** | Trend Research | — | `/analytics` + `/competitor-profiling` | Trends do período | Paralelo |
| **5-7 (PARALELO)** | Hook Finder | — | `/marketing-psychology` + `/customer-research` | Hooks para cada dia (7 total) | Paralelo |
| **5-7 (PARALELO)** | Script Writer | — | `/copywriting` + `/marketing-psychology` | Scripts para cada dia (7 total) | Paralelo |
| **5-7 (PARALELO)** | Caption Writer | — | `/copywriting` + `/copy-editing` + `/social` | Captions para cada dia (7 total) | Paralelo |
| 8 | Metrics Analyst | — | `/analytics` + `/cro` | KPI Setup + Performance Predictions | Minuto 45 |
| 9 | Brand Reviewer | — | `/copy-editing` + `/content-strategy` | ✅ Calendário aprovado ou 🔄 PRECISA REVISÃO | Minuto 50 |
| 10 | Quality Control | — | Protocol check | ✅ PROCESSO VALIDADO | Minuto 55 |
| 11 | Judith | — | Human decision | ✅ APROVADO ou ❌ REJEITADO | Minuto 60 |

### Decisões de Consenso

**Se Marketing Director e Social Media Manager discordam sobre mix de conteúdo:**
→ Escalada para **CMO** (define priority)

**Se Metrics Analyst questiona viabilidade de KPIs:**
→ **Marketing Director** explica ou ajusta

**Se Brand Reviewer rejeita calendário:**
→ Retorna para **agente específico** com feedback

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
✅ /ads (Marketing Director) — opcional se usar paid ads
✅ /cro (Metrics Analyst) — para conversion goals
```

### Pontos de Aprovação

1. **CMO** → Objetivos
2. **Brand Architect** → Estratégia
3. **Marketing Director** → Plano tático
4. **Brand Reviewer** → Calendário final
5. **Quality Control** → Processo
6. **Judith** → Publicação

---

## 🔄 WORKFLOW 3: REPURPOSE_CONTENT

### Estrutura de Liderança

```
👑 CMO (aprova objetivo)
  ↓
🏛️ Brand Architect (LIDERA estratégia)
  ↓
📱 Social Media Manager (coordena formatos)
  ↓
[5 Script Writers + 5 Caption Writers em PARALELO]
  ↓
✅ Brand Reviewer (aprova todos os formatos)
  ↓
🔍 Quality Control (valida processo)
  ↓
👩‍💼 Judith (aprovação humana final)
```

### Sequência (Sequential + Parallel)

| Etapa | Agente Líder | Participa | Skill | Output | Formatos |
|-------|-------------|-----------|-------|--------|----------|
| 1 | CMO | — | — | Aprova objetivo | — |
| 2 | Brand Architect | — | `/content-strategy` | Estratégia de repurposing | — |
| 3 | Social Media Manager | — | `/content-strategy` + `/social` | Specs por formato | 6 formatos |
| **4-5 (PARALELO)** | Script Writer x5 | — | `/copywriting` | Script para cada formato | Stories, Carousel, Email, Blog, TikTok |
| **4-5 (PARALELO)** | Caption Writer x5 | — | `/copywriting` + `/copy-editing` + `/social` | Caption para cada formato | Idem |
| 6 | Visual Creative | — | `/ad-creative` + `/marketing-psychology` | Visual specs para cada formato | Idem |
| 7 | Metrics Analyst | — | `/analytics` | Performance predictions por formato | Idem |
| 8 | Brand Reviewer | — | `/copy-editing` + `/content-strategy` | ✅ Todos aprovados ou 🔄 PRECISA REVISÃO | Idem |
| 9 | Quality Control | — | Protocol check | ✅ PROCESSO VALIDADO | — |
| 10 | Judith | — | Human decision | ✅ APROVADO ou ❌ REJEITADO | — |

### Decisões de Consenso

**Se Script Writer discorda de como adaptar para cada formato:**
→ Consulta **Social Media Manager** (expert em formatos)

**Se Visual Creative e Caption Writer discordam sobre specs:**
→ Escalada para **CMO**

### Skills Necessários

```
✅ /content-strategy (Brand Architect, Social Media Manager)
✅ /copywriting (5x Script Writers, 5x Caption Writers)
✅ /copy-editing (5x Caption Writers, Brand Reviewer)
✅ /social (Social Media Manager, 5x Caption Writers)
✅ /ad-creative (Visual Creative)
✅ /marketing-psychology (Visual Creative)
✅ /analytics (Metrics Analyst)
```

### Pontos de Aprovação

1. **CMO** → Objetivo
2. **Brand Architect** → Estratégia
3. **Social Media Manager** → Specs por formato
4. **Brand Reviewer** → Conteúdo final (6 formatos)
5. **Quality Control** → Processo
6. **Judith** → Publicação

---

## ⚙️ Fluxo de Conectar Agentes (Próxima Etapa)

### Passo 1: Atualizar Cada Workflow File

Para cada workflow, adicionar seções:

```markdown
## Agentes Envolvidos

| Ordem | Agente | Skill | Responsabilidade |
|-------|--------|-------|------------------|
| 1 | CMO | — | Aprova objetivo |
| 2 | Brand Architect | /content-strategy | Define estratégia |
| ... | ... | ... | ... |

## Sequência de Execução

1. CMO aprova
2. Brand Architect define estratégia
3. ...

## Pontos de Aprovação

1. CMO → Objetivo
2. Brand Architect → Estratégia
3. ...

## Decisões de Consenso

Se [AGENTE_A] discorda de [AGENTE_B]:
→ Escalada para [AGENTE_DECISOR]
```

### Passo 2: Atualizar Cada Arquivo de Agente

Para cada agente, adicionar seção:

```markdown
## Workflows Onde Participa

| Workflow | Posição | Responsabilidade | Skill |
|----------|---------|------------------|-------|
| CREATE_REELS | 4 | Encontrar hooks irresistíveis | /marketing-psychology |
| CREATE_CAMPAIGN | Paralelo | Hooks para cada dia | /marketing-psychology |
| REPURPOSE_CONTENT | Não participa | — | — |
```

### Passo 3: Criar Arquivo Master

Criar `workflows/AGENT_WORKFLOW_MAPPING.md` com:
- Tabela cruzada: Agente x Workflow
- Skills por agente
- Pontos de decisão

---

## 📋 Checklist: Antes de Executar Conexões

- [ ] Todos os workflows principais mapeados (3 ou mais)
- [ ] Todos os agentes entenderam seus papéis
- [ ] Skills referenciados estão em SKILLS_USAGE_MAP.md
- [ ] Pontos de aprovação estão claros
- [ ] Escalada de conflitos está definida
- [ ] Judith sabe que é aprovação final sempre

---

## 🚀 Próxima Ação

1. **Revisar este documento** com você
2. **Iniciar conexões** (atualizar files de workflow)
3. **Atualizar agentes** com seus papéis
4. **Criar tabela cruzada** (Agent x Workflow)
5. **Validar com CMO** (protocolo funciona?)
6. **Testar CREATE_REELS** (primeiro workflow real)

---

*Plan: Connect Agents to Workflows*  
*Project: Judith AI Creative Team*  
*Brand: Bem me Qué*  
*Date: 07/08/2026*
