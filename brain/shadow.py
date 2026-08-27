"""
Shadow comparison — mede os dois caminhos antes de trocar qualquer coisa.

    legacy lexical (producao)   vs   Brain lexical (paralelo)

Nenhum agente e plugado. Nenhuma resposta muda. Isto e instrumento de
medicao, e o resultado dele e o que vai justificar (ou desaconselhar) o
cutover na F3.

COMO LER O RESULTADO
--------------------

O numero que mais importa nao e "quantos documentos cada lado achou", e sim
POR QUE eles diferem. Um documento que aparece so no legacy pode ser:

- um documento que o Brain filtrou por status (TO_VALIDATE, o caso de hoje);
- um documento que o Brain filtrou por politica de acesso;
- uma diferenca real de recall.

Os tres tem tratamentos opostos, e confundi-los levaria a conclusao errada.
Por isso `filtered_out` vem separado por motivo em cada caso.

O ESTADO DE HOJE, DECLARADO
---------------------------

Zero documentos CONFIRMED. Entao o Brain em modo producao devolve VAZIO para
tudo, e a comparacao mostra 100% de diferenca. Isso nao mede qualidade de
retrieval — mede que a fila de validacao ainda nao andou.

Para medir retrieval de verdade existe `mode="review"`, que roda a busca com
os olhos do Knowledge Manager (todos os status). E o unico numero da F2.5 que
diz algo sobre a arquitetura, e nao sobre a fila.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Mode = Literal["production", "review"]


@dataclass(frozen=True)
class GoldenCase:
    """Uma pergunta real, com o que deveria aparecer."""

    query: str
    agent_id: str
    categoria: str
    #: Chaves que uma boa resposta precisaria ter aberto. Vazio quando a
    #: pergunta legitimamente nao tem fonte no repositorio.
    esperado: tuple[str, ...] = ()
    #: True quando a resposta certa e "nao existe fonte para isso".
    espera_lacuna: bool = False


#: Golden set. Perguntas escritas como uma cliente escreveria, mais as
#: perguntas internas que os agentes de fato fazem.
GOLDEN_SET: tuple[GoldenCase, ...] = (
    # --- produtos ---
    GoldenCase("quais ebooks vocês têm?", "customer-support-agent", "produtos", ("PRODUCTS",)),
    GoldenCase("o que ensina o ebook de recheios?", "customer-support-agent", "produtos", ("PRODUCTS",)),
    GoldenCase("o ebook serve para iniciante?", "customer-support-agent", "produtos", ("COMMENTS_FAQ", "PRODUCTS")),
    # --- ofertas e preco ---
    GoldenCase("quanto custa o ebook?", "sales-conversion-agent", "ofertas", ("OFFERS", "PRODUCTS")),
    GoldenCase("tem desconto essa semana?", "sales-conversion-agent", "ofertas", ("OFFERS",)),
    GoldenCase("qual o link para comprar?", "sales-conversion-agent", "ofertas", ("OFFERS", "PRODUCTS")),
    GoldenCase("existe combo com os tres ebooks?", "sales-conversion-agent", "ofertas", ("OFFERS",)),
    # --- politicas ---
    GoldenCase("posso pedir reembolso?", "customer-support-agent", "politicas", ("PRODUCTS", "BUSINESS_RULES")),
    GoldenCase("qual o prazo de garantia?", "customer-support-agent", "politicas", ("PRODUCTS", "BUSINESS_RULES")),
    GoldenCase("quando recebo o acesso depois de pagar?", "customer-support-agent", "politicas", ("PRODUCTS",)),
    # --- voz e branding ---
    GoldenCase("qual o tom de voz da marca?", "caption-writer", "voz", ("VOICE",)),
    GoldenCase("que palavras a marca nunca usa?", "caption-writer", "voz", ("VOICE",)),
    GoldenCase("qual o posicionamento da Bem me Que?", "brand-architect", "branding", ("BRAND",)),
    GoldenCase("quais sao os pilares de conteudo?", "social-media-manager", "branding", ("CONTENT_PILLARS",)),
    GoldenCase("qual a paleta de cores da marca?", "visual-creative", "branding", ("VISUAL_IDENTITY",)),
    # --- chocolate (tecnica) ---
    GoldenCase("como deixar o bombom brilhante?", "customer-support-agent", "chocolate", ("COMMENTS_FAQ",)),
    GoldenCase("como temperar chocolate corretamente?", "customer-support-agent", "chocolate", ("COMMENTS_FAQ",)),
    GoldenCase("preciso de equipamento profissional?", "customer-support-agent", "chocolate", ("COMMENTS_FAQ",)),
    GoldenCase("qual a temperatura exata da temperagem?", "customer-support-agent", "chocolate", espera_lacuna=True),
    # --- FAQ ---
    GoldenCase("posso vender os bombons que eu fizer?", "customer-support-agent", "faq", ("COMMENTS_FAQ",)),
    GoldenCase("quem e a Judith?", "community-dm-agent", "faq", ("BRAND",)),
    # --- interno (nao deve chegar a cliente) ---
    GoldenCase("como funciona o handoff entre agentes?", "knowledge-manager", "interno", ("HANDOFF_CONTRACT",)),
    GoldenCase("quais agentes existem no time?", "knowledge-manager", "interno", ("AGENT_ROSTER",)),
    GoldenCase("qual a regra de aprovacao de conteudo?", "knowledge-manager", "interno", ("BUSINESS_RULES",)),
    # --- lacunas conhecidas ---
    GoldenCase("qual o engajamento do instagram este mes?", "cmo", "lacuna", espera_lacuna=True),
    GoldenCase("quantas vendas fizemos ontem?", "analytics-bi-agent", "lacuna", espera_lacuna=True),
)


@dataclass
class CaseResult:
    query: str
    agent_id: str
    categoria: str
    esperado: list[str]
    legacy: list[str]
    brain: list[str]
    legacy_lacuna: bool
    brain_vazio: bool
    somente_legacy: list[str] = field(default_factory=list)
    somente_brain: list[str] = field(default_factory=list)
    bloqueados: dict[str, int] = field(default_factory=dict)
    acesso_negado: str | None = None
    provenance_completo: bool = False
    disclosure_bloqueou: bool = False

    @property
    def legacy_recall(self) -> float | None:
        if not self.esperado:
            return None
        return len(set(self.esperado) & set(self.legacy)) / len(self.esperado)

    @property
    def brain_recall(self) -> float | None:
        if not self.esperado:
            return None
        return len(set(self.esperado) & set(self.brain)) / len(self.esperado)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pergunta": self.query,
            "agente": self.agent_id,
            "categoria": self.categoria,
            "esperado": self.esperado,
            "legacy": self.legacy,
            "brain": self.brain,
            "recall_legacy": self.legacy_recall,
            "recall_brain": self.brain_recall,
            "somente_legacy": self.somente_legacy,
            "somente_brain": self.somente_brain,
            "legacy_declarou_lacuna": self.legacy_lacuna,
            "bloqueados_pela_politica": self.bloqueados,
            "acesso_negado": self.acesso_negado,
            "provenance_completo": self.provenance_completo,
        }


_CAMPOS_DE_PROVENANCE = (
    "fonte",
    "documento",
    "camada",
    "status",
    "versao",
    "aprovado_por",
    "origem",
    "tipo_de_fonte",
    "topics",
    "secao",
)


def _rodar_legacy(caso: GoldenCase, limit: int) -> tuple[list[str], bool]:
    from agents.knowledge_policies import get_policy
    from agents.knowledge_sources import search_documents

    politica = get_policy(caso.agent_id)
    resultado = search_documents(
        caso.query,
        sources=politica.documents,
        missing=politica.missing_sources,
        num_documents=limit,
    )
    chaves = [str(d["fonte"]) for d in resultado if d.get("fonte") and d.get("status") != "FONTE_NAO_DISPONIVEL"]
    lacuna = any(d.get("status") in ("FONTE_NAO_DISPONIVEL", "NENHUM_RESULTADO") for d in resultado)
    return chaves, lacuna


def _rodar_brain(caso: GoldenCase, repository: Any, limit: int, mode: Mode) -> CaseResult:
    from brain.access_policy import REVIEW_STATUSES, AccessDenied, resolve_access
    from brain.retrieval import search

    resultado = CaseResult(
        query=caso.query,
        agent_id=caso.agent_id,
        categoria=caso.categoria,
        esperado=list(caso.esperado),
        legacy=[],
        brain=[],
        legacy_lacuna=False,
        brain_vazio=True,
    )

    try:
        acesso = resolve_access(caso.agent_id)
    except AccessDenied as erro:
        resultado.acesso_negado = str(erro)
        return resultado

    if mode == "review":
        # Os olhos do revisor: mede retrieval, nao a fila de validacao.
        from dataclasses import replace

        acesso = replace(acesso, statuses=REVIEW_STATUSES)

    busca = search(agent_id=caso.agent_id, query=caso.query, repository=repository, limit=limit, access=acesso)
    resultado.brain = [h.provenance.external_key or h.provenance.document_id for h in busca.hits]
    resultado.brain_vazio = not busca.hits
    resultado.bloqueados = dict(busca.filtered_out)
    resultado.disclosure_bloqueou = "conteudo_pago_sem_permissao" in busca.filtered_out
    if busca.hits:
        payload = busca.hits[0].as_dict()
        resultado.provenance_completo = all(campo in payload for campo in _CAMPOS_DE_PROVENANCE)
    return resultado


def run_shadow(repository: Any, *, mode: Mode = "review", limit: int = 4) -> list[CaseResult]:
    """Roda o golden set nos dois caminhos. Nao altera nada."""

    resultados: list[CaseResult] = []
    for caso in GOLDEN_SET:
        resultado = _rodar_brain(caso, repository, limit, mode)
        legacy, lacuna = _rodar_legacy(caso, limit)
        resultado.legacy = legacy
        resultado.legacy_lacuna = lacuna
        resultado.somente_legacy = [k for k in legacy if k not in resultado.brain]
        resultado.somente_brain = [k for k in resultado.brain if k not in legacy]
        resultados.append(resultado)
    return resultados


def shadow_summary(resultados: list[CaseResult]) -> dict[str, Any]:
    com_esperado = [r for r in resultados if r.esperado]
    lacunas = [r for r in resultados if not r.esperado]

    def media(valores: list[float | None]) -> float | None:
        reais = [v for v in valores if v is not None]
        return round(sum(reais) / len(reais), 3) if reais else None

    por_categoria: dict[str, dict[str, Any]] = {}
    for resultado in com_esperado:
        entrada = por_categoria.setdefault(resultado.categoria, {"casos": 0, "legacy": [], "brain": []})
        entrada["casos"] += 1
        entrada["legacy"].append(resultado.legacy_recall)
        entrada["brain"].append(resultado.brain_recall)
    for entrada in por_categoria.values():
        entrada["recall_legacy"] = media(entrada.pop("legacy"))
        entrada["recall_brain"] = media(entrada.pop("brain"))

    bloqueios: dict[str, int] = {}
    for resultado in resultados:
        for motivo, quantidade in resultado.bloqueados.items():
            bloqueios[motivo] = bloqueios.get(motivo, 0) + quantidade

    return {
        "casos": len(resultados),
        "casos_com_fonte_esperada": len(com_esperado),
        "casos_de_lacuna": len(lacunas),
        "recall_legacy": media([r.legacy_recall for r in com_esperado]),
        "recall_brain": media([r.brain_recall for r in com_esperado]),
        "por_categoria": por_categoria,
        "brain_vazio": sum(1 for r in resultados if r.brain_vazio),
        "legacy_vazio": sum(1 for r in resultados if not r.legacy),
        "acessos_negados": sum(1 for r in resultados if r.acesso_negado),
        "bloqueios_por_politica": bloqueios,
        "bloqueios_de_conteudo_pago": sum(1 for r in resultados if r.disclosure_bloqueou),
        "provenance_completo_em_todos": all(r.provenance_completo for r in resultados if r.brain),
        "lacunas_declaradas_pelo_legacy": sum(1 for r in lacunas if r.legacy_lacuna),
    }
