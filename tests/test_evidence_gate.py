"""
Evidence Gate — testes deterministicos (sem LLM).

Cobre os casos A..J pedidos para o hardening do ANSWER_DM: conversa social
passa sem consulta, claim factual exige fonte real, TEMPLATE nao fundamenta
claim comercial, e a cliente nunca ve vocabulario interno.
"""

from __future__ import annotations

import pytest

from orchestration.evidence_gate import (
    COMMERCIAL_SOURCES_OF_TRUTH,
    customer_facing_message,
    detect_factual_claims,
    evaluate_final_response,
    leaks_internal_terms,
    strip_internal_references,
)

SALES = "sales-conversion-agent"
SUPPORT = "customer-support-agent"


def _gate(response: str, *, agent_id: str = SALES, references=None, opened=None, escalated: bool = False):
    return evaluate_final_response(
        agent_id=agent_id,
        response=response,
        references=references or [],
        sources_opened=opened or [],
        escalated=escalated,
    )


# --- Deteccao de claim ------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "Oi!",
        "Oii, tudo bem? 😊",
        "Obrigada pelo carinho ❤️",
        "Que bom que gostou!",
        "Voce quer para presente ou para voce mesma?",
        "Entendi, deixa eu ver com voce entao.",
        "Poxa, imagino a frustracao. Vamos resolver juntas.",
    ],
)
def test_conversa_social_nao_tem_claim_factual(texto: str) -> None:
    assert detect_factual_claims(texto) == []


@pytest.mark.parametrize(
    ("texto", "claim"),
    [
        ("O ebook custa R$ 47", "preco"),
        ("Sai por 37 reais", "preco"),
        ("Temos 20% de desconto essa semana", "desconto"),
        ("A garantia e de 7 dias para devolucao", "politica_reembolso"),
        ("Voce pode pedir reembolso", "politica_reembolso"),
        ("O prazo e de 7 dias", "prazo"),
        ("O acesso e liberado imediatamente apos o pagamento", "acesso_entrega"),
        ("O ebook ensina temperagem passo a passo", "conteudo_produto"),
        ("Ainda temos vagas disponiveis", "disponibilidade"),
    ],
)
def test_afirmacao_de_negocio_e_detectada(texto: str, claim: str) -> None:
    assert claim in detect_factual_claims(texto)


# --- A / F / J: passa sem evidencia ----------------------------------------


@pytest.mark.parametrize("texto", ["Oi! Como posso te ajudar? 😊", "Obrigada ❤️", "Que legal! De onde voce e?"])
def test_A_F_J_social_passa_sem_nenhuma_consulta(texto: str) -> None:
    result = _gate(texto)

    assert result.status == "PASS"
    assert result.evidence_required is False
    assert result.outbound_allowed is True
    assert customer_facing_message(result) is None


def test_clarificacao_passa_sem_consulta() -> None:
    result = _gate("Voce ja comprou algum dos ebooks ou seria a primeira vez?")
    assert result.status == "PASS"
    assert result.evidence_required is False


# --- B / C: claim sustentado por fonte real --------------------------------


def test_B_preco_com_offers_aberto_passa() -> None:
    result = _gate(
        "O Recheios Profissionais esta R$ 37 hoje.",
        references=["OFFERS — precos oficiais"],
        opened=["OFFERS"],
    )

    assert result.status == "PASS"
    assert result.evidence_required is True
    assert "preco" in result.factual_claims_detected
    assert result.outbound_allowed is True


def test_C_conteudo_de_produto_com_products_aberto_passa() -> None:
    result = _gate(
        "Esse ebook ensina barras e lascas, com combinacoes de castanhas e frutas.",
        references=["PRODUCTS — catalogo"],
        opened=["PRODUCTS"],
    )

    assert result.status == "PASS"
    assert "conteudo_produto" in result.factual_claims_detected


# --- G: preco certo, mas sem abrir fonte -----------------------------------


def test_G_preco_sem_abrir_fonte_e_bloqueado() -> None:
    """Mesmo o valor correto e bloqueado: acertar de memoria nao e evidencia."""

    result = _gate("O Recheios Profissionais custa R$ 37.", references=[], opened=[])

    assert result.status == "NEEDS_EVIDENCE"
    assert result.outbound_allowed is False


def test_claim_comercial_com_fonte_errada_e_bloqueado() -> None:
    """Abriu VOICE e falou de preco: VOICE nao e fonte de dado comercial."""

    result = _gate("O ebook custa R$ 47.", references=["VOICE"], opened=["VOICE"])

    assert result.status == "NEEDS_EVIDENCE"
    assert not COMMERCIAL_SOURCES_OF_TRUTH & set(result.sources_opened)


# --- H: citou documento que nao abriu --------------------------------------


def test_H_citacao_de_documento_nao_aberto_e_rejeitada() -> None:
    result = _gate(
        "Segundo o catalogo, o ebook custa R$ 47.",
        references=["OFFERS — precos oficiais"],
        opened=["VOICE"],
    )

    assert result.status == "REJECTED"
    assert result.citations_without_source
    assert result.outbound_allowed is False


def test_marcador_de_honestidade_nao_e_citacao_fabricada() -> None:
    """Quem escreve 'nenhuma fonte consultada' esta sendo honesto, nao citando."""

    result = _gate("O ebook custa R$ 47.", references=["nenhuma fonte consultada"], opened=[])
    assert result.status == "NEEDS_EVIDENCE"  # e nao REJECTED


# --- D: excecao de politica -> humano --------------------------------------


def test_D_reembolso_fora_do_prazo_exige_humano() -> None:
    """BUSINESS_RULES 11: nem com a fonte certa o agente concede excecao."""

    result = _gate(
        "Voce pode pedir reembolso depois dos 7 dias, sim.",
        agent_id=SUPPORT,
        references=["PRODUCTS"],
        opened=["PRODUCTS"],
    )

    assert result.status == "HUMAN_REQUIRED"
    assert result.outbound_allowed is False


def test_politica_dentro_do_prazo_com_fonte_passa() -> None:
    result = _gate(
        "A garantia e de 7 dias para devolucao.",
        agent_id=SUPPORT,
        references=["PRODUCTS"],
        opened=["PRODUCTS"],
    )
    assert result.status == "PASS"


def test_politica_sem_fonte_e_bloqueada() -> None:
    result = _gate("Voce tem direito a reembolso.", agent_id=SUPPORT, references=[], opened=[])
    assert result.status == "NEEDS_EVIDENCE"


# --- E: desconto -----------------------------------------------------------


def test_E_desconto_sem_fonte_e_bloqueado() -> None:
    result = _gate("Sim, tenho um cupom de desconto pra voce!", references=[], opened=[])

    assert result.status == "NEEDS_EVIDENCE"
    assert "desconto" in result.factual_claims_detected


# --- I: fonte TEMPLATE/A_VERIFICAR ------------------------------------------


def test_I_claim_comercial_apoiado_so_em_template_exige_humano() -> None:
    """AUDIENCE e template. Serve de contexto, nao confirma dado comercial."""

    result = _gate(
        "O ebook custa R$ 47 e o acesso e liberado na hora.",
        references=["AUDIENCE"],
        opened=["AUDIENCE"],
    )

    assert result.status in {"NEEDS_EVIDENCE", "HUMAN_REQUIRED"}
    assert result.outbound_allowed is False


def test_template_junto_de_fonte_confirmada_passa() -> None:
    """TEMPLATE nao contamina: o que decide e ter a fonte vigente aberta."""

    result = _gate(
        "O ebook custa R$ 47.",
        references=["OFFERS", "VOICE"],
        opened=["OFFERS", "VOICE"],
    )

    assert result.status == "PASS"
    assert "VOICE" in result.unreliable_sources


# --- Escalacao --------------------------------------------------------------


def test_mensagem_escalada_nunca_sai_sozinha() -> None:
    result = _gate("Vou te responder ja ja.", escalated=True)

    assert result.status == "HUMAN_REQUIRED"
    assert result.outbound_allowed is False


# --- UX: a cliente nunca ve vocabulario interno ----------------------------


@pytest.mark.parametrize(
    "result",
    [
        _gate("O ebook custa R$ 47.", references=[], opened=[]),
        _gate("Reembolso depois do prazo pode.", references=["PRODUCTS"], opened=["PRODUCTS"]),
        _gate("Segundo OFFERS custa R$ 47.", references=["OFFERS"], opened=["VOICE"]),
    ],
)
def test_mensagem_ao_cliente_nao_vaza_termo_interno(result) -> None:
    mensagem = customer_facing_message(result)
    assert mensagem

    proibidos = [
        "needs_evidence",
        "human_required",
        "rejected",
        "fonte_nao_disponivel",
        "qc",
        "quality control",
        "agenthandoff",
        "sources_opened",
        ".md",
        "offers",
        "products",
        "business_rules",
        "traceback",
    ]
    for termo in proibidos:
        assert termo not in mensagem.casefold(), f"vazou {termo!r} para a cliente"


@pytest.mark.parametrize(
    ("bruto", "esperado_ausente"),
    [
        ("Segundo PRODUCTS.md, o ebook inclui videos bonus.", "PRODUCTS"),
        ("O ebook esta R$ 37. Segundo OFFERS.md, o link e https://pay.kiwify.com.br/x.", "OFFERS"),
        ("De acordo com OFFERS - precos (confiabilidade: vigente), custa R$ 47.", "OFFERS"),
        ("O acesso e liberado na hora. Fonte: PRODUCTS.md", "PRODUCTS"),
        ("Conforme o documento PRODUCTS, a garantia e de 7 dias.", "PRODUCTS"),
        ("Voce recebe acesso imediato (confiabilidade: vigente).", "confiabilidade"),
    ],
)
def test_saneamento_remove_documento_interno_da_prosa(bruto: str, esperado_ausente: str) -> None:
    """Observado em execucao real: o agente escrevia 'Segundo OFFERS.md' no
    texto que iria para a cliente."""

    limpo = strip_internal_references(bruto)

    assert esperado_ausente not in limpo
    assert not leaks_internal_terms(limpo)


@pytest.mark.parametrize(
    "bruto",
    [
        "Segundo PRODUCTS.md, o ebook inclui videos bonus.",
        "O ebook esta R$ 37. Segundo OFFERS.md, o link e https://pay.kiwify.com.br/x.",
        "Conforme o documento PRODUCTS, a garantia e de 7 dias.",
    ],
)
def test_saneamento_preserva_a_informacao_util(bruto: str) -> None:
    """Tirar a citacao nao pode levar junto o dado que a cliente pediu."""

    limpo = strip_internal_references(bruto)

    assert limpo and limpo[0].isupper(), "a frase precisa continuar bem formada"
    assert ",  " not in limpo and not limpo.startswith(",")
    for dado in ("R$ 37", "7 dias", "videos bonus", "https://pay.kiwify.com.br/x"):
        if dado in bruto:
            assert dado in limpo, f"o saneamento apagou o dado {dado!r}"


@pytest.mark.parametrize(
    "texto",
    [
        "Oi! Tudo bem? Como posso te ajudar hoje? 😊",
        # Regressao: com IGNORECASE o padrao de documento casava palavra
        # comum e o saneamento comia prosa ("Vou ver isso" -> "Vou pra voce").
        "Oi! Que bom te ver aqui. Posso ajudar?",
        "Vou ver isso pra voce.",
        "Quer ver o link?",
        "Segundo o que voce falou, prefere trufas.",
        "A fonte de cacau e brasileira.",
        "Conforme combinamos, te envio amanha.",
        "O ebook custa R$ 37 e ensina ganaches.",
    ],
)
def test_saneamento_nao_mexe_em_conversa_normal(texto: str) -> None:
    assert strip_internal_references(texto) == texto


def test_mensagem_ao_cliente_e_natural_e_curta() -> None:
    result = _gate("O ebook custa R$ 47.", references=[], opened=[])
    mensagem = customer_facing_message(result)

    assert mensagem and len(mensagem) < 200
    assert "confirmar" in mensagem.casefold()
