"""
Knowledge Policies — agent_id -> whitelist de fontes.
-----------------------------------------------------

Uma politica por agente, num dict. Nenhum agente pesquisa o repositorio
inteiro: ele so enxerga o que a sua politica lista.

Divisao de responsabilidade (a mesma do CMO, generalizada):
- `instructions` dizem COMO agir;
- `KNOWLEDGE_POLICIES` diz O QUE cada agente pode consultar;
- `FONTE_NAO_DISPONIVEL` diz o que ainda nao existe e de quem e.

Este modulo so declara dados e monta tools/retriever. Toda a leitura, busca,
provenance e formatacao vive em `agents/knowledge_sources.py` — nao ha 19
copias da mesma logica.

Excecao consciente: o CMO (`agents/judith_team/cmo.py`) continua com o
catalogo proprio dele em `knowledge_sources.py`, porque foi aprovado numa
rodada anterior e a instrucao foi nao refaze-lo. A politica dele e registrada
aqui por referencia, para que os testes de isolamento cubram os 20 agentes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from agno.tools import tool

from agents.knowledge_sources import (
    BRAND_ARCHITECT_DOCUMENTS,
    BRAND_ARCHITECT_MISSING_SOURCES,
    CMO_DOCUMENTS,
    CMO_MISSING_SOURCES,
    DOCS_ROOT,
    DocumentSource,
    MissingSource,
    build_knowledge_retriever,
    build_source_catalog,
    read_document,
)

# ---------------------------------------------------------------------------
# Catalogo compartilhado — cada arquivo declarado UMA vez
# ---------------------------------------------------------------------------

# Bloco de IDs de pixel/analytics: nenhum agente de negocio precisa disso, e
# vazar num briefing ou legenda seria pior do que inutil. O mesmo bloco esta
# duplicado em BRAND.md e WEBSITE_AUDIT.md - os dois precisam do corte, e ha
# teste que falha se algum documento voltar a expor a secao.
_BRAND_EXCLUDED = ("Tracking e Analytics",)

_CATALOG: tuple[DocumentSource, ...] = (
    # --- Marca ---
    DocumentSource(
        key="BRAND",
        title="BRAND — identidade, posicionamento e diferenciais",
        relative_path="JUDITH-AI-TEAM/brand/BRAND.md",
        summary="Posicionamento oficial, proposta de valor, diferenciais, palavras-chave da marca.",
        excluded_sections=_BRAND_EXCLUDED,
    ),
    DocumentSource(
        key="VOICE",
        title="VOICE — tom de voz",
        relative_path="JUDITH-AI-TEAM/brand/VOICE.md",
        summary="Personalidade, expressoes que combinam e que nao combinam, regras de comunicacao.",
        reliability="template",
        caveat="O documento se declara TEMPLATE, inferido do site/Instagram e pendente de validacao da Judith. Emojis e hashtags estao marcados 'A VALIDAR COM JUDITH'.",
    ),
    DocumentSource(
        key="AUDIENCE",
        title="AUDIENCE — publico-alvo",
        relative_path="JUDITH-AI-TEAM/brand/AUDIENCE.md",
        summary="Personas, dores, linguagem do publico.",
        reliability="template",
        caveat="O documento se declara TEMPLATE, pendente de validacao da Judith.",
    ),
    DocumentSource(
        key="CONTENT_PILLARS",
        title="CONTENT_PILLARS — pilares editoriais e proporcao",
        relative_path="JUDITH-AI-TEAM/brand/CONTENT_PILLARS.md",
        summary="Os 4 pilares, proporcao semanal sugerida e temas sazonais.",
        reliability="template",
        caveat="Pilares e proporcoes sao PROPOSTOS, nao validados pela Judith.",
    ),
    DocumentSource(
        key="VISUAL_IDENTITY",
        title="VISUAL_IDENTITY — paleta, tipografia e direcao visual",
        relative_path="JUDITH-AI-TEAM/brand/VISUAL_IDENTITY.md",
        summary="Paleta, universo visual, o que fazer e o que evitar em peca visual.",
        reliability="template",
        caveat="Cores e fontes foram inferidas do site, nao confirmadas pela Judith.",
    ),
    DocumentSource(
        key="PRODUCTS",
        title="PRODUCTS — identidade estavel dos produtos",
        relative_path="JUDITH-AI-TEAM/brand/PRODUCTS.md",
        summary="Nome, subtitulo, formato, escopo, paginas, receitas e bonus comprovado. NAO tem preco.",
        caveat="Preco, desconto e checkout nao moram aqui — sao de OFFERS.md.",
    ),
    DocumentSource(
        key="OFFERS",
        title="OFFERS — condicao comercial atual",
        relative_path="JUDITH-AI-TEAM/brand/OFFERS.md",
        summary="Unica fonte de preco, desconto, checkout, garantia e status de oferta.",
        caveat=(
            "Precos verificados no checkout da Kiwify em 2026-08-28. O schema.org do site "
            "publica 25.00 para O Segredo do Chocolate — isso e bug do site, nao o preco: "
            "o checkout cobra R$ 47,00."
        ),
    ),
    DocumentSource(
        key="OFFER_STRATEGY_INTERNAL",
        title="OFFER_STRATEGY_INTERNAL — ideias e roadmap de oferta",
        relative_path="JUDITH-AI-TEAM/brand/OFFER_STRATEGY_INTERNAL.md",
        summary="Propostas de marketing NAO implementadas. Nada aqui e oferta ativa.",
        caveat="Documento interno: nenhuma linha dele pode chegar a cliente, nem resumida.",
        reliability="template",
    ),
    # --- Negocio e governanca ---
    DocumentSource(
        key="PRD",
        title="PRD — objetivos e roadmap do projeto",
        relative_path="JUDITH-AI-TEAM/PRD.md",
        summary="Objetivo do produto, escopo e roadmap.",
    ),
    DocumentSource(
        key="STATUS",
        title="STATUS — estado do projeto (V1)",
        relative_path="JUDITH-AI-TEAM/STATUS.md",
        summary="O que ja existe, o que falta, decisoes tomadas.",
        reliability="snapshot",
    ),
    DocumentSource(
        key="STATUS_V2",
        title="STATUS V2 — documentacao vs implementacao Agno",
        relative_path="JUDITH-AI-TEAM-V2/STATUS_V2.md",
        summary="Quais agentes existem em codigo e quais integracoes ainda sao TOOL PLANNED.",
        reliability="snapshot",
    ),
    DocumentSource(
        key="BUSINESS_RULES",
        title="BUSINESS_RULES — regras de negocio vinculantes (V2)",
        relative_path="JUDITH-AI-TEAM-V2/BUSINESS_RULES.md",
        summary="Regras que nenhuma decisao ou peca pode contradizer.",
    ),
    DocumentSource(
        key="COLLABORATION_PROTOCOL_V1",
        title="AGENT_COLLABORATION_PROTOCOL V1 — protocolo original",
        relative_path="JUDITH-AI-TEAM/agents/AGENT_COLLABORATION_PROTOCOL.md",
        summary="Hierarquia, formato de handoff, regra de consenso e as 8 regras de seguranca originais.",
    ),
    DocumentSource(
        key="COLLABORATION_PROTOCOL_V2",
        title="AGENT_COLLABORATION_PROTOCOL V2 — colaboracao e escalada",
        relative_path="JUDITH-AI-TEAM-V2/protocol/AGENT_COLLABORATION_PROTOCOL_V2.md",
        summary="Roteamento por intencao, escalada, e as regras de seguranca 9 a 12.",
    ),
    DocumentSource(
        key="HANDOFF_CONTRACT",
        title="AGENT_HANDOFF_CONTRACT — contrato de passagem de trabalho",
        relative_path="JUDITH-AI-TEAM-V2/protocol/AGENT_HANDOFF_CONTRACT.md",
        summary="Campos obrigatorios de um handoff entre agentes.",
    ),
    DocumentSource(
        key="AGENT_ROSTER",
        title="AGENT_ROSTER — quem faz o que no time",
        relative_path="JUDITH-AI-TEAM-V2/AGENT_ROSTER.md",
        summary="Os 21 papeis e o tier de cada um. Use para delegar ao agente certo.",
    ),
    DocumentSource(
        key="ORCHESTRATION_V2",
        title="ORCHESTRATION_V2 — como os workflows executam hoje",
        relative_path="JUDITH-AI-TEAM-V2/ORCHESTRATION_V2.md",
        summary="Registry, quality control deterministico e os 3 workflows implementados.",
    ),
    # --- Fontes de pesquisa e auditoria ---
    DocumentSource(
        key="COMMENTS_FAQ",
        title="COMMENTS_FAQ — duvidas recorrentes do publico",
        relative_path="JUDITH-AI-TEAM/sources/COMMENTS_FAQ.md",
        summary="Perguntas que o publico repete e as FAQs oficiais do site.",
        reliability="snapshot",
        caveat="Retrato manual antigo, nao um fluxo ao vivo de comentarios.",
    ),
    DocumentSource(
        key="COMPETITORS",
        title="COMPETITORS — analise de concorrentes",
        relative_path="JUDITH-AI-TEAM/sources/COMPETITORS.md",
        summary="Mapeamento manual de concorrentes.",
        reliability="snapshot",
    ),
    DocumentSource(
        key="INSTAGRAM_AUDIT",
        title="INSTAGRAM_AUDIT — auditoria manual do perfil",
        relative_path="JUDITH-AI-TEAM/sources/INSTAGRAM_AUDIT.md",
        summary="Numeros de perfil e analise de conteudo levantados a mao.",
        reliability="template",
        caveat="O documento se declara TEMPLATE e pede analise manual. NAO e metrica ao vivo do Instagram.",
    ),
    DocumentSource(
        key="WEBSITE_AUDIT",
        title="WEBSITE_AUDIT — auditoria do site",
        relative_path="JUDITH-AI-TEAM/sources/WEBSITE_AUDIT.md",
        summary="Estrutura e conteudo do site de vendas.",
        reliability="snapshot",
        excluded_sections=_BRAND_EXCLUDED,
    ),
    DocumentSource(
        key="PRODUCT_PAGES_AUDIT",
        title="PRODUCT_PAGES_AUDIT — auditoria das paginas de produto",
        relative_path="JUDITH-AI-TEAM/sources/PRODUCT_PAGES_AUDIT.md",
        summary="Paginas de produto a analisar e o template de analise.",
        reliability="template",
        caveat="O documento e um template de analise ainda nao preenchido — nao contem conclusoes reais.",
    ),
    # --- Playbooks de oficio (V1) ---
    DocumentSource(
        key="PLAYBOOK_HOOK",
        title="Playbook Hook Finder (V1) — tipos de hook e formato de saida",
        relative_path="JUDITH-AI-TEAM/agents/HOOK_FINDER.md",
        summary="Tipos de gancho, formato de entrega e regras de hook.",
    ),
    DocumentSource(
        key="PLAYBOOK_SCRIPT",
        title="Playbook Script Writer (V1) — estrutura de roteiro",
        relative_path="JUDITH-AI-TEAM/agents/SCRIPT_WRITER.md",
        summary="Estrutura de roteiro, ritmo e formato de entrega.",
    ),
    DocumentSource(
        key="PLAYBOOK_CAPTION",
        title="Playbook Caption Writer (V1) — estrutura de legenda e tipos de CTA",
        relative_path="JUDITH-AI-TEAM/agents/CAPTION_WRITER.md",
        summary="Estrutura ideal de legenda, tipos de CTA e regras de escrita.",
    ),
    DocumentSource(
        key="PLAYBOOK_VISUAL",
        title="Playbook Visual Creative (V1) — briefing visual",
        relative_path="JUDITH-AI-TEAM/agents/VISUAL_CREATIVE.md",
        summary="Como montar briefing visual, shot list e mood.",
    ),
    DocumentSource(
        key="PLAYBOOK_VIDEO",
        title="Playbook Video Editor (V1) — decisoes de edicao",
        relative_path="JUDITH-AI-TEAM/agents/VIDEO_EDITOR.md",
        summary="Cortes, ritmo, legendas e trilha.",
    ),
    DocumentSource(
        key="PLAYBOOK_SOCIAL",
        title="Playbook Social Media Manager (V1) — timing e formato",
        relative_path="JUDITH-AI-TEAM/agents/SOCIAL_MEDIA_MANAGER.md",
        summary="Timing, hashtags, formato e otimizacao por plataforma.",
    ),
    DocumentSource(
        key="PLAYBOOK_MARKETING_DIRECTOR",
        title="Playbook Marketing Director (V1) — plano de campanha",
        relative_path="JUDITH-AI-TEAM/agents/MARKETING_DIRECTOR.md",
        summary="Como montar campanha, mix de conteudo e alocacao.",
    ),
    DocumentSource(
        key="PLAYBOOK_BRAND_REVIEW",
        title="Playbook Brand Reviewer (V1) — checklist de revisao",
        relative_path="JUDITH-AI-TEAM/agents/BRAND_REVIEWER.md",
        summary="O que validar antes de aprovar e como rejeitar com motivo.",
    ),
    DocumentSource(
        key="PLAYBOOK_TREND",
        title="Playbook Trend Research (V1) — pesquisa de tendencia",
        relative_path="JUDITH-AI-TEAM/agents/TREND_RESEARCH.md",
        summary="Como contextualizar conteudo com tendencia e o que exige fonte.",
    ),
    DocumentSource(
        key="PLAYBOOK_VIRAL",
        title="Playbook Viral Research (V1) — analise de conteudo viral",
        relative_path="JUDITH-AI-TEAM/agents/VIRAL_RESEARCH_AGENT.md",
        summary="Criterios de analise viral e a regra de usar apenas dado publico.",
    ),
    DocumentSource(
        key="PLAYBOOK_METRICS",
        title="Playbook Metrics Analyst (V1) — leitura de performance",
        relative_path="JUDITH-AI-TEAM/agents/METRICS_ANALYST.md",
        summary="Que metricas acompanhar e como reportar.",
    ),
    DocumentSource(
        key="PLAYBOOK_PRODUCT_MARKETING",
        title="Playbook Product Marketing (V1) — narrativa de produto",
        relative_path="JUDITH-AI-TEAM/agents/PRODUCT_MARKETING.md",
        summary="Como posicionar e lancar um produto digital.",
    ),
    # --- Workflows ---
    DocumentSource(
        key="WORKFLOWS_V1",
        title="ORCHESTRATOR (V1) — pipelines de conteudo",
        relative_path="JUDITH-AI-TEAM/workflows/ORCHESTRATOR.md",
        summary="Sequencia de agentes em CREATE_REELS, CREATE_CAMPAIGN e REPURPOSE_CONTENT.",
    ),
    DocumentSource(
        key="WORKFLOW_CREATE_REEL",
        title="CREATE_REEL_FULL (V1) — pipeline completo de reel",
        relative_path="JUDITH-AI-TEAM/workflows/CREATE_REEL_FULL.md",
        summary="Etapas, entregaveis e gates do fluxo de reel.",
    ),
    DocumentSource(
        key="WORKFLOW_CREATE_CAMPAIGN",
        title="CREATE_CAMPAIGN (V1) — pipeline de campanha",
        relative_path="JUDITH-AI-TEAM/workflows/CREATE_CAMPAIGN.md",
        summary="Como planejar uma campanha de varios dias.",
    ),
    DocumentSource(
        key="WORKFLOW_REPURPOSE",
        title="REPURPOSE_CONTENT (V1) — reaproveitamento de conteudo",
        relative_path="JUDITH-AI-TEAM/workflows/REPURPOSE_CONTENT.md",
        summary="Como transformar uma peca em varias.",
    ),
    DocumentSource(
        key="DECISION_CARD",
        title="JUDITH_DECISION_CARD_TEMPLATE — formato de decisao para a Judith",
        relative_path="JUDITH-AI-TEAM/workflows/JUDITH_DECISION_CARD_TEMPLATE.md",
        summary="Como apresentar uma decisao que precisa de aprovacao humana.",
    ),
    DocumentSource(
        key="WORKFLOWS_V2_INDEX",
        title="WORKFLOWS_V2_INDEX — catalogo de workflows V2",
        relative_path="JUDITH-AI-TEAM-V2/workflows/WORKFLOWS_V2_INDEX.md",
        summary="Os workflows previstos em V2 e quais estao implementados.",
    ),
    # --- Modelos de governanca (V2) ---
    DocumentSource(
        key="MEMORY_MODEL",
        title="MEMORY_MODEL — tipos de memoria previstos",
        relative_path="JUDITH-AI-TEAM-V2/models/MEMORY_MODEL.md",
        summary="Session, Customer, Business e Agent Performance Memory.",
        caveat="Modelo conceitual: nenhuma dessas memorias esta implementada.",
    ),
    DocumentSource(
        key="LEARNING_EVALS_MODEL",
        title="LEARNING_EVALS_MODEL — ciclo de aprendizado e avaliacao",
        relative_path="JUDITH-AI-TEAM-V2/models/LEARNING_EVALS_MODEL.md",
        summary="Como uma melhoria vira versao nova, sempre com aprovacao humana.",
    ),
    DocumentSource(
        key="AUTONOMY_MODEL",
        title="AUTONOMY_MODEL — niveis de autonomia por agente",
        relative_path="JUDITH-AI-TEAM-V2/models/AUTONOMY_MODEL.md",
        summary="O que cada nivel permite e o que sempre exige humano.",
    ),
    DocumentSource(
        key="KNOWLEDGE_REFRESH_POLICY",
        title="KNOWLEDGE_REFRESH_POLICY — validade e atualizacao de fontes",
        relative_path="JUDITH-AI-TEAM-V2/models/KNOWLEDGE_REFRESH_POLICY.md",
        summary="Quando um documento vence e quem e dono de atualiza-lo.",
    ),
    DocumentSource(
        key="HANDOFF_EXAMPLES",
        title="HANDOFF_EXAMPLES — handoffs reais capturados de execucao",
        relative_path="JUDITH-AI-TEAM-V2/HANDOFF_EXAMPLES.md",
        summary="Exemplos reais de passagem de trabalho entre agentes.",
    ),
    # --- Video ---
    DocumentSource(
        key="VIDEO_ENGINE_PLAN",
        title="VIDEO_ENGINE_PLAN — arquitetura do motor de video",
        relative_path="JUDITH-AI-TEAM/docs/VIDEO_ENGINE_PLAN.md",
        summary="Pipeline de geracao de rascunho de reel e fases de implementacao.",
        reliability="snapshot",
        caveat="Plano escrito antes do motor Remotion existir — confira contra VIDEO_EDIT_SPEC, que e o contrato real em codigo.",
    ),
    DocumentSource(
        key="VIDEO_EDIT_SPEC",
        title="VideoEditSpec — contrato real de edicao (schema Zod)",
        relative_path="services/video-editor/src/schema/video-edit-spec.schema.ts",
        summary="Campos aceitos pelo motor de video: cenas, camadas, transicoes, export. Fonte de verdade do contrato.",
        root="project",
    ),
    # --- Evals ---
    DocumentSource(
        key="EVALS_README",
        title="EVALS README — estrutura de avaliacao dos agentes",
        relative_path="evals/README.md",
        summary="Formato de cases.yaml, status por agente e como rodar hoje.",
        root="project",
    ),
)

DOCUMENTS: dict[str, DocumentSource] = {source.key: source for source in _CATALOG}

# ---------------------------------------------------------------------------
# Craft knowledge — conhecimento GERAL de oficio
#
# Camada nova na Agent Foundation V2. Ate aqui os agentes so tinham fatos da
# Judith; nao tinham o oficio. Craft orienta JULGAMENTO profissional e nunca
# serve como evidencia de afirmacao factual sobre o negocio — claim comercial
# continua exigindo OFFERS/PRODUCTS.
# Ver docs/JUDITH-AI-TEAM-V2/knowledge/craft/README.md
# ---------------------------------------------------------------------------

_CRAFT_DIR = "JUDITH-AI-TEAM-V2/knowledge/craft"

_CRAFT: tuple[DocumentSource, ...] = tuple(
    DocumentSource(
        key=f"CRAFT_{nome}",
        title=f"Craft: {titulo}",
        relative_path=f"{_CRAFT_DIR}/{nome}_CRAFT.md",
        summary=f"Conhecimento GERAL de oficio: {titulo}. Nao e fato sobre a Bem me Que.",
    )
    for nome, titulo in (
        ("SHORTFORM", "atencao, hook, retencao e estrutura de video curto"),
        ("COPY", "legenda, legibilidade, CTA e copy educativa"),
        ("BRAND", "posicionamento, coerencia e revisao editorial"),
        ("CONVERSATION", "descoberta, objecao, suporte, de-escalation e roteamento"),
        ("OFFER_FUNNEL", "design de oferta, precificacao, funil e friccao"),
        ("ANALYTICS", "KPI, funil, coorte, atribuicao e variancia"),
        ("RESEARCH", "pesquisa qualitativa, sinal vs ruido e tendencia"),
        ("VISUAL", "hierarquia, composicao, legibilidade e continuidade"),
        ("STRATEGY", "objetivo, priorizacao, trade-off e decisao"),
        ("KNOWLEDGE_GOVERNANCE", "proveniencia, frescor, conflito e versionamento"),
        ("EVALUATION", "rubrica, gold set, regressao e taxonomia de falha"),
    )
)

DOCUMENTS.update({source.key: source for source in _CRAFT})



# As fichas V2 sao geradas a partir do disco, nao de uma lista escrita a mao:
# assim o catalogo nunca promete uma ficha que nao existe.
_FICHAS_DIR = DOCS_ROOT / "JUDITH-AI-TEAM-V2" / "agents"
AGENT_FICHAS: tuple[DocumentSource, ...] = tuple(
    DocumentSource(
        key=f"FICHA_{path.stem.replace('-', '_').upper()}",
        title=f"Ficha V2 — {path.stem}",
        relative_path=f"JUDITH-AI-TEAM-V2/agents/{path.name}",
        summary=f"Definicao completa do agente {path.stem}: papel, limites, knowledge, KPIs, failure modes.",
    )
    for path in sorted(_FICHAS_DIR.glob("*.md"))
)
DOCUMENTS.update({source.key: source for source in AGENT_FICHAS})


# ---------------------------------------------------------------------------
# Fontes que ainda NAO existem
# ---------------------------------------------------------------------------

_GAPS: tuple[MissingSource, ...] = (
    MissingSource(
        key="METRICAS_INSTAGRAM",
        title="Metricas ao vivo do Instagram (alcance, engajamento, retencao)",
        ask_agent="analytics-bi-agent",
        reason="Instagram Insights nao esta conectado (TOOL PLANNED). INSTAGRAM_AUDIT e levantamento manual, nao metrica.",
        keywords=("alcance", "engajamento", "retencao", "impressoes", "insights", "metrica", "metricas", "kpi", "kpis"),
    ),
    MissingSource(
        key="VENDAS_KIWIFY",
        title="Vendas, receita e reembolsos reais",
        ask_agent="analytics-bi-agent",
        reason="Integracao Kiwify nao existe (TOOL PLANNED). Nenhum numero de venda esta disponivel no sistema.",
        keywords=("venda", "vendas", "vendemos", "vendeu", "receita", "faturamento", "faturou", "reembolso", "kiwify", "pedido", "pedidos"),
    ),
    MissingSource(
        key="CRM_PIPELINE",
        title="Pipeline de leads e ciclo de vida do cliente",
        ask_agent="crm-lifecycle-agent",
        reason="CRM externo nao esta conectado (TOOL PLANNED).",
        keywords=("crm", "lead", "leads", "pipeline", "segmento", "segmentacao", "lifecycle", "churn"),
    ),
    MissingSource(
        key="HISTORICO_DM",
        title="Historico real de DMs e comentarios",
        ask_agent="customer-insights-agent",
        reason="Nenhum fluxo de DM/comentario esta conectado. COMMENTS_FAQ e um retrato manual antigo.",
        keywords=("dm", "dms", "comentario", "comentarios", "conversa", "conversas", "mensagens"),
    ),
    MissingSource(
        key="CALENDARIO_EDITORIAL",
        title="Calendario editorial vigente",
        ask_agent="social-media-manager",
        reason="Nao existe arquivo de calendario no repo — CONTENT_PILLARS traz apenas uma proporcao semanal sugerida.",
        keywords=("calendario", "cronograma", "agenda", "postagens", "publicacoes", "programacao"),
    ),
    MissingSource(
        key="HISTORICO_POSTS",
        title="Historico de posts publicados e sua performance",
        ask_agent="analytics-bi-agent",
        reason="Nao ha base de posts publicados; o Instagram nao esta conectado.",
        keywords=("historico", "posts", "publicados", "performance", "performou", "funcionou", "resultado"),
    ),
    MissingSource(
        key="EXEMPLOS_APROVADOS",
        title="Historico de pecas aprovadas e rejeitadas",
        ask_agent="brand-reviewer",
        reason="Nenhum historico de aprovacao/rejeicao e persistido — nao ha exemplo real para calibrar.",
        keywords=("exemplo", "exemplos", "aprovado", "aprovados", "rejeitado", "rejeitados", "precedente"),
    ),
    MissingSource(
        key="DECISOES_ESTRATEGICAS",
        title="Decisoes estrategicas anteriores",
        ask_agent="cmo",
        reason="Business Memory nao esta implementada — decisoes passadas nao sobrevivem entre sessoes.",
        keywords=("decisao", "decisoes", "decidimos", "precedente", "anteriores"),
    ),
    MissingSource(
        key="TENDENCIAS_ATUAIS",
        title="Tendencias de mercado atuais",
        ask_agent="market-trend-intelligence",
        reason="Nenhuma fonte externa de tendencia esta conectada (Apify/scraping sao TOOL PLANNED).",
        keywords=("tendencia", "tendencias", "trend", "trends", "viral", "viralizar", "audio", "trending"),
    ),
    MissingSource(
        key="DATA_DICTIONARY",
        title="Dicionario de dados e definicoes de KPI",
        ask_agent="analytics-bi-agent",
        reason="Nao existe data dictionary nem documento de definicao de KPI no repo.",
        keywords=("definicao", "dicionario", "atribuicao", "attribution", "formula", "calculo"),
    ),
    MissingSource(
        key="GOLD_DATASET",
        title="Gold dataset e resultados de regressao dos agentes",
        ask_agent="ai-performance-evals-agent",
        reason="evals/*/cases.yaml existem, mas nao ha gold dataset preenchido nem pipeline de regressao rodando.",
        keywords=("gold", "dataset", "regressao", "baseline", "score", "nota", "avaliacao"),
    ),
    MissingSource(
        key="CASOS_SUPORTE",
        title="Casos de suporte resolvidos",
        ask_agent="customer-support-agent",
        reason="Nao ha base de tickets ou casos resolvidos documentados.",
        keywords=("ticket", "tickets", "caso", "casos", "chamado", "atendimento"),
    ),
)

MISSING: dict[str, MissingSource] = {gap.key: gap for gap in _GAPS}


# ---------------------------------------------------------------------------
# Politicas por agente
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentKnowledgePolicy:
    """Whitelist de um agente: o que ele pode abrir e o que sabe que falta."""

    agent_id: str
    documents: tuple[DocumentSource, ...]
    missing_sources: tuple[MissingSource, ...] = ()


def _policy(agent_id: str, docs: Sequence[str], gaps: Sequence[str] = ()) -> AgentKnowledgePolicy:
    return AgentKnowledgePolicy(
        agent_id=agent_id,
        documents=tuple(DOCUMENTS[key] for key in docs),
        missing_sources=tuple(MISSING[key] for key in gaps),
    )


_KNOWLEDGE_GOVERNANCE_DOCS = (
    "KNOWLEDGE_REFRESH_POLICY",
    "MEMORY_MODEL",
    "LEARNING_EVALS_MODEL",
    "AUTONOMY_MODEL",
    "BUSINESS_RULES",
    "COLLABORATION_PROTOCOL_V1",
    "COLLABORATION_PROTOCOL_V2",
    "HANDOFF_CONTRACT",
    "AGENT_ROSTER",
    "STATUS",
    "STATUS_V2",
    "PRD",
    "ORCHESTRATION_V2",
    "WORKFLOWS_V2_INDEX",
    "BRAND",
    "VOICE",
    "AUDIENCE",
    "CONTENT_PILLARS",
    "VISUAL_IDENTITY",
    "PRODUCTS",
    "OFFERS",
)

_POLICIES: tuple[AgentKnowledgePolicy, ...] = (
    _policy(
        "marketing-director",
        ("BRAND", "AUDIENCE", "PRODUCTS", "OFFERS", "CONTENT_PILLARS", "PLAYBOOK_MARKETING_DIRECTOR",
         "WORKFLOW_CREATE_CAMPAIGN", "WORKFLOWS_V1", "BUSINESS_RULES", "AGENT_ROSTER")
        + ("CRAFT_STRATEGY", "CRAFT_OFFER_FUNNEL", "CRAFT_ANALYTICS",),
        ("CALENDARIO_EDITORIAL", "HISTORICO_POSTS", "METRICAS_INSTAGRAM", "VENDAS_KIWIFY", "DECISOES_ESTRATEGICAS"),
    ),
    _policy(
        "social-media-manager",
        ("BRAND", "VOICE", "AUDIENCE", "CONTENT_PILLARS", "PLAYBOOK_SOCIAL", "INSTAGRAM_AUDIT",
         "WORKFLOWS_V1", "BUSINESS_RULES", "AGENT_ROSTER")
        + ("CRAFT_COPY", "CRAFT_SHORTFORM", "CRAFT_ANALYTICS",),
        ("CALENDARIO_EDITORIAL", "HISTORICO_POSTS", "METRICAS_INSTAGRAM", "TENDENCIAS_ATUAIS"),
    ),
    _policy(
        "market-trend-intelligence",
        ("AUDIENCE", "CONTENT_PILLARS", "PRODUCTS", "COMPETITORS", "INSTAGRAM_AUDIT", "WEBSITE_AUDIT",
         "PLAYBOOK_TREND", "PLAYBOOK_VIRAL", "BUSINESS_RULES")
        + ("CRAFT_RESEARCH",),
        ("TENDENCIAS_ATUAIS", "METRICAS_INSTAGRAM", "HISTORICO_POSTS"),
    ),
    _policy(
        "hook-finder",
        ("VOICE", "AUDIENCE", "CONTENT_PILLARS", "PLAYBOOK_HOOK", "COMMENTS_FAQ", "BUSINESS_RULES")
        + ("CRAFT_SHORTFORM",),
        ("METRICAS_INSTAGRAM", "EXEMPLOS_APROVADOS", "HISTORICO_POSTS", "TENDENCIAS_ATUAIS"),
    ),
    _policy(
        "script-writer",
        ("BRAND", "VOICE", "AUDIENCE", "CONTENT_PILLARS", "PRODUCTS", "OFFERS", "PLAYBOOK_SCRIPT",
         "WORKFLOW_CREATE_REEL", "BUSINESS_RULES")
        + ("CRAFT_SHORTFORM", "CRAFT_COPY",),
        ("EXEMPLOS_APROVADOS", "HISTORICO_POSTS"),
    ),
    _policy(
        "caption-writer",
        ("BRAND", "VOICE", "AUDIENCE", "CONTENT_PILLARS", "PRODUCTS", "OFFERS", "PLAYBOOK_CAPTION",
         "COMMENTS_FAQ", "BUSINESS_RULES")
        + ("CRAFT_COPY",),
        ("EXEMPLOS_APROVADOS", "HISTORICO_POSTS"),
    ),
    _policy(
        "visual-creative",
        ("BRAND", "VISUAL_IDENTITY", "CONTENT_PILLARS", "PLAYBOOK_VISUAL", "PRODUCTS", "BUSINESS_RULES")
        + ("CRAFT_VISUAL",),
        ("EXEMPLOS_APROVADOS",),
    ),
    _policy(
        "video-editor",
        ("BRAND", "VOICE", "VISUAL_IDENTITY", "VIDEO_ENGINE_PLAN", "VIDEO_EDIT_SPEC", "PLAYBOOK_VIDEO",
         "CONTENT_PILLARS", "BUSINESS_RULES")
        + ("CRAFT_VISUAL", "CRAFT_SHORTFORM",),
        ("EXEMPLOS_APROVADOS", "METRICAS_INSTAGRAM"),
    ),
    _policy(
        "offer-funnel-strategist",
        ("PRODUCTS", "OFFERS", "AUDIENCE", "BRAND", "WEBSITE_AUDIT", "PRODUCT_PAGES_AUDIT", "COMMENTS_FAQ",
         "PLAYBOOK_PRODUCT_MARKETING", "BUSINESS_RULES")
        + ("CRAFT_OFFER_FUNNEL", "CRAFT_ANALYTICS",),
        ("VENDAS_KIWIFY", "METRICAS_INSTAGRAM", "CRM_PIPELINE", "HISTORICO_DM"),
    ),
    _policy(
        "sales-conversion-agent",
        ("PRODUCTS", "OFFERS", "AUDIENCE", "VOICE", "COMMENTS_FAQ", "WEBSITE_AUDIT", "BUSINESS_RULES")
        + ("CRAFT_CONVERSATION",),
        ("VENDAS_KIWIFY", "CRM_PIPELINE", "HISTORICO_DM"),
    ),
    _policy(
        "crm-lifecycle-agent",
        ("PRODUCTS", "OFFERS", "AUDIENCE", "VOICE", "BUSINESS_RULES", "COLLABORATION_PROTOCOL_V2")
        + ("CRAFT_CONVERSATION",),
        ("CRM_PIPELINE", "VENDAS_KIWIFY", "HISTORICO_DM"),
    ),
    _policy(
        "community-dm-agent",
        ("BRAND", "VOICE", "AUDIENCE", "PRODUCTS", "OFFERS", "COMMENTS_FAQ", "AGENT_ROSTER",
         "COLLABORATION_PROTOCOL_V2", "BUSINESS_RULES")
        + ("CRAFT_CONVERSATION",),
        ("HISTORICO_DM", "EXEMPLOS_APROVADOS"),
    ),
    _policy(
        "customer-support-agent",
        ("PRODUCTS", "OFFERS", "COMMENTS_FAQ", "WEBSITE_AUDIT", "VOICE", "BUSINESS_RULES",
         "COLLABORATION_PROTOCOL_V2")
        + ("CRAFT_CONVERSATION",),
        ("CASOS_SUPORTE", "VENDAS_KIWIFY", "CRM_PIPELINE"),
    ),
    _policy(
        "analytics-bi-agent",
        ("PLAYBOOK_METRICS", "INSTAGRAM_AUDIT", "WEBSITE_AUDIT", "PRODUCT_PAGES_AUDIT", "PRODUCTS", "OFFERS",
         "CONTENT_PILLARS", "STATUS_V2", "BUSINESS_RULES")
        + ("CRAFT_ANALYTICS",),
        ("METRICAS_INSTAGRAM", "VENDAS_KIWIFY", "CRM_PIPELINE", "DATA_DICTIONARY", "HISTORICO_POSTS"),
    ),
    _policy(
        "customer-insights-agent",
        ("AUDIENCE", "COMMENTS_FAQ", "PRODUCTS", "COMPETITORS", "WEBSITE_AUDIT", "BUSINESS_RULES")
        + ("CRAFT_RESEARCH",),
        ("HISTORICO_DM", "VENDAS_KIWIFY", "CRM_PIPELINE"),
    ),
    _policy(
        "knowledge-manager",
        _KNOWLEDGE_GOVERNANCE_DOCS + tuple(source.key for source in AGENT_FICHAS)
        + ("CRAFT_KNOWLEDGE_GOVERNANCE",),
        ("DECISOES_ESTRATEGICAS", "EXEMPLOS_APROVADOS", "METRICAS_INSTAGRAM", "VENDAS_KIWIFY"),
    ),
    _policy(
        "ai-performance-evals-agent",
        ("EVALS_README", "LEARNING_EVALS_MODEL", "AUTONOMY_MODEL", "ORCHESTRATION_V2", "HANDOFF_CONTRACT",
         "HANDOFF_EXAMPLES", "STATUS_V2", "AGENT_ROSTER", "BUSINESS_RULES")
        + tuple(source.key for source in AGENT_FICHAS)
        + ("CRAFT_EVALUATION",),
        ("GOLD_DATASET", "METRICAS_INSTAGRAM", "EXEMPLOS_APROVADOS", "HISTORICO_POSTS"),
    ),
    _policy(
        "brand-reviewer",
        ("BRAND", "VOICE", "AUDIENCE", "CONTENT_PILLARS", "VISUAL_IDENTITY", "PRODUCTS", "OFFERS",
         "PLAYBOOK_BRAND_REVIEW", "BUSINESS_RULES", "COLLABORATION_PROTOCOL_V1")
        + ("CRAFT_BRAND", "CRAFT_COPY",),
        ("EXEMPLOS_APROVADOS", "METRICAS_INSTAGRAM"),
    ),
)

KNOWLEDGE_POLICIES: dict[str, AgentKnowledgePolicy] = {policy.agent_id: policy for policy in _POLICIES}

# CMO e Brand Architect ja tinham catalogo proprio de rodadas anteriores.
# Sao registrados por referencia para que os testes de isolamento e o
# inventario cubram o time inteiro, sem reescrever nenhum dos dois.
KNOWLEDGE_POLICIES["cmo"] = AgentKnowledgePolicy(
    agent_id="cmo", documents=CMO_DOCUMENTS, missing_sources=CMO_MISSING_SOURCES
)
KNOWLEDGE_POLICIES["brand-architect"] = AgentKnowledgePolicy(
    agent_id="brand-architect",
    documents=BRAND_ARCHITECT_DOCUMENTS,
    missing_sources=BRAND_ARCHITECT_MISSING_SOURCES,
)


def register_policy(policy: AgentKnowledgePolicy) -> None:
    """Registra a politica de um agente que monta o catalogo por conta propria."""

    KNOWLEDGE_POLICIES[policy.agent_id] = policy


class UnknownAgentPolicyError(KeyError):
    """agent_id sem politica de Knowledge declarada."""


def get_policy(agent_id: str) -> AgentKnowledgePolicy:
    try:
        return KNOWLEDGE_POLICIES[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(KNOWLEDGE_POLICIES))
        raise UnknownAgentPolicyError(f'agente "{agent_id}" nao tem politica de Knowledge. Conhecidos: {known}') from exc


# ---------------------------------------------------------------------------
# Fabrica: agent_id -> retriever + tools
# ---------------------------------------------------------------------------


def build_retriever_for(agent_id: str) -> Callable[..., list[dict[Any, Any] | str]]:
    """Retriever que alimenta a tool nativa `search_knowledge_base` do Agno.

    F2.8: o agente promovido tem este retriever apontado para o Brain tambem.

    Sem isso ele ficaria com DOIS caminhos de conhecimento — as tools do Brain
    e este retriever no lexical congelado, que devolve nada. O modelo escolhe
    um dos dois sem saber a diferenca, e metade das perguntas volta com
    "nenhuma fonte consultada" mesmo com o conteudo disponivel. Foi exatamente
    o que apareceu no primeiro teste em producao.
    """

    from brain.cutover import build_brain_retriever_for, is_brain_native

    if is_brain_native(agent_id):
        return build_brain_retriever_for(agent_id)

    policy = get_policy(agent_id)
    return build_knowledge_retriever(policy.documents, policy.missing_sources)


def build_knowledge_tools_for(agent_id: str) -> list[Any]:
    """As duas tools de consulta, ligadas a whitelist deste agente.

    Sao closures sobre a politica: o agente nao consegue pedir um documento
    que nao esta na lista dele, porque `read_document` so conhece a lista.
    """

    # F2.8: agente promovido le do Brain. A troca acontece aqui, num ponto so,
    # e e revertida apagando o nome de BRAIN_NATIVE_AGENTS. Ver brain/cutover.py.
    from brain.cutover import build_brain_tools_for, is_brain_native

    if is_brain_native(agent_id):
        return build_brain_tools_for(agent_id)

    policy = get_policy(agent_id)
    chaves = ", ".join(source.key for source in policy.documents)

    def listar_fontes_disponiveis() -> dict[str, Any]:
        return build_source_catalog(policy.documents, policy.missing_sources)

    def ler_documento(fonte: str) -> dict[str, Any]:
        return read_document(fonte, policy.documents)

    listar_fontes_disponiveis.__doc__ = (
        "Lista as fontes que voce pode consultar e, principalmente, as que NAO "
        "existem — com o agente responsavel por cada lacuna.\n\n"
        "Listar NAO e consultar: para citar evidencia, abra o documento."
    )
    ler_documento.__doc__ = (
        "Le um documento inteiro pela chave e devolve conteudo, confiabilidade "
        f"e ressalvas.\n\nChaves validas: {chaves}."
    )

    return [
        tool(name="listar_fontes_disponiveis")(listar_fontes_disponiveis),
        tool(name="ler_documento")(ler_documento),
    ]
