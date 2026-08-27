"""
Judith Brain — fundacao de Knowledge governada (F2).

    brain/models.py         vocabulario: camadas, status, disclosure
    brain/taxonomy.py       classificacao deterministica dos documentos
    brain/schema.py         tabelas
    brain/repository.py     o unico modulo que sabe SQL sobre Knowledge
    brain/access_policy.py  quem pode ver o que (fail-closed)
    brain/retrieval.py      brain.search() — a porta unica dos agentes
    brain/chunking.py       corte que preserva estrutura
    brain/security.py       segredo bloqueia; injecao sinaliza
    brain/conflicts.py      representacao de contradicao, sem resolver
    brain/backfill.py       espelha docs/ no store, sem tocar em docs/

Sem embeddings, sem pgvector, sem retrieval semantico — isso e F3.
"""

from brain.retrieval import search

__all__ = ["search"]
