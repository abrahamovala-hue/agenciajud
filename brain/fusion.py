"""
Hybrid Fusion — juntar duas listas ordenadas sem inventar relevancia.

    lexical   [c3, c1, c7, ...]   score inteiro, escala 0..N, sem teto
    vetorial  [c7, c2, c3, ...]   cosseno, escala -1..1

POR QUE RRF E NAO SOMA PONDERADA DE SCORE
------------------------------------------

Os dois scores nao sao comparaveis. O lexical conta ocorrencia de termo: um
chunk que repete "casquinha" seis vezes pontua 12; outro pontua 4. O cosseno
vive entre -1 e 1 e, na pratica, entre 0.2 e 0.6 para quase tudo. Somar exige
normalizar, e normalizar exige escolher um minimo e um maximo — que mudam a
cada busca. O mesmo chunk ficaria em posicoes diferentes dependendo de quem
mais apareceu na consulta, o que e o oposto de explicavel.

Reciprocal Rank Fusion (Cormack et al., 2009) descarta a magnitude e usa so a
POSICAO:

    score(d) = soma_sobre_pernas( peso / (K + posicao_do_d_naquela_perna) )

Uma perna que nao devolveu o documento simplesmente nao contribui. Nao ha
normalizacao, nao ha calibracao, nao ha parametro por consulta. E a resposta a
pergunta "por que este chunk ficou no top-3?" e literal: ele foi 1o no lexical
e 4o no vetorial — os numeros estao no proprio resultado.

SOBRE O K
---------

K=60 e o valor do artigo original e o que praticamente toda implementacao usa.
Ele amortece a diferenca entre as primeiras posicoes: com K=60 a distancia
entre o 1o e o 2o lugar e pequena, entao uma perna sozinha nao domina a fusao
so por ter ordenado com muita confianca. K baixo faria o 1o lugar de qualquer
perna vencer quase sempre — na pratica, escolher a perna em vez de fundir.

Deterministico: mesma entrada, mesma saida, sem LLM, sem aleatoriedade. O
desempate final e pela ordem de chegada da primeira perna, e nao pelo hash da
chave — hash daria ordem estavel mas arbitraria, e "arbitrario mas estavel"
ainda e inexplicavel para quem le o resultado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Constante de amortecimento do RRF. Ver a nota acima antes de mexer.
RRF_K = 60

#: Peso por perna. Iguais de proposito na V1.
#:
#: Comecar assimetrico seria calibrar contra intuicao antes de ter medida. O
#: shadow existe para produzir o numero que justifica (ou nao) mudar isto, e
#: qualquer ajuste futuro tem que citar esse numero.
DEFAULT_WEIGHTS: dict[str, float] = {"lexical": 1.0, "vetorial": 1.0}


@dataclass
class FusedItem:
    """Um candidato depois da fusao, com o porque junto."""

    key: str
    score: float
    #: perna -> posicao (1-based). Perna ausente = nao devolveu este item.
    ranks: dict[str, int] = field(default_factory=dict)
    #: perna -> contribuicao no score final. Soma = `score`.
    contributions: dict[str, float] = field(default_factory=dict)

    def explain(self) -> str:
        """Uma linha legivel. E o que responde "por que ficou no top-3?"."""

        if not self.ranks:
            return "sem perna: nao foi devolvido por nenhuma busca"
        partes = [f"{perna} #{posicao}" for perna, posicao in sorted(self.ranks.items())]
        return f"{' + '.join(partes)} -> RRF {self.score:.5f}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "chave": self.key,
            "score_hibrido": round(self.score, 6),
            "posicoes": dict(self.ranks),
            "contribuicoes": {k: round(v, 6) for k, v in self.contributions.items()},
            "explicacao": self.explain(),
        }


def reciprocal_rank_fusion(
    rankings: dict[str, list[str]],
    *,
    k: int = RRF_K,
    weights: dict[str, float] | None = None,
) -> list[FusedItem]:
    """Funde listas ordenadas de chaves. Determinístico e explicavel.

    `rankings` e {nome_da_perna: [chave_em_1o, chave_em_2o, ...]}. Chave
    repetida dentro de uma perna conta so a primeira aparicao — posicao e
    unica por definicao.

    A ordem de saida e por score decrescente; empate mantem a ordem em que a
    chave apareceu pela primeira vez, varrendo as pernas na ordem em que foram
    passadas. Empate acontece de verdade: dois documentos em 1o e 2o lugar de
    pernas diferentes recebem o mesmo score.
    """

    pesos = weights or DEFAULT_WEIGHTS
    itens: dict[str, FusedItem] = {}

    for perna, chaves in rankings.items():
        peso = pesos.get(perna, 1.0)
        vistas: set[str] = set()
        for posicao, chave in enumerate(chaves, start=1):
            if chave in vistas:
                continue
            vistas.add(chave)
            item = itens.setdefault(chave, FusedItem(key=chave, score=0.0))
            contribuicao = peso / (k + posicao)
            item.ranks[perna] = posicao
            item.contributions[perna] = contribuicao
            item.score += contribuicao

    ordem_de_chegada = {chave: indice for indice, chave in enumerate(itens)}
    return sorted(itens.values(), key=lambda i: (-i.score, ordem_de_chegada[i.key]))
