"""
Envia as fontes primarias para o Brain de PRODUCAO. One-shot, offline.

    PDF (pasta externa)  ->  extracao local  ->  HTTPS autenticado  ->  Postgres privado

POR QUE ESTE SCRIPT E NAO UM `railway ssh`
------------------------------------------

O Postgres de producao so responde na rede privada da Railway. Os caminhos
foram testados um a um antes de escrever isto — ver `app/admin_ingestion.py`.

O que atravessa a rede e o TEXTO ja extraido, nao o PDF. O arquivo original
nunca sai da pasta da Judith: producao guarda o `sha256`, a contagem de
paginas e o tamanho, que e o que prova identidade.

COMO USAR

    # 1. ligar a rota (uma vez)
    railway variables --set ADMIN_INGESTION_ENABLED=true --service agenciajud

    # 2. enviar
    python scripts/push_primary_sources.py --url https://<app> --key <OS_SECURITY_KEY>

    # 3. DESLIGAR a rota
    railway variables --set ADMIN_INGESTION_ENABLED=false --service agenciajud

O passo 3 nao e opcional. A rota existe para uma importacao, nao para ficar.

SEGURANCA

- Nao imprime corpo de documento, receita, gramagem nem a chave.
- Nao grava nada no repositorio.
- Idempotente: reenviar o mesmo conteudo nao cria versao nova.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

ROUTE = "/admin/knowledge/primary-sources"


def montar_payload(folder: str | None = None) -> dict[str, Any]:
    """Extrai os PDFs e monta o corpo. Nada e enviado aqui."""

    from brain.ingestion import OUTLINE_KEYS, SOURCE_ID_PRIMARY, SOURCE_ID_SITE
    from brain.primary_sources import (
        DEFAULT_SOURCE_DIR,
        build_ebook_chunks,
        build_outline,
        discover,
        load_recipes,
    )

    achados = discover(folder or DEFAULT_SOURCE_DIR)
    if achados.missing:
        raise SystemExit(f"fontes ausentes, nada enviado: {achados.missing}")

    documentos: list[dict[str, Any]] = []

    for item in achados.classified:
        spec = item.spec
        assert spec is not None
        documento = item.document
        eh_ebook = spec.entitlement_scope is not None
        source_id = SOURCE_ID_PRIMARY if eh_ebook else SOURCE_ID_SITE
        receitas = load_recipes(documento) if spec.key == "EBOOK_RECHEIOS" else None

        artifact = {
            "filename": documento.filename,
            "sha256": documento.sha256,
            "size_bytes": documento.size_bytes,
            "page_count": documento.page_count,
            "normalized_sha256": documento.normalized_sha256,
            "source_authority": spec.authority,
            "provided_by": "Judith",
        }

        documentos.append(
            {
                "external_key": spec.key,
                "title": spec.title,
                "body": documento.text,
                "layer": "L1" if eh_ebook else "L3",
                "content_access": "ENTITLEMENT_REQUIRED" if eh_ebook else "PUBLIC",
                "source_id": source_id,
                "source_kind": "judith" if eh_ebook else "business",
                "topics": ["ebook", "tecnica", "chocolate"] if eh_ebook else ["site", "oferta", "produto"],
                "source_authority": spec.authority,
                "entitlement_scope": spec.entitlement_scope,
                "source_ref": f"externo:{documento.filename}",
                "chunks": build_ebook_chunks(documento, spec=spec, recipes=receitas),
                "artifact": artifact,
            }
        )

        if eh_ebook:
            documentos.append(
                {
                    "external_key": OUTLINE_KEYS[spec.key],
                    "title": f"{spec.title} — ficha do produto",
                    "body": build_outline(documento, spec=spec, recipes=receitas),
                    "layer": "L3",
                    "content_access": "PUBLIC",
                    "source_id": source_id,
                    "source_kind": "judith",
                    "topics": ["produto", "ebook"],
                    "source_authority": "DERIVED_DOCUMENT",
                    "entitlement_scope": None,
                    "source_ref": f"derivado de externo:{documento.filename}",
                    "chunks": [],
                    "artifact": None,
                }
            )

    return {"documents": documentos}


def enviar(url: str, key: str, payload: dict[str, Any], *, timeout: int = 180) -> dict[str, Any]:
    corpo = json.dumps(payload).encode("utf-8")
    requisicao = urllib.request.Request(
        url.rstrip("/") + ROUTE,
        data=corpo,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:  # noqa: S310
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", errors="replace")[:400]
        raise SystemExit(f"HTTP {erro.code}: {detalhe}") from erro


def main() -> None:
    parser = argparse.ArgumentParser(description="Envia as fontes primarias para o Brain de producao.")
    parser.add_argument("--url", required=True, help="base do app, ex: https://agenciajud-production.up.railway.app")
    parser.add_argument("--key", required=True, help="OS_SECURITY_KEY (nunca impressa)")
    parser.add_argument("--folder", default=None, help="pasta das fontes (default: a da Judith)")
    parser.add_argument("--dry-run", action="store_true", help="monta o payload e mostra o resumo, sem enviar")
    argumentos = parser.parse_args()

    payload = montar_payload(argumentos.folder)

    print("payload montado (nenhum conteudo impresso):")
    for documento in payload["documents"]:
        print(
            "  %-28s %-22s chars=%-7d chunks=%-3d artifact=%s"
            % (
                documento["external_key"],
                documento["content_access"],
                len(documento["body"]),
                len(documento["chunks"]),
                (documento["artifact"] or {}).get("sha256", "-")[:12],
            )
        )

    if argumentos.dry_run:
        print("\ndry-run: nada enviado.")
        return

    resultado = enviar(argumentos.url, argumentos.key, payload)
    print("\nresposta de producao:")
    for documento in resultado.get("documentos", []):
        print(
            "  %-28s v%-2d chunks=%-3d %-22s %s"
            % (
                documento["external_key"],
                documento["versao"],
                documento["chunks"],
                documento["content_access"],
                "gravado" if documento["mudou"] else "inalterado",
            )
        )
    print("\n  artifacts:", len(resultado.get("artifacts", [])))
    print("  totais   :", resultado.get("totais"))
    print("  confirmados automaticamente:", resultado.get("confirmados_automaticamente"))


if __name__ == "__main__":
    main()
