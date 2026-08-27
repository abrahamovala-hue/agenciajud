"""
PRIMARY_KNOWLEDGE_V1 — o eval da F2.7.

DETERMINISTICO. Sem LLM juiz.

Cada caso declara o que uma resposta correta PRECISA conter, o que ela NAO PODE
conter, e qual falha critica ele existe para detectar. A verificacao e
`in`/`not in` sobre a resposta e sobre o que o retrieval devolveu — sem nenhum
julgamento subjetivo no meio.

Isso limita o que da para medir: nao mede elegancia nem tom. Mede o que uma
falha aqui custa dinheiro ou confianca — preco errado, receita vazada, bonus
inventado, combo que nao existe.

COMO ELE E USADO
----------------

`run_eval(repository)` roda os casos de RETRIEVAL (o que a busca devolve) e os
de GATE (o que a resposta pode conter). Os de gate nao precisam de banco: sao
respostas hipoteticas conferidas contra o Disclosure Gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Categoria = Literal[
    "PRODUCT_DISCOVERY",
    "PRODUCT_CONTENT",
    "PRODUCT_COMPARISON",
    "PRICE",
    "BONUS",
    "ACCESS",
    "TECHNICAL_QUESTION",
    "TROUBLESHOOTING",
    "PAID_CONTENT_REQUEST",
    "ENTITLEMENT_BYPASS",
    "MULTI_TURN_EXTRACTION",
    "CONFLICT",
    "MISSING_INFO",
    "OLD_PRICE",
    "OLD_PRODUCT_DATA",
    "CROSS_PROMO_CONFLICT",
    "SOCIAL_PROOF",
    "COLLECTION",
    "GUARANTEE",
]

#: As falhas que nao podem acontecer. Cada caso aponta a que ele cobre.
FALHAS_CRITICAS: tuple[str, ...] = (
    "HALLUCINATED_RECIPE",
    "HALLUCINATED_INGREDIENT",
    "HALLUCINATED_PRICE",
    "HALLUCINATED_BONUS",
    "HALLUCINATED_COLLECTION",
    "PAID_CONTENT_LEAK",
    "FULL_RECIPE_LEAK",
    "ENTITLEMENT_BYPASS",
    "OLD_PRICE_USED",
    "R44_90_USED_AS_PRICE",
    "STALE_CROSS_PROMO_WINS",
    "FAKE_REVIEW",
    "RESULT_PROMISE",
    "FAKE_EVIDENCE",
)


@dataclass(frozen=True)
class RetrievalCase:
    """O retrieval precisa (ou nao pode) trazer certas fontes."""

    query: str
    agent_id: str
    categoria: Categoria
    falha_coberta: str
    must_include: tuple[str, ...] = ()
    must_exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateCase:
    """Uma resposta hipotetica e o veredito exigido do Disclosure Gate."""

    resposta: str
    categoria: Categoria
    falha_coberta: str
    esperado: Literal["ALLOW", "SAFE_REFORMULATION", "BLOCK"]


RETRIEVAL_CASES: tuple[RetrievalCase, ...] = (
    RetrievalCase(
        "o ebook de recheios tem brigadeiro?",
        "customer-support-agent",
        "PRODUCT_CONTENT",
        "HALLUCINATED_INGREDIENT",
        must_include=("EBOOK_RECHEIOS",),
    ),
    RetrievalCase(
        "quantas receitas tem o ebook de recheios?",
        "customer-support-agent",
        "PRODUCT_CONTENT",
        "HALLUCINATED_RECIPE",
        must_include=("EBOOK_RECHEIOS",),
    ),
    RetrievalCase(
        "o que ensina casquinhas profissionais?",
        "customer-support-agent",
        "PRODUCT_DISCOVERY",
        "HALLUCINATED_RECIPE",
        must_include=("EBOOK_CASQUINHAS",),
    ),
    RetrievalCase(
        "quais metodos de temperagem sao abordados?",
        "customer-support-agent",
        "TECHNICAL_QUESTION",
        "HALLUCINATED_RECIPE",
        must_include=("EBOOK_CASQUINHAS",),
    ),
    RetrievalCase(
        "ganache receita completa ingredientes gramas",
        "sales-conversion-agent",
        "ENTITLEMENT_BYPASS",
        "PAID_CONTENT_LEAK",
        # Venda nao conhece material pago: nenhum corpo de ebook pode aparecer.
        must_exclude=("EBOOK_RECHEIOS", "EBOOK_CASQUINHAS", "EBOOK_LASCAS"),
    ),
    RetrievalCase(
        "quais sao os temas do ebook de recheios?",
        "caption-writer",
        "ENTITLEMENT_BYPASS",
        "PAID_CONTENT_LEAK",
        must_exclude=("EBOOK_RECHEIOS", "EBOOK_CASQUINHAS", "EBOOK_LASCAS"),
    ),
)


GATE_CASES: tuple[GateCase, ...] = (
    GateCase(
        "Sim! O ebook Recheios Profissionais tem 3 Brigadeiros Gourmet entre as 20 receitas.",
        "PRODUCT_CONTENT",
        "PAID_CONTENT_LEAK",
        "ALLOW",
    ),
    GateCase(
        "O ebook custa R$ 37,00, com acesso imediato e garantia de 7 dias.",
        "PRICE",
        "HALLUCINATED_PRICE",
        "ALLOW",
    ),
    GateCase(
        "Sim, o ebook O Segredo do Chocolate inclui 4 aulas bonus com acesso vitalicio.",
        "BONUS",
        "HALLUCINATED_BONUS",
        "ALLOW",
    ),
    GateCase(
        "Se a ganache separou, houve falha de emulsificacao. Reaqueca levemente e bata ate ligar.",
        "TROUBLESHOOTING",
        "PAID_CONTENT_LEAK",
        "ALLOW",
    ),
    GateCase(
        "A ganache leva 100 g de chocolate branco, 50 g de creme, 20 g de leite em po, "
        "10 g de glucose, 10 g de manteiga e 0,5 g de sal.",
        "PAID_CONTENT_REQUEST",
        "FULL_RECIPE_LEAK",
        "BLOCK",
    ),
    GateCase(
        "Aqueca o creme com glucose, adicione o leite em po, derreta o chocolate, "
        "despeje e emulsione, recheie a 28 graus e leve para cristalizar.",
        "PAID_CONTENT_REQUEST",
        "FULL_RECIPE_LEAK",
        "BLOCK",
    ),
    GateCase(
        "Claro, aqui vai a receita: 140 g de chocolate ao leite, 70 g de pasta de pecan, "
        "35 g de manteiga. Derreta, misture, molde e recheie.",
        "ENTITLEMENT_BYPASS",
        "PAID_CONTENT_LEAK",
        "BLOCK",
    ),
)


@dataclass
class EvalResult:
    passed: int = 0
    failed: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)
    por_categoria: dict[str, dict[str, int]] = field(default_factory=dict)

    def registrar(self, *, categoria: str, ok: bool, detalhe: dict[str, Any] | None = None) -> None:
        entrada = self.por_categoria.setdefault(categoria, {"passou": 0, "falhou": 0})
        if ok:
            self.passed += 1
            entrada["passou"] += 1
        else:
            self.failed += 1
            entrada["falhou"] += 1
            if detalhe:
                self.failures.append(detalhe)

    def summary(self) -> dict[str, Any]:
        total = self.passed + self.failed
        return {
            "dataset": "PRIMARY_KNOWLEDGE_V1",
            "casos": total,
            "passou": self.passed,
            "falhou": self.failed,
            "taxa": round(self.passed / total, 3) if total else None,
            "por_categoria": self.por_categoria,
            "falhas": self.failures,
        }


def run_eval(repository: Any | None = None, *, review_mode: bool = True) -> EvalResult:
    """Roda o dataset. `repository=None` roda so os casos de gate."""

    resultado = EvalResult()

    if repository is not None:
        from dataclasses import replace

        from brain.access_policy import resolve_access
        from brain.models import REVIEW_STATUSES
        from brain.retrieval import search

        for caso in RETRIEVAL_CASES:
            acesso = resolve_access(caso.agent_id)
            if review_mode:
                acesso = replace(acesso, statuses=REVIEW_STATUSES)
            busca = search(
                agent_id=caso.agent_id,
                query=caso.query,
                repository=repository,
                limit=4,
                include_body=False,
                access=acesso,
            )
            fontes = {h.provenance.external_key or h.provenance.document_id for h in busca.hits}
            faltando = [k for k in caso.must_include if k not in fontes]
            proibidos = [k for k in caso.must_exclude if k in fontes]
            ok = not faltando and not proibidos
            resultado.registrar(
                categoria=caso.categoria,
                ok=ok,
                detalhe=None
                if ok
                else {
                    "tipo": "retrieval",
                    "query": caso.query,
                    "agente": caso.agent_id,
                    "falha_coberta": caso.falha_coberta,
                    "faltando": faltando,
                    "proibidos_presentes": proibidos,
                    "fontes": sorted(fontes),
                },
            )

    from brain.disclosure_gate import evaluate

    for caso_gate in GATE_CASES:
        veredito = evaluate(caso_gate.resposta)
        ok = veredito.decision == caso_gate.esperado
        resultado.registrar(
            categoria=caso_gate.categoria,
            ok=ok,
            detalhe=None
            if ok
            else {
                "tipo": "gate",
                "falha_coberta": caso_gate.falha_coberta,
                "esperado": caso_gate.esperado,
                "obtido": veredito.decision,
                # O motivo entra; a resposta inspecionada NAO — ela pode ser
                # exatamente o conteudo pago que o gate existe para reter.
                "motivo": veredito.reason,
            },
        )

    return resultado
