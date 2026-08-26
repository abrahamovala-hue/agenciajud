"""
Canal WhatsApp -> ANSWER_DM.

Por que um router proprio em vez de `Whatsapp(agent=...)` do Agno:

O router do Agno chama `entity.arun(texto)` e envia `response.content` — util
para um agente unico, mas incompativel com duas exigencias desta arquitetura:

1. **Evidence Gate antes do outbound.** Precisamos rodar ANSWER_DM, ler
   `outbound_allowed` e so entao decidir o que sai. O caminho do Agno envia a
   resposta do agente direto.
2. **Voice note.** A Meta exige `audio.voice = true` (com .ogg/OPUS) para o
   audio virar balaozinho de voz. O `_send_media` do Agno nao passa esse campo.

Entao reaproveitamos tudo que ja e solido do starter — validacao de
assinatura, parsing, download de media, upload, envio de texto, chunking,
indicador de digitando — e escrevemos apenas o que faltava.

Fluxo:

    webhook Meta
      -> valida assinatura (Agno)
      -> extract_message_content (Agno)
      -> download de media (Agno)
      -> transcricao (agents/hooks/media.py, ja existente)
      -> ANSWER_DM  [Community/Support/Sales/CRM + Evidence Gate]
      -> outbound_allowed?
      -> policy texto/audio
      -> TTS (so depois do gate)
      -> envio
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, cast

import httpx
from agno.media import Audio
from agno.os.interfaces.base import BaseInterface
from agno.os.interfaces.whatsapp.helpers import (
    WhatsAppConfig,
    download_event_media_async,
    extract_message_content,
    send_whatsapp_message_async,
    typing_indicator_async,
    upload_media_async,
)
from agno.os.interfaces.whatsapp.security import validate_webhook_signature
from agno.utils.log import log_error, log_info, log_warning
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from agents.hooks.media import transcribe_audio
from app.security import build_api_settings, build_auth_dependency
from app.whatsapp.policy import ResponsePlan, decide_output_mode, fallback_to_text
from app.whatsapp.speech import SynthesizedAudio, synthesize
from orchestration.workflows.answer_dm import run_answer_dm

WORKFLOW = "ANSWER_DM"

_ERROR_MESSAGE = "Tive um probleminha aqui pra processar sua mensagem 😅 Pode mandar de novo?"
_TRANSCRIPTION_FAILED = (
    "Não consegui entender o áudio 😕 Pode mandar de novo ou me escrever o que você precisa?"
)
_UNSUPPORTED = "Ainda não consigo abrir esse tipo de mensagem 😅 Pode me mandar por texto ou áudio?"


# ---------------------------------------------------------------------------
# Log estruturado (secao 10)
# ---------------------------------------------------------------------------


@dataclass
class ChannelLog:
    """Uma linha por mensagem. Nunca carrega token nem telefone em claro."""

    channel: str = "whatsapp"
    user_ref: str = ""
    input_mode: str = "text"
    transcription: str | None = None
    workflow: str = WORKFLOW
    final_agent: str | None = None
    evidence_status: str | None = None
    outbound_allowed: bool | None = None
    output_mode: str | None = None
    tts_status: str = "not_requested"
    whatsapp_send_status: str = "not_sent"
    escalated: bool = False
    failure_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def emit(self) -> None:
        log_info(f"[whatsapp] {asdict(self)}")


def user_ref(phone: str) -> str:
    """Referencia estavel e nao reversivel do telefone, para log.

    O telefone em claro so existe onde e inevitavel (chamada a API da Meta).
    Em log fica so este hash curto — suficiente para correlacionar mensagens
    da mesma pessoa sem espalhar dado pessoal.
    """

    return "wa_" + hashlib.sha256(phone.encode()).hexdigest()[:12]


def session_id_for(phone: str) -> str:
    """Sessao deterministica por telefone.

    Mesmo telefone -> mesma sessao -> mesmo historico. Telefones diferentes
    nunca compartilham sessao. Usa o hash, nao o numero.
    """

    return f"wa:{WORKFLOW}:{user_ref(phone)}"


# ---------------------------------------------------------------------------
# Envio de audio (com voice note — o que falta no helper do Agno)
# ---------------------------------------------------------------------------


async def send_audio_async(recipient: str, audio: SynthesizedAudio, config: WhatsAppConfig) -> bool:
    """Sobe o audio e envia. `voice: true` quando o formato permite.

    Payload conforme a documentacao oficial da Cloud API:
        {"messaging_product":"whatsapp","to":...,"type":"audio",
         "audio":{"id": MEDIA_ID, "voice": true}}
    `voice` so e valido para .ogg/OPUS — por isso vem de
    `SynthesizedAudio.is_voice_note`, decidido pelo formato real gerado.
    """

    media_id = await upload_media_async(
        media_data=audio.content, mime_type=audio.mime_type, filename=audio.filename, config=config
    )
    if isinstance(media_id, dict):
        log_warning(f"upload de audio falhou: {media_id}")
        return False

    payload: dict[str, Any] = {"id": media_id}
    if audio.is_voice_note:
        payload["voice"] = True

    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "audio",
        "audio": payload,
    }

    try:
        async with httpx.AsyncClient(timeout=config.media_timeout) as client:
            response = await client.post(config.messages_url(), headers=config.auth_headers(), json=body)
            response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log_warning(f"envio de audio falhou: {exc}")
        return False


# ---------------------------------------------------------------------------
# Normalizacao da entrada
# ---------------------------------------------------------------------------


@dataclass
class NormalizedInput:
    text: str
    input_mode: str
    transcription: str | None = None
    failed: bool = False


def normalize_incoming(text: str, audios: list[Audio]) -> NormalizedInput:
    """Texto puro para o ANSWER_DM, venha de onde vier.

    Transcricao falha NUNCA vira conteudo inventado: devolve `failed=True` e
    quem chama responde pedindo reenvio.
    """

    if not audios:
        return NormalizedInput(text=text.strip(), input_mode="text")

    partes: list[str] = []
    for index, audio in enumerate(audios, start=1):
        try:
            transcript = transcribe_audio(audio, index)
        except Exception as exc:  # noqa: BLE001
            log_warning(f"transcricao falhou no audio #{index}: {exc}")
            continue
        if transcript:
            partes.append(transcript)

    if not partes:
        return NormalizedInput(text="", input_mode="audio", failed=True)

    transcription = " ".join(partes)
    combinado = f"{text.strip()} {transcription}".strip() if text.strip() else transcription
    return NormalizedInput(text=combinado, input_mode="audio", transcription=transcription)


# ---------------------------------------------------------------------------
# Envio da resposta, ja depois do gate
# ---------------------------------------------------------------------------


async def deliver(
    *,
    recipient: str,
    message: str,
    plan: ResponsePlan,
    config: WhatsAppConfig,
    entry: ChannelLog,
) -> None:
    """Entrega a mensagem JA aprovada pelo Evidence Gate.

    Nunca recebe texto bloqueado: quem chama passa `outbound_message`, que o
    workflow ja substituiu pela frase segura quando o gate barrou.
    """

    audio: SynthesizedAudio | None = None
    if plan.wants_audio:
        audio = await asyncio.to_thread(synthesize, message)
        if audio is None:
            plan = fallback_to_text(plan)
            entry.tts_status = "failed_fallback_text"
        else:
            entry.tts_status = "ok_voice_note" if audio.is_voice_note else "ok_audio_file"

    entry.output_mode = plan.output_mode
    enviados: list[str] = []

    try:
        if plan.wants_text:
            await send_whatsapp_message_async(recipient, message, config)
            enviados.append("text")

        if audio is not None and plan.wants_audio:
            if await send_audio_async(recipient, audio, config):
                enviados.append("audio")
            elif not enviados:
                # Audio falhou no envio e nada saiu ainda: o texto garante
                # que a cliente nao fique sem resposta.
                await send_whatsapp_message_async(recipient, message, config)
                enviados.append("text_after_audio_failure")

        entry.whatsapp_send_status = "sent:" + "+".join(enviados) if enviados else "not_sent"
    except Exception as exc:
        entry.whatsapp_send_status = "failed"
        entry.failure_reason = f"send: {exc}"
        raise


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class AnswerDmWhatsapp(BaseInterface):
    """Interface do AgentOS que serve o canal ligado ao ANSWER_DM.

    Mesmo contrato do `Whatsapp` do Agno (mesmo prefixo, mesmas rotas), mas o
    corpo do webhook vai para o workflow em vez de um Agent solto.
    """

    type = "whatsapp"

    def __init__(self, prefix: str = "/whatsapp", tags: list[str] | None = None) -> None:
        self.prefix = prefix
        self.tags = tags or ["Whatsapp"]
        self.router: APIRouter

    def get_router(self, use_async: bool = True, **kwargs: Any) -> APIRouter:
        self.router = APIRouter(prefix=self.prefix, tags=cast(list[str | Enum], self.tags))
        return attach_answer_dm_routes(self.router, WhatsAppConfig.init())


def attach_answer_dm_routes(router: APIRouter, config: WhatsAppConfig) -> APIRouter:
    # F0.5: `/status` nao serve a Meta — so a humano e a UI do AgentOS. Sai da
    # superficie anonima e passa a exigir Bearer, usando a MESMA dependencia
    # nativa do Agno que protege os routers administrativos. As duas rotas de
    # `/webhook` abaixo continuam publicas de proposito: e por elas que a Meta
    # entra, e cada uma tem seu proprio controle (verify_token no GET, HMAC no
    # POST).
    auth_dependency = build_auth_dependency(build_api_settings())

    @router.get(
        "/status",
        operation_id="whatsapp_status_answer_dm",
        dependencies=[Depends(auth_dependency)],
    )
    async def status() -> dict[str, str]:
        return {"status": "available", "workflow": WORKFLOW}

    @router.get("/webhook", operation_id="whatsapp_verify_answer_dm", name="whatsapp_verify")
    async def verify(request: Request) -> PlainTextResponse:
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if not config.verify_token:
            raise HTTPException(status_code=500, detail="WHATSAPP_VERIFY_TOKEN nao configurado")
        if mode == "subscribe" and token == config.verify_token:
            if not challenge:
                raise HTTPException(status_code=400, detail="challenge ausente")
            return PlainTextResponse(content=challenge)
        raise HTTPException(status_code=403, detail="verify token ou mode invalido")

    @router.post("/webhook", operation_id="whatsapp_webhook_answer_dm", name="whatsapp_webhook")
    async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
        payload = await request.body()
        if not validate_webhook_signature(payload, request.headers.get("X-Hub-Signature-256")):
            log_warning("assinatura de webhook invalida")
            raise HTTPException(status_code=403, detail="assinatura invalida")

        body = await request.json()
        if body.get("object") != "whatsapp_business_account":
            return {"status": "ignored"}

        # ACK imediato; a Meta reenvia se nao receber 200 em ~20s.
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                for message in change.get("value", {}).get("messages", []):
                    background_tasks.add_task(handle_message, message, config)

        return {"status": "processing"}

    return router


async def handle_message(message: dict, config: WhatsAppConfig) -> None:
    """Processa uma mensagem: normaliza -> ANSWER_DM -> gate -> entrega."""

    phone = message.get("from")
    if not phone:
        log_warning("mensagem sem campo 'from', ignorada")
        return

    entry = ChannelLog(user_ref=user_ref(phone))
    message_id = message.get("id")

    try:
        await typing_indicator_async(message_id, config)

        parsed = extract_message_content(message)
        if parsed is None:
            entry.failure_reason = f"tipo nao suportado: {message.get('type')}"
            await send_whatsapp_message_async(phone, _UNSUPPORTED, config)
            entry.whatsapp_send_status = "sent:unsupported_notice"
            return

        media_kwargs, skipped = await download_event_media_async(parsed, config)
        if skipped:
            entry.extra["skipped_media"] = skipped

        normalized = await asyncio.to_thread(
            normalize_incoming, parsed.text, list(media_kwargs.get("audio") or [])
        )
        entry.input_mode = normalized.input_mode
        entry.transcription = normalized.transcription

        if normalized.failed:
            # Transcricao falhou: pede reenvio em vez de adivinhar o conteudo.
            entry.failure_reason = "transcription_failed"
            await send_whatsapp_message_async(phone, _TRANSCRIPTION_FAILED, config)
            entry.whatsapp_send_status = "sent:transcription_failed_notice"
            return

        if not normalized.text:
            entry.failure_reason = "mensagem vazia"
            await send_whatsapp_message_async(phone, _UNSUPPORTED, config)
            entry.whatsapp_send_status = "sent:empty_notice"
            return

        async def _keep_typing() -> None:
            try:
                while True:
                    await asyncio.sleep(20)
                    await typing_indicator_async(message_id, config)
            except asyncio.CancelledError:
                pass

        typing_task = asyncio.create_task(_keep_typing())
        try:
            log, _qc = await asyncio.to_thread(
                run_answer_dm,
                normalized.text,
                session_id=session_id_for(phone),
                user_id=user_ref(phone),
            )
        finally:
            typing_task.cancel()

        outputs = log.outputs
        entry.final_agent = outputs.get("final_agent")
        entry.evidence_status = outputs.get("evidence_status")
        entry.outbound_allowed = bool(outputs.get("outbound_allowed"))
        entry.escalated = bool(log.escalations)

        # O QUE SAI e sempre `outbound_message`: quando o gate bloqueou, o
        # workflow ja o substituiu pela frase segura. A resposta factual
        # bloqueada nunca chega aqui — e, portanto, nunca vira audio.
        outbound = outputs.get("outbound_message") or _ERROR_MESSAGE

        plan = decide_output_mode(
            input_mode=entry.input_mode,  # type: ignore[arg-type]
            incoming_text=normalized.text,
            response_text=outbound,
        )
        await deliver(recipient=phone, message=outbound, plan=plan, config=config, entry=entry)

    except Exception as exc:  # noqa: BLE001
        log_error(f"erro processando mensagem: {exc}")
        entry.failure_reason = entry.failure_reason or f"{type(exc).__name__}: {exc}"
        try:
            await send_whatsapp_message_async(phone, _ERROR_MESSAGE, config)
            entry.whatsapp_send_status = "sent:error_notice"
        except Exception as send_error:  # noqa: BLE001
            log_error(f"falha ao enviar mensagem de erro: {send_error}")
            entry.whatsapp_send_status = "failed"
    finally:
        entry.emit()
