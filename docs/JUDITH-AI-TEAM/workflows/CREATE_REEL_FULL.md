# 🎬 CREATE_REEL_FULL — Workflow Principal

> Workflow completo do Judith AI Creative Team que transforma uma ideia em um Reel profissional pronto para publicar, passando por todos os agentes até aprovação final de Judith.

**Versão:** 1.0  
**Status:** ✅ Official  
**Data:** 07 de Agosto de 2026  
**Tempo Esperado:** 4-6 horas  

---

## 🎯 Objetivo

Transformar uma ideia simples em um **Reel profissional completo** (com script, edição, thumbnail, caption) que está pronto para publicar após aprovação de Judith.

**Entrada:** Tema + Objetivo  
**Saída:** Reel completo (roteiro + edição + thumbnail + caption + aprovação)  
**Aprovação Final:** Judith (humano)

---

## 📋 Fluxo Completo: 13 Etapas

### **Etapa 1: Chief Marketing Officer** 👑

**Agente:** CHIEF_MARKETING_OFFICER  
**Skills:** —  
**Entrada:** Tema ou ideia bruta  
**Duração:** 5 minutos

**Responsabilidades:**
- Definir objetivo estratégico do reel
- Identificar qual produto/oferta será conectado
- Decidir prioridade (urgência, público-alvo)
- Escolher quais agentes participarão
- Validar que faz sentido para negócio

**Saída:**
```markdown
## Objetivo Estratégico do Reel

Tema: [tema]
Objetivo: [vender X / crescer seguidores / estabelecer autoridade]
Produto/Oferta: [qual oferta será conectada]
Público: [qual persona]
Prioridade: [urgência]
KPI Esperado: [métrica de sucesso]
```

**Próximo:** Trend Research Agent

---

### **Etapa 2: Trend Research Agent** 🔍

**Agente:** TREND_RESEARCH  
**Skills:** `/analytics`, `/competitor-profiling`, `/customer-research`  
**Entrada:** Tema + Objetivo  
**Duração:** 15 minutos

**Responsabilidades:**
- Pesquisar ideias similares
- Analisar tendências atuais
- Buscar conteúdos que funcionam
- Levantar dúvidas frequentes do público
- Identificar gaps (o que ninguém está fazendo)

**Saída:**
```markdown
## 10 Ideias Possíveis para o Reel

1. [Ideia 1 + Por que funciona]
2. [Ideia 2 + Por que funciona]
...
10. [Ideia 10 + Por que funciona]

### Recomendação
Ideia [X] tem maior potencial porque: [motivo]

### Referências
- [Conteúdo similar que funciona]
- [Trend atual relevante]
```

**Próximo:** Creative Brief Generator

---

### **Etapa 3: Creative Brief Generator** 📝

**Agente:** BRAND_ARCHITECT  
**Skills:** `/content-strategy`, `/marketing-psychology`  
**Entrada:** Tema escolhido + 10 ideias  
**Duração:** 15 minutos

**Responsabilidades:**
- Transformar ideia em brief claro
- Definir promessa (o que o reel promete)
- Definir público exato
- Escolher emoção principal
- Conectar com brand pillars

**Saída:**
```markdown
## Creative Brief

**Tema:** [tema exato]

**Promessa:** [O que o reel promete ao espectador]

**Público:** [Persona exata]

**CTA Esperado:** [O que queremos que façam]

**Oferta Relacionada:** [Qual produto/ebook]

**Emoção Principal:** [Curiosidade / Inspiração / Riso / Medo / Esperança]

**Brand Pillar:** [Qual pilar de CONTENT_PILLARS.md]

**Restrições:** [O que NÃO fazer]
```

**Próximo:** Hook Architect

---

### **Etapa 4: Hook Architect** 🎣

**Agente:** HOOK_FINDER  
**Skills:** `/marketing-psychology`, `/customer-research`, `/competitor-profiling`  
**Entrada:** Creative Brief  
**Duração:** 20 minutos

**Responsabilidades:**
- Criar 10 hooks diferentes
- Cada hook deve capturar atenção em 1-3 segundos
- Variação de abordagens (curiosidade, medo, riso, etc)
- Testar contra linguagem real do público

**Saída:**
```markdown
## 10 Hooks Possíveis

1. [Hook 1 - Tipo: Curiosidade]
2. [Hook 2 - Tipo: Medo/Urgência]
3. [Hook 3 - Tipo: Riso]
4. [Hook 4 - Tipo: Discrepância]
5. [Hook 5 - Tipo: Prova Social]
6. [Hook 6 - Tipo: Educação]
7. [Hook 7 - Tipo: Pergunta]
8. [Hook 8 - Tipo: Ousadia]
9. [Hook 9 - Tipo: Nostalgia]
10. [Hook 10 - Tipo: Esperança]

### Notas
[Contexto de cada hook]
```

**Próximo:** Hook Scoring Agent

---

### **Etapa 5: Hook Scoring Agent** 🏆

**Agente:** BRAND_ARCHITECT (scoring + validação)  
**Skills:** `/marketing-psychology`, `/content-strategy`  
**Entrada:** 10 Hooks  
**Duração:** 15 minutos

**Responsabilidades:**
- Avaliar cada hook por critérios
- Pontuar (1-10) em cada dimensão
- Escolher hook vencedor
- Justificar decisão

**Saída:**
```markdown
## Hook Scoring — 5 Critérios

| Hook | Curiosidade | Premium | Autenticidade | CLARITY | Score Total |
|------|-------------|---------|---------------|---------|-------------|
| 1 | 9 | 8 | 7 | 9 | 8.2 |
| 2 | 7 | 9 | 8 | 7 | 7.8 |
| 3 | 8 | 7 | 9 | 9 | 8.3 |
| ... | ... | ... | ... | ... | ... |

### Critério CLARITY Explicado
**CLARITY Score (5-10):**
- 5-6 = Ambíguo, pode confundir audiência
- 7-8 = Claro, mas poderia ser melhorado
- 9-10 = Crystal clear, zero ambiguidade em 3 segundos

**Exemplo:**
- Hook: "Drageia artesanal custa tudo"
  - Interpretação 1: "custa muito dinheiro" ❌
  - Interpretação 2: "custa [tempo/técnica]" ✅
  - CLARITY Score: 6 (ambíguo)
  - Ação: Reescrever para clareza

### Hook Vencedor
**Hook [X]: "[Texto do hook]"**

**Por quê:**
- Maior potencial de retenção
- Alinhado com brand (premium)
- Linguagem clara (sem ambiguidade)
- Autêntico, não fake
- Score alto em CLARITY (9-10)
```

**Próximo:** Script Writer

---

### **Etapa 6: Script Writer** ✍️

**Agente:** SCRIPT_WRITER  
**Skills:** `/copywriting`, `/marketing-psychology`, `/customer-research`  
**Entrada:** Hook vencedor + Creative Brief  
**Duração:** 20 minutos

**Responsabilidades:**
- Criar roteiro completo do reel
- Incluir fala (voiceover ou diálogo)
- Indicar texto na tela (on-screen text)
- Marcar tempos e cenas
- Escrever CTA claro

**Saída:**
```markdown
## Roteiro Completo (45-60 segundos)

### [0-3s] HOOK
**On-screen text:** "[Hook text]"
**Voiceover:** "[Hook fala]"
[Scene 1 description]

### [3-15s] EDUCATION / SETUP
**On-screen text:** "[Text]"
**Voiceover:** "[Fala explicando]"
[Scene 2 description]

### [15-35s] PROOF / DEMO
**On-screen text:** "[Texto adicional]"
**Voiceover:** "[Demonstração]"
[Scene 3-4 descriptions]

### [35-45s] CALL TO ACTION — 3 OPTIONS

**OPTION 1: Direct Sales (Se quer conversão rápida)**
Voiceover: "[CTA fala direta - Compre agora]"
Visual: Product + shop link
Best for: Urgência, conversão direta

**OPTION 2: Consultative (Se quer educação + vendas)**
Voiceover: "[CTA conversacional - Clique para saber mais]"
Visual: Product + link to educational content
Best for: Bem Me Qué tone (premium, consultivo)

**OPTION 3: Social Proof (Se quer amplificação)**
Voiceover: "[CTA social - Compartilhe com alguém]"
Visual: Product + share button
Best for: Reach multiplicada, social signals

On-screen text: [Depende da opção escolhida]

### Timing
- Total: 45 segundos
- Hook: 3s
- Body: 30s
- CTA: 5s

### Brand Architect Selects
[Escolhe OPTION 1, 2, ou 3 baseado em brand strategy]
```

**Próximo:** Brand Reviewer (Script Draft Check)

---

### **Etapa 6.5: Brand Reviewer — Script Draft Validation** ⚡ (NOVO)

**Agente:** BRAND_REVIEWER  
**Skills:** `/copy-editing`, `/content-strategy`  
**Entrada:** Roteiro draft (antes de visual direction)  
**Duração:** 10 minutos  
**Objetivo:** Catch ambiguidades e tone issues ANTES de visual planning

**Responsabilidades:**
- Revisar hook para ambiguidades
- Revisar roteiro para clareza de linguagem
- Validar brand alignment (tone)
- Flag qualquer confusão potencial (teste: "someone reading this could think X?")

**Saída:**
```markdown
## Brand Review — Script Draft Validation

**STATUS:**
- ✅ APROVADO - Enviar para Production Manager
- 🔴 REJEIÇÃO - Feedback específico para Script Writer

### Se Aprovado
Sem mudanças necessárias. Prosseguir para Etapa 7.

### Se Rejeição
**Problema Identificado:** [Específico]
**Feedback:** [Claro e acionável]
**Para:** Script Writer revisar antes de Etapa 7
```

**Próximo:** Se aprovado → Production Manager; Se rejeição → Script Writer revisa

---

### **Etapa 7: Production Manager** 📹

**Agente:** VISUAL_CREATIVE  
**Skills:** `/ad-creative`, `/marketing-psychology`  
**Entrada:** Roteiro completo  
**Duração:** 15 minutos

**Responsabilidades:**
- Criar checklist de gravação
- Listar cenas necessárias
- Especificar materiais/produtos
- Definir iluminação
- Sequenciar ordem de gravação (o mais eficiente)

**Saída:**
```markdown
## Production Checklist — Versão Prática

### SCENES TO FILM (Com descrição + duração esperada)

**SCENE 1: [Nome]** (X segundos)
📸 [Descrição: o que aparece na câmera]
- Equipment: [Câmera, lente, luz necessária]
- Duration: Filmar ~Y segundos (5-7 takes esperadas)
- Backup: [Se Scene 1 não funcionar, usar Plan B]
- [CONFIRMAR COM JUDITH]: Você consegue fazer este shot?

**SCENE 2: [Nome]** (X segundos)
📸 [Descrição]
- Equipment: [Spec]
- Duration: ~Y segundos
- Backup: [Plan B]
- [CONFIRMAR COM JUDITH]: Essa localização/iluminação é viável?

[Repetir para cada cena]

### MATERIALS & PROPS

**Necessários:**
- [ ] Produto A (quantidade: X)
- [ ] Produto B (quantidade: X)
- [ ] Props (item 1, item 2, etc)

**Backup (se algo quebrar):**
- [ ] [Backup item 1]
- [ ] [Backup item 2]

### EQUIPMENT

**Necessário:**
- [ ] Camera [Spec]
- [ ] Lens [Spec]
- [ ] Lighting [Tipo: macro ring light / key light / etc]
- [ ] Tripod / Stabilizer
- [ ] Audio [Microfone / Voiceover setup]

[CONFIRMAR COM JUDITH]: Você tem todo este equipamento?

### LOCATION + SETUP

- Location: [Onde filmar]
- Setup Time: ~X minutos
- Filming Time: ~X minutos (total)
- Break Time: ~X minutos
- **Total Time:** ~Z minutos

[CONFIRMAR COM JUDITH]: Esse tempo é realista para você?

### FILMING ORDER (Mais eficiente)

1. [Scene X] — sem talento, melhor iluminação já
2. [Scene Y] — com talento/produto, com setup
3. [Scene Z] — close-ups se necessário
4. [Voiceover] — em casa/estúdio, último

### COMPLEXITY SCORE

Simplicidade: ⭐ [1-5 stars]
- 1-2 stars: Rápido (30-60 min gravação)
- 3 stars: Médio (60-90 min gravação)
- 4-5 stars: Complexo (90+ min gravação)

[CONFIRMAR COM JUDITH]: Essa complexidade te preocupa?

### RISK MANAGEMENT

**Risk 1:** [Cosa que poderia dar errado]
→ Backup: [Plano B]

**Risk 2:** [Cosa que poderia dar errado]
→ Backup: [Plano B]

### Checklist Final

- [ ] Todos os materiais prontos?
- [ ] Equipamento testado?
- [ ] Localização confirmada?
- [ ] Iluminação pronta?
- [ ] Backup plan definido?
```

**Próximo:** Video Editor Director

---

### **Etapa 8: Video Editor Director** 🎥

**Agente:** VIDEO_EDITOR  
**Skills:** `/content-strategy`, `/copy-editing`  
**Entrada:** Roteiro + Production Checklist + VIDEO_CATALOG.md  
**Duração:** 30-45 minutos (edição real) + 15 min brief  
**Guia:** VIDEO_EDITOR_GUIDE.md (como procurar vídeos no catálogo)

**Responsabilidades:**
- Consultar VIDEO_CATALOG.md para vídeos disponíveis
- Criar briefing de edição com arquivos específicos
- Especificar cortes, transições, color grading
- Definir ritmo (pacing)
- Indicar legendas e timing
- Documentar B-roll necessário / faltando
- Definir exportação final

**Processo:**
1. Ler roteiro completo (ETAPA 6 output)
2. Para cada cena, procurar no VIDEO_CATALOG.md
3. Documentar arquivo específico + timeline
4. Se vídeo faltando, sugerir workaround
5. Criar Video Editing Brief com tudo especificado

**Saída:**
```markdown
## Video Editing Brief

### Cortes & Transições
- [0-3s]: Cut sharp (hook impactante)
- [3-15s]: Zoom in (atenção no produto)
- [15-35s]: J-cut (áudio antes de visual)
- [35-45s]: Fade out (suave no CTA)

### Ritmo (BPM)
- Hook: 140 BPM (rápido, urgente)
- Body: 110 BPM (confortável)
- CTA: 130 BPM (chamado)
- Música: [Especificar gênero/mood]

### Legendas
- On-screen text (positions)
- Tamanho fonte
- Cor/sombra
- Timing de cada legenda

### B-roll
- [Scene 1 B-roll suggestions]
- [Scene 2 B-roll suggestions]

### Trilha Sonora
- Background music: [Especificar]
- Sound effects: [List]
- Voiceover: [Recording notes]

### Exportação Final
- Format: MP4
- Resolution: 1080x1920 (vertical, Reels)
- Frame rate: 30fps
- Bitrate: 10-12 Mbps
- File size: ~80-150MB

### Timeline Checklist
- [ ] All cuts done
- [ ] All transitions applied
- [ ] All text overlays added
- [ ] Audio levels balanced
- [ ] Color grading consistent
- [ ] Final review passed
```

**Próximo:** Cover Thumbnail Architect

---

### **Etapa 9: Cover Thumbnail Architect** 🖼️

**Agente:** VISUAL_CREATIVE  
**Skills:** `/ad-creative`, `/marketing-psychology`  
**Entrada:** Roteiro + Brand identity  
**Duração:** 15 minutos

**Responsabilidades:**
- Criar design de capa (thumbnail)
- Texto claro e legível
- Composição que chama atenção
- Variações (testar)

**Saída:**
```markdown
## Cover Thumbnail Design

### Versão Primária
**Texto Principal:** "[Texto impactante]"
**Subtexto:** "[Hook texto]"
**Composição:** [Descrição layout]
**Cores:** [RGB valores]
**Fonts:** [Especificar fontes]
**Imagem/Visual:** [Descrição]

### Versão Secundária (Alternativa)
[Descrição alternativa]

### Especificações Técnicas
- Tamanho: 1080x1920 pixels
- Segurança: Conteúdo importante no centro (área segura)
- Readability: Testado em mobile (pequeno)
- Contraste: Alto (preto/branco or bright colors)

### Brand Alignment
- [x] Cores da marca
- [x] Fonts alinhadas
- [x] Tone alinhado
- [x] Visual consistency
```

**Próximo:** Caption Writer

---

### **Etapa 10: Caption Writer** 📝

**Agente:** CAPTION_WRITER  
**Skills:** `/copywriting`, `/copy-editing`, `/social`  
**Entrada:** Roteiro + Produto + Oferta  
**Duração:** 15 minutos

**Responsabilidades:**
- Escrever caption atrativa
- Adicionar hashtags (quando faz sentido)
- Escrever CTA claro
- Otimizar para Instagram/TikTok

**Saída:**
```markdown
## Caption Final

**Caption:**
[Texto principal da legenda - 1-3 linhas]

[Parágrafo explicativo - opcional]

[Parágrafo de engajamento - pergunta ou curiosidade]

👉 [CTA com link ou "Link na bio"]

**Hashtags:**
#[Hashtag1] #[Hashtag2] #[Hashtag3] #[Hashtag4]
[+3-5 hashtags relevantes]

**CTA Button (se aplicável):**
[Link para: Kiwify / Email / WhatsApp]

### Optimization Notes
- Primeira linha é hook (primeiros caracteres importantes)
- Emojis para visual break
- Hashtags no final (melhora engagement)
- CTA claro e direto
```

**Próximo:** Brand Reviewer

---

### **Etapa 11: Brand Reviewer** ✅

**Agente:** BRAND_REVIEWER  
**Skills:** `/copy-editing`, `/content-strategy`, `/marketing-psychology`  
**Entrada:** Tudo acima (Roteiro, Edição Brief, Thumbnail, Caption)  
**Duração:** 20 minutos

**Responsabilidades:**
- Revisar tom (alinhado com VOICE.md?)
- Revisar clareza (está claro?)
- Revisar identidade (parece Bem Me Qué?)
- Revisar consistência (com histórico?)
- Validar promessa (está cumprida?)
- Validar CTA (está claro e funcional?)

**Checklist de Revisão:**
```markdown
## Brand Review Checklist

### Ton & Linguagem
- [x] Ton alinhado com VOICE.md (premium, conversacional)?
- [x] Linguagem alinhada com AUDIENCE.md?
- [x] Sem typos ou erros gramaticais?

### Identidade
- [x] Visual alinhado com VISUAL_IDENTITY.md?
- [x] Cores da marca respeitadas?
- [x] Fonts corretas?

### Conteúdo
- [x] Promessa está clara?
- [x] CTA está claro e funcional?
- [x] Oferta está conectada?
- [x] Sem claims falsos?

### Consistência
- [x] Alinhado com conteúdo anterior?
- [x] Segue CONTENT_PILLARS.md?
- [x] Sem contradições?

### Aprovação
- [x] ✅ APROVADO - Enviar para Quality Control
- [ ] 🔄 PRECISA REVISÃO - Feedback [específico para qual agente]
- [ ] ❌ REJEITADO - Motivo [crítico]
```

**Saída:**
```markdown
## Revisão Final - Brand Reviewer

**STATUS: ✅ APROVADO**

### Feedbacks (se houver)
[Nenhum, ou feedback específico]

### Pronto para?
Quality Control Agent
```

**Próximo:** Quality Control Agent

---

### **Etapa 12: Quality Control Agent** 🔍

**Agente:** BRAND_REVIEWER (QC validation)  
**Skills:** Protocol check (AGENT_COLLABORATION_PROTOCOL.md)  
**Entrada:** Documentação completa  
**Duração:** 10 minutos

**Responsabilidades:**
- Validar que todas as 12 etapas foram executadas
- Validar que nenhum agente foi ignorado
- Validar que saída está completa
- Validar que documentação é clara

**Checklist QC:**
```markdown
## Quality Control Checklist

### Workflow Completeness
- [x] Etapa 1: CMO Objetivo ✅
- [x] Etapa 2: Trend Research Ideas ✅
- [x] Etapa 3: Creative Brief ✅
- [x] Etapa 4: Hooks (10) ✅
- [x] Etapa 5: Hook Scoring ✅
- [x] Etapa 6: Script ✅
- [x] Etapa 7: Production Checklist ✅
- [x] Etapa 8: Editing Brief ✅
- [x] Etapa 9: Thumbnail ✅
- [x] Etapa 10: Caption ✅
- [x] Etapa 11: Brand Review ✅

### Documentation Quality
- [x] Cada etapa tem "Saída" clara?
- [x] Agentes estão documentados?
- [x] Tempos estão especificados?
- [x] Nada foi pulado?

### Approval Chain
- [x] CMO aprovou objetivo?
- [x] Brand Reviewer aprovou conteúdo?
- [x] Nenhum conflito não-resolvido?
```

**Saída:**
```markdown
## Quality Control Result

**STATUS: ✅ PROCESSO VALIDADO**

Todas as 12 etapas foram executadas.
Documentação está completa.
Pronto para aprovação de Judith.

**Enviando para Judith...**
```

**Próximo:** Judith

---

### **Etapa 13: Judith (Aprovação Humana)** 👩‍💼

**Agente:** JUDITH (Human Decision Maker)  
**Skills:** Human judgment  
**Entrada:** Judith Decision Card (1 página) + Todos os 12 outputs anteriores (referência)  
**Duração:** 2-5 minutos (Decision Card = -60% tempo)

**Responsabilidades:**
- Ler Judith Decision Card (essencial — 2 min)
- Revisar confirmações necessárias ([CONFIRMAR COM JUDITH])
- Confirmar que viabilidade é realista
- Tomar decisão final
- **Nunca publicar automaticamente**

**Entrada:**
```markdown
### Judith Decision Card
[Ver JUDITH_DECISION_CARD_TEMPLATE.md para estrutura]

Contém:
- Hook + Promessa exata
- Roteiro estruturado (não prosa completa)
- Checklist prático (o que gravar)
- Materiais necessários
- [CONFIRMAR COM JUDITH] checklist
- Approvals de todos os agentes
- Quick decision form
```

**Decisão Final:**
```markdown
## Aprovação Humana - Judith

**Análise:**
[Judith lê Decision Card em ~2 min]
[Judith confirma [CONFIRMAR COM JUDITH] checklist]

**Decisão:**
- ✅ APROVADO - Publicar [Data/Hora]
- ❌ REJEITADO - Motivo [Específico]
- 🔄 COM MUDANÇAS - Feedback [Para qual agente]

**Se Aprovado:**
Reel vai ao ar em [Data/Hora]
Métricas a acompanhar: [KPIs]

**Se Rejeitado/Mudanças:**
[Agente específico faz revisão]
[Volta ao workflow em etapa apropriada]
[Re-submit via Judith Decision Card]

### Observação Importante
Judith nunca é saltada.
Mesmo com pressão, essa aprovação é obrigatória.
Nenhum reel publica sem Judith confirmar.
```

---

## 📊 Sequência Visual

```
                              🎬 CREATE_REEL_FULL
                                      ↓
                    ┌─────────────────────────────────┐
                    │  1. CMO - Objetivo Estratégico  │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 2. Trend Research - 10 Ideias   │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 3. Creative Brief - Briefing    │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 4. Hook Architect - 10 Hooks    │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 5. Hook Scoring - Hook Winner   │
                    │    (com CLARITY Score)          │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 6. Script Writer - Roteiro      │
                    │    (3 CTA Options)              │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 6.5 Brand Reviewer - Script     │
                    │     Draft Validation ⭐ NOVO    │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 7. Production Manager - Checklist│
                    │    (Prático + [CONFIRMAR])      │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 8. Video Editor - Edição Brief  │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 9. Thumbnail Architect - Capa   │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 10. Caption Writer - Legenda    │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 11. Brand Reviewer - Validação  │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 12. Quality Control - QC Check  │
                    └─────────────────────────────────┘
                                      ↓
                    ┌─────────────────────────────────┐
                    │ 13. Judith - Decision Card      │
                    │     (2 min approval) ⭐ OTIMIZADO│
                    └─────────────────────────────────┘
                                      ↓
                           ✅ REEL PRONTO PARA
                              PUBLICAR
```

---

## 📋 Tempo Total Esperado

| Etapa | Agente | Duração | Nota |
|-------|--------|---------|------|
| 1 | CMO | 5 min | — |
| 2 | Trend Research | 15 min | — |
| 3 | Creative Brief | 15 min | — |
| 4 | Hook Architect | 20 min | — |
| 5 | Hook Scoring | 15 min | Agora com CLARITY Score |
| 6 | Script Writer | 20 min | Oferece 3 CTA options |
| **6.5** | **Brand Reviewer** | **10 min** | **NOVO — Pre-check de ambiguidades** |
| 7 | Production Manager | 15 min | Agora mais prático + [CONFIRMAR COM JUDITH] |
| 8 | Video Editor | 45 min | — |
| 9 | Thumbnail Architect | 15 min | — |
| 10 | Caption Writer | 15 min | — |
| 11 | Brand Reviewer | 20 min | — |
| 12 | Quality Control | 10 min | — |
| 13 | Judith | 2-5 min | **OTIMIZADO — Usa Decision Card** |
| **TOTAL** | **—** | **3.5-5 horas** | **Tempo reduzido (-30 min) + qualidade melhorada** |

---

## 🔗 Agentes Envolvidos

| Etapa | Agente | Agente Real | Skills |
|-------|--------|-------------|--------|
| 1 | CMO | CHIEF_MARKETING_OFFICER | — |
| 2 | Trend Research | TREND_RESEARCH | `/analytics`, `/competitor-profiling`, `/customer-research` |
| 3 | Creative Brief | BRAND_ARCHITECT | `/content-strategy`, `/marketing-psychology` |
| 4 | Hook Architect | HOOK_FINDER | `/marketing-psychology`, `/customer-research`, `/competitor-profiling` |
| 5 | Hook Scoring | BRAND_ARCHITECT | `/marketing-psychology`, `/content-strategy` |
| 6 | Script Writer | SCRIPT_WRITER | `/copywriting`, `/marketing-psychology`, `/customer-research` |
| 7 | Production Manager | VISUAL_CREATIVE | `/ad-creative`, `/marketing-psychology` |
| 8 | Video Editor | VIDEO_EDITOR | `/content-strategy`, `/copy-editing` |
| 9 | Thumbnail | VISUAL_CREATIVE | `/ad-creative`, `/marketing-psychology` |
| 10 | Caption Writer | CAPTION_WRITER | `/copywriting`, `/copy-editing`, `/social` |
| 11 | Brand Reviewer | BRAND_REVIEWER | `/copy-editing`, `/content-strategy`, `/marketing-psychology` |
| 12 | Quality Control | BRAND_REVIEWER | Protocol check |
| 13 | Judith | JUDITH | Human decision |

---

## ✅ Regras Vinculantes

1. **Nenhum pulo de etapa** → Todas as 13 etapas são obrigatórias
2. **Nenhuma rejeição silenciosa** → Feedback sempre claro
3. **Escalada em conflito** → CMO decide
4. **Documentação obrigatória** → Cada etapa tem "Saída" clara
5. **Aprovação de Judith é final** → Nunca publicar automaticamente
6. **Ordem sequencial** → Não pode pular agentes

---

## 🚀 Status: Pronto para Usar

**Este workflow está 100% documentado e pronto para:**
- ✅ Ser testado com agentes reais
- ✅ Ser iterado baseado em feedback
- ✅ Ser escalado para produção
- ✅ Servir como base para outros workflows

**Próximo passo:** Testar CREATE_REEL_FULL com um exemplo real.

---

*Workflow: CREATE_REEL_FULL*  
*Project: Judith AI Creative Team*  
*Brand: Bem me Qué*  
*Version: 1.0 Official*
