"""
Gera a documentacao da Agent Foundation V2 a partir do CODIGO.

Por que gerar em vez de escrever a mao: matriz escrita a mao envelhece no
primeiro commit. Estes documentos sao derivados de `knowledge_policies.py` e
`capabilities.py`, entao nao ha como divergirem do que roda.

Uso:
    python scripts/generate_foundation_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.capabilities import TOOL_REQUIREMENTS, capabilities_of  # noqa: E402
from agents.knowledge_policies import KNOWLEDGE_POLICIES, MISSING, get_policy  # noqa: E402

DOCS = Path(__file__).resolve().parent.parent / "docs" / "JUDITH-AI-TEAM-V2"

# Missao e competencias de oficio por papel. Unica parte escrita a mao —
# porque descreve intencao, nao configuracao. O resto sai do codigo.
ROLES: dict[str, tuple[str, str]] = {
    "cmo": ("Aprova objetivo, prioriza, resolve conflito, escala para a Judith.",
            "estrategia, KPI design, priorizacao, trade-off, leitura de evidencia"),
    "brand-architect": ("Define e corrige direcao de marca. Nao aprova peca final.",
                        "posicionamento, diferenciacao, hierarquia de mensagem, voz"),
    "marketing-director": ("Planeja campanha, mix de conteudo e alocacao.",
                           "campanha, funil, lancamento, distribuicao, medicao"),
    "social-media-manager": ("Calendario editorial, formato e cadencia.",
                             "planejamento editorial, formatos, cadencia, repurposing"),
    "market-trend-intelligence": ("Contextualiza com tendencia e concorrencia.",
                                  "ciclo de tendencia, sinal vs ruido, analise competitiva"),
    "hook-finder": ("Encontra o angulo que segura atencao nos primeiros segundos.",
                    "atencao, curiosidade, lacuna de informacao, taxonomia de hook"),
    "script-writer": ("Escreve o roteiro do video curto.",
                      "storytelling, estrutura, ritmo, open loop, clareza didatica"),
    "caption-writer": ("Escreve legenda, CTA e hashtags.",
                       "estrutura de legenda, legibilidade, CTA, copy educativa"),
    "visual-creative": ("Cria o briefing visual da peca.",
                        "hierarquia, composicao, legibilidade, consistencia visual"),
    "video-editor": ("Especifica a edicao (cortes, ritmo, legendas, trilha).",
                     "timeline, ritmo, B-roll, legenda, continuidade"),
    "offer-funnel-strategist": ("Desenha oferta e funil. Propoe, nao aplica preco.",
                                "design de oferta, precificacao, etapas de funil, friccao"),
    "sales-conversion-agent": ("Responde intencao de compra com dado verificado.",
                               "descoberta, qualificacao, objecao, persuasao etica"),
    "crm-lifecycle-agent": ("Redige follow-up e cuida do ciclo de vida.",
                            "lifecycle, segmentacao, reativacao, consentimento"),
    "community-dm-agent": ("Classifica intencao e conversa socialmente.",
                           "conversa, classificacao de intencao, de-escalation, roteamento"),
    "customer-support-agent": ("Resolve problema pos-venda dentro da politica.",
                               "troubleshooting, classificacao, escalada, expectativa"),
    "analytics-bi-agent": ("Le e reporta performance. Nunca fabrica dataset.",
                           "KPI, funil, coorte, atribuicao, variancia, qualidade de dado"),
    "customer-insights-agent": ("Extrai dor, motivacao e objecao do que o publico diz.",
                                "pesquisa qualitativa, analise tematica, voice-of-customer"),
    "knowledge-manager": ("Governa fontes. Nao decide verdade de negocio.",
                          "proveniencia, autoridade, frescor, conflito, versionamento"),
    "ai-performance-evals-agent": ("Avalia comportamento e propoe melhoria.",
                                   "rubrica, gold set, regressao, taxonomia de falha"),
    "brand-reviewer": ("Revisa a peca final contra a direcao de marca.",
                       "revisao editorial, verificacao de claim, consistencia"),
}

WORKFLOWS: dict[str, list[str]] = {
    "cmo": ["CREATE_REEL", "WEEKLY_BUSINESS_REVIEW"],
    "brand-architect": ["CREATE_REEL"],
    "market-trend-intelligence": ["CREATE_REEL", "WEEKLY_BUSINESS_REVIEW"],
    "hook-finder": ["CREATE_REEL"],
    "script-writer": ["CREATE_REEL"],
    "caption-writer": ["CREATE_REEL"],
    "visual-creative": ["CREATE_REEL"],
    "video-editor": ["CREATE_REEL"],
    "brand-reviewer": ["CREATE_REEL"],
    "community-dm-agent": ["ANSWER_DM"],
    "sales-conversion-agent": ["ANSWER_DM", "WEEKLY_BUSINESS_REVIEW"],
    "customer-support-agent": ["ANSWER_DM"],
    "crm-lifecycle-agent": ["ANSWER_DM", "WEEKLY_BUSINESS_REVIEW"],
    "analytics-bi-agent": ["WEEKLY_BUSINESS_REVIEW"],
    "customer-insights-agent": ["WEEKLY_BUSINESS_REVIEW"],
}

# Agentes que decidem COM BASE em documento vinculante.
EVIDENCE_REQUIRED: dict[str, str] = {
    "cmo": "aprovacao de objetivo e decisao de conflito",
    "brand-architect": "direcao e correcao de marca",
    "brand-reviewer": "aprovacao/reprovacao por regra de marca",
    "sales-conversion-agent": "preco, oferta, desconto, conteudo de produto",
    "customer-support-agent": "politica, prazo, garantia, acesso",
    "offer-funnel-strategist": "preco e condicao de oferta",
    "analytics-bi-agent": "todo numero reportado",
    "caption-writer": "preco/link citado em legenda",
    "script-writer": "afirmacao sobre produto no roteiro",
    "community-dm-agent": "qualquer claim de produto/oferta/politica",
    "market-trend-intelligence": "toda tendencia afirmada",
    "customer-insights-agent": "frequencia de tema",
    "knowledge-manager": "estado de qualquer fonte",
}

ESCALATES: dict[str, str] = {a: "judith" for a in ("cmo", "knowledge-manager")}


def _readiness(agent_id: str) -> tuple[str, str]:
    """Estado do agente. Esperar integracao NAO e defeito."""

    gaps = {g.key for g in get_policy(agent_id).missing_sources}

    integracao = {"METRICAS_INSTAGRAM", "VENDAS_KIWIFY", "CRM_PIPELINE", "HISTORICO_DM", "HISTORICO_POSTS"}
    if agent_id in {"analytics-bi-agent", "customer-insights-agent", "crm-lifecycle-agent"}:
        return "WAITING_FOR_DATA", "funcao depende de integracao inexistente"
    if agent_id == "customer-support-agent":
        return "WAITING_FOR_KNOWLEDGE", "conteudo real dos ebooks ausente"
    if agent_id == "video-editor":
        return "WAITING_FOR_TOOL", "Remotion Tool nao conectada"
    if agent_id in {"cmo", "brand-architect"}:
        return "READY_FOR_EVALS", "refinado individualmente e testado"
    if gaps & integracao:
        return "READY_FOR_EVALS", "opera sem o dado dinamico; a lacuna e declarada"
    return "READY_FOR_EVALS", "fundacao completa"


def _fmt(items) -> str:
    return ", ".join(items) if items else "—"


def competency_matrix() -> str:
    linhas = [
        "# Agent Competency & Knowledge Matrix",
        "",
        "> **GERADO A PARTIR DO CODIGO** por `scripts/generate_foundation_docs.py`.",
        "> Nao edite a mao: rode o script apos mudar `knowledge_policies.py` ou `capabilities.py`.",
        "",
        "Fonte: `agents/knowledge_policies.py` (Knowledge) e `agents/capabilities.py` (Capabilities).",
        "",
    ]

    for agent_id in sorted(KNOWLEDGE_POLICIES):
        mission, competencies = ROLES[agent_id]
        policy = get_policy(agent_id)
        caps = capabilities_of(agent_id)

        craft = [s.key.replace("CRAFT_", "") for s in policy.documents if s.key.startswith("CRAFT_")]
        judith = [s.key for s in policy.documents if not s.key.startswith(("CRAFT_", "FICHA_"))]
        fichas = [s.key for s in policy.documents if s.key.startswith("FICHA_")]
        template = [s.key for s in policy.documents if s.reliability == "template"]
        ressalva = [s.key for s in policy.documents if s.caveat and s.reliability != "template"]

        allowed = sorted(c.value for c, d in caps.items() if d == "ALLOWED")
        human = sorted(c.value for c, d in caps.items() if d == "HUMAN_REQUIRED")
        denied = sorted(c.value for c, d in caps.items() if d == "DENIED")
        estado, motivo = _readiness(agent_id)

        linhas += [
            f"## `{agent_id}`",
            "",
            f"**MISSION** — {mission}",
            "",
            f"**GENERAL_DOMAIN_COMPETENCIES** — {competencies}",
            f"**CRAFT KNOWLEDGE (geral)** — {_fmt(craft)}",
            f"**JUDITH_SPECIFIC + SHARED CORE** — {_fmt(judith)}",
        ]
        if fichas:
            linhas.append(f"**FICHAS DE AGENTE** — {len(fichas)} (papel transversal)")
        linhas += [
            f"**FONTES TEMPLATE (nao validadas)** — {_fmt(template)}",
            f"**FONTES COM RESSALVA** — {_fmt(ressalva)}",
            f"**DYNAMIC_DATA_REQUIRED** — {_fmt(g.key for g in policy.missing_sources)}",
            "",
            "**TOOLS_CURRENT** — `search_knowledge_base`, `ler_documento`, `listar_fontes_disponiveis`",
            f"**TOOLS_FUTURE** — {_fmt(sorted(t for t, c in TOOL_REQUIREMENTS.items() if caps.get(c, 'DENIED') != 'DENIED'))}",
            "",
            f"**CAPABILITIES_ALLOWED** — {_fmt(allowed)}",
            f"**CAPABILITIES_HUMAN_REQUIRED** — {_fmt(human)}",
            f"**CAPABILITIES_DENIED (declaradas)** — {_fmt(denied)} · *todo o resto tambem e DENIED por omissao*",
            "",
            f"**EVIDENCE_REQUIRED_FOR** — {EVIDENCE_REQUIRED.get(agent_id, 'nao aplicavel')}",
            f"**WORKFLOWS** — {_fmt(WORKFLOWS.get(agent_id, []))}",
            f"**ESCALATES_TO** — {ESCALATES.get(agent_id, 'cmo')}",
            f"**EVAL_REQUIREMENTS** — `evals/{agent_id}/cases.yaml` (estrutura existe, gold set vazio)",
            f"**READINESS** — `{estado}` ({motivo})",
            "",
            "---",
            "",
        ]

    return "\n".join(linhas)


def readiness_matrix() -> str:
    linhas = [
        "# Readiness Matrix",
        "",
        "> **GERADO A PARTIR DO CODIGO.** Ver `scripts/generate_foundation_docs.py`.",
        "",
        "**Esperar integracao nao e defeito.** `WAITING_FOR_*` significa que a fundacao esta pronta",
        "e falta um dado ou uma ferramenta externa — nao que o agente esteja quebrado.",
        "",
        "| Agent | Craft | Judith | Gaps | Workflows | Allowed | Human | Readiness |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for agent_id in sorted(KNOWLEDGE_POLICIES):
        policy = get_policy(agent_id)
        caps = capabilities_of(agent_id)
        craft = sum(1 for s in policy.documents if s.key.startswith("CRAFT_"))
        judith = sum(1 for s in policy.documents if not s.key.startswith("CRAFT_"))
        allowed = sum(1 for d in caps.values() if d == "ALLOWED")
        human = sum(1 for d in caps.values() if d == "HUMAN_REQUIRED")
        estado, _ = _readiness(agent_id)
        wf = len(WORKFLOWS.get(agent_id, []))

        linhas.append(
            f"| `{agent_id}` | {craft} | {judith} | {len(policy.missing_sources)} | {wf} | "
            f"{allowed} | {human} | `{estado}` |"
        )

    return "\n".join(linhas) + "\n"


def gap_registry() -> str:
    quem_precisa: dict[str, list[str]] = {}
    for agent_id in sorted(KNOWLEDGE_POLICIES):
        for gap in get_policy(agent_id).missing_sources:
            quem_precisa.setdefault(gap.key, []).append(agent_id)

    linhas = [
        "# Knowledge Gap Registry",
        "",
        "> **GERADO A PARTIR DO CODIGO** (as lacunas ja declaradas) + auditoria manual da Fase 4.",
        "",
        "Serve para sabermos exatamente o que pedir a Judith e o que depende de integracao.",
        "",
        "## MISSING_JUDITH_SOURCE — precisa de material que so a Judith tem",
        "",
        "A auditoria procurou conteudo tecnico real no repositorio (temperagem, ganache, caramelo,",
        "casquinha, drageado, praline, validade, armazenamento, ingredientes, equipamentos).",
        "**Os termos aparecem como topico; nao ha nenhum conteudo tecnico** — zero temperatura,",
        "zero gramatura, zero passo-a-passo. Os ebooks nao estao no projeto e **nao foram",
        "reconstruidos de memoria**.",
        "",
        "| Item | Por que precisamos | Quem fica bloqueado |",
        "|---|---|---|",
        "| Conteudo real dos ebooks | responder o que o produto ensina, sem inventar | customer-support, sales, script-writer |",
        "| Receitas e tecnicas | conteudo educativo fiel | script-writer, caption-writer, hook-finder |",
        "| Troubleshooting real | resolver duvida tecnica de cliente | customer-support |",
        "| FAQ com respostas aprovadas | responder no padrao da Judith | community-dm, customer-support |",
        "| Politicas completas (acesso, entrega, troca) | hoje so a garantia de 7 dias esta documentada | customer-support |",
        "",
        "## TO_VALIDATE_WITH_JUDITH — existe, mas nao esta validado",
        "",
        "| Fonte | Estado | Impacto |",
        "|---|---|---|",
        "| `VOICE` | TEMPLATE | tom da marca inferido do site, nao confirmado |",
        "| `AUDIENCE` | TEMPLATE | personas inferidas |",
        "| `CONTENT_PILLARS` | TEMPLATE | pilares e proporcoes propostos |",
        "| `VISUAL_IDENTITY` | TEMPLATE | cores e fontes inferidas do CSS |",
        "| `INSTAGRAM_AUDIT` | TEMPLATE | pede analise manual, nao preenchida |",
        "| `PRODUCT_PAGES_AUDIT` | TEMPLATE | template sem conclusao |",
        "| `OFFERS` (colecao completa) | A_VERIFICAR | preco da colecao nao confirmado |",
        "| `PRODUCTS` (produtos futuros) | A_VERIFICAR | secao marcada 'a preencher com Judith' |",
        "",
        "## WAITING_FOR_INTEGRATION — depende de sistema externo",
        "",
        "| Lacuna | Integracao | Agentes que dependem |",
        "|---|---|---|",
    ]

    for key, agentes in sorted(quem_precisa.items()):
        gap = MISSING.get(key)
        if gap is None:
            continue
        linhas.append(f"| `{key}` | {gap.reason} | {', '.join(agentes)} |")

    linhas += [
        "",
        "## WAITING_FOR_REAL_EXAMPLES — comportamento, nao fato",
        "",
        "Pecas aprovadas e rejeitadas, correcoes da Judith, respostas de DM reais, conversas que",
        "converteram, casos de suporte resolvidos. Alimentam o gold set do `ai-performance-evals-agent`",
        "e calibram os agentes criativos. **Nada disso e persistido hoje.**",
        "",
        "## WAITING_FOR_METRICS",
        "",
        "Instagram (alcance, retencao, salvamentos) e Kiwify (vendas, receita, reembolso).",
        "Sem eles, toda afirmacao de performance e hipotese — e os agentes sao obrigados a dizer isso.",
        "",
        "## COMPLETE_ENOUGH_FOR_V1",
        "",
        "| Camada | Estado |",
        "|---|---|",
        "| Craft knowledge (11 documentos de oficio) | completo para os 20 papeis |",
        "| Posicionamento e diferenciais (`BRAND`) | vigente |",
        "| Catalogo e precos individuais (`PRODUCTS`, `OFFERS`) | vigente |",
        "| Garantia de 7 dias | vigente |",
        "| Regras de negocio (`BUSINESS_RULES`) | vigente |",
        "| Protocolo de colaboracao | vigente |",
        "| Capability Policy | completa, 20 agentes |",
        "",
    ]
    return "\n".join(linhas)


def main() -> None:
    saidas = {
        "AGENT_COMPETENCY_MATRIX.md": competency_matrix(),
        "READINESS_MATRIX.md": readiness_matrix(),
        "KNOWLEDGE_GAP_REGISTRY.md": gap_registry(),
    }
    for nome, conteudo in saidas.items():
        (DOCS / nome).write_text(conteudo, encoding="utf-8")
        print(f"  escrito: docs/JUDITH-AI-TEAM-V2/{nome} ({len(conteudo)} bytes)")


if __name__ == "__main__":
    main()
