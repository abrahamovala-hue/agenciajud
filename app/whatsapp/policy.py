"""
Policy de canal: texto, audio, ou os dois.

Deterministica de proposito. O LLM decide O QUE responder; o protocolo do
canal e decisao de codigo — deixar o modelo escolher formato de saida daria
comportamento instavel a cada execucao.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

InputMode = Literal["text", "audio"]
OutputMode = Literal["text", "audio", "text_and_audio"]

# "me responde por audio", "manda audio", "pode falar", "prefiro ouvir"
_ASKS_FOR_AUDIO = re.compile(
    r"\b(responde|responda|manda|mande|envia|envie|grava|grave|fala|fale)\b[^.?!]{0,30}\b(audio|voz|falando|gravad\w+)\b"
    r"|\b(por|em|de)\s+(audio|voz)\b"
    r"|\b(prefiro|queria|quero)\b[^.?!]{0,20}\b(ouvir|audio|voz)\b"
)
_ASKS_FOR_TEXT = re.compile(
    r"\b(responde|responda|manda|mande|escreve|escreva)\b[^.?!]{0,30}\b(texto|escrito|escrevendo)\b"
    r"|\b(por|em)\s+(texto|escrito)\b"
    r"|\b(nao|sem)\b[^.?!]{0,20}\b(audio|voz)\b"
)
_HAS_LINK = re.compile(r"https?://|\bwww\.")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn").casefold()


@dataclass(frozen=True)
class ResponsePlan:
    output_mode: OutputMode
    reason: str

    @property
    def wants_audio(self) -> bool:
        return self.output_mode in ("audio", "text_and_audio")

    @property
    def wants_text(self) -> bool:
        return self.output_mode in ("text", "text_and_audio")


def decide_output_mode(*, input_mode: InputMode, incoming_text: str, response_text: str) -> ResponsePlan:
    """Regras, em ordem de prioridade:

    1. Pedido explicito da cliente vence tudo.
    2. Audio recebido -> audio de volta (espelha o canal escolhido por ela).
    3. Texto recebido -> texto.
    4. Resposta com link sempre inclui texto: link falado nao da para copiar.
    """

    asked_text = bool(_ASKS_FOR_TEXT.search(_normalize(incoming_text)))
    asked_audio = bool(_ASKS_FOR_AUDIO.search(_normalize(incoming_text)))
    has_link = bool(_HAS_LINK.search(response_text or ""))

    if asked_text:
        return ResponsePlan("text", "cliente pediu texto explicitamente")

    if asked_audio:
        if has_link:
            return ResponsePlan("text_and_audio", "cliente pediu audio, mas a resposta tem link a copiar")
        return ResponsePlan("audio", "cliente pediu audio explicitamente")

    if input_mode == "audio":
        if has_link:
            return ResponsePlan("text_and_audio", "audio recebido, mas a resposta tem link a copiar")
        return ResponsePlan("audio", "audio recebido -> audio de volta")

    return ResponsePlan("text", "texto recebido -> texto de volta")


def fallback_to_text(plan: ResponsePlan) -> ResponsePlan:
    """TTS falhou: a resposta sai por escrito em vez de nao sair."""

    return ResponsePlan("text", f"fallback: TTS falhou ({plan.reason})")
