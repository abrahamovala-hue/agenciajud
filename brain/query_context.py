"""
Contexto de conversa para a query do Brain — o minimo para follow-up funcionar.

O PROBLEMA MEDIDO
-----------------

A query do Brain era a mensagem literal. Numa conversa real isso quebra na
segunda frase:

    turno 1: "me passa a receita de pistache"
    turno 2: "entao so os ingredientes"    -> 0 resultados

"entao so os ingredientes" nao tem termo proprio nenhum: nenhum documento fala
de "entao", "so" ou "ingredientes" o bastante para pontuar. A cliente sabe do
que esta falando; o retrieval nao.

O QUE ISTO FAZ, E O QUE NAO FAZ
-------------------------------

Guarda a ULTIMA mensagem substantiva da cliente por sessao e a costura na
query quando a mensagem atual e eliptica. So isso.

Nao despeja historico. Nao guarda resposta de agente. Nao guarda telefone —
a chave e o `session_id`, que ja chega anonimizado (`wa:ANSWER_DM:wa_<hash>`).

TROCA DE ASSUNTO
----------------

"mudando de assunto, minha ganache separou" nao pode arrastar a conversa de
preco anterior para dentro de uma busca tecnica. Marcadores explicitos de
virada limpam o contexto antes de enriquecer.

POR QUE `ContextVar` E NAO UM PARAMETRO
---------------------------------------

A tool de busca e uma closure sobre `agent_id`; ela nao recebe `session_id`, e
o Agno nao o repassa. Plumbar isso pelo Agno exigiria mexer na forma como
todos os agentes sao construidos.

`ContextVar` resolve com escopo correto: o workflow marca a sessao no inicio
da execucao e ela vale so ali dentro — inclusive sob concorrencia async, que e
como o webhook do WhatsApp atende. Um dict global daria a conversa de uma
cliente para outra.
"""

from __future__ import annotations

import re
import unicodedata
from contextvars import ContextVar

#: Sessao da execucao em curso. `None` fora de uma execucao — e ai nao ha
#: enriquecimento, que e o comportamento correto para chamada isolada.
_session: ContextVar[str | None] = ContextVar("judith_brain_session", default=None)

#: Ultima mensagem substantiva por sessao. Uma por sessao: o follow-up se
#: apoia no turno imediatamente anterior, nao na conversa inteira.
_ultimo_turno: dict[str, str] = {}

#: Teto do dicionario. Sem isso um processo longo acumularia uma entrada por
#: cliente para sempre.
_MAX_SESSOES = 500

#: Uma mensagem se sustenta sozinha com 2 termos proprios: "me passa a receita
#: de pistache" tem exatamente dois (receita, pistache) e e uma pergunta
#: completa. Exigir 3 fazia essa frase ser tratada como continuacao — e como
#: continuacao nao vira contexto, o follow-up seguinte nao tinha em que se
#: apoiar. Medido: era a causa de "entao so os ingredientes" nao recuperar nada
#: mesmo com o J2 ligado.
_MIN_TERMOS_PROPRIOS = 2

#: Abertura de continuacao. "e tem como salvar?" tem dois termos proprios e
#: mesmo assim depende do turno anterior — o "e" inicial e o sinal. Por isso a
#: elipse tem dois caminhos, nao um limiar so.
_ABERTURAS_DE_CONTINUACAO = ("e ", "e o ", "e a ", "entao", "então", "mas ", "ai ", "aí ", "ok e ")
_MAX_TERMOS_COM_CONECTIVO = 4

#: Palavras que nao identificam assunto. Nao e stopword completa de PT — e a
#: lista das que aparecem em follow-up curto e nao ajudam a recuperar nada.
_VAZIAS = frozenset(
    {
        "e", "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
        "em", "no", "na", "para", "pra", "por", "com", "sem", "que", "qual",
        "quais", "entao", "so", "somente", "apenas", "esse", "essa", "este",
        "esta", "isso", "aquele", "aquela", "outro", "outra", "ele", "ela",
        "me", "meu", "minha", "seu", "sua", "tem", "ter", "é", "eh", "ok",
        "sim", "nao", "mas", "ai", "ja", "tambem", "voce", "vc", "manda",
        "passa", "diz", "fala", "ver", "pode", "poderia", "queria", "quero",
    }
)

#: Viradas explicitas de assunto. Antes delas o contexto anterior morre.
_TROCA_DE_ASSUNTO = (
    "mudando de assunto",
    "mudando de tema",
    "outra coisa",
    "agora sobre",
    "outra pergunta",
    "esquece isso",
    "deixa isso",
    "mudando",
)


def _fold(texto: str) -> str:
    normal = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in normal if not unicodedata.combining(c)).casefold()


def _termos_proprios(texto: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", _fold(texto)) if len(t) > 1 and t not in _VAZIAS]


def muda_de_assunto(mensagem: str) -> bool:
    baixo = _fold(mensagem)
    return any(marca in baixo for marca in _TROCA_DE_ASSUNTO)


def is_elliptical(mensagem: str) -> bool:
    """A mensagem se sustenta sozinha numa busca?

    Dois caminhos, porque um limiar so nao cobre os dois jeitos de a cliente
    continuar uma conversa:

    1. quase nenhum termo proprio — "entao so os ingredientes";
    2. abre com conectivo e e curta — "e tem como salvar?".

    Troca explicita de assunto nunca e elipse: ela e o oposto.
    """

    if muda_de_assunto(mensagem):
        return False

    termos = len(_termos_proprios(mensagem))
    if termos < _MIN_TERMOS_PROPRIOS:
        return True

    baixo = _fold(mensagem).lstrip()
    if any(baixo.startswith(a) for a in _ABERTURAS_DE_CONTINUACAO):
        return termos < _MAX_TERMOS_COM_CONECTIVO
    return False


def set_session(session_id: str | None) -> None:
    """Marca a sessao da execucao em curso."""

    _session.set(session_id)


def remember(mensagem: str, *, session_id: str | None = None) -> None:
    """Guarda a mensagem como contexto do proximo turno, se ela se sustentar.

    Mensagem eliptica NAO vira contexto: guardar "entao so os ingredientes"
    faria o turno seguinte herdar uma frase que tambem nao diz nada.
    """

    sessao = session_id or _session.get()
    if not sessao:
        return

    if muda_de_assunto(mensagem):
        _ultimo_turno.pop(sessao, None)

    if is_elliptical(mensagem):
        return

    if len(_ultimo_turno) >= _MAX_SESSOES and sessao not in _ultimo_turno:
        _ultimo_turno.pop(next(iter(_ultimo_turno)), None)
    _ultimo_turno[sessao] = mensagem.strip()[:400]


def enrich(query: str, *, session_id: str | None = None) -> tuple[str, bool]:
    """Devolve (query, foi_enriquecida).

    Enriquece SO quando a query e eliptica e existe turno anterior. Uma
    pergunta que se sustenta sozinha nao e tocada — arrastar contexto para
    dentro dela mudaria o resultado de uma busca que ja estava certa.
    """

    sessao = session_id or _session.get()
    if not sessao or not is_elliptical(query):
        return query, False

    anterior = _ultimo_turno.get(sessao)
    if not anterior:
        return query, False

    return f"{anterior} {query}".strip(), True


def forget(session_id: str) -> None:
    _ultimo_turno.pop(session_id, None)


def reset() -> None:
    """Usado pelos testes."""

    _ultimo_turno.clear()
    _session.set(None)
