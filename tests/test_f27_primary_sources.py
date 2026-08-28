"""
F2.7 — fontes primarias, ingestao, canonicalizacao e acesso.

DOIS GRUPOS DE TESTE, COM EXIGENCIAS DIFERENTES
-----------------------------------------------

Os que dependem dos PDFs da Judith rodam so na maquina dela: os arquivos sao
propriedade intelectual paga e ficam FORA do repositorio, entao no CI eles
sao pulados (`requires_pdfs`). Isso e uma consequencia direta da regra de
seguranca — nao um teste frouxo.

Os que valem SEMPRE sao os que protegem o repositorio de si mesmo: nenhum PDF
versionado, nenhum preco em PRODUCTS, nenhum valor hipotetico recuperavel em
OFFERS. Esses rodam em qualquer lugar, porque o que eles verificam esta no
proprio repositorio.
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from brain.primary_sources import DEFAULT_SOURCE_DIR

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs" / "JUDITH-AI-TEAM"

requires_pdfs = pytest.mark.skipif(
    not DEFAULT_SOURCE_DIR.exists(),
    reason="PDFs da Judith ficam fora do repositorio (propriedade intelectual paga)",
)


@lru_cache(maxsize=1)
def achados():  # type: ignore[no-untyped-def]
    """Descoberta memoizada.

    `discover()` extrai 33 MB de PDF. Sem cache, cada teste refazia a extracao
    inteira e a suite passava de dois minutos — o que na pratica faria alguem
    parar de roda-la.
    """

    from brain.primary_sources import discover

    return discover()


# =============================================================================
# SEGURANCA — vale sempre, inclusive no CI
# =============================================================================


class TestNenhumPdfNoRepositorio:
    def test_nenhum_pdf_versionado(self) -> None:
        rastreados = subprocess.run(
            ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        assert [a for a in rastreados if a.lower().endswith(".pdf")] == []

    def test_pasta_de_fontes_esta_fora_do_repositorio(self) -> None:
        """Nao basta nao estar commitado: precisa ser inalcancavel por `git add`."""

        assert RAIZ not in DEFAULT_SOURCE_DIR.parents
        assert DEFAULT_SOURCE_DIR != RAIZ

    def test_nenhum_corpo_de_receita_em_docs(self) -> None:
        """Uma receita completa nunca pode ter vazado para um arquivo versionado.

        Assinatura de receita: varias gramagens no mesmo documento. Os docs de
        marca falam de produto, nao de formula.
        """

        for arquivo in DOCS.rglob("*.md"):
            texto = arquivo.read_text(encoding="utf-8")
            gramagens = re.findall(r"\b\d+(?:[.,]\d+)?\s*g\b", texto)
            assert len(gramagens) < 5, f"{arquivo.name} tem {len(gramagens)} gramagens — parece receita"


# =============================================================================
# CANONICALIZACAO — vale sempre
# =============================================================================


class TestProductsNaoTemDadoComercial:
    """PRODUCTS e identidade. Preco tem um dono so, e nao e este documento."""

    @pytest.fixture()
    def texto(self) -> str:
        return (DOCS / "brand" / "PRODUCTS.md").read_text(encoding="utf-8")

    def test_sem_preco(self, texto: str) -> None:
        assert re.search(r"R\$\s?\d", texto) is None

    def test_sem_checkout(self, texto: str) -> None:
        assert "kiwify" not in texto.lower()

    def test_sem_desconto(self, texto: str) -> None:
        """Sem VALOR de desconto.

        A palavra pode aparecer — o documento diz, em duas linhas, que desconto
        mora em OFFERS. Proibir a palavra proibiria a regra que aponta para o
        dono certo do dado, que e o oposto do que este teste quer garantir.
        """

        assert "% off" not in texto
        assert re.search(r"\d+\s*%\s*(de\s+)?desconto", texto, re.IGNORECASE) is None

    def test_tem_identidade_dos_tres_produtos(self, texto: str) -> None:
        assert "O Segredo do Chocolate" in texto
        assert "Lascas & Barras de Chocolate Premium" in texto
        assert "Recheios Profissionais" in texto
        assert "Casquinhas Profissionais" in texto

    def test_recheios_declara_20_receitas_e_brigadeiros(self, texto: str) -> None:
        assert "20" in texto
        assert "Brigadeiros Gourmet" in texto

    def test_lascas_declara_bonus_comprovado(self, texto: str) -> None:
        assert "4" in texto
        assert "vital" in texto.lower()

    def test_casquinhas_nao_ganha_bonus_por_inferencia(self, texto: str) -> None:
        """O PDF de Casquinhas nao documenta bonus. PRODUCTS nao pode inventar."""

        bloco = texto.split("## 3. Casquinhas Profissionais")[1]
        assert "não documenta" in bloco


class TestOffersEFonteComercialUnica:
    @pytest.fixture()
    def texto(self) -> str:
        return (DOCS / "brand" / "OFFERS.md").read_text(encoding="utf-8")

    def test_preco_hipotetico_nao_e_recuperavel(self, texto: str) -> None:
        """R$ 44,90 nunca foi praticado. Nao pode existir como texto em OFFERS."""

        assert "44,90" not in texto
        assert "44.90" not in texto

    def test_sem_countdown_como_campanha(self, texto: str) -> None:
        assert "countdown" not in texto.lower()

    def test_sem_roadmap_nem_todo(self, texto: str) -> None:
        assert "- [ ]" not in texto
        assert "Pontos de Melhoria" not in texto

    def test_sem_combo_inventado(self, texto: str) -> None:
        assert "UNAVAILABLE" in texto

    def test_checkouts_vigentes(self, texto: str) -> None:
        for slug in ("8GRurLG", "Eu6Eb9p", "GlA8RXr"):
            assert slug in texto

    def test_checkouts_mortos_marcados_como_mortos(self, texto: str) -> None:
        """Os links antigos podem aparecer, mas so na secao que os aposenta."""

        for slug in ("od97l73", "r8LmYVZ"):
            assert slug in texto
            assert "INDISPON" in texto.upper()

    def test_tem_last_verified(self, texto: str) -> None:
        assert "2026-08-27" in texto

    def test_nao_inventa_prazo(self, texto: str) -> None:
        assert "desconhecido" in texto.lower()

    def test_conflito_de_preco_esta_declarado(self, texto: str) -> None:
        assert "25.00" in texto
        assert "NEEDS_JUDITH" in texto


class TestEstrategiaFoiMovidaNaoApagada:
    @pytest.fixture()
    def texto(self) -> str:
        return (DOCS / "brand" / "OFFER_STRATEGY_INTERNAL.md").read_text(encoding="utf-8")

    def test_as_ideias_continuam_auditaveis(self, texto: str) -> None:
        for ideia in ("combo", "ountdown", "order bump", "depoimento"):
            assert ideia.lower() in texto.lower()

    def test_marcadas_como_proposta_e_nao_fato(self, texto: str) -> None:
        assert "PROPOSTA" in texto
        assert "DEPRECATED" in texto

    def test_o_valor_hipotetico_foi_removido_do_texto(self, texto: str) -> None:
        """Marcar como hipotese nao basta: retrieval devolve trecho, nao rotulo."""

        assert "44,90" not in texto

    def test_declarado_interno(self, texto: str) -> None:
        assert "INTERNAL_ONLY" in texto


class TestBusinessRulesTemDonoUnico:
    @pytest.fixture()
    def texto(self) -> str:
        return (RAIZ / "docs" / "JUDITH-AI-TEAM-V2" / "BUSINESS_RULES.md").read_text(encoding="utf-8")

    def test_preco_nao_vem_mais_de_duas_fontes(self, texto: str) -> None:
        assert "OFFERS.md` / `brand/PRODUCTS.md" not in texto
        assert "exclusivamente de `brand/OFFERS.md`" in texto

    def test_promessa_de_resultado_continua_proibida(self, texto: str) -> None:
        assert "resultado garantido" in texto

    def test_cross_promo_nao_vence_fonte_primaria(self, texto: str) -> None:
        assert "Promoção cruzada não é fonte canônica" in texto


class TestTaxonomia:
    def test_estrategia_interna_e_internal_only(self) -> None:
        from brain.taxonomy import content_access_for

        assert (
            content_access_for(
                key="OFFER_STRATEGY_INTERNAL",
                relative_path="JUDITH-AI-TEAM/brand/OFFER_STRATEGY_INTERNAL.md",
            )
            == "INTERNAL_ONLY"
        )


# =============================================================================
# ACESSO POR AGENTE — vale sempre
# =============================================================================


class TestAcessoPorAgente:
    def test_venda_nao_conhece_material_pago(self) -> None:
        """Vender nao exige a formula: o outline responde tudo que a venda precisa."""

        from brain.access_policy import resolve_access

        acesso = resolve_access("sales-conversion-agent")
        assert acesso.can_know_paid is False
        assert "EBOOK_RECHEIOS" not in acesso.external_keys  # type: ignore[operator]
        assert "PRODUCT_OUTLINE_RECHEIOS" in acesso.external_keys  # type: ignore[operator]

    def test_suporte_conhece_material_pago(self) -> None:
        from brain.access_policy import resolve_access

        acesso = resolve_access("customer-support-agent")
        assert acesso.can_know_paid is True
        assert "EBOOK_RECHEIOS" in acesso.external_keys  # type: ignore[operator]

    def test_knowledge_manager_ve_tudo(self) -> None:
        from brain.access_policy import resolve_access

        acesso = resolve_access("knowledge-manager")
        for chave in ("EBOOK_RECHEIOS", "EBOOK_CASQUINHAS", "EBOOK_LASCAS"):
            assert chave in acesso.external_keys  # type: ignore[operator]

    def test_conteudo_nao_recebe_corpo_pago(self) -> None:
        from brain.access_policy import resolve_access

        for agente in ("caption-writer", "script-writer", "hook-finder", "social-media-manager"):
            acesso = resolve_access(agente)
            assert acesso.can_know_paid is False, agente
            assert not {"EBOOK_RECHEIOS", "EBOOK_CASQUINHAS", "EBOOK_LASCAS"} & set(
                acesso.external_keys or ()
            ), agente

    def test_agente_sem_concessao_nao_ganha_nada(self) -> None:
        """Fail-closed: a tabela concede, nunca abre por default."""

        from brain.access_policy import native_grants

        assert native_grants("analytics-bi-agent") == frozenset()
        assert native_grants("agente-inexistente") == frozenset()

    def test_nenhum_agente_escreve_knowledge(self) -> None:
        from agents.knowledge_policies import KNOWLEDGE_POLICIES
        from brain.access_policy import resolve_access

        for agente in KNOWLEDGE_POLICIES:
            assert resolve_access(agente).can_write_knowledge is False, agente


# =============================================================================
# INGESTAO — exige os PDFs
# =============================================================================


@requires_pdfs
class TestDescoberta:
    def test_encontra_as_quatro_fontes(self) -> None:
        achados_ = achados()
        assert achados_.missing == []
        assert len(achados_.classified) == 4

    def test_site_nao_e_confundido_com_ebook(self) -> None:
        """A homepage cita 'recheios' e 'profissionais' — assinatura fraca erra aqui."""

        item = achados().by_key("SITE_SNAPSHOT")
        assert item is not None
        assert item.document.filename.lower().endswith(".pdf")
        assert item.spec is not None
        assert item.spec.authority == "USER_PROVIDED_OFFICIAL_SITE_SNAPSHOT"

    @pytest.mark.parametrize(
        ("chave", "paginas"),
        [("EBOOK_RECHEIOS", 25), ("EBOOK_CASQUINHAS", 25), ("EBOOK_LASCAS", 31), ("SITE_SNAPSHOT", 18)],
    )
    def test_contagem_de_paginas(self, chave: str, paginas: int) -> None:
        item = achados().by_key(chave)
        assert item is not None
        assert item.document.page_count == paginas
        assert len(item.document.pages) == paginas
        assert item.document.empty_pages == []


@requires_pdfs
class TestReparoDeGlifo:
    def test_travessao_restaurado_em_recheios(self) -> None:
        item = achados().by_key("EBOOK_RECHEIOS")
        assert item is not None
        assert item.document.repaired_dashes == 40
        assert "Formato Rosca — Rendimento: 24 bombons" in item.document.text

    def test_numero_de_verdade_nao_e_destruido(self) -> None:
        """Em Casquinhas e Lascas os '4' sao numeros reais — nao travessoes."""

        achados_ = achados()
        for chave in ("EBOOK_CASQUINHAS", "EBOOK_LASCAS"):
            item = achados_.by_key(chave)
            assert item is not None
            assert item.document.repaired_dashes == 0, chave
        lascas = achados_.by_key("EBOOK_LASCAS")
        assert lascas is not None
        assert "Aula 4" in lascas.document.text

    def test_sem_byte_de_controle_no_texto(self) -> None:
        """PostgreSQL recusa NUL em campo text; SQLite aceita em silencio.

        Este teste existe porque a suite local passou e a primeira gravacao em
        producao falhou com "cannot contain NUL bytes". O banco de teste
        escondeu o que o banco real encontrou — entao a checagem passa a viver
        aqui, e nao so no Postgres.
        """

        for item in achados().classified:
            texto = item.document.text
            assert chr(0) not in texto, item.spec.key
            permitidos = (10, 13, 9)  # LF, CR, TAB
            proibidos = [c for c in texto if ord(c) < 32 and ord(c) not in permitidos]
            assert proibidos == [], item.spec.key

    def test_remocao_de_controle_e_contada(self) -> None:
        """Normalizacao silenciosa e o que esta fase existe para nao fazer."""

        lascas = achados().by_key("EBOOK_LASCAS")
        assert lascas is not None
        assert lascas.document.dropped_controls > 0
        assert any("controle" in aviso for aviso in lascas.document.warnings)

    def test_texto_bruto_preservado(self) -> None:
        item = achados().by_key("EBOOK_RECHEIOS")
        assert item is not None
        assert item.document.raw_text != item.document.text


@requires_pdfs
class TestRecheios:
    @pytest.fixture()
    def receitas(self):  # type: ignore[no-untyped-def]
        from brain.primary_sources import load_recipes

        item = achados().by_key("EBOOK_RECHEIOS")
        assert item is not None
        return load_recipes(item.document)

    def test_vinte_receitas(self, receitas) -> None:  # type: ignore[no-untyped-def]
        assert len(receitas) == 20

    def test_distribuicao_por_categoria(self, receitas) -> None:  # type: ignore[no-untyped-def]
        contagem: dict[str, int] = {}
        for r in receitas:
            contagem[r.category] = contagem.get(r.category, 0) + 1
        assert contagem == {"GANACHES": 7, "BRIGADEIROS GOURMET": 3, "GIANDUIAS": 8, "CARAMELOS": 2}

    def test_brigadeiros_estao_presentes(self, receitas) -> None:  # type: ignore[no-untyped-def]
        nomes = {r.name for r in receitas if r.category == "BRIGADEIROS GOURMET"}
        assert nomes == {
            "Brigadeiro Gourmet de Paçoca",
            "Brigadeiro Gourmet de Pão de Mel",
            "Brigadeiro Gourmet com Bolo de Cenoura",
        }

    def test_toda_receita_tem_ingrediente_e_passo(self, receitas) -> None:  # type: ignore[no-untyped-def]
        assert [r.name for r in receitas if not r.ingredients] == []
        assert [r.name for r in receitas if not r.steps] == []

    def test_receita_continuada_e_uma_so(self, receitas) -> None:  # type: ignore[no-untyped-def]
        """Bolo de Cenoura ocupa 2 paginas e continua sendo UMA receita."""

        bolo = next(r for r in receitas if "Bolo de Cenoura" in r.name)
        assert bolo.pages == [13, 14]

    def test_nenhuma_pagina_pertence_a_duas_receitas(self, receitas) -> None:  # type: ignore[no-untyped-def]
        vistas: set[int] = set()
        for r in receitas:
            for pagina in r.pages:
                assert pagina not in vistas, f"pagina {pagina} em duas receitas"
                vistas.add(pagina)

    def test_invariante_quebrado_levanta(self) -> None:
        """Ingerir um catalogo errado seria pior do que falhar."""

        from brain.recipes import RecipeSetError, parse_recipes

        item = achados().by_key("EBOOK_RECHEIOS")
        assert item is not None
        with pytest.raises(RecipeSetError):
            parse_recipes(item.document.pages[:10], index={})


@requires_pdfs
class TestCasquinhasELascas:
    def test_casquinhas_cobre_os_tres_metodos(self) -> None:
        item = achados().by_key("EBOOK_CASQUINHAS")
        assert item is not None
        texto = item.document.text.lower()
        for metodo in ("adição", "tablagem", "mycryo"):
            assert metodo in texto, metodo

    def test_cross_promo_e_classificada_como_tal(self) -> None:
        """A ultima secao de Casquinhas fala de Recheios. Nao e fonte de Recheios."""

        from brain.primary_sources import build_ebook_chunks

        item = achados().by_key("EBOOK_CASQUINHAS")
        assert item is not None
        pedacos = build_ebook_chunks(item.document, spec=item.spec)
        tipos = {p["page"]: p["content_kind"] for p in pedacos}
        assert tipos[24] == "CROSS_PROMOTION"

    def test_lascas_tem_identidade_dupla(self) -> None:
        item = achados().by_key("EBOOK_LASCAS")
        assert item is not None
        assert item.spec.title == "O Segredo do Chocolate"
        assert item.spec.subtitle == "Lascas & Barras de Chocolate Premium"

    def test_lascas_tem_quatro_aulas_bonus_e_vitalicio(self) -> None:
        from brain.primary_sources import _proven_bonus
        item = achados().by_key("EBOOK_LASCAS")
        assert item is not None
        bonus = _proven_bonus(item.document)
        assert bonus is not None
        assert len(bonus["itens"]) == 4
        assert "vitalicio" in bonus["acesso"]
        assert bonus["pagina"] == 30

    def test_bonus_nao_e_inferido_entre_produtos(self) -> None:
        from brain.primary_sources import _proven_bonus

        achados_ = achados()
        for chave in ("EBOOK_RECHEIOS", "EBOOK_CASQUINHAS"):
            item = achados_.by_key(chave)
            assert item is not None
            assert _proven_bonus(item.document) is None, chave


@requires_pdfs
class TestOutlineSeguro:
    def test_outline_nao_carrega_formula(self) -> None:
        from brain.primary_sources import build_outline, load_recipes

        achados_ = achados()
        for chave in ("EBOOK_RECHEIOS", "EBOOK_CASQUINHAS", "EBOOK_LASCAS"):
            item = achados_.by_key(chave)
            assert item is not None
            receitas = load_recipes(item.document) if chave == "EBOOK_RECHEIOS" else None
            texto = build_outline(item.document, spec=item.spec, recipes=receitas)
            assert re.search(r"\b\d+\s*g\b", texto) is None, chave
            assert "Modo de Preparo" not in texto, chave

    def test_outline_descreve_o_produto(self) -> None:
        from brain.primary_sources import build_outline, load_recipes

        item = achados().by_key("EBOOK_RECHEIOS")
        assert item is not None
        texto = build_outline(item.document, spec=item.spec, recipes=load_recipes(item.document))
        assert "20 receitas" in texto
        assert "Brigadeiro Gourmet de Paçoca" in texto


@requires_pdfs
class TestIngestaoNoStore:
    @pytest.fixture()
    def repositorio(self, tmp_path):  # type: ignore[no-untyped-def]
        from sqlalchemy import create_engine

        from brain.repository import KnowledgeRepository

        engine = create_engine(f"sqlite:///{tmp_path / 'f27.sqlite'}")
        repo = KnowledgeRepository(engine)
        repo.ensure_tables()
        return repo

    def test_ingere_artifacts_e_documentos(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        from brain.ingestion import ingest_primary_sources

        relatorio = ingest_primary_sources(repositorio)
        resumo = relatorio.summary()
        assert resumo["artifacts"] == 4
        assert resumo["documentos"] == 7
        assert resumo["documentos_pagos"] == 3
        assert resumo["erros"] == []

    def test_nada_vira_confirmed(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        from brain.ingestion import ingest_primary_sources

        relatorio = ingest_primary_sources(repositorio)
        assert relatorio.summary()["confirmados_automaticamente"] == 0
        assert all(d["status"] == "TO_VALIDATE" for d in relatorio.documents)

    def test_idempotente(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        from brain.ingestion import ingest_primary_sources

        ingest_primary_sources(repositorio)
        antes = repositorio.counts()
        segundo = ingest_primary_sources(repositorio)
        assert repositorio.counts() == antes
        assert segundo.summary()["artifacts_novos"] == 0

    def test_artifact_guarda_o_original(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        import hashlib

        from brain.ingestion import ingest_primary_sources

        relatorio = ingest_primary_sources(repositorio)
        for registro in relatorio.artifacts:
            bytes_gravados = repositorio.artifact_bytes(registro["artifact_id"])
            assert bytes_gravados is not None
            assert hashlib.sha256(bytes_gravados).hexdigest() == registro["sha256"]

    def test_metadata_nao_carrega_os_bytes(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        from brain.ingestion import ingest_primary_sources

        relatorio = ingest_primary_sources(repositorio)
        meta = repositorio.get_artifact_metadata(relatorio.artifacts[0]["artifact_id"])
        assert meta is not None
        assert "content" not in meta

    def test_provenance_gravada(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        from brain.ingestion import ingest_primary_sources

        ingest_primary_sources(repositorio)
        documento = repositorio.get_document_by_external_key("EBOOK_RECHEIOS")
        assert documento is not None
        assert documento["source_authority"] == "USER_AUTHORIZED_PRIMARY_SOURCE"
        assert documento["provided_by"] == "Judith"
        assert documento["entitlement_scope"] == "ebook_recheios_profissionais"
        assert documento["content_access"] == "ENTITLEMENT_REQUIRED"

    def test_chunk_de_receita_carrega_recipe_id_e_pagina(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        from brain.ingestion import ingest_primary_sources

        ingest_primary_sources(repositorio)
        documento = repositorio.get_document_by_external_key("EBOOK_RECHEIOS")
        assert documento is not None
        versao = repositorio.get_current_version(documento["document_id"])
        assert versao is not None
        pedacos = repositorio.get_chunks(versao["version_id"])
        receitas = [p for p in pedacos if p["content_kind"] == "RECIPE"]
        assert len(receitas) == 21  # 20 receitas, uma delas em 2 paginas
        assert all(p["recipe_id"] for p in receitas)
        assert all(p["page"] for p in receitas)

    def test_outline_e_publico_e_o_ebook_nao(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        from brain.ingestion import ingest_primary_sources

        ingest_primary_sources(repositorio)
        outline = repositorio.get_document_by_external_key("PRODUCT_OUTLINE_RECHEIOS")
        ebook = repositorio.get_document_by_external_key("EBOOK_RECHEIOS")
        assert outline is not None and ebook is not None
        assert outline["content_access"] == "PUBLIC"
        assert outline["layer"] == "L3"
        assert ebook["content_access"] == "ENTITLEMENT_REQUIRED"
        assert ebook["layer"] == "L1"


@requires_pdfs
class TestRetrievalComEbooks:
    @pytest.fixture()
    def repositorio(self, tmp_path):  # type: ignore[no-untyped-def]
        from sqlalchemy import create_engine

        from brain.ingestion import ingest_primary_sources
        from brain.repository import KnowledgeRepository

        engine = create_engine(f"sqlite:///{tmp_path / 'f27r.sqlite'}")
        repo = KnowledgeRepository(engine)
        repo.ensure_tables()
        ingest_primary_sources(repo)
        return repo

    def _buscar(self, repositorio, agente: str, pergunta: str):  # type: ignore[no-untyped-def]
        from dataclasses import replace

        from brain.access_policy import resolve_access
        from brain.models import REVIEW_STATUSES
        from brain.retrieval import search

        acesso = replace(resolve_access(agente), statuses=REVIEW_STATUSES)
        return search(agent_id=agente, query=pergunta, repository=repositorio, limit=4, access=acesso)

    def test_brigadeiro_e_encontrado(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        resultado = self._buscar(repositorio, "customer-support-agent", "o ebook de recheios tem brigadeiro?")
        assert any(h.provenance.external_key == "EBOOK_RECHEIOS" for h in resultado.hits)

    def test_diversidade_por_documento(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        """Um ebook nao pode ocupar o top-k inteiro e expulsar as outras fontes."""

        from brain.retrieval import MAX_PER_DOCUMENT

        resultado = self._buscar(repositorio, "customer-support-agent", "temperagem chocolate brilho")
        por_documento: dict[str, int] = {}
        for hit in resultado.hits:
            chave = hit.provenance.external_key or hit.provenance.document_id
            por_documento[chave] = por_documento.get(chave, 0) + 1
        # A segunda passada pode estourar o teto quando nao ha outra fonte; o
        # que nao pode e o teto nunca valer.
        assert min(por_documento.values()) <= MAX_PER_DOCUMENT

    def test_nunca_duas_vezes_a_mesma_receita(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        resultado = self._buscar(repositorio, "customer-support-agent", "ganache chocolate creme")
        receitas = [h.provenance.recipe_id for h in resultado.hits if h.provenance.recipe_id]
        assert len(receitas) == len(set(receitas))

    def test_venda_nao_recebe_corpo_pago(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        resultado = self._buscar(repositorio, "sales-conversion-agent", "ganache receita ingredientes")
        assert all(h.provenance.external_key != "EBOOK_RECHEIOS" for h in resultado.hits)

    def test_provenance_completa(self, repositorio) -> None:  # type: ignore[no-untyped-def]
        resultado = self._buscar(repositorio, "customer-support-agent", "temperagem")
        assert resultado.hits
        payload = resultado.hits[0].as_dict()
        for campo in ("fonte", "autoridade", "tipo_de_conteudo", "pagina", "camada", "status", "versao"):
            assert campo in payload, campo


# =============================================================================
# EVAL PRIMARY_KNOWLEDGE_V1
# =============================================================================


class TestEvalDeterministico:
    def test_casos_de_gate_passam_sem_banco(self) -> None:
        """Os casos de gate nao dependem de ingestao — rodam sempre, ate no CI."""

        from brain.eval_primary_knowledge import run_eval

        resultado = run_eval(None)
        assert resultado.failed == 0, resultado.summary()["falhas"]
        assert resultado.passed >= 7

    def test_dataset_cobre_as_falhas_criticas(self) -> None:
        from brain.eval_primary_knowledge import (
            FALHAS_CRITICAS,
            GATE_CASES,
            RETRIEVAL_CASES,
        )

        cobertas = {c.falha_coberta for c in RETRIEVAL_CASES} | {c.falha_coberta for c in GATE_CASES}
        assert cobertas <= set(FALHAS_CRITICAS)
        assert "FULL_RECIPE_LEAK" in cobertas
        assert "PAID_CONTENT_LEAK" in cobertas


@requires_pdfs
class TestEvalComRetrieval:
    def test_dataset_completo_passa(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from sqlalchemy import create_engine

        from brain.eval_primary_knowledge import run_eval
        from brain.ingestion import ingest_primary_sources
        from brain.repository import KnowledgeRepository

        engine = create_engine(f"sqlite:///{tmp_path / 'eval.sqlite'}")
        repositorio = KnowledgeRepository(engine)
        repositorio.ensure_tables()
        ingest_primary_sources(repositorio)

        resultado = run_eval(repositorio)
        assert resultado.failed == 0, resultado.summary()["falhas"]


# =============================================================================
# CONTEUDO PAGO NAO ENTRA EM PERSISTENCIA
# =============================================================================


class TestExecutionLogNaoGuardaConteudoPago:
    def test_outputs_nao_sao_persistidos(self) -> None:
        """`final_response` pode conter material pago. Ele nao pode ir ao banco.

        A F1 ja definiu `_row()` como allowlist; este teste trava essa
        propriedade contra o dia em que alguem adicionar `outputs` "porque
        seria util para debugar".
        """

        from orchestration.execution_repository import _OUTCOME_ALLOWLIST

        # `_row` le `log.outputs`, mas so pelas chaves desta allowlist. O que
        # importa nao e se `outputs` e tocado — e QUAIS chaves saem dele.
        for proibido in ("final_response", "outbound_message", "message", "raw_payload"):
            assert proibido not in _OUTCOME_ALLOWLIST, proibido

    def test_telemetria_do_gate_nao_carrega_texto(self) -> None:
        """`disclosure_reason` pode ser persistido porque so tem contagem."""

        from brain.disclosure_gate import evaluate

        veredito = evaluate("A ganache leva 100 g de chocolate branco, 50 g de creme, 20 g de leite em po, 10 g de sal, 5 g de glucose.")
        assert veredito.decision == "BLOCK"
        assert "chocolate branco" not in veredito.reason
        assert "100 g" not in veredito.reason

    def test_gate_esta_plugado_no_fluxo(self) -> None:
        import inspect as _inspect

        from orchestration.workflows import answer_dm

        fonte = _inspect.getsource(answer_dm._finalize)
        assert "_apply_disclosure_gate" in fonte

    def test_gate_nunca_derruba_a_resposta(self) -> None:
        """Instrumentacao de seguranca que quebra a resposta troca um problema por outro."""

        from orchestration.workflows.answer_dm import _apply_disclosure_gate

        assert _apply_disclosure_gate("oi, tudo bem?", agent_id="customer-support-agent") is None
        assert _apply_disclosure_gate("", agent_id="agente-que-nao-existe") is None
