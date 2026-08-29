# CLAUDE.md

Contexto pra Claude Code trabalhar neste repo.

## Projeto

**agno-whatsapp-starter** — template plug-and-play pra criar um agente de IA que atende no WhatsApp Meta oficial. Projeto prático do módulo "Agente de IA no WhatsApp com Agno" do curso Engenheiro de Produtos IA (NoCode StartUp).

**Filosofia:** 1 agente, 1 arquivo, poucas abstrações. O aluno precisa bater o olho no código e entender o que está acontecendo.

## Arquitetura

```
AgentOS (app/main.py)
└── My Agent (agents/my_agent.py)   # persona customizavel pelo aluno
```

Interface WhatsApp (`app/interfaces.py`) é ativada automaticamente quando `WHATSAPP_ENABLED=true` e as 4 credenciais estão preenchidas. Webhook path: `/whatsapp/webhook`.

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | Agno (Python) |
| Runtime | AgentOS |
| Modelo | OpenAI GPT-4.1 (`OpenAIResponses`) |
| DB | PostgreSQL + pgvector |
| Canal | WhatsApp Business API (Meta oficial) via `agno.os.interfaces.whatsapp.Whatsapp` |
| Deploy | Railway (1 clique) |

## Arquivos-chave

| Arquivo | Papel |
|---|---|
| `agents/my_agent.py` | **Persona mora aqui.** Aluno edita `instructions`. |
| `app/main.py` | Ponto de entrada. Registra o agent no AgentOS, expõe `/health`. |
| `app/interfaces.py` | Habilita Whatsapp() condicionalmente. Valida env vars. |
| `app/config.yaml` | Quick prompts da UI do AgentOS. |
| `db/session.py` | `get_postgres_db()` helper. |
| `compose.yaml` | Dev local (app + pgvector). |
| `railway.json` | Config de deploy Railway. |
| `.env.example` | Template comentado das env vars. |

## Convenções

### Padrão do agent

```python
from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from db import get_postgres_db

my_agent = Agent(
    id="my-agent",
    name="My Agent",
    model=OpenAIResponses(id="gpt-4.1"),
    db=get_postgres_db(),
    instructions="...",
    enable_agentic_memory=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
```

### WhatsApp interface

`Whatsapp()` do Agno 2.5+ lê env vars direto. **Não passar** `access_token`, `phone_number_id` etc. como kwargs — quebra com `TypeError`. Só passar `agent=my_agent`.

### Banco

- Sem knowledge base, use `get_postgres_db()` direto.
- Se adicionar KB no futuro, usar helper `create_knowledge(name, table)` do `db/`.

## Comandos

```bash
# Setup local
cp .env.example .env
docker compose up -d --build

# Logs
docker compose logs -f agentos-api

# Restart após editar persona
docker compose restart agentos-api

# Smoke tests
./scripts/venv_setup.sh && source .venv/bin/activate
python -m pytest tests/
```

## Deploy — GitHub `main` é a única fonte oficial

```bash
# código → testes → commit → push → deploy a partir de main → smoke
git push origin main
railway redeploy --from-source --yes --service agenciajud
```

O serviço `agenciajud` está conectado a `abrahamovala-hue/agenciajud`, branch
`main`. Todo deployment de produção precisa carregar `commitHash` e `branch`
verificáveis no `meta` — é assim que se sabe qual código está no ar.

**O push sozinho não deploya.** Medido: 5 minutos após o push, nada disparou.
A causa provável é o Railway GitHub App não ter acesso a este repositório —
foi preciso passar `--branch` ao conectar a origem, que é o contorno
documentado justamente para repo invisível ao App. Enquanto isso não for
autorizado no GitHub, o deploy é disparado à mão com `--from-source`, que
puxa o commit mais recente da origem configurada (≠ `redeploy` puro, que só
reusa o build anterior).

**`railway up` NÃO é o caminho normal.** Ele envia o diretório local e cria um
deployment **sem commit nem branch**, o que abre uma divergência silenciosa:
o Railway continua exibindo a origem do GitHub enquanto roda outra coisa.

Foi o que aconteceu de fato: a origem do serviço ficou presa em `49f4121`
enquanto produção rodava 15 commits à frente, vindos de uploads. Um
"Redeploy from GitHub" teria revertido sete fases de trabalho.

`railway up` fica disponível só para emergência — e, se for usado, a
divergência precisa ser desfeita em seguida com um deploy a partir de `main`.

Conferir a proveniência do que está no ar:

```bash
railway deployment list --json | python -c "import sys,json; m=json.load(sys.stdin)[0]['meta']; print(m.get('branch'), m.get('commitHash'))"
```

## Env vars

Ver `.env.example` pra lista comentada. Obrigatórias em produção:

- `OPENAI_API_KEY`
- `DB_*` (na Railway, via reference vars do serviço Postgres)
- `WHATSAPP_ENABLED`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` quando ligar o canal
- `PRINT_ENV_ON_LOAD=False` (sempre)

### F3 — Hybrid RAG

| Var | Valores | Default | O que faz |
|---|---|---|---|
| `RAG_MODE` | `current` \| `hybrid_shadow` \| `hybrid` | `current` — **producao roda `hybrid`** | Como o Brain recupera. Valor desconhecido cai no default. |
| `BRAIN_ADMIN_ENABLED` | `true` \| ausente | ausente | Registra `/admin/brain/{status,embeddings,eval,executions}`. Desligue depois de usar. |
| `BRAIN_EMBEDDER` | `deterministic` \| ausente | ausente | `deterministic` roda a suite sem rede. **Nunca em producao.** |

`RAG_MODE` e o rollback da F3: apagar a variavel volta ao lexical puro, sem
migration e sem rebuild. Foi exercitado de verdade no cutover
(`hybrid` -> `hybrid_shadow` -> `hybrid`), nao so declarado.

`hybrid_shadow` calcula o hibrido, registra no ExecutionLog e devolve o
resultado lexical — shadow que muda a resposta nao e shadow. Ele grava as DUAS
pernas na mesma execucao (`sources_opened` e `shadow_sources`), e e o unico
jeito de compara-las sobre a query que o agente DE FATO escreve. Isso importa:
o eval offline mede a frase da cliente, e producao usa a frase que o LLM
compoe a partir dela. Sao coisas diferentes.

O piso de similaridade mora em `Embedder.score_floor` (0.60 para
`text-embedding-3-small`) e foi calibrado por varredura contra o acervo real —
ver a tabela em `brain/retrieval.py:VECTOR_SCORE_FLOOR`. Quando o acervo
mudar, **remedir** com `POST /admin/brain/eval` passando `vector_floor`.
Nunca ajustar por intuicao: peso lexical maior parecia obvio e foi medido e
reprovado (recall 0.780 -> 0.633).

O indice semantico vive em `judith_knowledge_embeddings` (migration 005,
reversivel). Ele e DERIVADO: descartar a tabela nao perde conhecimento, so
custa reindexar. Modelo: `text-embedding-3-small`, 1536 dimensoes, pela
`OPENAI_API_KEY` que ja existe.

Indexar producao (as rotas so existem com a flag ligada):

```bash
curl -H "Authorization: Bearer $OS_SECURITY_KEY"   https://agenciajud-production.up.railway.app/admin/brain/status
curl -X POST -H "Authorization: Bearer $OS_SECURITY_KEY" -H "Content-Type: application/json"   -d '{}' https://agenciajud-production.up.railway.app/admin/brain/embeddings
curl -H "Authorization: Bearer $OS_SECURITY_KEY"   "https://agenciajud-production.up.railway.app/admin/brain/executions?limit=5"
```

O pipeline e idempotente por `(checksum, modelo)`: rodar de novo sem mudanca
de conteudo faz zero chamada de API. `/admin/brain/executions` devolve so a
telemetria das execucoes — nunca a mensagem da cliente nem a resposta.

## Adicionar features (trilha de evolução)

Alunos avançados podem estender:

- **Tools:** passar `tools=[...]` no Agent. Ex: `GoogleCalendarTools()`, `SlackTools()`, `MCPTools(url=...)`. Lista completa: https://docs.agno.com/tools/toolkits
- **Outro modelo:** trocar `OpenAIResponses(id="gpt-4.1")` por `Claude(id="claude-sonnet-4-5")` (adicionar dep `anthropic` em `pyproject.toml`).
- **Knowledge base:** via UI do `os.agno.com` (Add URL / Upload File) ou via `create_knowledge()` helper em código.
- **Múltiplos agents:** criar outro arquivo em `agents/` e adicionar em `agents=[my_agent, outro_agent]` no `main.py`.

## Referências Agno

- [docs.agno.com/introduction](https://docs.agno.com/introduction)
- [agent-os/introduction](https://docs.agno.com/agent-os/introduction)
- [interfaces/whatsapp](https://docs.agno.com/agent-os/interfaces/whatsapp/introduction)
- [deploy/templates/railway](https://docs.agno.com/deploy/templates/railway/deploy)
- [docs.agno.com/llms-full.txt](https://docs.agno.com/llms-full.txt) (docs completas em formato LLM-friendly)
