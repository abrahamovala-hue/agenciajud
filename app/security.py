"""
API Security — superficie publica minima do AgentOS.
----------------------------------------------------

Por que este modulo existe:

O AgentOS expoe ~100 rotas administrativas (rodar agente, escrever knowledge,
migrar banco, resolver aprovacao, criar schedule). Sem chave configurada o
Agno deixa TODAS anonimas — `agno/os/auth.py:97` retorna `True` quando
`settings.os_security_key` e vazio. Em producao isso e inaceitavel.

Mecanismo usado: o nativo do proprio Agno 2.6.4 (`AgnoAPISettings`), nao uma
auth paralela. `os_security_key` vira uma dependencia Bearer em todo router
administrativo; as interfaces (WhatsApp) e o `/health` ficam de fora por
construcao, que e exatamente o recorte que precisamos.

Fail-closed: em runtime Railway a chave e OBRIGATORIA e validada no boot por
`utils/validate_envs.py`. Sem ela o processo nao sobe — mesma decisao ja
tomada para o Postgres. Em dev local, sem chave, a API continua aberta para
nao atrapalhar o desenvolvimento.

O que NAO fazemos, de proposito: confiar em IP de origem ou em header
encaminhado (`X-Forwarded-For`, `X-Real-IP`). Header e dado do cliente, nao
credencial.

F0.5 — superficie anonima reduzida ao contrato minimo:

O Agno publica `/` (home) e `/info` sem autenticacao por construcao, e o
nosso canal publicava `/whatsapp/status`. Nenhuma das tres e necessaria para
Meta ou para o healthcheck da Railway. Elas agora exigem Bearer, usando a
MESMA dependencia nativa (`agno.os.auth.get_authentication_dependency`) —
nao existe segunda implementacao de auth neste projeto.

Para `/` e `/info`, que nascem dentro do Agno, usamos o mecanismo nativo de
resolucao de conflito do proprio AgentOS: `on_route_conflict="preserve_base_app"`
(agno/os/app.py:951). Registramos a rota no `base_app` antes de `get_app()` e
o AgentOS pula a versao dele. Ver `app/main.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from os import getenv
from typing import TYPE_CHECKING, Any

from agno import __version__ as agno_version
from agno.os.auth import get_authentication_dependency
from agno.os.schema import InfoResponse
from agno.os.settings import AgnoAPISettings
from fastapi import Depends, FastAPI

from utils.validate_envs import is_railway_runtime

if TYPE_CHECKING:
    from agno.os import AgentOS

# Contrato de producao: a superficie anonima e EXATAMENTE isto.
#
#   /health             -> healthcheck da Railway (GET)
#   /whatsapp/webhook   -> Meta Cloud API. GET = verificacao por
#                          hub.verify_token; POST = entrega de mensagem,
#                          protegida por HMAC X-Hub-Signature-256
#                          (agno/os/interfaces/whatsapp/security.py,
#                          usada em app/whatsapp/channel.py).
#
# Qualquer outra rota exige Bearer. Nao ha excecao "so leitura" nem
# "so metadado": `/`, `/info` e `/whatsapp/status` sairam daqui na F0.5.
PUBLIC_PATH_ALLOWLIST: frozenset[str] = frozenset(
    {
        "/health",
        "/whatsapp/webhook",
    }
)

# Tamanho minimo da chave. 32 chars de entropia real tornam forca bruta
# remota inviavel; abaixo disso a chave e teatro.
MIN_SECURITY_KEY_LENGTH = 32


def build_api_settings() -> AgnoAPISettings:
    """Monta as settings do AgentOS a partir do ambiente.

    - `os_security_key`: liga a autenticacao Bearer nos routers administrativos.
    - `docs_enabled`: em producao desliga /docs, /redoc e /openapi.json. Com a
      auth ligada eles nao vazam dado, mas continuam publicando o mapa da
      superficie administrativa — nao ha motivo de expor isso.
    """

    key = (getenv("OS_SECURITY_KEY") or "").strip()
    production = is_railway_runtime()

    return AgnoAPISettings(
        os_security_key=key or None,
        docs_enabled=not production,
    )


def build_auth_dependency(settings: AgnoAPISettings) -> Callable[..., Any]:
    """Dependencia de autenticacao para rotas que registramos no `base_app`.

    Delega para `agno.os.auth.get_authentication_dependency`, a mesma funcao
    que o AgentOS usa nos routers administrativos. Consequencias importantes
    de reusar em vez de reescrever:

    - Sem `os_security_key` (dev local) ela devolve True e a rota fica aberta.
    - Com JWT configurado ela cede a vez para o middleware de JWT.
    - O token interno do scheduler continua valendo.

    Escrever uma checagem propria aqui quebraria os tres comportamentos.
    """

    return get_authentication_dependency(settings)


def install_authenticated_metadata_routes(
    base_app: FastAPI,
    agent_os: AgentOS,
    settings: AgnoAPISettings,
) -> None:
    """Registra `/` e `/info` no `base_app`, agora exigindo Bearer.

    O AgentOS publica as duas sem autenticacao por construcao
    (agno/os/routers/home.py e agno/os/router.py:239). Como o AgentOS foi
    montado com `on_route_conflict="preserve_base_app"`, registrar aqui faz
    ele pular a versao dele e usar estas (agno/os/app.py:951).

    Precisa rodar ANTES de `agent_os.get_app()` — e la que o AgentOS monta as
    rotas e detecta o conflito (agno/os/app.py:758). `AgentOS.__init__` nao
    registra rota nenhuma, entao chamar logo apos o construtor e seguro.

    O corpo das respostas e identico ao do Agno de proposito: o unico
    comportamento que muda e a exigencia do token.
    """

    auth_dependency = build_auth_dependency(settings)

    @base_app.get("/", tags=["Home"], operation_id="get_api_info", dependencies=[Depends(auth_dependency)])
    async def get_api_info() -> dict[str, Any]:
        return {
            "name": "AgentOS API",
            "id": agent_os.id or "agno-agentos",
            "version": agent_os.version or "1.0.0",
        }

    @base_app.get(
        "/info",
        tags=["Core"],
        operation_id="get_info",
        response_model=InfoResponse,
        dependencies=[Depends(auth_dependency)],
    )
    async def get_info() -> InfoResponse:
        return InfoResponse(
            agno_version=agno_version,
            agent_count=len(agent_os.agents or []),
            team_count=len(agent_os.teams or []),
            workflow_count=len(agent_os.workflows or []),
        )
