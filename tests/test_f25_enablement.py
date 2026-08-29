"""
F2.5 — docs em producao, legacy congelado, L0 SYSTEM, review queue, shadow.

O teste que mais importa neste arquivo e o do congelamento: `docs/` passou a
existir dentro do container, e a unica coisa entre isso e 77 documentos novos
aparecendo para 20 agentes e o escopo do retriever lexical.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from agents.knowledge_scope import (
    LEGACY_BASELINE_KEYS,
    current_scope,
    is_legacy_visible,
    scope_report,
)
from brain.backfill import _catalogo, run_backfill
from brain.conflicts import outranks, precedence
from brain.models import DEFAULT_VERBATIM_LIMITS, LAYERS, decide_disclosure, verbatim_violation
from brain.repository import KnowledgeRepository
from brain.review import FIRST_QUEUE, build_review_packet, packet_summary
from brain.shadow import GOLDEN_SET, run_shadow, shadow_summary
from brain.taxonomy import layer_for, source_kind_for
from db.migrations import MIGRATIONS, run_migrations

RAILWAY_MARKERS = ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_NAME", "RAILWAY_PROJECT_ID")


@pytest.fixture
def dev(monkeypatch):
    for marcador in RAILWAY_MARKERS:
        monkeypatch.delenv(marcador, raising=False)
    monkeypatch.delenv("LEGACY_KNOWLEDGE_SCOPE", raising=False)


@pytest.fixture
def producao(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("LEGACY_KNOWLEDGE_SCOPE", raising=False)


@pytest.fixture(scope="module")
def store():
    """Store com os 79 documentos. Modulo inteiro reusa."""

    motor = create_engine("sqlite://")
    run_migrations(motor)
    repositorio = KnowledgeRepository(motor)
    relatorio = run_backfill(repositorio)
    yield repositorio, relatorio
    motor.dispose()


# --- A. docs em producao + freeze do legacy ---------------------------------


def test_docs_nao_esta_mais_no_dockerignore() -> None:
    """Sem isto o Brain nao tem o que backfillar em producao."""

    from pathlib import Path

    conteudo = Path(".dockerignore").read_text(encoding="utf-8")
    linhas = [linha.strip() for linha in conteudo.splitlines() if linha.strip() and not linha.startswith("#")]

    assert "docs" not in linhas, "docs voltou para o .dockerignore; o Brain fica cego em producao"


def test_producao_congela_o_legacy_por_padrao(producao) -> None:
    """Fail-closed: ampliar exige acao explicita, nunca acontece sozinho."""

    assert current_scope() == "frozen"


def test_desenvolvimento_continua_com_tudo(dev) -> None:
    assert current_scope() == "full"


def test_escopo_pode_ser_declarado_explicitamente(monkeypatch) -> None:
    monkeypatch.setenv("LEGACY_KNOWLEDGE_SCOPE", "full")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")

    assert current_scope() == "full"
    assert scope_report()["origem"] == "env"


def test_legacy_congelado_so_ve_o_baseline(producao) -> None:
    """O teste central da F2.5."""

    visiveis = [chave for chave in _catalogo() if is_legacy_visible(chave)]

    assert set(visiveis) == set(LEGACY_BASELINE_KEYS)
    assert len(visiveis) == 2


@pytest.mark.parametrize("chave", ["OFFERS", "PRODUCTS", "BRAND", "VOICE", "BUSINESS_RULES", "COMMENTS_FAQ"])
def test_documento_novo_nao_vaza_para_o_legacy_em_producao(producao, chave) -> None:
    assert not is_legacy_visible(chave)


def test_busca_legacy_congelada_nao_devolve_documento_novo(producao) -> None:
    from agents.knowledge_policies import get_policy
    from agents.knowledge_sources import search_documents

    politica = get_policy("customer-support-agent")
    resultado = search_documents(
        "quanto custa o ebook?",
        sources=politica.documents,
        missing=politica.missing_sources,
    )

    fontes = {str(d.get("fonte")) for d in resultado if d.get("fonte")}
    assert not (fontes & {"OFFERS", "PRODUCTS", "COMMENTS_FAQ"}), f"legacy ampliou: {fontes}"


def test_ler_documento_fora_do_escopo_nao_finge_que_leu(producao) -> None:
    """Recusa explicita convida menos a inventar do que silencio."""

    from agents.knowledge_policies import get_policy
    from agents.knowledge_sources import read_document

    politica = get_policy("customer-support-agent")
    resposta = read_document("OFFERS", politica.documents)

    assert resposta["status"] == "FORA_DO_ESCOPO_ATUAL"
    assert "conteudo" not in resposta


def test_catalogo_nao_anuncia_o_que_nao_pode_servir(producao) -> None:
    from agents.knowledge_policies import (
        build_knowledge_tools_for,  # noqa: F401
        get_policy,
    )
    from agents.knowledge_sources import build_source_catalog

    politica = get_policy("customer-support-agent")
    catalogo = build_source_catalog(politica.documents, politica.missing_sources)
    anunciadas = {d["fonte"] for d in catalogo["documentos_disponiveis"]}

    assert anunciadas <= set(LEGACY_BASELINE_KEYS)


def test_em_dev_o_legacy_continua_completo(dev) -> None:
    """Congelar producao nao pode quebrar o desenvolvimento."""

    from agents.knowledge_policies import get_policy
    from agents.knowledge_sources import search_documents

    politica = get_policy("customer-support-agent")
    resultado = search_documents(
        "quanto custa o ebook?",
        sources=politica.documents,
        missing=politica.missing_sources,
    )

    assert any(d.get("fonte") in ("OFFERS", "PRODUCTS") for d in resultado)


def test_brain_enxerga_tudo_mesmo_com_legacy_congelado(producao, store) -> None:
    """As duas decisoes sao separadas: o arquivo chegar, e o agente ver."""

    from brain.backfill import _catalogo

    _repo, relatorio = store

    # Contra o catalogo, nao contra um numero: a F2.7 adicionou
    # OFFER_STRATEGY_INTERNAL e o total mudou sem que nada estivesse errado.
    assert relatorio.total == len(_catalogo())
    assert not is_legacy_visible("OFFERS")


# --- B. L0 SYSTEM -----------------------------------------------------------


def test_l0_existe_no_vocabulario() -> None:
    assert "L0" in LAYERS
    assert source_kind_for("L0") == "system"


def test_l0_e_o_ultimo_na_precedencia() -> None:
    """O ponto todo da camada: nao competir com verdade comercial."""

    assert precedence("L3") < precedence("L1") < precedence("L2") < precedence("L0")
    assert outranks("L3", "L0")
    assert outranks("L1", "L0")
    assert outranks("L2", "L0")
    assert not outranks("L0", "L3")


@pytest.mark.parametrize(
    ("chave", "caminho", "esperado"),
    [
        ("FICHA_01_CMO", "JUDITH-AI-TEAM-V2/agents/01-cmo.md", "L0"),
        ("HANDOFF_CONTRACT", "JUDITH-AI-TEAM-V2/protocol/AGENT_HANDOFF_CONTRACT.md", "L0"),
        ("MEMORY_MODEL", "JUDITH-AI-TEAM-V2/models/MEMORY_MODEL.md", "L0"),
        ("PLAYBOOK_HOOK", "JUDITH-AI-TEAM/agents/HOOK_FINDER.md", "L0"),
        ("WORKFLOWS_V1", "JUDITH-AI-TEAM/workflows/ORCHESTRATOR.md", "L0"),
        ("AGENT_ROSTER", "JUDITH-AI-TEAM-V2/AGENT_ROSTER.md", "L0"),
    ],
)
def test_documentacao_interna_virou_l0(chave, caminho, esperado) -> None:
    assert layer_for(key=chave, relative_path=caminho) == esperado


@pytest.mark.parametrize(
    ("chave", "caminho", "esperado"),
    [
        # Preco, produto e politica NUNCA sao SYSTEM.
        ("OFFERS", "JUDITH-AI-TEAM/brand/OFFERS.md", "L3"),
        ("PRODUCTS", "JUDITH-AI-TEAM/brand/PRODUCTS.md", "L3"),
        ("BUSINESS_RULES", "JUDITH-AI-TEAM-V2/BUSINESS_RULES.md", "L3"),
        ("VOICE", "JUDITH-AI-TEAM/brand/VOICE.md", "L3"),
        ("COMMENTS_FAQ", "JUDITH-AI-TEAM/sources/COMMENTS_FAQ.md", "L3"),
        # Tecnica da Judith continua L1.
        ("RECEITA", "JUDITH-AI-TEAM-V2/knowledge/judith/recipes/x.md", "L1"),
        # Oficio generico continua L2.
        ("CRAFT_COPY", "JUDITH-AI-TEAM-V2/knowledge/craft/COPY_CRAFT.md", "L2"),
    ],
)
def test_o_que_nao_pode_virar_system(chave, caminho, esperado) -> None:
    assert layer_for(key=chave, relative_path=caminho) == esperado


def test_migration_003_e_reversivel_e_registra_o_que_fez() -> None:
    from db.migrations.m003_system_layer import RECLASSIFIED_TO_L0

    migration = next(m for m in MIGRATIONS if m.version == 3)

    assert migration.reversible
    assert len(RECLASSIFIED_TO_L0) == 55
    assert "OFFERS" not in RECLASSIFIED_TO_L0
    assert "BUSINESS_RULES" not in RECLASSIFIED_TO_L0
    assert "FICHA_01_CMO" in RECLASSIFIED_TO_L0


def test_distribuicao_final_por_camada(store) -> None:
    from brain.backfill import _catalogo

    _repo, relatorio = store
    camadas = relatorio.by_layer()

    # L0 e L2 estao congelados desde a F2.5; L3 cresce quando um documento de
    # negocio novo entra. E por isso que so os dois primeiros sao numeros.
    assert camadas["L0"] == 55
    assert camadas["L2"] == 11
    assert camadas["L3"] >= 13
    assert sum(camadas.values()) == len(_catalogo())


def test_reconciliacao_corrige_camada_sem_criar_versao(store) -> None:
    """Sem isto, mudanca de taxonomia nunca chegaria ao banco.

    O checksum do arquivo nao muda quando a classificacao muda, entao o
    backfill pularia o documento e a camada velha ficaria para sempre.
    """

    repo, _ = store
    documento = repo.get_document_by_external_key("FICHA_01_CMO")
    versoes_antes = len(repo.get_versions(documento["document_id"]))

    repo.reconcile_metadata(
        document_id=documento["document_id"],
        layer="L2",  # finge que estava errado
        topics=("sistema",),
        content_access="INTERNAL_ONLY",
        source_ref=documento["source_ref"],
        title=documento["title"],
    )
    assert repo.get_document_by_external_key("FICHA_01_CMO")["layer"] == "L2"

    alteracoes = run_backfill(repo).mapped
    corrigido = next(item for item in alteracoes if item.external_key == "FICHA_01_CMO")

    assert corrigido.layer == "L0"
    assert corrigido.reconciled, "a correcao aconteceu em silencio"
    assert len(repo.get_versions(documento["document_id"])) == versoes_antes


def test_source_ref_aponta_para_o_arquivo(store) -> None:
    repo, _ = store

    assert repo.get_document_by_external_key("OFFERS")["source_ref"] == "JUDITH-AI-TEAM/brand/OFFERS.md"


# --- C. Disclosure Policy V2 ------------------------------------------------


def test_public_revela_normalmente() -> None:
    policy = decide_disclosure(content_access="PUBLIC", agent_is_customer_facing=True, agent_can_know_paid=False)

    assert policy.can_reveal_full_method is True
    assert policy.can_reveal_full_recipe is True
    assert policy.max_verbatim_chars is None


def test_receita_completa_bloqueada_sem_entitlement() -> None:
    policy = decide_disclosure(
        content_access="ENTITLEMENT_REQUIRED", agent_is_customer_facing=True, agent_can_know_paid=True
    )

    assert policy.can_reveal_full_recipe is False


def test_metodo_completo_bloqueado_sem_entitlement() -> None:
    policy = decide_disclosure(
        content_access="ENTITLEMENT_REQUIRED", agent_is_customer_facing=True, agent_can_know_paid=True
    )

    assert policy.can_reveal_full_method is False
    assert policy.requires_entitlement is True


def test_entitlement_verificado_libera_tudo() -> None:
    """O caminho existe pronto. Nenhum chamador passa True hoje."""

    policy = decide_disclosure(
        content_access="ENTITLEMENT_REQUIRED",
        agent_is_customer_facing=True,
        agent_can_know_paid=True,
        entitlement_verified=True,
    )

    assert policy.can_reveal_full_recipe is True
    assert policy.max_verbatim_chars is None


def test_conteudo_pago_conhecivel_mas_com_citacao_curta() -> None:
    """O default conservador: da para atender bem sem entregar o produto."""

    policy = decide_disclosure(
        content_access="ENTITLEMENT_REQUIRED", agent_is_customer_facing=True, agent_can_know_paid=True
    )

    assert policy.can_know is True
    assert policy.can_summarize is True
    assert policy.can_quote is True
    assert policy.max_verbatim_chars == DEFAULT_VERBATIM_LIMITS["ENTITLEMENT_REQUIRED"]


def test_teto_de_citacao_e_configuravel() -> None:
    policy = decide_disclosure(
        content_access="SUPPORT_USE",
        agent_is_customer_facing=True,
        agent_can_know_paid=False,
        max_verbatim_chars=80,
    )

    assert policy.max_verbatim_chars == 80


def test_verbatim_violation_respeita_o_teto() -> None:
    policy = decide_disclosure(
        content_access="ENTITLEMENT_REQUIRED", agent_is_customer_facing=True, agent_can_know_paid=True
    )
    limite = DEFAULT_VERBATIM_LIMITS["ENTITLEMENT_REQUIRED"]

    assert verbatim_violation("x" * (limite + 1), policy) is True
    assert verbatim_violation("x" * limite, policy) is False


def test_quem_nao_pode_citar_nao_cita_nada() -> None:
    policy = decide_disclosure(content_access="INTERNAL_ONLY", agent_is_customer_facing=True, agent_can_know_paid=True)

    assert verbatim_violation("qualquer coisa", policy) is True
    assert verbatim_violation("   ", policy) is False


def test_policy_viaja_no_resultado_da_busca(store) -> None:
    repo, _ = store
    from dataclasses import replace

    from brain.access_policy import resolve_access
    from brain.retrieval import search

    acesso = replace(resolve_access("customer-support-agent"), statuses=frozenset({"TO_VALIDATE", "DRAFT"}))
    resultado = search(agent_id="customer-support-agent", query="preco do ebook", repository=repo, access=acesso)

    assert resultado.hits
    divulgacao = resultado.hits[0].as_dict()["divulgacao"]
    for campo in (
        "pode_consultar",
        "pode_sintetizar",
        "pode_citar",
        "maximo_de_citacao_literal",
        "pode_entregar_metodo_completo",
        "pode_entregar_receita_completa",
        "exige_compra_verificada",
    ):
        assert campo in divulgacao


# --- D. Review queue --------------------------------------------------------


def test_review_packet_cobre_os_seis(store) -> None:
    repo, _ = store

    itens = build_review_packet(repo)

    assert [item.key for item in itens] == list(FIRST_QUEUE)


def test_review_packet_nao_altera_status(store) -> None:
    """A recomendacao e leitura, nunca acao."""

    repo, _ = store
    antes = {chave: repo.get_document_by_external_key(chave)["status"] for chave in FIRST_QUEUE}

    itens = build_review_packet(repo)
    depois = {chave: repo.get_document_by_external_key(chave)["status"] for chave in FIRST_QUEUE}

    assert antes == depois
    assert packet_summary(itens)["status_alterados"] == 0
    assert repo.status_report().get("CONFIRMED", 0) == 0


def test_review_packet_lista_o_que_exige_a_judith(store) -> None:
    repo, _ = store
    itens = {item.key: item for item in build_review_packet(repo)}

    # A F2.7 resolveu documentalmente o "A VERIFICAR" da colecao completa, e
    # OFFERS deixou de ter pendencia marcada dentro do texto. O packet
    # continua tendo que apontar pendencia onde ela existe — hoje, nos
    # documentos que ainda se declaram template.
    pendentes = [chave for chave, item in itens.items() if item.needs_judith]
    assert pendentes, "o packet parou de detectar qualquer pendencia — provavelmente quebrou"
    assert all("linha" in ponto for chave in pendentes for ponto in itens[chave].needs_judith)


def test_template_nunca_e_recomendado_para_aprovacao(store) -> None:
    repo, _ = store
    itens = {item.key: item for item in build_review_packet(repo)}

    assert itens["VOICE"].recommendation == "KEEP_DRAFT"
    assert itens["VOICE"].reliability == "template"


def test_recomendacao_traz_o_porque(store) -> None:
    repo, _ = store

    for item in build_review_packet(repo):
        assert item.rationale, f"{item.key} recomendado sem justificativa"
        assert item.recommendation in ("APPROVE", "EDIT", "KEEP_TO_VALIDATE", "KEEP_DRAFT")


def test_packet_aponta_onde_o_mesmo_valor_aparece(store) -> None:
    repo, _ = store
    itens = {item.key: item for item in build_review_packet(repo)}

    # Ate a F2.7 PRODUCTS e OFFERS carregavam os mesmos precos, e o packet
    # apontava a duplicacao. A canonicalizacao removeu preco de PRODUCTS: um
    # dado volatil passou a ter um dono so. Entao a ausencia deste conflito e
    # agora o resultado CORRETO, e e isso que este teste trava.
    assert "PRODUCTS" not in itens["OFFERS"].conflicts
    assert "OFFERS" not in itens["PRODUCTS"].conflicts


# --- E. Shadow comparison ---------------------------------------------------


def test_golden_set_cobre_as_categorias_pedidas() -> None:
    categorias = {caso.categoria for caso in GOLDEN_SET}

    assert {"produtos", "ofertas", "politicas", "voz", "branding", "chocolate", "faq", "interno"} <= categorias


def test_shadow_roda_os_dois_caminhos(store, dev) -> None:
    repo, _ = store

    resultados = run_shadow(repo, mode="review")

    assert len(resultados) == len(GOLDEN_SET)
    assert any(r.legacy for r in resultados), "o legacy nao devolveu nada"
    assert any(r.brain for r in resultados), "o Brain nao devolveu nada"


def test_shadow_mede_recall_dos_dois(store, dev) -> None:
    repo, _ = store

    resumo = shadow_summary(run_shadow(repo, mode="review"))

    assert resumo["recall_legacy"] is not None
    assert resumo["recall_brain"] is not None
    assert resumo["provenance_completo_em_todos"] is True


def test_shadow_em_producao_mostra_a_fila_parada(store, dev) -> None:
    """Zero CONFIRMED => Brain vazio. Nao e bug, e a fila nao ter andado."""

    repo, _ = store

    resultados = run_shadow(repo, mode="production")
    negocio = [r for r in resultados if r.agent_id != "knowledge-manager"]

    assert all(r.brain_vazio for r in negocio), "documento nao aprovado saiu em modo producao"


def test_shadow_preserva_o_comportamento_de_lacuna(store, dev) -> None:
    """MissingSource continua declarando o que nao existe."""

    repo, _ = store
    resultados = run_shadow(repo, mode="review")
    lacunas = [r for r in resultados if not r.esperado]

    assert lacunas
    assert any(r.legacy_lacuna for r in lacunas)


def test_shadow_nao_altera_nada(store, dev) -> None:
    repo, _ = store
    antes = repo.counts()

    run_shadow(repo, mode="review")

    assert repo.counts() == antes


# --- F. Nenhum agente foi plugado no Brain ----------------------------------


#: Os UNICOS pontos onde codigo de agente/orquestracao pode tocar o Brain, e
#: por qual porta.
#:
#: `answer_dm` usa o Disclosure Gate: nao e retrieval, nao busca, nao muda o
#: que o agente sabe — so inspeciona o texto ja escrito antes de sair.
#:
#: `knowledge_policies` usa `brain.cutover`: e o mecanismo de troca de caminho
#: da F2.8, e existe num LUGAR SO de proposito. Se um segundo modulo aparecer
#: aqui, o cutover deixou de ter um ponto unico de reversao.
#: `brain.query_context` entrou com o J2. Ele NAO e retrieval: nao busca, nao
#: devolve conhecimento, nao consulta o banco. Guarda a ultima mensagem da
#: cliente e costura contexto numa query eliptica. O workflow e o unico lugar
#: que conhece a sessao, entao e o unico que pode marca-la.
#: `brain.retrieval_trace` entrou com a F3. Ele tambem NAO e retrieval: nao
#: busca, nao consulta o banco, nao devolve conhecimento e nao carrega corpo.
#: E um buffer de diagnostico — modo, contagem de candidatos, latencia — que o
#: workflow abre antes do run e le depois. Se ele sumir, a resposta, o
#: `sources_opened` e o Evidence Gate ficam identicos; o que se perde e a
#: capacidade de explicar depois por que um trecho apareceu.
_IMPORTS_DE_BRAIN_PERMITIDOS: dict[str, tuple[str, ...]] = {
    "orchestration/workflows/answer_dm.py": (
        "brain.disclosure_gate",
        "brain.access_policy",
        "brain.query_context",
        "brain.retrieval_trace",
    ),
    "agents/knowledge_policies.py": ("brain.cutover",),
    # `step_helpers` le de `brain.cutover` apenas os NOMES das tools de
    # consulta — o contrato com o Evidence Gate. Nao chama o interruptor, nao
    # monta tool, nao busca. Copiar esses nomes em vez de importa-los foi o
    # bug que bloqueou a resposta de preco em producao.
    "orchestration/step_helpers.py": ("brain.cutover",),
}

#: Quem pode acionar a TROCA de caminho. Importar o contrato de nomes nao e a
#: mesma coisa que ligar/desligar o cutover — e o segundo que precisa ter um
#: lugar so.
_MODULOS_QUE_ACIONAM_O_CUTOVER = ("agents/knowledge_policies.py",)


def test_brain_e_alcancado_por_uma_porta_so() -> None:
    """Nenhum agente monta retrieval por conta propria.

    Ate a F2.7 nenhum modulo de agente podia importar Brain. A F2.8 abriu UMA
    porta — `brain.cutover`, em `knowledge_policies` — e este teste passou a
    guardar essa porta em vez de proibir a casa inteira.

    Importar `brain.retrieval`, `brain.repository`, `brain.backfill` ou
    `brain.ingestion` direto continua proibido em qualquer lugar: seria
    cutover sem o interruptor que o reverte.
    """

    import re
    from pathlib import Path

    proibidos = ("brain.retrieval", "brain.repository", "brain.backfill", "brain.ingestion")
    ofensores: list[str] = []

    for arquivo in list(Path("agents").rglob("*.py")) + list(Path("orchestration").rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        modulos = set(re.findall(r"(?:from|import)\s+(brain(?:\.[\w.]+)?)", texto))
        if not modulos:
            continue
        chave = arquivo.as_posix()
        permitidos = set(_IMPORTS_DE_BRAIN_PERMITIDOS.get(chave, ()))
        nao_autorizados = modulos - permitidos
        if nao_autorizados or any(p in modulos for p in proibidos):
            ofensores.append(f"{chave}: {sorted(nao_autorizados or modulos)}")

    assert ofensores == [], f"dependencia nao autorizada do Brain: {ofensores}"


def test_cutover_tem_um_interruptor_so() -> None:
    """Reverter precisa ser apagar um nome, nao caçar imports."""

    import re
    from pathlib import Path

    from brain.cutover import ENV_VAR, brain_native_agents

    assert ENV_VAR == "BRAIN_NATIVE_AGENTS"

    # O que precisa ter UM lugar so e quem ACIONA a troca de caminho. Ler o
    # contrato de nomes de tool nao aciona nada.
    acionadores = ("is_brain_native", "build_brain_tools_for", "build_brain_retriever_for")
    encontrados = []
    for arquivo in list(Path("agents").rglob("*.py")) + list(Path("orchestration").rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        if any(re.search(rf"\b{a}\b", texto) for a in acionadores):
            encontrados.append(arquivo.as_posix())

    assert sorted(encontrados) == sorted(_MODULOS_QUE_ACIONAM_O_CUTOVER), (
        f"o cutover deixou de ter um interruptor so: {encontrados}"
    )

    # Sem a variavel declarada, ninguem e nativo — o default nunca promove.
    import os

    anterior = os.environ.pop(ENV_VAR, None)
    try:
        assert brain_native_agents() == frozenset()
    finally:
        if anterior is not None:
            os.environ[ENV_VAR] = anterior


def test_retriever_de_producao_continua_o_lexical(dev) -> None:
    from agents.knowledge_policies import build_retriever_for

    resultado = build_retriever_for("customer-support-agent")("qual o preco do ebook?")

    assert resultado
    assert all(isinstance(d, dict) for d in resultado)
