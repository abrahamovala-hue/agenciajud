"""
TEST DATA para WEEKLY_BUSINESS_REVIEW.

Nao vem de nenhuma integracao real (Instagram Insights e Kiwify nao estao
conectados - ver STATUS_V2.md). Numeros inventados para exercitar o
workflow. `VALID_FIXTURES` tem dado "completo"; `EMPTY_FIXTURES` simula
"nenhuma fonte disponivel" para testar se os agentes recusam inventar
numero.
"""

from __future__ import annotations

VALID_FIXTURES: dict[str, str] = {
    "analytics-bi-agent": (
        "[TEST DATA - nao e dado real do Instagram/Kiwify]\n"
        "Semana de 17-23/08/2026. Posts publicados: 5 (3 Reels, 2 Carrossel). "
        "Alcance total: 12.400 (semana anterior: 10.100, +23%). "
        "Engajamento medio: 4.2% (semana anterior: 3.8%). "
        "Post com melhor performance: Reel 'Tecnica de Temperagem' - 2.100 likes, 340 comments. "
        "Post com pior performance: Carrossel 'Historia da Marca' - 210 likes, 8 comments."
    ),
    "customer-insights-agent": (
        "[TEST DATA - nao e dado real de conversas]\n"
        "12 comentarios e 8 DMs coletados na semana. Temas recorrentes: "
        "'duvida sobre temperagem' (5 ocorrencias), 'pergunta se serve pra iniciante' (4 ocorrencias), "
        "'elogio ao resultado dos bombons' (6 ocorrencias)."
    ),
    "sales-conversion-agent": (
        "[TEST DATA - nao e dado real do Kiwify]\n"
        "7 conversas com intencao de compra na semana. 3 mencionaram preco como objecao. "
        "2 pediram recomendacao entre os 3 ebooks."
    ),
    "crm-lifecycle-agent": (
        "[TEST DATA - nao e dado real de CRM]\n"
        "4 novos leads qualificados na semana. 2 leads da semana anterior ainda sem follow-up feito."
    ),
    "market-trend-intelligence": (
        "[TEST DATA - nao e dado real de scraping]\n"
        "Observacao manual: formato 'macro close-up + educativo' parece estar performando bem no nicho "
        "de confeitaria essa semana (sem fonte quantitativa - apenas observacao)."
    ),
}

EMPTY_FIXTURES: dict[str, str] = {
    "analytics-bi-agent": "[TEST DATA] Nenhum dado de performance foi coletado esta semana.",
    "customer-insights-agent": "[TEST DATA] Nenhum comentario ou DM foi coletado esta semana.",
    "sales-conversion-agent": "[TEST DATA] Nenhuma conversa de vendas foi registrada esta semana.",
    "crm-lifecycle-agent": "[TEST DATA] Nenhum lead foi registrado esta semana.",
    "market-trend-intelligence": "[TEST DATA] Nenhuma pesquisa de tendencia foi feita esta semana.",
}
