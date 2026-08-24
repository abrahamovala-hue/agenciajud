# Judith AI Business Team — V2

> Evolução documentada de **Judith AI Creative Team V1** para **Judith AI Business Team V2**.
> V1 não foi alterado. Este diretório é uma árvore paralela e rastreável.

---

## Relação com V1

| | V1 | V2 |
|---|---|---|
| Localização | `docs/JUDITH-AI-TEAM/` | `docs/JUDITH-AI-TEAM-V2/` |
| Escopo | Criação de conteúdo (Reels, campanhas, revisão) | Negócio completo: conteúdo + growth/vendas + suporte + inteligência + governança de qualidade e aprendizado |
| Protocolo | `agents/AGENT_COLLABORATION_PROTOCOL.md` (não sobrescrito) | `protocol/AGENT_COLLABORATION_PROTOCOL_V2.md` |
| Nº de agentes | 12 + CMO + Quality Control (14 nomeados) | 21 (ver `AGENT_ROSTER.md`) |
| Status | Documentação testada 3x em simulação (ver `STATUS.md` do V1) | Documentação nova; implementação Agno parcial (ver `STATUS_V2.md`) |

**V1 continua sendo a fonte de verdade para o que já foi testado** (o workflow `CREATE_REEL_FULL`, o protocolo de aprovação humana, os 12 agentes originais). V2 não descarta esse conhecimento — ele evolui (ver `AGENT_ROSTER.md`, coluna "Origem") e adiciona os papéis que faltavam para o sistema cobrir o negócio inteiro (vendas, CRM, suporte, insights, governança de aprendizado), não só produção de conteúdo.

---

## Estrutura

```
JUDITH-AI-TEAM-V2/
├── README.md                              ← este arquivo
├── AGENT_ROSTER.md                        ← lista dos 21 agentes, tier, origem, status
├── STATUS_V2.md                           ← o que é doc vs o que roda em Agno
│
├── agents/                                ← ficha completa de cada um dos 21 agentes
│   ├── 01-cmo.md
│   ├── 02-brand-architect.md
│   ├── ... (ver AGENT_ROSTER.md para a lista completa)
│   └── 21-quality-control-agent.md
│
├── protocol/
│   ├── AGENT_COLLABORATION_PROTOCOL_V2.md ← como os agentes colaboram
│   └── AGENT_HANDOFF_CONTRACT.md          ← formato estruturado de handoff (AgentHandoff)
│
├── workflows/
│   └── WORKFLOWS_V2_INDEX.md              ← todos os workflows V2 documentados
│
└── models/
    ├── MEMORY_MODEL.md                    ← Session / Customer / Business / Agent Performance
    ├── LEARNING_EVALS_MODEL.md            ← ciclo de aprendizado controlado (nunca automático)
    ├── AUTONOMY_MODEL.md                  ← LOW RISK / COMMERCIAL / SENSITIVE / PUBLICATION
    └── KNOWLEDGE_REFRESH_POLICY.md        ← freshness policy por tipo de dado
```

---

## Princípios que carregam do V1 para o V2

Estes princípios do `AGENT_COLLABORATION_PROTOCOL.md` original **não mudam** em V2:

1. **Regra de Ouro**: nenhum conteúdo é publicado sem aprovação da Judith.
2. **Escalada obrigatória em conflito**: dois agentes discordando escalam para o CMO, nunca votam.
3. **Nenhuma decisão unilateral fora do escopo do agente.**
4. **Documentação obrigatória em cada handoff** (V2 formaliza isso no `AgentHandoff`, ver `protocol/AGENT_HANDOFF_CONTRACT.md`).
5. **Reversão rápida em erro**: volta para quem criou, não descarta.

O que V2 adiciona por cima disso: papéis de growth/vendas/suporte/CRM, um modelo de memória com fronteiras explícitas, e um ciclo de aprendizado contínuo que é **sempre proposto por um agente e aprovado por um humano** — nunca auto-aplicado.

---

*Versão: 2.0 — Documentação*
*Substitui: nada (V1 permanece intacto)*
*Marca: Bem me Qué*
