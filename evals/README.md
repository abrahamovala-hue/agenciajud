# Evals — Judith AI Business Team V2

Infraestrutura inicial de avaliação, uma pasta por agente (21, espelhando `docs/JUDITH-AI-TEAM-V2/AGENT_ROSTER.md`). Cada pasta tem um `cases.yaml` com 6 casos mínimos: `happy_path`, `ambiguous_request`, `out_of_scope`, `handoff`, `escalation`, `bad_unsafe_input`.

**Isto não é um framework de execução automática.** São fixtures — casos de teste em formato estruturado, prontos para serem rodados manualmente (ou, depois, por um harness) contra o agente. Nenhum executor foi implementado nesta etapa.

## Status por agente

**20 de 21 agentes** estão implementados como `Agent` do Agno e rodando no AgentOS — os `cases.yaml` deles são executáveis de verdade contra `localhost:8000` hoje: `cmo`, `brand-architect`, `marketing-director`, `social-media-manager`, `market-trend-intelligence`, `hook-finder`, `script-writer`, `caption-writer`, `visual-creative`, `video-editor`, `offer-funnel-strategist`, `sales-conversion-agent`, `crm-lifecycle-agent`, `community-dm-agent`, `customer-support-agent`, `analytics-bi-agent`, `customer-insights-agent`, `knowledge-manager`, `ai-performance-evals-agent`, `brand-reviewer`.

**1 agente** ficou como documentação apenas, por design (não por pendência): `quality-control-agent` — é uma checagem determinística de processo (etapa documentada? sim/não), não um caso de uso de LLM. Ver a nota de implementação na própria ficha (`docs/JUDITH-AI-TEAM-V2/agents/21-quality-control-agent.md`).

Nenhum dos 20 agentes implementados tem Knowledge (RAG) conectada ainda — a grounding é o núcleo fixo escrito diretamente nas `instructions` de cada um. Casos que dependem de dado real de negócio (preço, histórico de cliente, métrica) vão testar corretamente a *recusa* do agente em inventar esse dado, não uma resposta com o dado em si.

## Formato de `cases.yaml`

```yaml
agent: <id do agente>
cases:
  - type: happy_path | ambiguous_request | out_of_scope | handoff | escalation | bad_unsafe_input
    input: "..."
    expected_behavior: "..."
```

## Como rodar manualmente hoje (para os 7 agentes implementados)

```bash
curl -X POST http://localhost:8000/agents/<agent-id>/runs \
  -F "message=<input do caso>" \
  -F "stream=false"
```
Comparar a resposta com `expected_behavior` do caso.
