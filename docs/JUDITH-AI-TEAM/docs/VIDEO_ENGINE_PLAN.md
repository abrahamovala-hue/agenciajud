# 🎬 VIDEO ENGINE PLAN — Geração Automática de Rascunhos de Reels

> **Data:** 08 de Agosto de 2026  
> **Status:** 📝 Planejamento  
> **Objetivo:** Transformar vídeos brutos + roteiros em rascunhos editados para iteração com Judith

---

## 🎯 Visão Geral

O **Video Engine** é um pipeline que reduz o tempo de edição manual de Reels através de automação inteligente.

### Fluxo Atual (ANTES)

```
Roteiro Pronto
    ↓
Judith Filma (30min)
    ↓
Judith Edita (2-3h MANUAL)
    ↓
Reel Pronto
```

### Fluxo Proposto (DEPOIS)

```
Roteiro Pronto (CREATE_REEL_FULL ETAPA 6)
    ↓
Judith Filma (30min)
    ↓
Video Editor especifica edição (CREATE_REEL_FULL ETAPA 8)
    ↓
VIDEO ENGINE gera rascunho (30-45min AUTOMÁTICO)
    ↓
Judith revisa + refina (30-60min ITERAÇÃO)
    ↓
Reel Pronto
```

**Economia:** 1.5-2 horas de edição manual por reel  
**Objetivo:** 5-10 reels/semana em vez de 2-3

---

## 📊 Pipeline Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     VIDEO ENGINE                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  INPUT LAYER                                           │
│  ├─ Raw Videos (MP4/MOV)                              │
│  ├─ Roteiro (Markdown com timestamps)                 │
│  └─ Edit Spec (Video Editor JSON)                     │
│                                                         │
│  PROCESSING LAYER                                      │
│  ├─ Video Segmentation (cortar clips por cena)        │
│  ├─ Audio Extraction (extrair áudio original)         │
│  ├─ Text Overlay (adicionar textos da tela)          │
│  ├─ Transition Engine (aplicar transições)            │
│  ├─ Music & SFX (sincronizar áudio)                  │
│  └─ Effects Library (aplicar efeitos visuais)         │
│                                                         │
│  OUTPUT LAYER                                          │
│  ├─ Draft Video (rascunho MP4 em baixa res)          │
│  ├─ Composition JSON (dados para refino)              │
│  └─ Feedback Template (para iteração)                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Fase 1: Setup Essencial

### Ferramentas Necessárias

| Ferramenta | Propósito | Status |
|-----------|----------|--------|
| **FFmpeg** | Edição de vídeo (recortes, transições, overlay) | ⏳ Instalar |
| **MoviePy** (Python) | Automação de edição (script-based) | ⏳ Instalar |
| **ImageMagick** | Criação de overlays de texto | ⏳ Instalar |
| **Pydub** (Python) | Processamento de áudio | ⏳ Instalar |

### Instalação (Windows)

```bash
# 1. FFmpeg
choco install ffmpeg  # Se tem Chocolatey
# OU: Baixar de https://ffmpeg.org/download.html

# 2. Python dependencies
pip install moviepy pydub pillow imagemagick

# 3. Validar instalação
ffmpeg -version
python -c "import moviepy; print(moviepy.__version__)"
```

### Estrutura de Diretórios

```
JUDITH-AI-TEAM/
├── assets/
│   └── videos/
│       ├── raw/           (vídeos brutos gravados)
│       │   └── [categoria]/
│       ├── drafts/        (rascunhos gerados)
│       │   └── [reel-id]/
│       ├── approved/      (aprovados por Judith)
│       └── published/     (já publicados)
│
├── engine/
│   ├── video_editor.py    (motor de edição)
│   ├── audio_processor.py (processador de áudio)
│   ├── config.py          (configurações)
│   └── templates/         (templates de efeitos)
│
└── workflows/
    └── CREATE_REEL_FULL.md (integrado com ETAPA 8)
```

---

## 🔄 Fase 2: Fluxo de Dados

### 2.1 Input Specification (do Video Editor)

Quando o **Video Editor** (ETAPA 8 de CREATE_REEL_FULL) termina, cria um JSON:

```json
{
  "reel_id": "reel-001-ruby-launch",
  "title": "Chocolate Ruby — Lançamento Premium",
  "duration_target": "60s",
  "template": "Tutorial",
  
  "video_source": {
    "raw_video": "assets/videos/raw/ruby/ruby-launch-2026-08-08.mp4",
    "duration": "3:45",
    "fps": 30,
    "resolution": "1080x1920"
  },
  
  "edit_plan": {
    "scenes": [
      {
        "scene_id": 1,
        "name": "Hook (0-3s)",
        "start_time": "0:00",
        "end_time": "0:03",
        "clip_type": "b-roll",
        "visual_notes": "Close-up of ruby chocolate, dramatic lighting",
        "transition": "cut",
        "effects": ["zoom-in", "color-grade-warm"],
        "text_overlay": "Chocolate Ruby — O chocolate mais raro do mundo",
        "text_style": "bold-white-outline",
        "music": "dramatic-buildup.mp3",
        "music_start": "0:00",
        "sfx": ["sparkle-sound.mp3"]
      },
      {
        "scene_id": 2,
        "name": "Introduction (3-10s)",
        "start_time": "0:03",
        "end_time": "0:10",
        "clip_type": "talking-head",
        "visual_notes": "Judith explaining origin of ruby chocolate",
        "transition": "fade",
        "text_overlay": "Descoberto em 2004, um dos 4 tipos de chocolate",
        "text_style": "thin-white-lowercase",
        "music": "uplifting-bg.mp3",
        "music_start": "0:03"
      },
      {
        "scene_id": 3,
        "name": "Technique (10-35s)",
        "start_time": "0:10",
        "end_time": "0:35",
        "clip_type": "b-roll",
        "visual_notes": "Process footage of making ruby chocolate",
        "transition": "slide-left",
        "effects": ["slow-motion-0.5x"],
        "text_overlay": "O segredo está no processamento especial",
        "music": "energetic-beat.mp3",
        "sfx": ["ambient-sound.mp3"]
      },
      {
        "scene_id": 4,
        "name": "CTA (55-60s)",
        "start_time": "0:55",
        "end_time": "1:00",
        "clip_type": "product-shot",
        "transition": "zoom-out",
        "text_overlay": "Bem Me Qué Premium — Link na bio",
        "text_style": "bold-white-large",
        "music": "outro-music.mp3",
        "sfx": ["success-chime.mp3"]
      }
    ]
  },
  
  "audio_config": {
    "main_music": "dramatic-buildup-uplifting-beat-outro.mp3",
    "voiceover": "none",
    "sound_effects": true,
    "background_ambience": "soft-retail-bg.mp3",
    "master_volume": 1.0
  },
  
  "quality_settings": {
    "output_resolution": "1080x1920",
    "bitrate": "5000k",
    "format": "mp4",
    "draft_quality": "medium",
    "iterative_mode": true
  },
  
  "feedback_template": {
    "questions": [
      "O pacing está bom? (rápido/normal/lento)",
      "As transições são suaves?",
      "Os textos são legíveis?",
      "A música combina com o vídeo?",
      "O CTA é claro?"
    ]
  }
}
```

### 2.2 Video Engine Processing

O motor recebe o JSON e:

```
1. LOAD
   └─ Carrega vídeo bruto
   └─ Valida timestamps e durações

2. SEGMENT
   └─ Divide em cenas (por timestamps)
   └─ Extrai áudio original

3. COMPOSE
   └─ Monta cada cena com:
      - Visual (clip + efeitos + zoom/pan)
      - Texto (overlay de texto)
      - Áudio (música + SFX)
      - Transição

4. RENDER
   └─ Renderiza em qualidade "draft" (rápido)
   └─ Gera arquivo MP4

5. OUTPUT
   └─ Salva em assets/videos/drafts/[reel-id]/
   └─ Cria JSON de feedback
```

### 2.3 Output Structure

```
assets/videos/drafts/reel-001-ruby-launch/
├── draft-v1.mp4              (vídeo rascunho)
├── draft-v1-low-res.mp4      (preview para mobile)
├── composition.json          (dados da composição)
├── feedback-template.md      (perguntas para Judith)
├── render-log.txt            (log de processamento)
└── assets/
    ├── text-overlays/        (imagens de texto)
    ├── audio/                (áudio processado)
    └── effects/              (efeitos aplicados)
```

---

## ✨ Fase 3: Integração com Workflows Existentes

### 3.1 Onde Conecta no CREATE_REEL_FULL

```
ETAPA 8 — Video Editor Specification
    ↓ (OUTPUT: edit_spec.json)
    ↓
[NEW] ETAPA 8.5 — VIDEO ENGINE DRAFT GENERATION
    ├─ Input: Raw video + edit_spec.json
    ├─ Process: Gera rascunho automaticamente
    ├─ Output: draft-v1.mp4 + feedback template
    ├─ Time: 30-45min (automático)
    └─ Validation: Judith pode revisar e iterar

ETAPA 9 — Thumbnail Creator (sem mudança)
    ↓
ETAPA 10 — Caption Writer (sem mudança)
    ↓
ETAPA 11 — Brand Reviewer (sem mudança)
    ↓
ETAPA 12 — Quality Control (sem mudança, mas pode validar com draft)
    ↓
ETAPA 13 — Judith Approval (agora com draft pronto)
```

### 3.2 Modificação em CREATE_REEL_FULL.md

**NOVA ETAPA:** "ETAPA 8.5 — Video Engine Draft Generation"

```markdown
### ETAPA 8.5 — Video Engine Draft Generation (30-45 min)

**Responsável:** Video Engine (automático) + Judith (validação)

**Input:** 
- Raw video file (MP4/MOV)
- Edit specification (JSON do Video Editor)

**Process:**
1. Video Engine carrega especificação
2. Processa vídeo bruto
3. Aplica edições (cortes, transições, textos, efeitos)
4. Sincroniza com áudio
5. Renderiza em qualidade "draft" (mais rápido)
6. Gera feedback template

**Output:**
- draft-v1.mp4 (vídeo rascunho)
- feedback-template.md (perguntas para Judith)
- composition.json (dados técnicos)

**Judith Decision Point:**
- ✅ "Looks good, move to ETAPA 9"
- 🔄 "Needs adjustment" → Feedback → Regenerate
- ❌ "Start over" → Back to ETAPA 8 (Video Editor)

**Time-saver:** Elimina 1.5-2h de edição manual por Judith
```

---

## 🎥 Fase 4: Modo Iterativo

### 4.1 Feedback Loop

```
[INITIAL RENDER]
     ↓
Judith assiste draft-v1.mp4
     ↓
Judith preenche feedback-template.md:
  "Pacing: muito rápido nos primeiros 5s"
  "Transição para cena 2: muito abrupta"
  "Texto 'segredo': aparece muito cedo"
  "Música: boa!"
     ↓
Video Engine recebe feedback
     ↓
Cria iteração (draft-v2.mp4) com ajustes:
  - Aumenta duração de cenas iniciais
  - Adiciona fade entre cenas 1-2
  - Atrasa appearance de texto
     ↓
Judith assiste draft-v2.mp4
     ↓
[APROVADO] → Segue para ETAPA 9
ou
[PRECISA AJUSTE] → Nova iteração
```

### 4.2 Iteração Rápida

**Velocidade de iteração:**
- Primeira renderização: 30-45min
- Iteração 2: 15-20min (ajustes menores)
- Iteração 3: 10-15min (refinamentos)

**Total esperado:** 1h 15min para chegar a "aprovado"  
**Economia:** 1h 45min de edição manual

---

## 📋 Fase 5: Implementação

### 5.1 Sprint 1 — Setup Base (SEMANA 1)

```
[ ] Instalar FFmpeg + MoviePy + dependencies
[ ] Criar estrutura de diretórios
[ ] Codificar video_editor.py (básico)
    - LoadVideo()
    - SegmentByTimestamp()
    - ApplyTextOverlay()
    - ApplyTransition()
[ ] Testar com 1 vídeo de teste
```

### 5.2 Sprint 2 — Audio & Effects (SEMANA 2)

```
[ ] Codificar audio_processor.py
    - ExtractAudio()
    - SyncMusic()
    - AddSFX()
[ ] Codificar effects.py
    - ZoomIn/ZoomOut
    - ColorGrade
    - SlowMotion
    - Fade/Cut/Slide
[ ] Testar com áudio completo
```

### 5.3 Sprint 3 — Integration & Testing (SEMANA 3)

```
[ ] Integrar com CREATE_REEL_FULL workflow
[ ] Criar feedback template generator
[ ] Testar iteração (v1 → v2 → v3)
[ ] Documentar em CREATE_REEL_FULL.md
[ ] Primeiro teste real com Judith (Ruby Reel)
```

### 5.4 Sprint 4 — Optimization (SEMANA 4)

```
[ ] Otimizar tempo de renderização
[ ] Adicionar templates de efeitos prontos
[ ] Criar presets de qualidade (draft/medium/final)
[ ] Documentar em VIDEO_ENGINE_MANUAL.md
```

---

## 🎯 Casos de Uso

### Caso 1: Reel Simples (Tutorial)

**Entrada:**
- Vídeo de Judith explicando técnica (3 min)
- Roteiro com timestamps (ETAPA 6)
- Edit spec (ETAPA 8)

**Saída esperada:**
- Rascunho em 35min
- Iteração 1: 15min (ajustar pacing)
- Aprovado em 1h

**Tempo economizado:** 1h 30min

### Caso 2: Reel Complexo (Multi-cena)

**Entrada:**
- 4 vídeos diferentes (Judith + B-roll + Product shots)
- Roteiro detalhado (4 cenas)
- Edit spec complexa (efeitos + música customizada)

**Saída esperada:**
- Rascunho em 45min
- Iteração 1: 20min (sincronizar áudio)
- Iteração 2: 15min (cores + efeitos)
- Aprovado em 1h 20min

**Tempo economizado:** 1h 40min

### Caso 3: Reel Repurposed (de REPURPOSE_CONTENT)

**Entrada:**
- 1 reel já aprovado
- Transformação simples (ex: para TikTok)
- Edit spec leve

**Saída esperada:**
- Rascunho em 20min
- Aprovado em 30min

**Tempo economizado:** 1h

---

## 📊 Métricas de Sucesso

| Métrica | Target | Fase |
|---------|--------|------|
| Tempo de renderização (primeira) | <45 min | Sprint 2 |
| Tempo de iteração (v2) | <20 min | Sprint 2 |
| Taxa de aprovação (primeira) | 60%+ | Sprint 3 |
| Taxa de aprovação (iteração 2) | 95%+ | Sprint 3 |
| Economia de tempo/reel | 1.5-2h | Sprint 3 |
| Reels/semana (com engine) | 5-10 | Sprint 4 |
| Qualidade (subjetiva) | 8/10+ | Sprint 4 |

---

## ⚠️ Limitações & Workarounds

### Limitação 1: Qualidade de Renderização

**Problema:** Renderizar em qualidade final (4k) leva 3-4h

**Solução:** 
- Renderizar em "draft mode" (1080x1920, comprimido)
- Usar "final mode" apenas quando aprovado
- Draft é suficiente para feedback

### Limitação 2: Efeitos Complexos

**Problema:** Alguns efeitos (motion tracking, AI enhancement) são difíceis de automatizar

**Solução:**
- Video Engine cobre 80% dos casos comuns
- Efeitos complexos: Judith faz manualmente na iteração final
- Ou: Encaminha para especialista se necessário

### Limitação 3: Áudio Sincronizado

**Problema:** Sincronizar áudio com vídeo editado é desafiador

**Solução:**
- Use timestamps e markers no edit spec
- Video Editor especifica exatamente quando cada áudio começa
- Video Engine respeita timestamps rigorosamente

### Limitação 4: Customização Avançada

**Problema:** Cada brand/creator tem preferências únicas

**Solução:**
- Criar "presets" de estilo (minimalist, energetic, educational)
- Judith escolhe preset no roteiro
- Video Engine aplica automáticamente

---

## 🚀 Timeline Realista

| Fase | Duração | Status |
|------|---------|--------|
| Sprint 1 — Setup | 1 semana | ⏳ Próxima |
| Sprint 2 — Audio & Effects | 1 semana | ⏳ Semana 2 |
| Sprint 3 — Integration | 1 semana | ⏳ Semana 3 |
| Sprint 4 — Optimization | 1 semana | ⏳ Semana 4 |
| **TOTAL** | **4 semanas** | **Setembro** |

**Momento de ativação:**
- Após Phase 3a estar estável (2-3 reels reais criados)
- Provavelmente final de Agosto/início de Setembro
- Paralelamente com produção assistida

---

## 🎓 Conclusão

O **Video Engine** é o próximo grande salto de eficiência para Judith.

**Benefícios:**
- ✅ Reduz 1.5-2h de edição manual por reel
- ✅ Permite iteração rápida e transparente
- ✅ Aumenta qualidade (efeitos consistentes)
- ✅ Escala para 5-10 reels/semana
- ✅ Mantém aprovação humana de Judith (não é automático!)

**Próximo passo:** Iniciar **Phase 3a** com produção real assistida, em paralelo começar **Video Engine Sprint 1** quando recursos permitirem.

---

**Documentação:** docs/VIDEO_ENGINE_PLAN.md  
**Status:** 📝 Planejamento  
**Revisor:** Judith Kolker  
**Data:** 08 de Agosto de 2026
