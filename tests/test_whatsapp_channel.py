"""
Canal WhatsApp — testes A..L com mocks, sem Meta e sem OpenAI reais.

Cobrem o contrato do canal: entrada normalizada, ANSWER_DM no meio, Evidence
Gate antes do TTS, policy de saida, fallbacks e isolamento de sessao.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from app.whatsapp import channel as ch
from app.whatsapp.policy import decide_output_mode, fallback_to_text
from app.whatsapp.speech import SynthesizedAudio, text_for_speech

# --- Dublês -----------------------------------------------------------------


@dataclass
class FakeConfig:
    access_token: str = "nao-usado-nos-testes"
    phone_number_id: str = "0"
    verify_token: str | None = None
    media_timeout: int = 5

    def messages_url(self) -> str:
        return "https://example.invalid/messages"

    def auth_headers(self) -> dict[str, str]:
        return {}


@pytest.fixture
def sent(monkeypatch) -> dict[str, list[Any]]:
    """Captura tudo que o canal tentaria enviar para a Meta."""

    registro: dict[str, list[Any]] = {"text": [], "audio": []}

    async def fake_send_text(recipient, message, config, italics=False):
        registro["text"].append(message)

    async def fake_send_audio(recipient, audio, config):
        registro["audio"].append(audio)
        return True

    async def fake_typing(message_id, config):
        return None

    monkeypatch.setattr(ch, "send_whatsapp_message_async", fake_send_text)
    monkeypatch.setattr(ch, "send_audio_async", fake_send_audio)
    monkeypatch.setattr(ch, "typing_indicator_async", fake_typing)
    return registro


def _voice_note() -> SynthesizedAudio:
    return SynthesizedAudio(content=b"OggS-fake", mime_type="audio/ogg", filename="r.ogg", is_voice_note=True)


def _fake_answer_dm(monkeypatch, *, outputs: dict[str, Any], escalations: bool = False):
    """Substitui run_answer_dm sem chamar LLM nenhum."""

    chamadas: list[dict[str, Any]] = []

    class FakeLog:
        def __init__(self) -> None:
            self.outputs = outputs
            self.escalations = ["x"] if escalations else []

    def fake_run(message: str, *, session_id=None, user_id=None, task_id=None, channel="internal"):
        chamadas.append({"message": message, "session_id": session_id, "user_id": user_id, "channel": channel})
        return FakeLog(), None

    monkeypatch.setattr(ch, "run_answer_dm", fake_run)
    return chamadas


def _message(kind: str = "text", body: str = "Oi!") -> dict[str, Any]:
    if kind == "text":
        return {"from": "5511999999999", "id": "wamid.1", "type": "text", "text": {"body": body}}
    return {"from": "5511999999999", "id": "wamid.1", "type": "audio", "audio": {"id": "media-1"}}


def _no_media(monkeypatch, audios: list[Any] | None = None) -> None:
    async def fake_download(parsed, config):
        return ({"audio": audios} if audios else {}), []

    monkeypatch.setattr(ch, "download_event_media_async", fake_download)


# --- A: texto -> Community -> texto ----------------------------------------


def test_A_texto_entra_e_sai_como_texto(monkeypatch, sent) -> None:
    _no_media(monkeypatch)
    _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "community-dm-agent",
            "evidence_status": "PASS",
            "outbound_allowed": True,
            "outbound_message": "Oi! Que bom te ver por aqui 😊",
        },
    )

    asyncio.run(ch.handle_message(_message("text", "Oi!"), FakeConfig()))

    assert sent["text"] == ["Oi! Que bom te ver por aqui 😊"]
    assert sent["audio"] == []


# --- B: preco -> Sales -> gate -> texto ------------------------------------


def test_B_pergunta_de_preco_passa_pelo_gate(monkeypatch, sent) -> None:
    _no_media(monkeypatch)
    chamadas = _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "sales-conversion-agent",
            "evidence_status": "PASS",
            "outbound_allowed": True,
            "outbound_message": "O Recheios Profissionais está R$ 37 hoje.",
        },
    )

    asyncio.run(ch.handle_message(_message("text", "Quanto custa o Recheios?"), FakeConfig()))

    assert chamadas[0]["message"] == "Quanto custa o Recheios?"
    assert sent["text"] == ["O Recheios Profissionais está R$ 37 hoje."]


# --- C: audio -> transcricao -> ANSWER_DM ----------------------------------


def test_C_audio_e_transcrito_antes_do_workflow(monkeypatch, sent) -> None:
    monkeypatch.setattr(ch, "transcribe_audio", lambda audio, index=1: "quanto custa o ebook?")
    _no_media(monkeypatch, audios=[object()])
    chamadas = _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "sales-conversion-agent",
            "evidence_status": "PASS",
            "outbound_allowed": True,
            "outbound_message": "Custa R$ 37.",
        },
    )
    monkeypatch.setattr(ch, "synthesize", lambda text: _voice_note())

    asyncio.run(ch.handle_message(_message("audio"), FakeConfig()))

    # O workflow recebe TEXTO, nunca bytes de audio.
    assert chamadas[0]["message"] == "quanto custa o ebook?"


# --- D: audio recebido -> resposta em audio --------------------------------


def test_D_audio_recebido_responde_em_audio(monkeypatch, sent) -> None:
    monkeypatch.setattr(ch, "transcribe_audio", lambda audio, index=1: "oi tudo bem?")
    _no_media(monkeypatch, audios=[object()])
    _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "community-dm-agent",
            "evidence_status": "PASS",
            "outbound_allowed": True,
            "outbound_message": "Tudo ótimo! Como posso ajudar?",
        },
    )
    monkeypatch.setattr(ch, "synthesize", lambda text: _voice_note())

    asyncio.run(ch.handle_message(_message("audio"), FakeConfig()))

    assert len(sent["audio"]) == 1
    assert sent["audio"][0].is_voice_note is True
    assert sent["text"] == [], "audio puro nao duplica o texto"


# --- E: pedido explicito de audio ------------------------------------------


def test_E_pedido_explicito_de_audio() -> None:
    plano = decide_output_mode(
        input_mode="text", incoming_text="me responde por áudio, por favor", response_text="Claro!"
    )
    assert plano.output_mode == "audio"


@pytest.mark.parametrize(
    "pedido",
    ["me responde por audio", "manda um audio", "prefiro ouvir", "pode falar por voz", "responde em áudio"],
)
def test_E_variacoes_do_pedido_de_audio(pedido: str) -> None:
    assert decide_output_mode(input_mode="text", incoming_text=pedido, response_text="ok").wants_audio


def test_pedido_explicito_de_texto_vence_audio_recebido() -> None:
    plano = decide_output_mode(
        input_mode="audio", incoming_text="me responde por texto", response_text="ok"
    )
    assert plano.output_mode == "text"


# --- F: TTS falha -> fallback texto ----------------------------------------


def test_F_tts_falha_cai_para_texto(monkeypatch, sent) -> None:
    monkeypatch.setattr(ch, "transcribe_audio", lambda audio, index=1: "oi")
    _no_media(monkeypatch, audios=[object()])
    _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "community-dm-agent",
            "evidence_status": "PASS",
            "outbound_allowed": True,
            "outbound_message": "Oi! Tudo bem?",
        },
    )
    monkeypatch.setattr(ch, "synthesize", lambda text: None)  # TTS falhou

    asyncio.run(ch.handle_message(_message("audio"), FakeConfig()))

    assert sent["text"] == ["Oi! Tudo bem?"], "a cliente nao pode ficar sem resposta"
    assert sent["audio"] == []


def test_F_fallback_marca_o_plano() -> None:
    plano = decide_output_mode(input_mode="audio", incoming_text="oi", response_text="ok")
    assert fallback_to_text(plano).output_mode == "text"


# --- G: transcricao falha -> mensagem segura -------------------------------


def test_G_transcricao_falha_pede_reenvio(monkeypatch, sent) -> None:
    def explode(audio, index=1):
        raise RuntimeError("api fora do ar")

    monkeypatch.setattr(ch, "transcribe_audio", explode)
    _no_media(monkeypatch, audios=[object()])
    chamadas = _fake_answer_dm(monkeypatch, outputs={})

    asyncio.run(ch.handle_message(_message("audio"), FakeConfig()))

    assert chamadas == [], "sem transcricao o workflow nem roda"
    assert len(sent["text"]) == 1
    assert "áudio" in sent["text"][0]


def test_G_normalize_nao_inventa_conteudo(monkeypatch) -> None:
    monkeypatch.setattr(ch, "transcribe_audio", lambda a, i=1: (_ for _ in ()).throw(RuntimeError("x")))

    resultado = ch.normalize_incoming("", [object()])

    assert resultado.failed is True
    assert resultado.text == ""
    assert resultado.transcription is None


# --- H: NEEDS_EVIDENCE nao vira audio --------------------------------------


def test_H_claim_bloqueado_nunca_e_sintetizado(monkeypatch, sent) -> None:
    """A garantia central: o texto bloqueado nao chega no TTS nem no envio."""

    sintetizados: list[str] = []

    monkeypatch.setattr(ch, "transcribe_audio", lambda a, i=1: "tem desconto?")
    _no_media(monkeypatch, audios=[object()])
    _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "sales-conversion-agent",
            "evidence_status": "NEEDS_EVIDENCE",
            "outbound_allowed": False,
            # o workflow ja trocou a resposta factual pela frase segura
            "outbound_message": "Deixa eu confirmar essa informação certinho 😊",
            "final_response": "Sim! 50% de desconto hoje!",
        },
    )

    def spy(text: str):
        sintetizados.append(text)
        return _voice_note()

    monkeypatch.setattr(ch, "synthesize", spy)

    asyncio.run(ch.handle_message(_message("audio"), FakeConfig()))

    assert sintetizados == ["Deixa eu confirmar essa informação certinho 😊"]
    assert all("desconto" not in t for t in sintetizados), "claim bloqueado virou audio"


# --- I: HUMAN_REQUIRED -----------------------------------------------------


def test_I_human_required_nao_envia_decisao_inventada(monkeypatch, sent) -> None:
    _no_media(monkeypatch)
    _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "customer-support-agent",
            "evidence_status": "HUMAN_REQUIRED",
            "outbound_allowed": False,
            "outbound_message": "Prefiro confirmar direto com a Judith 💛",
            "final_response": "Sim, pode pedir reembolso depois do prazo.",
        },
        escalations=True,
    )

    asyncio.run(ch.handle_message(_message("text", "posso pedir reembolso depois de 20 dias?"), FakeConfig()))

    assert sent["text"] == ["Prefiro confirmar direto com a Judith 💛"]
    assert all("reembolso depois do prazo" not in t for t in sent["text"])


# --- J: sessoes separadas por telefone -------------------------------------


def test_J_telefones_diferentes_tem_sessoes_diferentes() -> None:
    a = ch.session_id_for("5511999999999")
    b = ch.session_id_for("5511888888888")

    assert a != b
    assert ch.session_id_for("5511999999999") == a, "mesma pessoa, mesma sessao"


def test_J_sessao_e_user_ref_nao_contem_telefone() -> None:
    telefone = "5511999999999"
    assert telefone not in ch.session_id_for(telefone)
    assert telefone not in ch.user_ref(telefone)


def test_J_sessao_chega_ao_workflow(monkeypatch, sent) -> None:
    _no_media(monkeypatch)
    chamadas = _fake_answer_dm(
        monkeypatch,
        outputs={"final_agent": "community-dm-agent", "outbound_allowed": True, "outbound_message": "oi"},
    )

    asyncio.run(ch.handle_message(_message("text", "oi"), FakeConfig()))

    assert chamadas[0]["session_id"] == ch.session_id_for("5511999999999")
    assert chamadas[0]["user_id"] == ch.user_ref("5511999999999")


# --- K: resposta com link --------------------------------------------------


def test_K_resposta_com_link_sempre_inclui_texto() -> None:
    """Link falado em voz nao da para copiar."""

    plano = decide_output_mode(
        input_mode="audio",
        incoming_text="qual o link?",
        response_text="Claro! https://pay.kiwify.com.br/8GRurLG",
    )
    assert plano.output_mode == "text_and_audio"
    assert plano.wants_text and plano.wants_audio


def test_K_link_sai_do_audio_mas_fica_no_texto(monkeypatch, sent) -> None:
    monkeypatch.setattr(ch, "transcribe_audio", lambda a, i=1: "manda o link")
    _no_media(monkeypatch, audios=[object()])
    _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "sales-conversion-agent",
            "evidence_status": "PASS",
            "outbound_allowed": True,
            "outbound_message": "Aqui: https://pay.kiwify.com.br/8GRurLG",
        },
    )
    monkeypatch.setattr(ch, "synthesize", lambda text: _voice_note())

    asyncio.run(ch.handle_message(_message("audio"), FakeConfig()))

    assert any("kiwify" in t for t in sent["text"]), "o link precisa ir por escrito"
    assert len(sent["audio"]) == 1


def test_K_url_nao_entra_no_texto_falado() -> None:
    falado = text_for_speech("Aqui: https://pay.kiwify.com.br/8GRurLG — é só clicar")
    assert "http" not in falado and "kiwify" not in falado


# --- L: falha de envio -----------------------------------------------------


def test_L_falha_de_envio_e_registrada_sem_duplicar(monkeypatch) -> None:
    tentativas: list[str] = []

    async def falha_no_envio(recipient, message, config, italics=False):
        tentativas.append(message)
        raise RuntimeError("meta fora do ar")

    async def fake_typing(message_id, config):
        return None

    monkeypatch.setattr(ch, "send_whatsapp_message_async", falha_no_envio)
    monkeypatch.setattr(ch, "typing_indicator_async", fake_typing)
    _no_media(monkeypatch)
    _fake_answer_dm(
        monkeypatch,
        outputs={"final_agent": "community-dm-agent", "outbound_allowed": True, "outbound_message": "oi"},
    )

    asyncio.run(ch.handle_message(_message("text", "oi"), FakeConfig()))

    # 1 tentativa da resposta + 1 do aviso de erro. Nao ha retry silencioso
    # que mandaria a mesma resposta duas vezes.
    assert tentativas.count("oi") == 1


def test_L_audio_falha_no_envio_cai_para_texto(monkeypatch, sent) -> None:
    async def audio_falha(recipient, audio, config):
        return False

    monkeypatch.setattr(ch, "send_audio_async", audio_falha)
    monkeypatch.setattr(ch, "transcribe_audio", lambda a, i=1: "oi")
    _no_media(monkeypatch, audios=[object()])
    _fake_answer_dm(
        monkeypatch,
        outputs={"final_agent": "community-dm-agent", "outbound_allowed": True, "outbound_message": "Oi!"},
    )
    monkeypatch.setattr(ch, "synthesize", lambda text: _voice_note())

    asyncio.run(ch.handle_message(_message("audio"), FakeConfig()))

    assert sent["text"] == ["Oi!"], "envio de audio falhou -> texto garante a entrega"


# --- Log estruturado (secao 10) --------------------------------------------


def test_log_tem_todos_os_campos_e_nao_vaza_telefone(monkeypatch, sent, caplog) -> None:
    _no_media(monkeypatch)
    _fake_answer_dm(
        monkeypatch,
        outputs={
            "final_agent": "sales-conversion-agent",
            "evidence_status": "PASS",
            "outbound_allowed": True,
            "outbound_message": "R$ 37",
        },
    )

    entry = ch.ChannelLog(user_ref=ch.user_ref("5511999999999"))
    campos = entry.__dict__

    for campo in (
        "channel",
        "input_mode",
        "workflow",
        "final_agent",
        "evidence_status",
        "outbound_allowed",
        "output_mode",
        "tts_status",
        "whatsapp_send_status",
        "failure_reason",
    ):
        assert campo in campos

    assert "5511999999999" not in str(campos)


# --- Router: montagem e webhook --------------------------------------------


@pytest.fixture
def wa_env(monkeypatch):
    """Env de WhatsApp falso. Nenhuma credencial real e usada nos testes."""

    for key, value in {
        "WHATSAPP_ENABLED": "true",
        "WHATSAPP_ACCESS_TOKEN": "test-token",
        "WHATSAPP_PHONE_NUMBER_ID": "test-phone-id",
        "WHATSAPP_VERIFY_TOKEN": "test-verify",
        "WHATSAPP_SKIP_SIGNATURE_VALIDATION": "true",
    }.items():
        monkeypatch.setenv(key, value)


def _client(wa_interface):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(wa_interface.get_router())
    return TestClient(app)


def test_canal_padrao_e_o_answer_dm(wa_env) -> None:
    from app.interfaces import build_interfaces

    interfaces = build_interfaces(None)

    assert len(interfaces) == 1
    assert type(interfaces[0]).__name__ == "AnswerDmWhatsapp"


def test_flag_volta_para_o_agente_solto_do_starter(wa_env, monkeypatch) -> None:
    """Escotilha de depuracao: nao perdemos o caminho original."""

    monkeypatch.setenv("WHATSAPP_ROUTE_TO_AGENT", "true")
    from agents.my_agent import my_agent
    from app.interfaces import build_interfaces

    assert type(build_interfaces(my_agent)[0]).__name__ == "Whatsapp"


def test_whatsapp_desligado_nao_monta_interface(monkeypatch) -> None:
    """AgentOS local nao pode depender do canal."""

    monkeypatch.setenv("WHATSAPP_ENABLED", "false")
    from app.interfaces import build_interfaces

    assert build_interfaces(None) == []


def test_verificacao_de_webhook_da_meta(wa_env) -> None:
    from app.whatsapp import AnswerDmWhatsapp

    client = _client(AnswerDmWhatsapp())

    ok = client.get(
        "/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "test-verify", "hub.challenge": "12345"},
    )
    assert ok.status_code == 200 and ok.text == "12345"

    negado = client.get(
        "/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "1"},
    )
    assert negado.status_code == 403


def test_webhook_aceita_payload_da_meta_e_responde_rapido(wa_env, monkeypatch, sent) -> None:
    """A Meta reenvia se nao receber 200 rapido: ACK primeiro, processa depois."""

    _no_media(monkeypatch)
    _fake_answer_dm(
        monkeypatch,
        outputs={"final_agent": "community-dm-agent", "outbound_allowed": True, "outbound_message": "Oi!"},
    )

    from app.whatsapp import AnswerDmWhatsapp

    client = _client(AnswerDmWhatsapp())
    resposta = client.post(
        "/whatsapp/webhook",
        json={
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"messages": [_message("text", "Oi!")]}}]}],
        },
    )

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "processing"
    assert sent["text"] == ["Oi!"]


def test_webhook_ignora_objeto_que_nao_e_whatsapp(wa_env) -> None:
    from app.whatsapp import AnswerDmWhatsapp

    client = _client(AnswerDmWhatsapp())
    resposta = client.post("/whatsapp/webhook", json={"object": "page", "entry": []})

    assert resposta.json()["status"] == "ignored"


def test_classificacao_nao_polui_a_sessao_da_conversa(monkeypatch) -> None:
    """Regressao: com classify e resposta no mesmo session_id, os prompts de
    classificacao afogavam o historico e o agente esquecia a conversa."""

    sessoes: list[str | None] = []

    class Spy:
        def __init__(self, inner):
            self.inner = inner

        def run(self, message, **kwargs):
            sessoes.append(kwargs.get("session_id"))
            return self.inner.run(message, **kwargs)

    import orchestration.step_helpers as sh
    from orchestration.handoff import AgentStepDecision, RoutingDecision

    class FakeAgent:
        def run(self, message, output_schema=None, **kwargs):
            from unittest.mock import MagicMock

            if output_schema is RoutingDecision:
                content = RoutingDecision(
                    decision="d", output="o", confidence="alto",
                    recommended_next="community-dm-agent", route_to="community-dm-agent",
                )
            else:
                content = AgentStepDecision(
                    decision="d", output="Oi!", confidence="alto", recommended_next="judith"
                )
            return MagicMock(content=content, messages=[])

    monkeypatch.setattr(sh, "get_agent", lambda aid: Spy(FakeAgent()))

    from orchestration.workflows.answer_dm import run_answer_dm

    run_answer_dm("Oi!", session_id="wa:ANSWER_DM:wa_abc", user_id="wa_abc")

    assert sessoes[0] == "wa:ANSWER_DM:wa_abc:interno", "classificacao usa sessao interna"
    assert sessoes[1] == "wa:ANSWER_DM:wa_abc", "a resposta usa a sessao da conversa"
