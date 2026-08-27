"""
Legacy Knowledge Scope — congela o retrieval antigo enquanto o Brain cresce.

O PROBLEMA QUE ISTO RESOLVE
---------------------------

`docs/` estava no `.dockerignore` desde o commit inicial do template. Em
producao, 77 dos 79 documentos catalogados simplesmente nao existiam dentro
do container, e `search_documents()` pula fonte sem arquivo. Na pratica o
retrieval de knowledge nunca funcionou la.

A F2.5 leva `docs/` para a imagem — o Brain precisa dos arquivos para
backfillar. Mas o retriever lexical LE OS MESMOS ARQUIVOS. Sem nenhuma trava,
o mesmo deploy que alimenta o Brain faria 77 documentos aparecerem de uma vez
para 20 agentes, mudando toda resposta ao cliente sem eval nenhum.

Entao o arquivo chegar e a disponibilidade para o agente viram duas decisoes
separadas. Este modulo e a segunda.

O CONTRATO
----------

    LEGACY_KNOWLEDGE_SCOPE=frozen  -> o legacy so enxerga o baseline medido
    LEGACY_KNOWLEDGE_SCOPE=full    -> o legacy enxerga tudo que existe em disco

Default: `frozen` em runtime Railway, `full` fora dele. Fail-closed onde
importa — producao precisa de acao explicita para ampliar, desenvolvimento e
teste continuam como sempre foram.

O baseline e uma LISTA EXPLICITA, nao uma regra derivada. Derivar de
`root != "docs"` reproduziria o numero de hoje e ampliaria sozinho no dia em
que alguem catalogasse outro arquivo fora de `docs/`. Uma lista mente menos.

QUANDO ISTO SOME
----------------

No cutover: quando os documentos estiverem CONFIRMED pela Judith e os agentes
passarem a consultar o Brain, o caminho lexical inteiro sai — e este modulo
com ele. Ate la, ele existe para que "o Brain enxerga" e "o agente enxerga"
nao sejam a mesma frase.
"""

from __future__ import annotations

from os import getenv
from typing import Literal

Scope = Literal["frozen", "full"]

#: O que o retriever lexical conseguia servir em producao no momento da F2.5.
#: Medido, nao estimado: sao as duas unicas fontes catalogadas que vivem fora
#: de `docs/` e portanto sobreviveram ao `.dockerignore`.
LEGACY_BASELINE_KEYS: frozenset[str] = frozenset(
    {
        "EVALS_README",
        "VIDEO_EDIT_SPEC",
    }
)

_ENV_VAR = "LEGACY_KNOWLEDGE_SCOPE"


def _is_production() -> bool:
    # Mesmo sinal usado pelo hardening da API (utils/validate_envs.py).
    return bool(getenv("RAILWAY_ENVIRONMENT") or getenv("RAILWAY_SERVICE_NAME") or getenv("RAILWAY_PROJECT_ID"))


def current_scope() -> Scope:
    """Escopo ativo. Producao e `frozen` a menos que alguem diga o contrario."""

    declarado = (getenv(_ENV_VAR) or "").strip().lower()
    if declarado in ("frozen", "full"):
        return declarado  # type: ignore[return-value]
    return "frozen" if _is_production() else "full"


def is_legacy_visible(key: str) -> bool:
    """O retriever lexical pode servir este documento?

    Nao substitui a whitelist por agente de `knowledge_policies.py` — soma-se
    a ela. Um documento precisa passar nas duas.
    """

    if current_scope() == "full":
        return True
    return key in LEGACY_BASELINE_KEYS


def scope_report() -> dict[str, object]:
    """Estado do escopo, para log de boot e para os testes."""

    return {
        "scope": current_scope(),
        "producao": _is_production(),
        "baseline_keys": sorted(LEGACY_BASELINE_KEYS),
        "origem": "env" if (getenv(_ENV_VAR) or "").strip().lower() in ("frozen", "full") else "default",
    }
