"""
Judith Brain F2 — schema, migrations, versionamento e backfill.

Roda sobre SQLite em memoria, como a F1: SQL de verdade, sem Postgres no CI.

`tests/test_brain_access.py` cobre a politica de acesso e o conteudo pago.
`tests/test_brain_security.py` cobre segredo, injecao e imutabilidade.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

from brain.backfill import (
    BackfillReport,
    confidence_for,
    run_backfill,
    status_for,
    verify_originals,
)
from brain.chunking import MAX_CHUNK_CHARS, chunk_markdown
from brain.models import ALLOWED_TRANSITIONS, DOC_STATUSES, transition_allowed
from brain.repository import KnowledgeRepository, checksum_of
from brain.taxonomy import content_access_for, layer_for, topics_for
from db.migrations import MIGRATIONS, applied_versions, pending_migrations, rollback, run_migrations


@pytest.fixture
def engine():
    motor = create_engine("sqlite://")
    yield motor
    motor.dispose()


@pytest.fixture
def repo(engine):
    repositorio = KnowledgeRepository(engine)
    repositorio.ensure_tables()
    return repositorio


@pytest.fixture
def repo_migrado(engine):
    run_migrations(engine)
    return KnowledgeRepository(engine)


# --- 1. Migrations ----------------------------------------------------------


def test_migrations_criam_todas_as_tabelas(engine) -> None:
    run_migrations(engine)
    tabelas = set(inspect(engine).get_table_names())

    esperadas = {
        "judith_schema_migrations",
        "judith_execution_logs",
        "judith_knowledge_sources",
        "judith_knowledge_documents",
        "judith_knowledge_versions",
        "judith_knowledge_chunks",
        "judith_knowledge_conflicts",
    }
    assert esperadas <= tabelas, f"faltando: {esperadas - tabelas}"


def test_migrations_sao_idempotentes(engine) -> None:
    """Roda todo boot. Segunda execucao nao pode aplicar nada de novo."""

    from db.migrations.runner import MIGRATIONS

    primeira = run_migrations(engine)
    segunda = run_migrations(engine)

    # Contra o registro, nao contra um numero escrito a mao: cada migration
    # nova quebrava este teste sem que nada estivesse errado.
    assert primeira == [m.version for m in MIGRATIONS]
    assert segunda == []
    assert pending_migrations(engine) == []


def test_historico_registra_versao_nome_e_checksum(engine) -> None:
    run_migrations(engine)

    from db.migrations.runner import MIGRATIONS

    aplicadas = applied_versions(engine)

    assert set(aplicadas) == {m.version for m in MIGRATIONS}
    assert all(len(checksum) == 16 for checksum in aplicadas.values())


def test_versoes_de_migration_sao_unicas_e_ordenadas() -> None:
    versoes = [m.version for m in MIGRATIONS]

    assert versoes == sorted(set(versoes))


def test_migration_do_execution_log_nao_e_reversivel() -> None:
    """Dado de auditoria de producao nao ganha um DROP automatico."""

    execution_log = next(m for m in MIGRATIONS if m.version == 1)

    assert not execution_log.reversible


def test_rollback_recusa_migration_irreversivel(engine) -> None:
    run_migrations(engine)

    with pytest.raises(ValueError, match="nao e reversivel"):
        rollback(engine, 1)


def test_rollback_da_knowledge_funciona_e_pode_reaplicar(engine) -> None:
    """A 002 e reversivel porque o conteudo dela e derivado de docs/."""

    run_migrations(engine)
    rollback(engine, 2)

    assert "judith_knowledge_documents" not in set(inspect(engine).get_table_names())
    # ...e o execution log continua de pe.
    assert "judith_execution_logs" in set(inspect(engine).get_table_names())

    assert run_migrations(engine) == [2]


def test_migration_adota_execution_log_existente_sem_apagar(engine) -> None:
    """Producao ja tem a tabela com dado. A migration nao pode recria-la."""

    from orchestration.execution_log import ExecutionLog
    from orchestration.execution_repository import ExecutionRepository

    antigo = ExecutionRepository(engine)
    antigo.ensure_table()
    log = ExecutionLog(task_id="anterior-a-migration", workflow="ANSWER_DM")
    log.finish(status="completed")
    antigo.save(log)

    run_migrations(engine)

    assert antigo.get("anterior-a-migration") is not None, "migration destruiu dado existente"
    assert applied_versions(engine)[1]


# --- 2. Versionamento e imutabilidade ---------------------------------------


def _documento(repo: KnowledgeRepository, *, corpo: str = "# Doc\n\n## A\n\ntexto") -> str:
    repo.upsert_source(
        source_id="src_teste",
        kind="business",
        origin="manual",
        owner="judith",
        title="Fonte de teste",
    )
    return repo.create_document(
        source_id="src_teste",
        title="Documento de teste",
        layer="L3",
        status="TO_VALIDATE",
        content_access="INTERNAL_ONLY",
        checksum=checksum_of(corpo),
        external_key="TESTE",
        topics=("comercial",),
    )


def test_nova_versao_incrementa_e_preserva_a_anterior(repo) -> None:
    doc = _documento(repo)
    repo.add_version(document_id=doc, body="corpo v1", created_by="teste")
    repo.add_version(document_id=doc, body="corpo v2", created_by="teste", change_reason="correcao")

    versoes = repo.get_versions(doc)

    assert [v["version"] for v in versoes] == [1, 2]
    assert versoes[0]["body"] == "corpo v1", "a versao anterior foi reescrita"
    assert repo.get_current_version(doc)["version"] == 2


def test_version_e_unica_por_documento(repo) -> None:
    from datetime import UTC, datetime

    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError

    doc = _documento(repo)
    repo.add_version(document_id=doc, body="corpo", created_by="teste")

    with pytest.raises(IntegrityError), repo.engine.begin() as conexao:
        conexao.execute(
            insert(repo.versions).values(
                version_id="duplicada",
                document_id=doc,
                version=1,
                body="outra coisa",
                checksum="x",
                created_by="teste",
                created_at=datetime.now(UTC),
            )
        )


def test_checksum_acompanha_o_conteudo(repo) -> None:
    doc = _documento(repo)
    repo.add_version(document_id=doc, body="conteudo exato", created_by="teste")

    versao = repo.get_current_version(doc)

    assert versao["checksum"] == checksum_of("conteudo exato")
    assert repo.get_document(doc)["checksum"] == versao["checksum"]


# --- 3. Ciclo de status -----------------------------------------------------


def test_deprecated_e_terminal() -> None:
    assert ALLOWED_TRANSITIONS["DEPRECATED"] == frozenset()
    for status in DOC_STATUSES:
        assert not transition_allowed("DEPRECATED", status)


def test_transicao_proibida_levanta(repo) -> None:
    doc = _documento(repo)
    repo.set_status(document_id=doc, novo="DEPRECATED")

    with pytest.raises(ValueError, match="transicao de status proibida"):
        repo.set_status(document_id=doc, novo="DRAFT")  # DEPRECATED e terminal


def test_confirmed_so_por_aprovacao_humana(repo) -> None:
    """Regressao: `set_status` era uma porta lateral para CONFIRMED.

    A tabela de transicoes permite TO_VALIDATE -> CONFIRMED (e a transicao
    legitima), entao so a checagem explicita impede a promocao sem aprovacao.
    """

    doc = _documento(repo)

    with pytest.raises(ValueError, match="approve_version"):
        repo.set_status(document_id=doc, novo="CONFIRMED")

    assert repo.get_document(doc)["status"] == "TO_VALIDATE"


def test_aprovacao_exige_nome_humano(repo) -> None:
    doc = _documento(repo)
    repo.add_version(document_id=doc, body="corpo", created_by="teste")

    with pytest.raises(ValueError, match="aprovacao anonima"):
        repo.approve_version(document_id=doc, version=1, approved_by="   ")


def test_aprovacao_registra_quem_e_quando(repo) -> None:
    doc = _documento(repo)
    repo.add_version(document_id=doc, body="corpo", created_by="teste")

    repo.approve_version(document_id=doc, version=1, approved_by="Judith Kolker")

    versao = repo.get_current_version(doc)
    assert versao["approved_by"] == "Judith Kolker"
    assert versao["approved_at"] is not None
    assert repo.get_document(doc)["status"] == "CONFIRMED"


def test_deprecated_nao_apaga_o_documento(repo) -> None:
    doc = _documento(repo)
    repo.add_version(document_id=doc, body="corpo", created_by="teste")
    repo.set_status(document_id=doc, novo="DEPRECATED", deprecated_by="doc_sucessor")

    linha = repo.get_document(doc)

    assert linha is not None, "documento DEPRECATED sumiu do banco"
    assert linha["status"] == "DEPRECATED"
    assert linha["deprecated_by"] == "doc_sucessor"
    assert linha["valid_to"] is not None
    assert repo.get_versions(doc), "as versoes de um documento DEPRECATED foram apagadas"


def test_status_do_documento_propaga_para_os_chunks(repo) -> None:
    doc = _documento(repo)
    repo.add_version(document_id=doc, body="# t\n\n## A\n\ncorpo suficiente para virar chunk", created_by="teste")
    repo.set_status(document_id=doc, novo="DEPRECATED")

    versao = repo.get_current_version(doc)
    assert all(c["status"] == "DEPRECATED" for c in repo.get_chunks(versao["version_id"]))


# --- 4. Validation: reliability nunca vira aprovacao ------------------------


@pytest.mark.parametrize("reliability", ["vigente", "snapshot", "template"])
def test_reliability_nunca_promove_para_confirmed(reliability) -> None:
    """A regra absoluta da F2, num assert."""

    assert status_for(reliability=reliability, caveat="") != "CONFIRMED"


def test_template_vira_draft_e_vigente_vira_to_validate() -> None:
    assert status_for(reliability="template", caveat="") == "DRAFT"
    assert status_for(reliability="vigente", caveat="") == "TO_VALIDATE"
    assert status_for(reliability="snapshot", caveat="") == "TO_VALIDATE"


def test_caveat_de_pendencia_rebaixa_para_draft() -> None:
    caveat = "A secao de produtos futuros esta marcada como 'a ser preenchida com Judith'."

    assert status_for(reliability="vigente", caveat=caveat) == "DRAFT"


def test_confidence_e_sobre_a_fonte_nao_sobre_aprovacao() -> None:
    assert confidence_for("vigente") == "alto"
    assert confidence_for("template") == "baixo"


# --- 5. Backfill ------------------------------------------------------------


@pytest.fixture(scope="module")
def backfill_feito():
    """Backfill real do catalogo. Modulo inteiro reusa — le 79 arquivos."""

    motor = create_engine("sqlite://")
    repositorio = KnowledgeRepository(motor)
    repositorio.ensure_tables()
    relatorio = run_backfill(repositorio)
    yield repositorio, relatorio
    motor.dispose()


def test_todo_o_catalogo_foi_representado(backfill_feito) -> None:
    from agents.knowledge_policies import DOCUMENTS
    from agents.knowledge_sources import BRAND_ARCHITECT_DOCUMENTS, CMO_DOCUMENTS

    _repo, relatorio = backfill_feito
    esperadas = {d.key for d in list(DOCUMENTS.values()) + list(CMO_DOCUMENTS) + list(BRAND_ARCHITECT_DOCUMENTS)}
    migradas = {item.external_key for item in relatorio.mapped}

    assert esperadas - migradas == set(), f"documentos perdidos no backfill: {esperadas - migradas}"


def test_os_28_do_briefing_estao_entre_os_migrados(backfill_feito) -> None:
    """O briefing falava em 28 (CMO 17 + Brand Architect 11). Sao subconjunto."""

    from agents.knowledge_sources import BRAND_ARCHITECT_DOCUMENTS, CMO_DOCUMENTS

    _repo, relatorio = backfill_feito
    os_28 = {d.key for d in list(CMO_DOCUMENTS) + list(BRAND_ARCHITECT_DOCUMENTS)}
    migradas = {item.external_key for item in relatorio.mapped}

    assert os_28 <= migradas


def test_nenhuma_aprovacao_foi_inventada(backfill_feito) -> None:
    """O teste que mais importa nesta fase."""

    repo, relatorio = backfill_feito

    assert relatorio.by_status().get("CONFIRMED", 0) == 0
    assert repo.status_report().get("CONFIRMED", 0) == 0
    assert all(v["approved_by"] is None for doc in repo.list_documents() for v in repo.get_versions(doc["document_id"]))


def test_backfill_nao_bloqueou_nem_perdeu_documento(backfill_feito) -> None:
    _repo, relatorio = backfill_feito

    assert relatorio.blocked == []
    assert relatorio.missing_on_disk == []


def test_mapa_liga_fonte_documento_versao_e_chunks(backfill_feito) -> None:
    repo, relatorio = backfill_feito
    offers = next(item for item in relatorio.mapped if item.external_key == "OFFERS")

    assert offers.source_id
    assert repo.get_document(offers.document_id)["external_key"] == "OFFERS"
    assert offers.version == 1
    assert offers.chunks > 0
    assert len(repo.get_chunks(offers.version_id)) == offers.chunks


def test_backfill_e_idempotente(backfill_feito) -> None:
    """Deploy sem mudanca em docs/ nao cria versao nova."""

    repo, _ = backfill_feito
    antes = repo.counts()

    segundo = run_backfill(repo)

    assert repo.counts() == antes
    assert len(segundo.skipped_unchanged) == segundo.total


def test_conteudo_original_e_preservado_byte_a_byte(backfill_feito) -> None:
    repo, _ = backfill_feito

    assert verify_originals(repo) == [], "algum documento foi alterado no caminho"


def test_camadas_seguem_a_taxonomia(backfill_feito) -> None:
    _repo, relatorio = backfill_feito
    por_chave = {item.external_key: item for item in relatorio.mapped}

    assert por_chave["OFFERS"].layer == "L3"
    assert por_chave["BUSINESS_RULES"].layer == "L3"
    assert por_chave["CRAFT_COPY"].layer == "L2"
    # F2.5: ficha de agente virou L0 SYSTEM, nao L2.
    assert por_chave["FICHA_01_CMO"].layer == "L0"


def test_relatorio_por_status_nao_esconde_nada(backfill_feito) -> None:
    _repo, relatorio = backfill_feito
    resumo = relatorio.summary()

    assert sum(resumo["por_status"].values()) == resumo["documentos"]
    assert resumo["confirmados_automaticamente"] == 0


def test_missing_source_continua_funcionando() -> None:
    """A F2 nao pode ter quebrado o FONTE_NAO_DISPONIVEL."""

    from agents.knowledge_policies import get_policy
    from agents.knowledge_sources import search_documents

    politica = get_policy("cmo")
    resultado = search_documents(
        "qual o kpi de engajamento atual?",
        sources=politica.documents,
        missing=politica.missing_sources,
    )

    assert any(doc.get("status") == "FONTE_NAO_DISPONIVEL" for doc in resultado)


# --- 6. Taxonomia -----------------------------------------------------------


def test_taxonomia_e_deterministica() -> None:
    for _ in range(3):
        assert layer_for(key="OFFERS", relative_path="JUDITH-AI-TEAM/brand/OFFERS.md") == "L3"
        assert layer_for(key="CRAFT_COPY", relative_path="JUDITH-AI-TEAM-V2/knowledge/craft/COPY_CRAFT.md") == "L2"


def test_material_da_judith_nasce_como_pago() -> None:
    """Ebook ingerido no futuro ja entra ENTITLEMENT_REQUIRED por padrao."""

    acesso = content_access_for(key="RECEITA_X", relative_path="JUDITH-AI-TEAM-V2/knowledge/judith/recipes/x.md")

    assert acesso == "ENTITLEMENT_REQUIRED"
    assert layer_for(key="RECEITA_X", relative_path="JUDITH-AI-TEAM-V2/knowledge/judith/recipes/x.md") == "L1"


def test_offers_e_marcado_como_comercial() -> None:
    """E o topic `comercial` que liga a deteccao de conflito de preco."""

    assert "comercial" in topics_for(key="OFFERS", relative_path="JUDITH-AI-TEAM/brand/OFFERS.md")


# --- 7. Chunking ------------------------------------------------------------


def test_chunking_corta_em_secao_nao_em_caracteres() -> None:
    markdown = "# T\n\n## Primeira\n\ncorpo um\n\n## Segunda\n\ncorpo dois"

    chunks = chunk_markdown(markdown)

    assert [c.heading for c in chunks] == ["(inicio do documento)", "Primeira", "Segunda"]


def test_chunking_desce_para_subsecao_quando_a_secao_e_grande() -> None:
    grande = "x" * 2000
    markdown = f"## Secao\n\n### A\n\n{grande}\n\n### B\n\n{grande}"

    chunks = chunk_markdown(markdown)

    assert any("Secao > A" == c.heading for c in chunks)
    assert any("Secao > B" == c.heading for c in chunks)


def test_chunking_nao_divide_bloco_de_codigo() -> None:
    codigo = "```python\n" + "\n".join(f"linha_{i} = {i}" for i in range(40)) + "\n```"
    chunks = chunk_markdown(f"## Codigo\n\n{codigo}")

    corpos = [c.body for c in chunks]
    assert sum(corpo.count("```") for corpo in corpos) == 2
    assert any("```python" in corpo and corpo.rstrip().endswith("```") for corpo in corpos)


def test_paragrafo_gigante_fica_inteiro_e_marcado() -> None:
    """Preferimos chunk grande a chunk mutilado."""

    paragrafo = "palavra " * 900
    chunks = chunk_markdown(f"## S\n\n{paragrafo}")

    assert len(chunks) == 1
    assert chunks[0].oversized
    assert len(chunks[0].body) > MAX_CHUNK_CHARS


def test_ordinais_sao_densos_e_crescentes(backfill_feito) -> None:
    repo, relatorio = backfill_feito
    item = next(i for i in relatorio.mapped if i.chunks > 2)

    ordinais = [c["ordinal"] for c in repo.get_chunks(item.version_id)]

    assert ordinais == list(range(1, len(ordinais) + 1))


def test_chunk_guarda_heading_e_checksum(backfill_feito) -> None:
    repo, relatorio = backfill_feito
    item = next(i for i in relatorio.mapped if i.external_key == "BUSINESS_RULES")

    for chunk in repo.get_chunks(item.version_id):
        assert chunk["heading"]
        assert chunk["checksum"] == checksum_of(chunk["body"])


def test_relatorio_de_backfill_e_serializavel() -> None:
    relatorio = BackfillReport()

    assert relatorio.summary()["documentos"] == 0
