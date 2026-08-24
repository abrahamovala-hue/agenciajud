"""
Text-to-speech compartilhado do canal.

Fica FORA dos Agents de proposito: voz e protocolo de canal, nao
comportamento de agente. Nenhum dos 20 Agents sabe que TTS existe.

Formatos (verificados contra a documentacao oficial e empiricamente, nao
presumidos):

- Meta Cloud API aceita audio/aac, audio/amr, audio/mpeg, audio/mp4 e
  audio/ogg (OPUS, mono), ate 16 MB. Para virar VOICE NOTE (o balaozinho de
  audio do WhatsApp) o payload precisa de `audio.voice = true` e o arquivo
  precisa ser .ogg/OPUS.
- OpenAI TTS aceita response_format mp3/opus/aac/flac/wav/pcm. Rodando de
  verdade contra a API: `opus` devolve container OggS com OPUS — exatamente o
  que a Meta exige para voice note. Por isso o default e opus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from os import getenv
from typing import Literal, cast

from agno.utils.log import log_warning
from openai import OpenAI

DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "coral"
DEFAULT_TTS_FORMAT = "opus"

# response_format da OpenAI -> (mime aceito pela Meta, extensao, e voice note?)
_FORMATS: dict[str, tuple[str, str, bool]] = {
    "opus": ("audio/ogg", "ogg", True),
    "mp3": ("audio/mpeg", "mp3", False),
    "aac": ("audio/aac", "aac", False),
}

# Limite da Meta e 16 MB; cortamos bem antes porque texto longo vira audio
# longo e ninguem ouve um voice note de 5 minutos. O texto completo continua
# indo por escrito quando a policy decide texto+audio.
MAX_TTS_CHARS = 900


@dataclass(frozen=True)
class SynthesizedAudio:
    content: bytes
    mime_type: str
    filename: str
    is_voice_note: bool


def tts_settings() -> tuple[str, str, str]:
    """(modelo, voz, formato). Configuravel por env, sem segredo novo."""

    fmt = getenv("OPENAI_TTS_FORMAT", DEFAULT_TTS_FORMAT).strip().lower()
    if fmt not in _FORMATS:
        log_warning(f"OPENAI_TTS_FORMAT={fmt!r} nao e suportado pelo WhatsApp; usando {DEFAULT_TTS_FORMAT}")
        fmt = DEFAULT_TTS_FORMAT
    return (
        getenv("OPENAI_TTS_MODEL", DEFAULT_TTS_MODEL),
        getenv("OPENAI_TTS_VOICE", DEFAULT_TTS_VOICE),
        fmt,
    )


_URL = re.compile(r"https?://\S+")
_MARKDOWN = re.compile(r"[*_`#>]+")


def text_for_speech(text: str) -> str:
    """Prepara o texto para virar voz.

    URL falada em voz alta e ruido puro — quem escuta nao consegue copiar um
    link. A URL sai do audio; a policy do canal garante que ela vai junto por
    escrito (ver app/whatsapp/policy.py).
    """

    spoken = _URL.sub("", text or "")
    spoken = _MARKDOWN.sub("", spoken)
    spoken = re.sub(r"\n{2,}", ". ", spoken)
    spoken = re.sub(r"\s{2,}", " ", spoken).strip()
    return spoken[:MAX_TTS_CHARS]


def synthesize(text: str) -> SynthesizedAudio | None:
    """Gera o audio da resposta. Devolve None em qualquer falha.

    Nunca levanta: falha de TTS nao pode derrubar a resposta — o canal cai
    para texto (ver policy.fallback_to_text).
    """

    spoken = text_for_speech(text)
    if not spoken:
        return None

    model, voice, fmt = tts_settings()
    mime_type, extension, is_voice_note = _FORMATS[fmt]

    try:
        response = OpenAI().audio.speech.create(
            model=model,
            voice=voice,
            input=spoken,
            response_format=cast(Literal["mp3", "opus", "aac"], fmt),
        )
        content = response.content
    except Exception as exc:  # noqa: BLE001 - fallback para texto e sempre preferivel a erro
        log_warning(f"TTS falhou ({model}/{fmt}): {exc}")
        return None

    if not content:
        log_warning("TTS devolveu conteudo vazio")
        return None

    return SynthesizedAudio(
        content=content,
        mime_type=mime_type,
        filename=f"resposta.{extension}",
        is_voice_note=is_voice_note,
    )
