"""Fixtures compartilhadas da suite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from orchestration.execution_repository import ExecutionRepository, set_execution_repository


@pytest.fixture(autouse=True)
def execution_repository_em_memoria():
    """Aponta a persistencia de execucao para SQLite em memoria.

    Desde a F1 os workflows chamam `persist_execution()` no fim. Sem esta
    fixture, cada teste de workflow tentaria abrir conexao com o Postgres de
    producao — que nao existe no CI. O erro seria engolido por design
    (`persist_execution` nunca levanta), mas a suite pagaria o timeout de
    conexao a cada teste e nao provaria nada sobre a gravacao.

    Com um banco de verdade em memoria, o caminho de escrita e exercitado
    junto com o workflow, e cada teste comeca com a tabela vazia.
    """

    engine = create_engine("sqlite://")
    repositorio = ExecutionRepository(engine)
    repositorio.ensure_table()
    set_execution_repository(repositorio)
    yield repositorio
    set_execution_repository(None)
    engine.dispose()
