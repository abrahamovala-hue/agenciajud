# Agent Collaboration Protocol — V2

> Evolução de `docs/JUDITH-AI-TEAM/agents/AGENT_COLLABORATION_PROTOCOL.md` (V1, não sobrescrito).
> Este documento estende o protocolo original para os 21 agentes do Judith AI Business Team,
> preservando os princípios que já funcionavam e adicionando o que os novos domínios
> (vendas, CRM, suporte, inteligência) exigem.

---

## O que muda de V1 para V2

| Princípio V1 | Status em V2 |
|---|---|
| Regra de Ouro: nada publica sem Judith | **Mantida, sem exceção** |
| Escalada de conflito → CMO, nunca votação | **Mantida** |
| Formato estruturado de handoff | **Formalizado** como contrato `AgentHandoff` (ver `AGENT_HANDOFF_CONTRACT.md`) — mesmo espírito do template V1, agora com campos nomeados e estáveis |
| Hierarquia de 5 níveis | **Expandida** para 6 tiers (Direção, Content & Social, Growth & Sales, Customer Experience, Intelligence, Governança) — ver `AGENT_ROSTER.md` |
| Nenhum pulo de etapa | **Mantida**, agora verificável pelo Quality Control Agent contra o registro de `AgentHandoff` de cada etapa |
| Reversão rápida em erro | **Mantida** |

Este protocolo **não substitui** o V1 para os workflows que o V1 já cobre (`CREATE_REEL_FULL` etc. continuam válidos); ele **estende** a mesma lógica para os workflows novos de V2 (vendas, suporte, CRM, insights, evals).

---

## Hierarquia (6 tiers)

```
DIREÇÃO           → CMO, Brand Architect, Marketing Director
CONTENT & SOCIAL  → Social Media Manager, Market & Trend Intelligence, Hook Finder,
                     Script Writer, Caption Writer, Visual Creative, Video Editor
GROWTH & SALES    → Offer & Funnel Strategist, Sales & Conversion, CRM & Lifecycle
CUSTOMER EXPERIENCE → Community & DM, Customer Support
INTELLIGENCE      → Analytics & BI, Customer Insights, Knowledge Manager,
                     AI Performance & Evals
GOVERNANÇA        → Brand Reviewer, Quality Control Agent
```

Poder de decisão desce em cascata (Direção decide objetivo/estratégia → tiers executam dentro dela), mas **escalada sobe direto para o CMO** independente de quantos tiers de distância — não há hierarquia rígida de "só posso escalar para o tier acima".

---

## Como o roteamento funciona (novo em V2)

V1 assumia que todo trabalho vinha de um workflow disparado manualmente pela Judith. V2 adiciona **roteamento por intenção**: o Social Media Manager (para Instagram) recebe mensagens e decide para qual agente elas vão, sem chamar o time inteiro.

```
Mensagem/pedido chega
        ↓
Social Media Manager classifica intenção
        ↓
   ┌────┴─────┬──────────┬───────────┐
   ↓          ↓          ↓           ↓
Community   Sales &    Customer    (workflow de
& DM        Conversion Support     conteúdo, se
                                    for pedido de
                                    criação)
```

Ver `workflows/WORKFLOWS_V2_INDEX.md`, seção "Routing por Intenção", para os exemplos completos (do pedido original desta etapa, seção 9).

**Princípio:** nenhum agente é chamado "por garantia". Se a intenção é suporte, só Community & DM → Customer Support são acionados — não o time inteiro.

---

## Regra de Consenso (herdada, sem mudança de espírito)

1. Dois agentes discordam → cada um apresenta posição com evidência (documento/dado).
2. CMO decide, citando a evidência consultada.
3. Se a discordância persistir mesmo após decisão do CMO → escalada para Judith.

Nunca há votação. Nunca há decisão sem citar fonte.

---

## Regras de Segurança (herdadas + novas)

### Herdadas do V1 (sem mudança)
1. Nenhum pulo de etapa.
2. Nenhuma decisão unilateral fora do escopo do agente.
3. Escalada obrigatória em conflito.
4. Documentação completa obrigatória (agora via `AgentHandoff`).
5. Referência obrigatória (toda decisão cita fonte).
6. Nenhuma rejeição silenciosa.
7. Aprovação humana é obrigatória para publicação.
8. Reversão rápida em erro — volta para quem criou, não descarta.

### Novas em V2
9. **Nenhum agente edita o próprio prompt, instructions, código, guardrail, tool ou Knowledge crítico** (ver `models/LEARNING_EVALS_MODEL.md`). Toda melhoria passa pelo AI Performance & Evals Agent + aprovação humana.
10. **Dado de cliente só é usado dentro do escopo de consentimento da própria conversa** — nunca reaproveitado para contato não solicitado sem base de consentimento (`BUSINESS_RULES.md` regra 12).
11. **Nenhuma promessa de exceção de política (reembolso, desconto) sem escalar para humano.**
12. **Nenhum agente afirma ter consultado uma integração externa (Instagram API, Kiwify, CRM) que ainda não existe** — se a Tool está `TOOL PLANNED`, o agente diz isso explicitamente em vez de fingir ter o dado.

---

## Aprovação Humana

Idêntico ao V1: Judith é sempre o último passo antes de qualquer coisa pública. Em V2, isso se estende explicitamente a:

- Qualquer resposta de exceção de política (reembolso fora de prazo).
- Qualquer mudança de preço/oferta.
- Qualquer promoção de versão de agente (novo em V2 — ver `models/LEARNING_EVALS_MODEL.md`).
- Qualquer disparo de mensagem em massa (CRM & Lifecycle).

---

*Versão: 2.0*
*Substitui: nada — `docs/JUDITH-AI-TEAM/agents/AGENT_COLLABORATION_PROTOCOL.md` (V1) permanece a fonte para os workflows que já cobria*
