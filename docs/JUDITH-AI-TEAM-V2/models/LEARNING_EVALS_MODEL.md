# Learning & Evals Model — V2

> Implementa conceitualmente o ciclo de aprendizado contínuo pedido:
> `Interaction → structured log → outcome → user/Judith feedback → KPI →
> AI Performance & Evals → improvement proposal → regression eval → human approval → version bump`
>
> **Regra dura, sem exceção:** nenhum agente edita o próprio prompt, instructions, código,
> guardrail, tool ou Knowledge crítico (`BUSINESS_RULES.md` regra 19). Todo o ciclo abaixo
> termina em aprovação humana antes de qualquer mudança real acontecer.

---

## O ciclo, passo a passo

### 1. Interaction
Toda execução de agente (uma resposta, uma decisão, um handoff) é uma interação.

### 2. Structured log
Cada interação gera um registro com, no mínimo: agente, `task_id`/`workflow`, input, output (`AgentHandoff`, ver `protocol/AGENT_HANDOFF_CONTRACT.md`), confiança declarada, timestamp.

**Estado atual:** não implementado nesta etapa. Log estruturado precisa de uma tabela própria — candidato natural é o Postgres já usado pelo AgentOS (`db/session.py`), mas em tabela separada da sessão de conversa, dona do AI Performance & Evals Agent (ver `models/MEMORY_MODEL.md`, categoria 4).

### 3. Outcome
O que aconteceu depois: conteúdo foi aprovado? Rejeitado? Publicado? Cliente converteu?

### 4. User/Judith feedback
Correção explícita da Judith (ex.: editou um roteiro antes de gravar) ou feedback de cliente (ex.: reclamação).

### 5. KPI
Cada agente tem KPIs próprios definidos na sua ficha (seção "KPIs"). O outcome + feedback alimentam esses números.

### 6. AI Performance & Evals Agent
Consome log + outcome + feedback + KPI. Procura por:
- **Erro recorrente**: mesmo tipo de falha, ≥3 ocorrências (mesmo limiar usado pelo Customer Insights Agent para "padrão", por consistência).
- **Correção recorrente**: a Judith corrige o mesmo tipo de coisa repetidamente (sinal de que a instructions do agente não captura algo).
- **Padrão positivo**: o que está funcionando bem e deveria ser reforçado (não é só sobre corrigir erro).

### 7. Improvement proposal
Proposta formal: o quê mudar (instructions, exemplo gold, regra de roteamento), por quê (evidência quantificada), impacto esperado.

**Nunca inclui**: mudança de guardrail de segurança, mudança de Knowledge crítico (`BRAND.md`, `BUSINESS_RULES.md`) — essas exigem revisão humana direta, não passam pelo ciclo automatizado de proposta.

### 8. Regression eval
Antes de qualquer proposta ir para aprovação, compara **versão atual vs candidata** contra o gold dataset do agente (seção "Gold Examples" de cada ficha) + os casos de eval (`evals/[agent-name]/`, ver seção de testes desta etapa). Se a candidata piora qualquer caso que a versão atual acertava, a proposta é rejeitada automaticamente antes mesmo de chegar a um humano.

**Nota honesta sobre Agno:** a skill Agno carregada nesta sessão (`agents.md`, `teams.md`, `workflows.md`, `learning.md`, `tools.md`, `mcp.md`, `models.md`) não documenta um módulo nativo de eval/comparação de versão. Não inventamos uma API para isso — o "regression eval" aqui é lógica de aplicação (comparar outputs contra os casos em `evals/`), não uma feature built-in do framework.

### 9. Human approval
Judith revisa a proposta + resultado do regression eval e aprova ou rejeita. **Sem exceção — nenhuma mudança pula esta etapa.**

### 10. Version bump
Se aprovado: a instructions/ficha do agente é atualizada (versão incrementada na seção "Version" da ficha), e a mudança é registrada com data e motivo. Rollback é sempre possível porque a versão anterior não é apagada (mesmo princípio de "não sobrescrever" usado entre V1 e V2 deste próprio documento).

---

## Prevenção de regressão e rollback

- Toda versão promovida mantém a versão anterior acessível (git history do arquivo de instructions/ficha já cumpre isso, sem infraestrutura nova).
- Rollback = reverter para a versão anterior do arquivo + registrar o motivo.
- Nenhuma versão é "auto-promovida" — mesmo um regression eval 100% positivo não dispensa aprovação humana.

---

## O que fica para depois (não implementado nesta etapa)

- Log estruturado real em tabela dedicada.
- Execução automatizada do regression eval (hoje os casos em `evals/` são fixtures para rodar manualmente/por CI, não um pipeline automático).
- Qualquer mecanismo de "detectar padrão" além de contagem simples de ocorrência.

---

*Versão: 2.0*
*Implementação: conceitual. Nenhum log automático, nenhuma execução de eval automática, nenhuma promoção de versão foram implementados nesta etapa.*
