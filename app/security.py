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
"""

from __future__ import annotations

from os import getenv

from agno.os.settings import AgnoAPISettings

from utils.validate_envs import is_railway_runtime

# Rotas que PRECISAM continuar anonimas em producao:
#   /health        -> healthcheck da Railway
#   /whatsapp/*    -> Meta Cloud API (protegido por HMAC proprio, ver
#                     agno/os/interfaces/whatsapp/security.py e
#                     app/whatsapp/channel.py)
#   /  e  /info    -> identificacao do servico; nao expoem dado de negocio
PUBLIC_PATH_ALLOWLIST: frozenset[str] = frozenset(
    {
        "/",
        "/health",
        "/info",
        "/whatsapp/status",
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
