# Memory Model — V2

> Separa 4 categorias de memória conceitual e mapeia cada uma para o que o Agno
> oferece nativamente (`agno.learn.LearningMachine`, ver skill Agno carregada nesta sessão,
> arquivo `learning.md`). Onde o mapeamento não é direto, isso é dito explicitamente —
> não inventamos uma API do Agno que não existe.

---

## As 4 categorias

### 1. SESSION MEMORY — conversa atual
O que foi dito nesta conversa específica, para manter continuidade dentro dela.

**Mapeamento Agno:** `add_history_to_context` + `num_history_runs` no `Agent` (histórico de mensagens da sessão, nativo, já usado no starter atual — `agents/my_agent.py`/Jud já usa isso). Para um resumo mais estruturado (objetivo da sessão, progresso), o Agno também oferece `SessionContextConfig` dentro do `LearningMachine` (`mode`, `enable_planning`) — mas isso é um recurso adicional, não obrigatório para toda sessão simples.

**Quem usa:** todo agente conversacional (Community & DM, Sales & Conversion, Customer Support).

**Regra:** nunca persiste além da sessão sem virar Customer Memory explicitamente.

---

### 2. CUSTOMER MEMORY — contexto persistente do cliente (com consentimento)
Fatos e preferências sobre um cliente específico que **persistem entre sessões**, sempre dentro do escopo de consentimento (`BUSINESS_RULES.md` regra 12).

**Mapeamento Agno:** `UserMemoryConfig` (observações não-estruturadas sobre o usuário, ex.: "prefere ebook de recheios") + `UserProfileConfig` (campos estruturados, ex.: nome preferido), ambos do `LearningMachine`, chaveados por `user_id`. `user_id` aqui é o identificador do cliente (ex.: handle do Instagram ou e-mail, quando disponível).

**Quem usa:** Sales & Conversion Agent, CRM & Lifecycle Agent, Customer Support Agent.

**Regra:** só é criada quando o cliente iniciou contato (consentimento implícito de conversa) — nunca para contato não solicitado.

---

### 3. BUSINESS MEMORY — decisões e fatos do negócio
Decisões estratégicas, histórico de campanhas, resultado de mudanças de oferta — não é sobre "um cliente", é sobre o negócio como um todo, compartilhado entre agentes.

**Mapeamento Agno — decisão de arquitetura, não API documentada diretamente para este caso:** o `LearningMachine` do Agno é fundamentalmente centrado em `user_id` (memória "sobre alguém"). Para memória compartilhada entre agentes sobre o negócio, duas abordagens são compatíveis com o que a skill documenta, e a escolha entre elas é uma decisão nossa, não uma resposta única da documentação:

- **Opção A — Entity Memory com namespace global:** `EntityMemoryConfig(namespace="global")` tratando "campanha X", "decisão Y" como entidades com fatos/eventos. Vantagem: usa o mecanismo nativo de aprendizado do Agno.
- **Opção B — Knowledge, não Memory:** decisões estratégicas relevantes viram documento (como `STATUS_V2.md` já é) e entram via `create_knowledge()` (já existente em `db/session.py`), consultado por RAG. Vantagem: mais parecido com o que já existe no starter, mais fácil de auditar/versionar (é arquivo, não estado de banco opaco).

**Não implementamos nenhuma das duas nesta etapa** — fica registrado como decisão pendente para quando o primeiro agente que precisa de Business Memory de fato for implementado com essa necessidade (provavelmente CMO ou Marketing Director).

**Quem usaria:** CMO, Brand Architect, Marketing Director, Offer & Funnel Strategist.

---

### 4. AGENT PERFORMANCE MEMORY — acertos, falhas, feedback, evals
Histórico de performance de cada agente: correções da Judith, KPIs, versões, resultado de mudanças.

**Mapeamento Agno — também não é um encaixe direto:** isto não é "memória sobre um usuário" nem "memória sobre uma entidade de negócio" — é observabilidade/log estruturado sobre os próprios agentes. O `LearningMachine` do Agno não foi desenhado para isso (é centrado em usuário/entidade, não em "performance do próprio agente"). A abordagem mais honesta é **não forçar isso dentro de `LearningMachine`** e tratar como **log estruturado em tabela própria** (Postgres, fora do abstration de Memory do Agno), consultado pelo AI Performance & Evals Agent — que é, aliás, exatamente o desenho já descrito em `models/LEARNING_EVALS_MODEL.md` (`Interaction → structured log → ...`).

**Quem usa:** AI Performance & Evals Agent (dono conceitual desta categoria).

---

## Regra geral

**Nunca misturar as 4 numa memória global única.** Um agente de Sales nunca deveria "lembrar" de uma decisão estratégica do CMO via a mesma store que guarda preferência de um cliente — são domínios com regras de acesso, retenção e privacidade diferentes.

---

*Versão: 2.0*
*Nenhuma implementação de memória foi feita nesta etapa — este é o modelo conceitual + mapeamento honesto para as primitivas reais do Agno.*
