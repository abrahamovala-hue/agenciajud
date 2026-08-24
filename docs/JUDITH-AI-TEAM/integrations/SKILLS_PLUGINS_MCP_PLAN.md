# Plano de Integração: Skills, Plugins & MCPs

## Objetivo
Conectar todos os agentes e workflows do Judith AI Team ao Antigravity e Claude Code via Skills, Plugins e/ou MCPs.

## Arquitetura Proposta

```
┌─────────────────────────────────────────────┐
│       CLAUDE CODE / ANTIGRAVITY              │
│  (Interface do usuário final - Judith)       │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
   ┌────────┐ ┌─────────┐ ┌──────────┐
   │ Skills │ │ Plugins │ │   MCP    │
   │(Claude)│ │(Custom) │ │ Servers  │
   └────────┘ └─────────┘ └──────────┘
        │          │          │
        └──────────┼──────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
   ┌──────────────┐    ┌──────────────┐
   │ Agent Layer  │    │ Knowledge DB │
   │(Workflows)   │    │ (Brand Data) │
   └──────────────┘    └──────────────┘
```

## 1. Skills (Claude Code)

Skills são "receitas" reutilizáveis dentro do Claude Code.

### Skills Propostas

```
/judith-create-reel
  → Executa workflow CREATE_REELS
  → Pede: tema, tipo, objetivo
  → Retorna: hooks + roteiro + legenda + visual brief

/judith-create-campaign
  → Executa workflow CREATE_CAMPAIGN
  → Pede: produto, objetivo, timeline
  → Retorna: estratégia + calendário + conteúdo

/judith-repurpose-content
  → Executa workflow REPURPOSE_CONTENT
  → Pede: arquivo/link do conteúdo
  → Retorna: 5+ formatos diferentes

/judith-analyze-performance
  → Conecta com métricas
  → Analisa o que funcionou

/judith-check-brand
  → Valida conteúdo vs. brand guidelines
```

### Como Implementar
- Pasta: `.claude/skills/judith/`
- Arquivo: `SKILL.md` para cada skill
- Cada skill chama workflow + agentes relevantes

## 2. MCP Servers

MCPs são "extensões" que fornecem dados e tools para Claude.

### MCPs Propostos

#### A. Brand Knowledge MCP
**Objetivo:** Fornecer dados de marca em tempo real

**Resources:**
- `brand://voice` → VOICE.md
- `brand://audience` → AUDIENCE.md
- `brand://products` → PRODUCTS.md
- `brand://content-pillars` → CONTENT_PILLARS.md
- `brand://visual-identity` → VISUAL_IDENTITY.md

**Tools:**
- `validate_against_brand(content)` → Verifica se conteúdo está alinhado
- `get_brand_context(topic)` → Retorna contexto relevante

#### B. Workflow MCP
**Objetivo:** Executar workflows e gerenciar outputs

**Resources:**
- `workflow://create-reel`
- `workflow://create-campaign`
- `workflow://repurpose-content`

**Tools:**
- `start_workflow(type, inputs)` → Inicia workflow
- `get_workflow_status(workflow_id)` → Status
- `save_content(format, data)` → Salva output

#### C. Content Library MCP
**Objetivo:** Acessar biblioteca de conteúdo criado

**Resources:**
- `content://hooks` → Biblioteca de hooks
- `content://scripts` → Scripts anteriores
- `content://approved` → Conteúdo aprovado

**Tools:**
- `search_content(query)` → Busca conteúdo anterior
- `save_hook(hook_text, performance)` → Salva novo hook
- `get_similar_campaigns(topic)` → Retorna campanhas similares

#### D. Metrics MCP
**Objetivo:** Acessar e analisar métricas

**Resources:**
- `metrics://instagram-performance`
- `metrics://campaign-results`
- `metrics://hook-performance`

**Tools:**
- `get_post_performance(post_id)` → Métricas do post
- `analyze_trends()` → Análise de tendências
- `compare_performance(campaign1, campaign2)`

## 3. Fluxo Integrado

### Exemplo: Criar uma campanha

```
1. Usuário no Claude Code:
   /judith-create-campaign "Vender ebook de recheios"

2. Skill ativa e:
   - Chama Brand Knowledge MCP (contexto)
   - Executa BRAND_STRATEGIST agent
   - Executa MARKETING_DIRECTOR agent
   - Chama Workflow MCP (salva outputs)
   - Chama Content Library MCP (busca campanhas similares)
   - Retorna para usuário: estratégia + calendário + conteúdo

3. Usuário aprova/edita

4. Conteúdo vai para `content/campaigns/approved/`

5. Metrics MCP rastreia performance quando publicado
```

## 4. Configuração no Antigravity

No Antigravity, você vai:

1. **Criar um Agente Principal** chamado "Judith Creative Director"
   - Input: Descrição da necessidade
   - Output: Conteúdo completo + calendário

2. **Conectar Sub-Agentes** para cada specialist:
   - BRAND_STRATEGIST
   - SCRIPT_WRITER
   - CAPTION_WRITER
   - etc.

3. **Configurar Knowledge Base**
   - Apontar para pasta `brand/`
   - Apontar para pasta `sources/`

4. **Ativar MCPs**
   - Brand Knowledge MCP
   - Workflow MCP
   - Content Library MCP
   - Metrics MCP

## 5. Implementação (Próximas Semanas)

### Semana 1: Foundation
- [ ] Criar MCPs básicos (arquivos `.md` + configs)
- [ ] Testar Brand Knowledge MCP
- [ ] Criar Skills base

### Semana 2: Workflows
- [ ] Conectar Workflow MCP
- [ ] Testar CREATE_REELS workflow
- [ ] Testar CREATE_CAMPAIGN workflow

### Semana 3: Integration
- [ ] Ativar no Antigravity
- [ ] Testar fluxos end-to-end
- [ ] Refinement com feedback

### Semana 4: Optimization
- [ ] Metrics rastreamento
- [ ] Performance analysis
- [ ] V1 stable

## 6. Arquivos Necessários

Já temos:
- ✅ Brand documentation
- ✅ Agents definitions
- ✅ Workflows

Faltam:
- [ ] MCP configurations
- [ ] Skills files
- [ ] Antigravity integration configs
- [ ] Knowledge base setup

## 7. Próximos Passos

1. Você quer começar pelos **Skills** ou pelos **MCPs**?
2. Você tem acesso ao **Antigravity** para testar?
3. Qual é seu **deadline** para ter MVP rodando?
