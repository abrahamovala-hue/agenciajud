"""
Knowledge Sources — acesso sob demanda aos documentos reais do repositorio.
---------------------------------------------------------------------------

Por que este modulo existe:

O protocolo (Regra 5, "Referencia Obrigatoria") exige que toda decisao cite
uma fonte. Ate agora os agentes nao tinham como consultar fonte nenhuma - o
conhecimento estava congelado dentro das `instructions`. Isso e o oposto do
que a ficha manda: "Instructions dizem COMO agir; Knowledge fornece O QUE
consultar".

Como isto se conecta ao Agno (mecanismo nativo, sem abstracao propria):

O Agno adiciona a tool nativa `search_knowledge_base` quando
`agent.knowledge_retriever is not None and agent.search_knowledge` - NAO e
obrigatorio ter `Knowledge`/vector DB (ver agno/agent/_tools.py). Entao
plugamos um retriever que le os markdowns reais do repo. O agente decide
sozinho quando buscar; nada e injetado no contexto de graca.

O que este modulo deliberadamente NAO faz:

- Nao cria tabela, nao gera embedding, nao toca no Postgres. RAG vetorial via
  `db.create_knowledge()` continua sendo o passo futuro, e exige mudanca
  estrutural de banco.
- Nao inventa fonte. Uma fonte que ainda nao existe (KPI ao vivo, receita,
  CRM) e declarada como `FONTE_NAO_DISPONIVEL` junto com o agente que deve
  ser acionado - e isso vai para o modelo como resultado da busca, para que
  ele nao preencha a lacuna com invencao.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs"

# Raizes permitidas para uma fonte. A maioria dos documentos vive em `docs/`,
# mas alguns conhecimentos reais estao fora dela (`evals/`, a especificacao
# VideoEditSpec em `services/`). O campo `root` evita ter que reescrever os
# caminhos ja existentes.
_ROOTS = {"docs": DOCS_ROOT, "project": PROJECT_ROOT}

# Trecho maximo devolvido por secao. Os documentos deste repo sao pequenos
# (1-14 KB); o corte existe para o caso de STATUS.md crescer.
_MAX_SECTION_CHARS = 2400
_DEFAULT_NUM_DOCUMENTS = 4
_LEAD_SECTION_TITLE = "(inicio do documento)"


@dataclass(frozen=True)
class DocumentSource:
    """Um documento markdown real, versionado no repo."""

    key: str
    title: str
    relative_path: str
    summary: str
    # "vigente"  -> documento de referencia estavel (marca, regras, protocolo)
    # "snapshot" -> retrato de um momento; NAO e metrica ao vivo
    # "template" -> o proprio documento se declara incompleto/a preencher
    reliability: str = "vigente"
    # Ressalva pontual dentro de um documento vigente (ex.: uma secao marcada
    # "A VERIFICAR"). Vai junto do resultado; so aparece quando existe, para
    # nao mudar o payload de fontes que nao tem ressalva.
    caveat: str = ""
    # Secoes que este agente nao deve receber (titulo exato do "## ").
    # Usado para nao expor bloco irrelevante/sensivel ao papel do agente.
    excluded_sections: tuple[str, ...] = ()
    # "docs" (padrao) ou "project" — ver _ROOTS.
    root: str = "docs"

    @property
    def path(self) -> Path:
        return _ROOTS[self.root] / self.relative_path


@dataclass(frozen=True)
class MissingSource:
    """Uma fonte que a ficha do agente preve, mas que ainda nao existe.

    Existe explicitamente para que o agente responda "nao tenho esse dado,
    peca a X" em vez de alucinar um numero.
    """

    key: str
    title: str
    ask_agent: str
    reason: str
    keywords: tuple[str, ...]


# ---------------------------------------------------------------------------
# Catalogo do CMO (secao 5 da ficha docs/JUDITH-AI-TEAM-V2/agents/01-cmo.md)
# ---------------------------------------------------------------------------

CMO_DOCUMENTS: tuple[DocumentSource, ...] = (
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
        key="BRAND",
        title="BRAND — identidade da marca Bem me Que",
        relative_path="JUDITH-AI-TEAM/brand/BRAND.md",
        summary="Posicionamento, valores e promessa da marca.",
        # Excecao de seguranca (unica alteracao ao catalogo do CMO apos a
        # aprovacao dele): o bloco de tracking carrega IDs de pixel e um token
        # de verificacao. Nao serve a nenhuma decisao de marketing e nao deve
        # circular em briefing, log ou resposta. Mesma protecao ja aplicada ao
        # catalogo compartilhado em agents/knowledge_policies.py.
        excluded_sections=("Tracking e Analytics",),
    ),
    DocumentSource(
        key="VOICE",
        title="VOICE — tom de voz",
        relative_path="JUDITH-AI-TEAM/brand/VOICE.md",
        summary="Como a marca fala e o que ela nunca diz.",
    ),
    DocumentSource(
        key="AUDIENCE",
        title="AUDIENCE — publico-alvo",
        relative_path="JUDITH-AI-TEAM/brand/AUDIENCE.md",
        summary="Personas, dores, linguagem do publico.",
    ),
    DocumentSource(
        key="PRODUCTS",
        title="PRODUCTS — catalogo de produtos",
        relative_path="JUDITH-AI-TEAM/brand/PRODUCTS.md",
        summary="Produtos digitais, politica de garantia.",
    ),
    DocumentSource(
        key="OFFERS",
        title="OFFERS — precos, ofertas e links oficiais",
        relative_path="JUDITH-AI-TEAM/brand/OFFERS.md",
        summary="Unica fonte legitima de preco, desconto e link de compra.",
    ),
    DocumentSource(
        key="CONTENT_PILLARS",
        title="CONTENT_PILLARS — pilares de conteudo",
        relative_path="JUDITH-AI-TEAM/brand/CONTENT_PILLARS.md",
        summary="Pilares editoriais e proporcao entre eles.",
    ),
    DocumentSource(
        key="BUSINESS_RULES",
        title="BUSINESS_RULES — regras de negocio vinculantes (V2)",
        relative_path="JUDITH-AI-TEAM-V2/BUSINESS_RULES.md",
        summary="Regras que nenhuma decisao pode contradizer.",
    ),
    DocumentSource(
        key="COLLABORATION_PROTOCOL_V2",
        title="AGENT_COLLABORATION_PROTOCOL V2 — como o time colabora",
        relative_path="JUDITH-AI-TEAM-V2/protocol/AGENT_COLLABORATION_PROTOCOL_V2.md",
        summary="Hierarquia, escalada, consenso, regras de seguranca.",
    ),
    DocumentSource(
        key="AGENT_ROSTER",
        title="AGENT_ROSTER — quem faz o que no time",
        relative_path="JUDITH-AI-TEAM-V2/AGENT_ROSTER.md",
        summary="Os 21 papeis e o tier de cada um. Use para delegar ao agente certo.",
    ),
    DocumentSource(
        key="INSTAGRAM_AUDIT",
        title="INSTAGRAM_AUDIT — auditoria de Instagram",
        relative_path="JUDITH-AI-TEAM/sources/INSTAGRAM_AUDIT.md",
        summary="Retrato manual do perfil. NAO e metrica ao vivo.",
        reliability="template",
    ),
    DocumentSource(
        key="WEBSITE_AUDIT",
        title="WEBSITE_AUDIT — auditoria do site",
        relative_path="JUDITH-AI-TEAM/sources/WEBSITE_AUDIT.md",
        summary="Retrato manual do site. NAO e metrica ao vivo.",
        reliability="snapshot",
        # Mesmo bloco de IDs de tracking que existe no BRAND.md - esta
        # duplicado aqui, entao a protecao tambem precisa estar.
        excluded_sections=("Tracking e Analytics",),
    ),
    DocumentSource(
        key="COMMENTS_FAQ",
        title="COMMENTS_FAQ — duvidas recorrentes do publico",
        relative_path="JUDITH-AI-TEAM/sources/COMMENTS_FAQ.md",
        summary="Perguntas que o publico repete. Base qualitativa, nao quantitativa.",
        reliability="snapshot",
    ),
    DocumentSource(
        key="COMPETITORS",
        title="COMPETITORS — analise de concorrentes",
        relative_path="JUDITH-AI-TEAM/sources/COMPETITORS.md",
        summary="Mapeamento manual de concorrentes.",
        reliability="snapshot",
    ),
)

CMO_MISSING_SOURCES: tuple[MissingSource, ...] = (
    MissingSource(
        key="KPIS_ATUAIS",
        title="KPIs atuais (alcance, engajamento, conversao)",
        ask_agent="analytics-bi-agent",
        reason="Instagram Insights e Kiwify ainda sao TOOL PLANNED — nao ha metrica ao vivo no sistema.",
        keywords=("kpi", "metrica", "metricas", "alcance", "engajamento", "conversao", "performance", "resultado"),
    ),
    MissingSource(
        key="RECEITA",
        title="Receita / vendas realizadas",
        ask_agent="analytics-bi-agent",
        reason="Integracao Kiwify nao existe. Nenhum numero de venda esta disponivel no sistema.",
        keywords=("receita", "faturamento", "vendas", "vendemos", "vendeu", "vendido", "kiwify", "pedidos"),
    ),
    MissingSource(
        key="CAMPANHAS_ATIVAS",
        title="Campanhas em andamento",
        ask_agent="marketing-director",
        reason="Nao ha registro persistido de campanhas ativas.",
        keywords=("campanha", "campanhas", "calendario", "cronograma", "planejamento"),
    ),
    MissingSource(
        key="CUSTOMER_INSIGHTS_LIVE",
        title="Insights de cliente a partir de conversas reais",
        ask_agent="customer-insights-agent",
        reason="Nao ha volume de DM/comentario conectado; COMMENTS_FAQ e um retrato manual antigo.",
        keywords=("dor", "dores", "objecao", "objecoes", "insight", "insights", "cliente", "clientes", "publico"),
    ),
    MissingSource(
        key="TREND_INTELLIGENCE",
        title="Tendencias de mercado atuais",
        ask_agent="market-trend-intelligence",
        reason="Pesquisa de tendencia nao esta conectada a nenhuma fonte externa.",
        keywords=("tendencia", "tendencias", "trend", "trends", "viral", "mercado"),
    ),
    MissingSource(
        key="CRM_PIPELINE",
        title="Pipeline de leads e ciclo de vida",
        ask_agent="crm-lifecycle-agent",
        reason="CRM externo nao esta conectado.",
        keywords=("crm", "lead", "leads", "pipeline", "funil", "lifecycle"),
    ),
    MissingSource(
        key="DECISOES_ANTERIORES",
        title="Historico de decisoes estrategicas anteriores",
        ask_agent="judith",
        reason="Business Memory nao esta implementada — decisoes passadas nao sao persistidas entre sessoes.",
        keywords=("decisao", "decisoes", "historico", "anterior", "anteriores", "precedente"),
    ),
)


# ---------------------------------------------------------------------------
# Catalogo do Brand Architect
# (secao Knowledge da ficha docs/JUDITH-AI-TEAM-V2/agents/02-brand-architect.md)
#
# Whitelist propria, deliberadamente diferente da do CMO: o Brand Architect
# nao enxerga PRD/STATUS/OFFERS/auditorias - o papel dele e direcao de marca,
# nao prioridade de negocio nem preco. Em compensacao ele enxerga
# VISUAL_IDENTITY, que o CMO nao precisa.
# ---------------------------------------------------------------------------

BRAND_ARCHITECT_DOCUMENTS: tuple[DocumentSource, ...] = (
    DocumentSource(
        key="BRAND",
        title="BRAND — identidade, posicionamento e diferenciais",
        relative_path="JUDITH-AI-TEAM/brand/BRAND.md",
        summary="Posicionamento oficial, proposta de valor, diferenciais, palavras-chave da marca.",
        # Bloco de IDs de pixel/analytics: irrelevante para direcao de marca e
        # nao deve circular em briefing ou legenda.
        excluded_sections=("Tracking e Analytics",),
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
        title="PRODUCTS — catalogo e posicionamento de produto",
        relative_path="JUDITH-AI-TEAM/brand/PRODUCTS.md",
        summary="Produtos digitais e como cada um se posiciona. Consulte quando o tema for posicionamento de produto.",
        caveat="A secao de produtos futuros esta marcada como 'a ser preenchida com Judith'.",
    ),
    DocumentSource(
        key="COMPETITORS",
        title="COMPETITORS — analise de concorrentes",
        relative_path="JUDITH-AI-TEAM/sources/COMPETITORS.md",
        summary="Mapeamento manual de concorrentes. Base para argumentar diferenciacao.",
        reliability="snapshot",
    ),
    DocumentSource(
        key="BUSINESS_RULES",
        title="BUSINESS_RULES — regras de negocio vinculantes (V2)",
        relative_path="JUDITH-AI-TEAM-V2/BUSINESS_RULES.md",
        summary="Regras que nenhuma direcao de marca pode contradizer.",
    ),
    DocumentSource(
        key="COLLABORATION_PROTOCOL_V2",
        title="AGENT_COLLABORATION_PROTOCOL V2 — colaboracao e escalada",
        relative_path="JUDITH-AI-TEAM-V2/protocol/AGENT_COLLABORATION_PROTOCOL_V2.md",
        summary="Quem decide o que, como escalar conflito, o que exige aprovacao humana.",
    ),
    DocumentSource(
        key="AGENT_ROSTER",
        title="AGENT_ROSTER — quem faz o que no time",
        relative_path="JUDITH-AI-TEAM-V2/AGENT_ROSTER.md",
        summary="Os 21 papeis. Use para delegar execucao ao agente certo.",
    ),
)

BRAND_ARCHITECT_MISSING_SOURCES: tuple[MissingSource, ...] = (
    MissingSource(
        key="EXEMPLOS_APROVADOS_REJEITADOS",
        title="Historico de pecas aprovadas e rejeitadas pelo Brand Reviewer",
        ask_agent="brand-reviewer",
        reason="Nenhum historico de aprovacao/rejeicao e persistido — nao ha como calibrar 'o que parece a marca' por exemplo real.",
        keywords=("exemplo", "exemplos", "aprovado", "aprovados", "rejeitado", "rejeitados", "historico", "precedente"),
    ),
    MissingSource(
        key="DECISOES_ESTRATEGICAS",
        title="Decisoes estrategicas anteriores de posicionamento",
        ask_agent="cmo",
        reason="Business Memory nao esta implementada — decisoes passadas nao sobrevivem entre sessoes.",
        keywords=("decisao", "decisoes", "posicionamento anterior", "ja decidimos", "antes"),
    ),
    MissingSource(
        key="PERFORMANCE_POR_PILAR",
        title="Performance historica por pilar/angulo de conteudo",
        ask_agent="analytics-bi-agent",
        reason="Instagram Insights nao esta conectado — nao ha dado de qual pilar performou melhor.",
        keywords=("performance", "engajamento", "alcance", "metrica", "metricas", "kpi", "resultado", "funcionou"),
    ),
    MissingSource(
        key="RECEITA",
        title="Faturamento e vendas realizadas",
        ask_agent="analytics-bi-agent",
        reason="Integracao Kiwify nao existe, e faturamento esta fora do escopo do Brand Architect.",
        keywords=("faturamento", "faturou", "receita", "vendas", "vendemos", "vendeu", "lucro", "kiwify"),
    ),
    MissingSource(
        key="TENDENCIAS",
        title="Tendencias de mercado atuais",
        ask_agent="market-trend-intelligence",
        reason="Pesquisa de tendencia nao esta conectada a fonte externa, e nao e papel do Brand Architect pesquisar.",
        keywords=("tendencia", "tendencias", "trend", "trends", "viral", "viralizar", "mercado"),
    ),
)


# ---------------------------------------------------------------------------
# Leitura e busca
# ---------------------------------------------------------------------------

_PT_STOPWORDS = frozenset(
    ["a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sob", "sobre", "e", "ou", "mas", "que", "qual", "quais", "quando", "onde", "como", "porque", "pois", "se", "ja", "nao", "sim", "ao", "aos", "pelo", "pela", "ser", "estar", "tem", "ter", "foi", "era", "sao", "isso", "isto", "aquilo", "esse", "essa", "este", "esta", "meu", "minha", "nosso", "nossa", "me", "te", "se", "lhe", "nos", "vos", "eu", "voce", "vc", "ele", "ela", "eles", "elas", "quero", "queria", "preciso", "pode", "posso", "deve", "mais", "menos", "muito", "pouco", "todo", "toda", "todos", "todas", "cada", "outro", "outra", "qualquer", "entao", "agora"]
)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.casefold()


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", _normalize(text))
    return [t for t in tokens if len(t) >= 3 and t not in _PT_STOPWORDS]


@lru_cache(maxsize=256)
def _load(relative_path: str, root: str = "docs") -> str:
    return (_ROOTS[root] / relative_path).read_text(encoding="utf-8")


def _split_sections(content: str) -> list[tuple[str, str]]:
    """Divide o markdown em (titulo_da_secao, texto). Corta em '## '."""

    lines = content.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = _LEAD_SECTION_TITLE
    current: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if any(l.strip() for l in current):
                sections.append((current_title, current))
            current_title = line[3:].strip()
            current = []
        else:
            current.append(line)

    if any(l.strip() for l in current):
        sections.append((current_title, current))

    return [(title, "\n".join(body).strip()) for title, body in sections]


def _visible_sections(source: DocumentSource) -> list[tuple[str, str]]:
    """Secoes do documento menos as que este agente nao deve receber."""

    sections = _split_sections(_load(source.relative_path, source.root))
    if not source.excluded_sections:
        return sections
    return [(title, body) for title, body in sections if title not in source.excluded_sections]


def _render(sections: Sequence[tuple[str, str]]) -> str:
    parts = [body if title == _LEAD_SECTION_TITLE else f"## {title}\n\n{body}" for title, body in sections]
    return "\n\n".join(parts)


def read_document(key: str, sources: Sequence[DocumentSource]) -> dict[str, Any]:
    """Devolve o documento inteiro. Erro explicito se a chave nao existir."""

    catalog = {source.key: source for source in sources}
    source = catalog.get(key.strip().upper())
    if source is None:
        return {
            "status": "CHAVE_INVALIDA",
            "chave_pedida": key,
            "chaves_validas": sorted(catalog),
        }

    if not source.path.exists():
        # Documento catalogado mas ausente do disco: nunca fingir que leu.
        return {"status": "ARQUIVO_AUSENTE", "documento": source.title, "arquivo": source.relative_path}

    payload: dict[str, Any] = {
        "status": "OK",
        "documento": source.title,
        "arquivo": source.relative_path,
        "confiabilidade": source.reliability,
        "conteudo": _render(_visible_sections(source)),
    }
    if source.caveat:
        payload["ressalva"] = source.caveat
    return payload


def search_documents(
    query: str,
    sources: Sequence[DocumentSource],
    missing: Sequence[MissingSource] = (),
    num_documents: int = _DEFAULT_NUM_DOCUMENTS,
) -> list[dict[str, Any]]:
    """Busca por sobreposicao de termos nas secoes dos documentos.

    Nao e busca semantica - e correspondencia lexical sobre um corpus de ~16
    arquivos pequenos, o que e suficiente e totalmente auditavel. Fontes
    inexistentes relevantes para a pergunta entram no resultado marcadas como
    FONTE_NAO_DISPONIVEL.
    """

    terms = _tokenize(query)
    results: list[tuple[int, dict[str, Any]]] = []

    for source in sources:
        if not source.path.exists():
            continue

        key_tokens = set(_tokenize(f"{source.key} {source.title} {source.summary}"))
        for section_title, body in _visible_sections(source):
            haystack = _normalize(f"{section_title}\n{body}")
            section_title_tokens = set(_tokenize(section_title))

            score = 0
            for term in terms:
                hits = haystack.count(term)
                if hits:
                    score += min(hits, 5)
                if term in section_title_tokens:
                    score += 4
                if term in key_tokens:
                    score += 3

            if score > 0:
                hit: dict[str, Any] = {
                    "fonte": source.key,
                    "documento": source.title,
                    "arquivo": source.relative_path,
                    "confiabilidade": source.reliability,
                    "secao": section_title,
                    "conteudo": body[:_MAX_SECTION_CHARS],
                }
                if source.caveat:
                    hit["ressalva"] = source.caveat
                results.append((score, hit))

    results.sort(key=lambda item: item[0], reverse=True)
    payload = [doc for _score, doc in results[:num_documents]]

    query_tokens = set(terms)
    for gap in missing:
        if query_tokens & set(gap.keywords):
            payload.append(
                {
                    "fonte": gap.key,
                    "status": "FONTE_NAO_DISPONIVEL",
                    "descricao": gap.title,
                    "motivo": gap.reason,
                    "peca_para": gap.ask_agent,
                }
            )

    if not payload:
        payload.append(
            {
                "status": "NENHUM_RESULTADO",
                "observacao": (
                    "Nenhum documento do repositorio cobre esta pergunta. Nao invente o dado: "
                    "diga que a fonte nao existe ou peca ao agente responsavel."
                ),
                "fontes_disponiveis": [source.key for source in sources],
            }
        )

    return payload


def build_knowledge_retriever(
    sources: Sequence[DocumentSource],
    missing: Sequence[MissingSource] = (),
) -> Callable[..., list[dict[Any, Any] | str]]:
    """Cria o `knowledge_retriever` no formato que o Agno espera.

    Assinatura aceita por agno/agent/_default_tools.py:
        (agent, query, num_documents=None, **kwargs) -> Optional[list[dict|str]]

    O tipo de retorno usa `dict[Any, Any] | str` (e nao `dict[str, Any]`)
    porque `list` e invariante: e a unica forma de casar com a assinatura que
    o Agno declara.
    """

    def retriever(query: str, num_documents: int | None = None, **_kwargs: Any) -> list[dict[Any, Any] | str]:
        docs: list[dict[Any, Any] | str] = list(
            search_documents(
                query,
                sources=sources,
                missing=missing,
                num_documents=num_documents or _DEFAULT_NUM_DOCUMENTS,
            )
        )
        return docs

    return retriever


def build_source_catalog(
    sources: Sequence[DocumentSource],
    missing: Sequence[MissingSource] = (),
) -> dict[str, Any]:
    """Catalogo do que da para consultar e do que nao existe (com o dono)."""

    return {
        "documentos_disponiveis": [
            {
                "fonte": source.key,
                "descricao": source.summary,
                "confiabilidade": source.reliability,
                "existe_em_disco": source.path.exists(),
            }
            for source in sources
        ],
        "fontes_nao_disponiveis": [
            {"fonte": gap.key, "descricao": gap.title, "motivo": gap.reason, "peca_para": gap.ask_agent}
            for gap in missing
        ],
    }
