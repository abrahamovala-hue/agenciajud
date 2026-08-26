"""
API Hardening (F0.1) — a superficie publica do AgentOS.

Contrato coberto aqui:

1. Em producao a chave e OBRIGATORIA (fail-closed no boot).
2. Com a chave ligada, a superficie anonima e EXATAMENTE o allowlist:
   /health e /whatsapp/webhook. Nada mais (F0.5).
3. Rota administrativa sem Bearer -> 401; com Bearer certo -> passa.
4. Header encaminhado (X-Forwarded-*) NUNCA autentica.
5. /docs, /redoc e /openapi.json somem em producao.
6. Dev local sem chave continua utilizavel.

Nao usa Postgres: monta um AgentOS real sobre InMemoryDb, entao roda em CI
sem infra. As rotas montadas sao as mesmas de producao.
"""

from __future__ import annotations

import pytest
from agno.agent import Agent
from agno.db.in_memory import InMemoryDb
from agno.os import AgentOS
from agno.os.interfaces.whatsapp import Whatsapp
from agno.os.settings import AgnoAPISettings
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient

from app.security import (
    MIN_SECURITY_KEY_LENGTH,
    PUBLIC_PATH_ALLOWLIST,
    build_api_settings,
    install_authenticated_metadata_routes,
)

VALID_KEY = "k" * MIN_SECURITY_KEY_LENGTH
RAILWAY_MARKERS = ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_NAME", "RAILWAY_PROJECT_ID")


# --- Helpers ----------------------------------------------------------------


def _build_os(security_key: str | None, *, with_whatsapp: bool, production: bool) -> AgentOS:
    """Monta um AgentOS equivalente ao de producao, sem banco externo."""

    agent = Agent(id="probe-agent", name="Probe", db=InMemoryDb())
    interfaces = [Whatsapp(agent=agent)] if with_whatsapp else []
    return AgentOS(
        name="AgentOS",
        db=InMemoryDb(),
        agents=[agent],
        interfaces=interfaces,
        settings=AgnoAPISettings(os_security_key=security_key, docs_enabled=not production),
    )


def _build_os_like_main() -> AgentOS:
    """Monta o AgentOS EXATAMENTE como o `app/main.py` — sem Postgres.

    Fidelidade importa aqui. A primeira versao da F0.1 passou nos testes e
    ainda assim deixou /docs aberto em producao, porque o teste montava o
    AgentOS sem `base_app` e producao montava com. Este helper reusa as
    mesmas funcoes de producao (`build_api_settings`,
    `install_authenticated_metadata_routes`, `AnswerDmWhatsapp`) e le o
    ambiente do mesmo jeito, entao nao ha um segundo "quase igual" para
    divergir.
    """

    from fastapi import FastAPI

    from app.whatsapp import AnswerDmWhatsapp

    api_settings = build_api_settings()
    base_app = FastAPI(
        title="AgentOS",
        docs_url="/docs" if api_settings.docs_enabled else None,
        redoc_url="/redoc" if api_settings.docs_enabled else None,
        openapi_url="/openapi.json" if api_settings.docs_enabled else None,
    )
    agent = Agent(id="probe-agent", name="Probe", db=InMemoryDb())
    agent_os = AgentOS(
        name="AgentOS",
        base_app=base_app,
        db=InMemoryDb(),
        agents=[agent],
        interfaces=[AnswerDmWhatsapp()],
        settings=api_settings,
        on_route_conflict="preserve_base_app",
    )
    install_authenticated_metadata_routes(base_app, agent_os, api_settings)
    return agent_os


def _auth_dependency_present(route) -> bool:
    """Percorre a arvore de dependencias da rota atras da auth do Agno.

    Precisa ser recursivo: o Agno declara a dependencia ora em
    `router.dependencies`, ora como parametro (`_: bool = Depends(...)`).
    Olhar so um dos dois da falso negativo.
    """

    def walk(dep, seen: set[int]) -> bool:
        if id(dep) in seen:
            return False
        seen.add(id(dep))
        fn = getattr(dep, "call", None)
        if fn is not None and getattr(fn, "__name__", "") == "auth_dependency":
            return True
        return any(walk(child, seen) for child in getattr(dep, "dependencies", []) or [])

    dependant = getattr(route, "dependant", None)
    return walk(dependant, set()) if dependant is not None else False


def _anonymous_paths(app) -> set[str]:
    paths: set[str] = set()
    for route in app.routes:
        if isinstance(route, (APIRoute, APIWebSocketRoute)) and not _auth_dependency_present(route):
            paths.add(route.path)
    return paths


@pytest.fixture(autouse=True)
def _whatsapp_env(monkeypatch):
    """O `Whatsapp()` do Agno le as credenciais no build do router.

    Valores falsos: nenhum teste aqui fala com a Meta — so precisamos que o
    router seja montado para inspecionar a superficie de rotas.
    """

    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token-de-teste")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-de-teste")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "secret-de-teste")


@pytest.fixture
def no_railway(monkeypatch):
    for marker in RAILWAY_MARKERS:
        monkeypatch.delenv(marker, raising=False)


@pytest.fixture
def on_railway(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")


@pytest.fixture
def prod_env(monkeypatch):
    """Ambiente de producao como a Railway entrega: runtime marcado + chave."""

    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("OS_SECURITY_KEY", VALID_KEY)


@pytest.fixture
def dev_env(monkeypatch):
    """Dev local: sem marcador de Railway e sem chave."""

    for marker in RAILWAY_MARKERS:
        monkeypatch.delenv(marker, raising=False)
    monkeypatch.delenv("OS_SECURITY_KEY", raising=False)


def _validate(monkeypatch, **env):
    from utils.validate_envs import validate_envs

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@postgres.railway.internal:5432/railway")
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    validate_envs.cache_clear()
    try:
        return validate_envs()
    finally:
        validate_envs.cache_clear()


# --- 1. Fail-closed no boot -------------------------------------------------


def test_producao_sem_chave_nao_sobe(monkeypatch, on_railway) -> None:
    with pytest.raises(ValueError, match="OS_SECURITY_KEY is missing"):
        _validate(monkeypatch, OS_SECURITY_KEY=None)


def test_producao_com_chave_vazia_nao_sobe(monkeypatch, on_railway) -> None:
    with pytest.raises(ValueError, match="OS_SECURITY_KEY is missing"):
        _validate(monkeypatch, OS_SECURITY_KEY="   ")


def test_producao_com_placeholder_nao_sobe(monkeypatch, on_railway) -> None:
    with pytest.raises(ValueError, match="OS_SECURITY_KEY is missing"):
        _validate(monkeypatch, OS_SECURITY_KEY="your-security-key-here-and-more-chars")


def test_producao_com_chave_curta_nao_sobe(monkeypatch, on_railway) -> None:
    with pytest.raises(ValueError, match="OS_SECURITY_KEY is too short"):
        _validate(monkeypatch, OS_SECURITY_KEY="curta-demais")


def test_producao_com_chave_valida_sobe(monkeypatch, on_railway) -> None:
    settings = _validate(monkeypatch, OS_SECURITY_KEY=VALID_KEY)

    assert settings.os_security_key == VALID_KEY


def test_dev_local_sem_chave_continua_utilizavel(monkeypatch, no_railway) -> None:
    settings = _validate(monkeypatch, OS_SECURITY_KEY=None)

    assert settings.os_security_key == ""


# --- 2. build_api_settings --------------------------------------------------


def test_settings_de_producao_desligam_docs(monkeypatch, on_railway) -> None:
    monkeypatch.setenv("OS_SECURITY_KEY", VALID_KEY)
    settings = build_api_settings()

    assert settings.os_security_key == VALID_KEY
    assert settings.docs_enabled is False


def test_settings_de_dev_mantem_docs(monkeypatch, no_railway) -> None:
    monkeypatch.delenv("OS_SECURITY_KEY", raising=False)
    settings = build_api_settings()

    assert settings.os_security_key is None
    assert settings.docs_enabled is True


def test_chave_com_espacos_e_normalizada(monkeypatch, no_railway) -> None:
    monkeypatch.setenv("OS_SECURITY_KEY", f"  {VALID_KEY}\n")

    assert build_api_settings().os_security_key == VALID_KEY


# --- 3. Superficie publica --------------------------------------------------


def test_superficie_anonima_e_exatamente_o_allowlist(prod_env) -> None:
    """Igualdade, nao subconjunto: nada sobra e nada some do contrato."""

    anonimas = _anonymous_paths(_build_os_like_main().get_app())

    # /workflows/ws valida o token dentro do handler (agno/os/router.py:280),
    # nao como dependencia — por isso nao aparece na arvore.
    anonimas.discard("/workflows/ws")

    assert anonimas == set(PUBLIC_PATH_ALLOWLIST), (
        f"sobrando: {sorted(anonimas - set(PUBLIC_PATH_ALLOWLIST))} / "
        f"faltando: {sorted(set(PUBLIC_PATH_ALLOWLIST) - anonimas)}"
    )


def test_agentos_cru_deixa_home_e_info_abertos() -> None:
    """Documenta o default do Agno que a F0.5 corrige.

    Sem as rotas do `base_app`, `/` e `/info` ficam anonimas mesmo com a chave
    configurada — nao existe flag no `AgnoAPISettings` para desligar as duas.
    """

    anonimas = _anonymous_paths(_build_os(VALID_KEY, with_whatsapp=True, production=True).get_app())

    assert {"/", "/info"} <= anonimas


def test_whatsapp_continua_anonimo() -> None:
    agent_os = _build_os(VALID_KEY, with_whatsapp=True, production=True)

    assert "/whatsapp/webhook" in _anonymous_paths(agent_os.get_app())


def test_health_continua_anonimo() -> None:
    agent_os = _build_os(VALID_KEY, with_whatsapp=True, production=True)

    assert "/health" in _anonymous_paths(agent_os.get_app())


def test_rotas_administrativas_sao_protegidas() -> None:
    agent_os = _build_os(VALID_KEY, with_whatsapp=True, production=True)
    anonimas = _anonymous_paths(agent_os.get_app())

    sensiveis = [
        "/agents",
        "/agents/{agent_id}/runs",
        "/knowledge/content",
        "/databases/all/migrate",
        "/sessions",
        "/memories",
        "/approvals/{approval_id}/resolve",
        "/schedules",
        "/eval-runs",
        "/metrics",
    ]
    expostas = [path for path in sensiveis if path in anonimas]

    assert not expostas, f"rotas sensiveis anonimas: {expostas}"


def test_sem_chave_tudo_fica_anonimo() -> None:
    """Documenta o comportamento do Agno que motiva o fail-closed."""

    agent_os = _build_os(None, with_whatsapp=False, production=False)
    client = TestClient(agent_os.get_app())

    assert client.get("/agents").status_code == 200


# --- 4. Comportamento HTTP real ---------------------------------------------


@pytest.fixture
def client_protegido():
    agent_os = _build_os(VALID_KEY, with_whatsapp=True, production=True)
    return TestClient(agent_os.get_app())


def test_admin_sem_token_responde_401(client_protegido) -> None:
    assert client_protegido.get("/agents").status_code == 401


def test_admin_com_token_errado_responde_401(client_protegido) -> None:
    resposta = client_protegido.get("/agents", headers={"Authorization": "Bearer token-errado"})

    assert resposta.status_code == 401


def test_admin_com_token_certo_passa(client_protegido) -> None:
    resposta = client_protegido.get("/agents", headers={"Authorization": f"Bearer {VALID_KEY}"})

    assert resposta.status_code == 200


def test_run_de_agente_sem_token_responde_401(client_protegido) -> None:
    resposta = client_protegido.post("/agents/probe-agent/runs", data={"message": "oi"})

    assert resposta.status_code == 401


def test_migration_de_banco_sem_token_responde_401(client_protegido) -> None:
    assert client_protegido.post("/databases/all/migrate").status_code == 401


def test_health_responde_sem_token(client_protegido) -> None:
    assert client_protegido.get("/health").status_code == 200


def test_webhook_do_whatsapp_responde_sem_token(client_protegido) -> None:
    """Sem token deve chegar ao handler da Meta — 403 (verify token), nunca 401."""

    resposta = client_protegido.get(
        "/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "1"},
    )

    assert resposta.status_code != 401


# --- 5. Header encaminhado nunca autentica ----------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Real-IP": "127.0.0.1"},
        {"X-Forwarded-Host": "localhost"},
        {"X-Forwarded-Proto": "https"},
        {"X-Api-Key": VALID_KEY},
        {"Authorization": VALID_KEY},
        {"Authorization": f"Basic {VALID_KEY}"},
    ],
)
def test_header_encaminhado_nao_autentica(client_protegido, headers) -> None:
    assert client_protegido.get("/agents", headers=headers).status_code == 401


# --- 6. Docs em producao ----------------------------------------------------


def test_docs_e_openapi_somem_em_producao(client_protegido) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client_protegido.get(path).status_code == 404, f"{path} continua exposto"


def test_docs_seguem_disponiveis_em_dev() -> None:
    agent_os = _build_os(None, with_whatsapp=False, production=False)
    client = TestClient(agent_os.get_app())

    assert client.get("/openapi.json").status_code == 200


# --- 7. Montagem real: AgentOS sobre base_app (como em app/main.py) ----------


def test_com_base_app_docs_somem_em_producao(prod_env) -> None:
    """Regressao: a primeira versao passava `docs_enabled` so ao AgentOS.

    Com `base_app`, o Agno ignora esse flag e /docs, /redoc e /openapi.json
    continuavam 200 em producao. Foi pego verificando o deploy real, nao aqui —
    este teste existe para que nao volte a passar despercebido.
    """

    client = TestClient(_build_os_like_main().get_app())

    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, f"{path} continua exposto com base_app"


def test_com_base_app_docs_ficam_em_dev(dev_env) -> None:
    client = TestClient(_build_os_like_main().get_app())

    assert client.get("/openapi.json").status_code == 200


def test_com_base_app_admin_continua_protegido(prod_env) -> None:
    client = TestClient(_build_os_like_main().get_app())

    assert client.get("/agents").status_code == 401
    assert client.get("/agents", headers={"Authorization": f"Bearer {VALID_KEY}"}).status_code == 200


# --- 8. F0.5: superficie anonima = /health + /whatsapp/webhook ---------------


@pytest.fixture
def client_producao(prod_env):
    return TestClient(_build_os_like_main().get_app())


@pytest.mark.parametrize("path", ["/", "/info", "/whatsapp/status"])
def test_metadados_nao_sao_mais_publicos(client_producao, path) -> None:
    """O aperto da F0.5. Antes as tres respondiam 200 a qualquer um."""

    assert client_producao.get(path).status_code == 401, f"{path} ainda e anonimo"


@pytest.mark.parametrize("path", ["/", "/info", "/whatsapp/status"])
def test_metadados_seguem_funcionando_com_token(client_producao, path) -> None:
    """Fechar nao pode virar quebrar: o cliente autenticado nao perdeu nada."""

    resposta = client_producao.get(path, headers={"Authorization": f"Bearer {VALID_KEY}"})

    assert resposta.status_code == 200, f"{path} quebrou para o cliente autenticado"


def test_payload_de_home_e_info_e_o_mesmo_do_agno(client_producao) -> None:
    auth = {"Authorization": f"Bearer {VALID_KEY}"}

    home = client_producao.get("/", headers=auth).json()
    assert home["name"] == "AgentOS API"
    assert home["version"] == "1.0.0"
    assert home["id"]

    info = client_producao.get("/info", headers=auth).json()
    assert set(info) == {"agno_version", "agent_count", "team_count", "workflow_count"}
    assert info["agent_count"] == 1


def test_status_do_whatsapp_preserva_o_workflow(client_producao) -> None:
    """`/status` fechou, mas continua dizendo por qual workflow o canal entra."""

    corpo = client_producao.get("/whatsapp/status", headers={"Authorization": f"Bearer {VALID_KEY}"}).json()

    assert corpo == {"status": "available", "workflow": "ANSWER_DM"}


def test_health_continua_publico_em_producao(client_producao) -> None:
    assert client_producao.get("/health").status_code == 200


def test_webhook_da_meta_continua_publico(client_producao) -> None:
    """GET com verify token errado: 403 do handler, nunca 401 da auth."""

    resposta = client_producao.get(
        "/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "1"},
    )

    assert resposta.status_code == 403


def test_webhook_da_meta_aceita_verify_token_correto(client_producao) -> None:
    resposta = client_producao.get(
        "/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-de-teste", "hub.challenge": "42"},
    )

    assert resposta.status_code == 200
    assert resposta.text == "42"


def test_post_do_webhook_sem_hmac_continua_403(client_producao) -> None:
    """O HMAC segue sendo o guarda do POST — a auth Bearer nao entrou na frente."""

    resposta = client_producao.post("/whatsapp/webhook", json={"object": "whatsapp_business_account"})

    assert resposta.status_code == 403


@pytest.mark.parametrize("path", ["/", "/info", "/whatsapp/status"])
def test_dev_local_mantem_metadados_abertos(dev_env, path) -> None:
    """Preferencia D: sem chave, o desenvolvimento local nao perde nada."""

    client = TestClient(_build_os_like_main().get_app())

    assert client.get(path).status_code == 200
