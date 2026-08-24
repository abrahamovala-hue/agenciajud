"""
Evidence Gate — nenhuma afirmacao factual sobre o negocio sai sem fonte real.

Aplicado a RESPOSTA FINAL que iria para a cliente, nao a cada etapa interna.
Classificar uma intencao nao exige abrir OFFERS; informar um preco exige.

100% deterministico, sem LLM — mesma decisao de design do
`orchestration/quality_control.py`. Reutiliza a infraestrutura que ja existe
(`sources_opened`, `references`, provenance do catalogo); nao cria mecanismo
paralelo.

Por que deteccao lexical de claim, e nao um classificador:
o gate precisa ser auditavel e barato o suficiente para rodar em toda
mensagem. Ele erra para o lado seguro — na duvida, exige evidencia. Um falso
positivo custa uma consulta a mais; um falso negativo manda preco inventado
para uma cliente real.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from agents.knowledge_policies import UnknownAgentPolicyError, get_policy

EvidenceStatus = Literal["PASS", "NEEDS_EVIDENCE", "HUMAN_REQUIRED", "REJECTED"]

ClaimType = Literal[
    "preco",
    "desconto",
    "politica_reembolso",
    "prazo",
    "acesso_entrega",
    "conteudo_produto",
    "disponibilidade",
    "procedimento_suporte",
]

# Claims comerciais/contratuais: uma resposta errada aqui gera prejuizo ou
# promessa que a empresa nao pode cumprir. BUSINESS_RULES regra 4 manda preco
# e link virem de OFFERS/PRODUCTS; regra 10, desconto so se existir em OFFERS.
COMMERCIAL_CLAIMS: frozenset[str] = frozenset(
    {"preco", "desconto", "politica_reembolso", "acesso_entrega", "conteudo_produto", "disponibilidade"}
)

# Fontes de verdade para dado comercial (BUSINESS_RULES regras 4, 7 e 10).
COMMERCIAL_SOURCES_OF_TRUTH: frozenset[str] = frozenset({"OFFERS", "PRODUCTS"})

_CLAIM_PATTERNS: dict[str, re.Pattern[str]] = {
    "preco": re.compile(
        r"(r\$\s*\d|\b\d{1,4}\s*(reais|conto)\b|\bcusta\b|\bpreco\b|\bvalor de\b|\bsai por\b|\bpor apenas\b)"
    ),
    "desconto": re.compile(r"(\bdesconto\b|\bpromoc|\bcupom\b|\boff\b|\bmetade do preco\b|\bcondicao especial\b)"),
    # `excec` entra aqui porque "posso abrir uma excecao pra voce" e uma
    # promessa de politica mesmo sem citar a palavra reembolso — sem isso a
    # frase nao virava claim e escapava do gate inteiro.
    "politica_reembolso": re.compile(
        r"(\breembols|\bdevoluc|\bestorno\b|\bgarantia\b|\bcancelamento\b|\bdinheiro de volta\b|\bexcec\w+)"
    ),
    "prazo": re.compile(r"(\b\d+\s*(dia|dias|hora|horas|semana|semanas|mes|meses)\b|\bprazo\b|\bvalido ate\b)"),
    "acesso_entrega": re.compile(
        r"(\bacesso\b|\bliberad|\bentrega\b|\bdownload\b|\benviad|\bchega no seu email\b|\blink de acesso\b)"
    ),
    "conteudo_produto": re.compile(
        r"(\bebook\b|\bensina\b|\bvem no\b|\binclui\b|\bmodulo|\baula|\breceita|\bvideo bonus\b|\bconteudo do\b)"
    ),
    "disponibilidade": re.compile(r"(\bdisponivel\b|\besgotad|\bvagas\b|\bestoque\b|\bultimas unidades\b|\blotad)"),
    "procedimento_suporte": re.compile(
        r"(\bvoce deve\b|\bbasta\b|\bpasso a passo\b|\bprocedimento\b|\bpara resolver\b|\bsiga\b)"
    ),
}

# Reembolso fora do prazo padrao e sempre humano (BUSINESS_RULES regra 11),
# independente de quanta evidencia o agente abriu.
# `(d?[eoa]s?\s+)*` cobre as contracoes do portugues — "depois DOS 7 dias",
# "fora DO prazo", "apos A garantia". Sem isso o gate deixava passar
# justamente a frase mais perigosa.
_POLICY_EXCEPTION = re.compile(
    r"((depois|apos|passad\w+|fora)\s+(d?[eoa]s?\s+)*(prazo|garantia|\d+\s*dias)|excec\w+|abrir excec)"
)


# Pedido de reembolso/troca combinado com prazo alem da garantia de 7 dias.
# Casa no texto da CLIENTE, nao na resposta do agente.
_REFUND_WORDS = re.compile(
    # `devol\w*` cobre devolver/devolucao/devolvi — `devolu\w*` deixava
    # "devolver" passar, que e a forma mais comum na fala da cliente.
    r"\b(reembols\w*|devol\w*|estorn\w*|dinheiro de volta|cancel\w*|troca|trocar)\b"
)
_BEYOND_WINDOW = re.compile(
    r"\b(\d+)\s*(dias?|semanas?|mes(es)?)\b|\b(mes passado|semana passada|ano passado|faz tempo)\b"
)


def _requests_policy_exception(message: str) -> bool:
    """A cliente esta pedindo excecao de politica?

    Verdadeiro quando ela fala de reembolso/devolucao E indica um prazo maior
    que a garantia documentada (7 dias). Fora dessa combinacao, um pedido de
    reembolso normal segue o fluxo comum.
    """

    norm = _normalize(message)
    if not _REFUND_WORDS.search(norm):
        return False

    for m in _BEYOND_WINDOW.finditer(norm):
        if m.group(4):  # "mes passado", "faz tempo"
            return True
        quantidade, unidade = int(m.group(1)), m.group(2)
        dias = quantidade * {"dia": 1, "dias": 1, "semana": 7, "semanas": 7}.get(unidade, 30)
        if dias > 7:
            return True
    return False


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").casefold()


def detect_factual_claims(text: str) -> list[str]:
    """Quais afirmacoes factuais verificaveis a resposta contem.

    Lista vazia = conversa social (saudacao, agradecimento, empatia,
    clarificacao). Nesse caso nenhuma evidencia e exigida.
    """

    if not text or not text.strip():
        return []

    normalized = _normalize(text)
    return [claim for claim, pattern in _CLAIM_PATTERNS.items() if pattern.search(normalized)]


@dataclass
class EvidenceGateResult:
    """Veredito do gate sobre a resposta final."""

    status: EvidenceStatus
    factual_claims_detected: list[str]
    evidence_required: bool
    sources_opened: list[str]
    references: list[str]
    citations_without_source: list[str] = field(default_factory=list)
    unreliable_sources: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def outbound_allowed(self) -> bool:
        """So PASS pode ir para a cliente. Todo o resto para no gate."""

        return self.status == "PASS"


def _reliability_of(agent_id: str, sources_opened: list[str]) -> dict[str, str]:
    """Confiabilidade de cada fonte aberta, segundo a whitelist do agente."""

    try:
        catalog = {source.key: source for source in get_policy(agent_id).documents}
    except UnknownAgentPolicyError:
        return {}

    return {key: catalog[key].reliability for key in sources_opened if key in catalog}


def evaluate_final_response(
    *,
    agent_id: str,
    response: str,
    references: list[str],
    sources_opened: list[str],
    escalated: bool = False,
    incoming_message: str = "",
) -> EvidenceGateResult:
    """Decide se esta resposta pode ser enviada a cliente.

    PASS            -> sem claim factual, ou claim sustentado por fonte aberta.
    NEEDS_EVIDENCE  -> ha claim e falta consulta real que o sustente.
    HUMAN_REQUIRED  -> excecao de politica, escalacao, ou claim comercial
                       apoiado apenas em fonte nao confirmada (TEMPLATE).
    REJECTED        -> citou fonte que nao abriu.
    """

    # O PEDIDO da cliente tambem decide. Medido em 5 execucoes do mesmo caso:
    # olhando so a resposta, o gate escalava ou nao dependendo da redacao do
    # agente ("fora da garantia" escalava; "passou do prazo de 7 dias" nao).
    # Decisao de seguranca nao pode depender de como o modelo escreveu — o
    # pedido "comprei ha 30 dias, quero reembolso" e determinístico.
    if incoming_message and _requests_policy_exception(incoming_message):
        return EvidenceGateResult(
            status="HUMAN_REQUIRED",
            factual_claims_detected=detect_factual_claims(response),
            evidence_required=True,
            sources_opened=[s for s in sources_opened if s],
            references=references,
            reason="A cliente pediu excecao de politica (reembolso fora do prazo). BUSINESS_RULES 11.",
        )

    claims = detect_factual_claims(response)
    opened = [s for s in sources_opened if s]
    reliability = _reliability_of(agent_id, opened)
    confirmed = [s for s in opened if reliability.get(s) == "vigente"]
    unreliable = [s for s in opened if reliability.get(s) in {"template", "snapshot"}]

    base = {
        "factual_claims_detected": claims,
        "sources_opened": opened,
        "references": references,
        "unreliable_sources": unreliable,
    }

    if escalated:
        return EvidenceGateResult(
            status="HUMAN_REQUIRED",
            evidence_required=bool(claims),
            reason="Mensagem escalada para revisao humana.",
            **base,
        )

    # Sem claim factual: conversa social. Nao exige nada.
    if not claims:
        return EvidenceGateResult(
            status="PASS",
            evidence_required=False,
            reason="Nenhuma afirmacao factual sobre o negocio na resposta.",
            **base,
        )

    # Citou fonte sem ter aberto documento nenhum: pior que nao consultar.
    fabricated = _fabricated_citations(references, opened)
    if fabricated:
        return EvidenceGateResult(
            status="REJECTED",
            evidence_required=True,
            citations_without_source=fabricated,
            reason="Resposta cita fonte que nao foi aberta nesta execucao.",
            **base,
        )

    if not opened:
        return EvidenceGateResult(
            status="NEEDS_EVIDENCE",
            evidence_required=True,
            reason=f"Resposta afirma {claims} sem ter consultado fonte nenhuma.",
            **base,
        )

    # Excecao de politica (reembolso fora do prazo, abrir excecao): sempre
    # humano, por BUSINESS_RULES regra 11 - nem a fonte certa autoriza o
    # agente a conceder isso sozinho.
    if "politica_reembolso" in claims and _POLICY_EXCEPTION.search(_normalize(response)):
        return EvidenceGateResult(
            status="HUMAN_REQUIRED",
            evidence_required=True,
            reason="Excecao de politica de reembolso: decisao humana obrigatoria (BUSINESS_RULES 11).",
            **base,
        )

    commercial = [c for c in claims if c in COMMERCIAL_CLAIMS]
    if commercial:
        # Preco, oferta, politica e conteudo de produto vem de OFFERS/PRODUCTS
        # (BUSINESS_RULES 4 e 10). Outra fonte nao substitui.
        if not COMMERCIAL_SOURCES_OF_TRUTH & set(opened):
            return EvidenceGateResult(
                status="NEEDS_EVIDENCE",
                evidence_required=True,
                reason=f"Claim comercial {commercial} exige OFFERS ou PRODUCTS; abriu {opened}.",
                **base,
            )
        # TEMPLATE/snapshot serve de contexto, nao fundamenta claim comercial.
        if not confirmed:
            return EvidenceGateResult(
                status="HUMAN_REQUIRED",
                evidence_required=True,
                reason=f"Claim comercial apoiado apenas em fonte nao confirmada: {unreliable}.",
                **base,
            )

    return EvidenceGateResult(
        status="PASS",
        evidence_required=True,
        reason=f"Claims {claims} sustentados por {confirmed or opened}.",
        **base,
    )


# Marcadores de honestidade nao sao citacao — mesma regra do quality_control.
_HONESTY = ("nenhuma fonte", "fonte nao disponivel", "fonte não disponível", "nao consultei", "não consultei")


def _fabricated_citations(references: list[str], opened: list[str]) -> list[str]:
    """Citacoes que nao correspondem a nenhum documento aberto.

    Casa por substring porque o agente escreve a referencia em prosa
    ("OFFERS — precos oficiais (confiabilidade: vigente)"), nao como chave
    limpa. Se nada foi aberto, qualquer citacao real e fabricada.
    """

    fabricated = []
    for ref in references:
        normalized = _normalize(ref)
        if any(marker in normalized for marker in _HONESTY):
            continue
        if not any(_normalize(source) in normalized for source in opened):
            fabricated.append(ref)
    return fabricated


# ---------------------------------------------------------------------------
# UX — o que a cliente ve
# ---------------------------------------------------------------------------

# Observado em execucao real: mesmo instruido a citar so no campo
# `references`, o agente escreve "Segundo OFFERS.md, ..." no texto da
# resposta. Nome de arquivo interno nao pode chegar na cliente, entao o
# saneamento e deterministico aqui em vez de depender do LLM lembrar.
_DOC_NAME = r"[A-Z][A-Z_]{2,}(?:\.md)?"

# A clausula INTEIRA, do conector ao documento — remover so o nome deixaria
# "Segundo , o ebook..." na cara da cliente.
# ATENCAO: sem re.IGNORECASE global. `_DOC_NAME` PRECISA casar so maiuscula —
# com IGNORECASE ele casava palavra comum ("isso", "aqui", "link") e o
# saneamento comia prosa normal ("Vou ver isso" -> "Vou pra voce").
# O conector usa flag inline (?i:...) para aceitar "Segundo"/"segundo".
# "ver" ficou de fora da lista de proposito: e verbo comum demais em PT-BR.
_CITATION_CLAUSE = re.compile(
    r"\(?(?i:\b(?:de acordo com|segundo|conforme|com base (?:em|no|na)|fonte)\b):?\s*"
    r"(?i:(?:o\s+|a\s+)?(?:documento\s+)?)"
    rf"{_DOC_NAME}"
    r"(?:\s*[—–-]\s*[^.,;\n)]{0,60})?"
    r"(?:\s*\([^)]*\))?\)?"
    r"\s*[,:;]?\s*"
)
# Parentetico solto: "(confiabilidade: template)", "(fonte: OFFERS)".
_CITATION_PAREN = re.compile(r"\s*\((?:confiabilidade|fonte|ressalva)[^)]*\)", re.IGNORECASE)
# Nome de arquivo sem conector nenhum.
_INTERNAL_PATH = re.compile(r"\b[\w/-]*(?:JUDITH-AI-TEAM|brand|sources)/[\w./-]+\.md\b|\b\w+\.md\b")
_LEFTOVER_SPACE = re.compile(r"[ \t]{2,}")


def strip_internal_references(text: str) -> str:
    """Remove citacao de documento interno do texto que vai para a cliente.

    A evidencia continua registrada em `references`/`sources_opened` no log —
    o que sai daqui e so a prosa, sem nome de arquivo.
    """

    if not text:
        return text

    cleaned = _CITATION_PAREN.sub("", text)
    cleaned = _CITATION_CLAUSE.sub("", cleaned)
    cleaned = _INTERNAL_PATH.sub("", cleaned)
    cleaned = _LEFTOVER_SPACE.sub(" ", cleaned)
    # Sobras de pontuacao no comeco da linha e antes de pontuacao final.
    cleaned = re.sub(r"(^|\n)\s*[,;:]\s*", r"\1", cleaned)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()
    # Remover "Segundo X, " do meio do texto deixa a frase seguinte em
    # minuscula ("... R$ 37. o link e ...") — recapitaliza apos ponto final.
    cleaned = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), cleaned)
    return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned


def leaks_internal_terms(text: str) -> bool:
    """True se sobrou nome de arquivo/documento interno no texto."""

    return bool(_INTERNAL_PATH.search(text or ""))

# A cliente nunca ve nome de arquivo, status do gate, nem vocabulario interno.
# Ela recebe uma frase natural; o motivo tecnico fica no ExecutionLog.
_CUSTOMER_MESSAGE: dict[str, str] = {
    "NEEDS_EVIDENCE": (
        "Deixa eu confirmar essa informação certinho antes de te responder — "
        "não quero te passar nada errado 😊 Já volto!"
    ),
    "HUMAN_REQUIRED": (
        "Essa aqui eu prefiro confirmar direto com a Judith pra te dar a resposta certa 💛 "
        "Ela te retorna já já!"
    ),
    "REJECTED": (
        "Deixa eu conferir essa informação na fonte oficial antes de te confirmar 😊 "
        "Um instantinho!"
    ),
}


def customer_facing_message(result: EvidenceGateResult) -> str | None:
    """Texto seguro para a cliente quando a resposta nao passou no gate.

    None quando a resposta pode seguir como o agente escreveu.
    """

    if result.outbound_allowed:
        return None
    return _CUSTOMER_MESSAGE[result.status]
