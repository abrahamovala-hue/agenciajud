"""
Manifesto de aprovacoes — quem aprovou o que, versionado em git.

POR QUE UM ARQUIVO E NAO UM ENDPOINT
------------------------------------

Aprovar um documento e um ato humano com consequencia comercial: a partir
dele o agente passa a afirmar aquilo para uma cliente. Um endpoint de
aprovacao deixaria esse ato sem rastro fora do banco — e o banco de producao
nao e alcancavel para auditoria.

Num arquivo, cada aprovacao carrega quem, o que e por que, passa por code
review e fica no historico do git para sempre. Reverter e um `git revert`,
nao uma arqueologia de log.

O boot aplica o manifesto. Idempotente: documento ja aprovado e ignorado.

A APROVACAO VALE PARA UM CONTEUDO, NAO PARA UM NOME
---------------------------------------------------

`approve_version()` grava `approved_by` numa VERSAO especifica. Quando o
arquivo muda, `add_version()` cria v+1 — e essa versao nova nasce **sem**
`approved_by`, porque ninguem a leu ainda.

O furo que isso deixa, e que `audit_drift()` existe para fechar: o campo
`status` do DOCUMENTO continua CONFIRMED da aprovacao anterior. Ou seja, um
documento pode estar marcado CONFIRMED enquanto sua versao vigente nunca foi
aprovada. O retrieval filtra por status, entao conteudo novo entraria em
producao pegando carona na aprovacao do conteudo velho.

`audit_drift()` compara os dois e denuncia. `apply_approvals()` nunca
re-aprova sozinho um documento que ja e CONFIRMED: a versao nova exige um
humano que a leu.

O QUE ISTO NAO FAZ
------------------

Nao aprova o que nao esta escrito aqui. Nao infere. Nao promove por
reliability, por autoridade da fonte, nem por "ja passou no eval".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Nome que fica gravado em `approved_by`. Precisa dizer QUEM decidiu.
#:
#: A Judith entregou os PDFs como fonte primaria atual e autorizou a ingestao;
#: o Abraao conduziu a execucao. Gravar so "judith" esconderia metade da
#: cadeia, e gravar so "sistema" seria mentira — nao existe aprovacao
#: automatica neste projeto.
APPROVER = "judith-kolker (via abrahao, F2.8 2026-08-28)"


@dataclass(frozen=True)
class Approval:
    external_key: str
    approved_by: str
    reason: str


#: --- FONTES PRIMARIAS -----------------------------------------------------
#:
#: O que esta aprovacao afirma: "a Judith publica e ensina este conteudo, e
#: entregou este arquivo como a versao atual dele".
#:
#: O que ela NAO afirma: que toda alegacao externa escrita dentro do ebook
#: ("o mercado cresce") foi verificada. Isso continua sendo AUTHORIAL_CLAIM.
#: Ver brain/models.py:AUTHORITY_MEANING.
_FONTES_PRIMARIAS = (
    ("EBOOK_RECHEIOS", "Ebook de Recheios Profissionais entregue pela Judith como fonte primaria atual."),
    ("EBOOK_CASQUINHAS", "Ebook de Casquinhas Profissionais entregue pela Judith como fonte primaria atual."),
    ("EBOOK_LASCAS", "Ebook O Segredo do Chocolate entregue pela Judith como fonte primaria atual."),
    (
        "SITE_SNAPSHOT",
        (
            "Snapshot do site oficial gerado pela propria Judith. Aprovado como registro do "
            "estado do site na captura — nao como estado de hoje."
        ),
    ),
)

#: --- DERIVADOS CANONICOS --------------------------------------------------
#:
#: Aprovaveis porque cada afirmacao comercial neles foi conferida contra o PDF
#: primario, o site ao vivo ou o checkout — e porque o que NAO esta comprovado
#: aparece rotulado como nao comprovado, em vez de omitido.
_DERIVADOS = (
    (
        "PRODUCTS",
        (
            "Identidade dos tres produtos derivada dos PDFs primarios. Sem preco, sem checkout. "
            "Bonus so onde o PDF comprova."
        ),
    ),
    (
        "OFFERS",
        (
            "Precos e checkouts verificados no site ao vivo e no checkout da Kiwify em 2026-08-28. "
            "O bonus de Recheios e Casquinhas fica declarado como afirmacao DO SITE, nao do produto."
        ),
    ),
    ("PRODUCT_OUTLINE_RECHEIOS", "Ficha segura derivada do PDF primario. Sem formula, sem metodo."),
    ("PRODUCT_OUTLINE_CASQUINHAS", "Ficha segura derivada do PDF primario. Sem formula, sem metodo."),
    ("PRODUCT_OUTLINE_LASCAS", "Ficha segura derivada do PDF primario. Sem formula, sem metodo."),
)


def _build() -> tuple[Approval, ...]:
    """O manifesto nao fixa versao nem checksum.

    Fixar exigiria colar hashes a mao e ficaria errado no primeiro `docs/` que
    mudasse — e o efeito seria aprovacao silenciosamente ignorada, pior do que
    recusada. A protecao real e outra: `apply_approvals` so aprova documento
    que ainda NAO e CONFIRMED, e `audit_drift` denuncia conteudo que mudou
    depois de aprovado.
    """

    return tuple(
        Approval(external_key=chave, approved_by=APPROVER, reason=motivo)
        for chave, motivo in _FONTES_PRIMARIAS + _DERIVADOS
    )


APPROVALS: tuple[Approval, ...] = _build()

#: Documentos que NAO sao aprovados, e por que. Existe para que a ausencia
#: seja uma decisao legivel, e nao um esquecimento.
NOT_APPROVED: dict[str, str] = {
    "OFFER_STRATEGY_INTERNAL": (
        "INTERNAL_ONLY e template: sao propostas, nao fatos. Aprovar daria a elas o "
        "mesmo peso de uma condicao comercial real."
    ),
    "COMMENTS_FAQ": (
        "Contem bloco 'A COLETAR' sobre comentarios do Instagram. O conteudo novo esta "
        "correto, mas o documento ainda se declara incompleto."
    ),
}


def apply_approvals(repository: Any, *, manifesto: tuple[Approval, ...] = APPROVALS) -> dict[str, Any]:
    """Aplica o manifesto. Idempotente e nao levanta.

    Falhar aqui nao pode derrubar o boot: um documento que nao aprovou continua
    TO_VALIDATE, e TO_VALIDATE nao vaza para producao. O risco de nao aprovar
    e um agente sem resposta; o risco de derrubar o boot e o WhatsApp mudo.
    """

    aplicadas: list[dict[str, Any]] = []
    ignoradas: list[dict[str, Any]] = []
    erros: list[str] = []

    for item in manifesto:
        try:
            documento = repository.get_document_by_external_key(item.external_key)
            if documento is None:
                ignoradas.append({"fonte": item.external_key, "motivo": "documento nao existe no store"})
                continue

            versao = repository.get_current_version(documento["document_id"])
            if versao is None:
                ignoradas.append({"fonte": item.external_key, "motivo": "sem versao vigente"})
                continue

            # Documento ja CONFIRMED nunca e re-aprovado por este manifesto,
            # mesmo que a versao vigente esteja sem `approved_by`.
            #
            # A versao anterior usava `status == CONFIRMED AND approved_by`, e
            # com isso um documento cujo conteudo mudou depois de aprovado caia
            # no `and` falso e era re-aprovado automaticamente — promovendo
            # texto que nenhum humano leu. `audit_drift` denuncia esse caso; a
            # decisao de aprovar a versao nova continua sendo humana.
            if str(documento["status"]) == "CONFIRMED":
                ignoradas.append(
                    {
                        "fonte": item.external_key,
                        "motivo": "ja aprovado"
                        if versao.get("approved_by")
                        else "CONFIRMED com versao vigente nao aprovada (deriva) — exige leitura humana",
                    }
                )
                continue

            repository.approve_version(
                document_id=documento["document_id"],
                version=int(versao["version"]),
                approved_by=item.approved_by,
            )
            aplicadas.append(
                {
                    "fonte": item.external_key,
                    "versao": int(versao["version"]),
                    "checksum": str(documento["checksum"])[:12],
                    "aprovado_por": item.approved_by,
                }
            )
        except Exception as erro:  # noqa: BLE001
            erros.append(f"{item.external_key}: {type(erro).__name__}: {erro}")

    return {
        "aprovadas": aplicadas,
        "ignoradas": ignoradas,
        "erros": erros,
        "nao_aprovados_por_decisao": sorted(NOT_APPROVED),
    }


def audit_drift(repository: Any) -> list[dict[str, Any]]:
    """Documentos CONFIRMED cuja versao vigente nunca foi aprovada.

    E o unico caminho pelo qual conteudo nao lido por um humano poderia sair
    em producao: o arquivo muda, `add_version` cria v+1 sem `approved_by`, e o
    `status` do documento continua CONFIRMED da aprovacao anterior.

    Devolve a lista para o boot reportar. Nao corrige sozinho: rebaixar para
    TO_VALIDATE tiraria o documento de producao sem ninguem pedir, e promover
    seria aprovar sem leitura. As duas escolhas sao humanas.
    """

    divergentes: list[dict[str, Any]] = []
    for documento in repository.list_documents(status="CONFIRMED"):
        versao = repository.get_current_version(documento["document_id"])
        if versao is None or versao.get("approved_by"):
            continue
        divergentes.append(
            {
                "fonte": documento.get("external_key") or documento["document_id"],
                "versao_vigente": int(versao["version"]),
                "status": str(documento["status"]),
                "checksum": str(documento["checksum"])[:12],
            }
        )
    return divergentes
