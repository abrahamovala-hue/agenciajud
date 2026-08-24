# Analytics Craft — KPI, funil, coorte e atribuição

> `GENERAL / REUSABLE`. Não contém dado da Bem me Qué.

## Um KPI só serve se for definível

Antes de reportar qualquer número, ele precisa ter: **numerador, denominador, janela e fonte**. "Engajamento 4%" não significa nada sem dizer 4% de quê, em que período, medido onde.

Métrica sem definição escrita gera duas leituras diferentes na mesma reunião.

## Vaidade vs decisão

| Métrica de vaidade | Métrica de decisão |
|---|---|
| seguidores | conversão por origem |
| visualizações | retenção por trecho |
| curtidas | salvamentos / compartilhamentos |
| alcance total | alcance em não-seguidores |

O teste: **se esse número mudar, alguma decisão muda?** Se não, é relatório, não análise.

## Funil

Funil é uma sequência de etapas onde cada uma só pode ser menor que a anterior. O valor não está no número absoluto — está em **onde cai mais**.

```
alcance → interesse → consideração → intenção → compra
```

Ao analisar: procure o maior degrau. É lá que uma melhoria pequena tem efeito grande.

## Coorte

Média sobre períodos diferentes mistura pessoas diferentes. Coorte agrupa por *quando entrou*, e é o que permite dizer se algo melhorou ou se a composição mudou.

Sem coorte, "a conversão caiu" pode significar apenas que entrou muita gente nova.

## Atribuição — leia com desconfiança

Atribuição atribui crédito, não causa. Limitações que precisam ser ditas junto do número:
- last-click superestima o canal do fim do funil;
- conteúdo orgânico influencia decisões que ele nunca recebe crédito por;
- janela curta demais corta ciclos de decisão longos;
- sem identificação entre dispositivos, o mesmo cliente vira duas pessoas.

Reportar atribuição sem ressalva transforma estimativa em fato.

## Variância

Nem toda oscilação é sinal. Antes de chamar de tendência:
- qual é a variação normal da métrica (baseline);
- o volume é suficiente para a diferença significar algo;
- houve mudança externa (sazonalidade, feriado, campanha).

Com pouco volume, uma diferença de 20% costuma ser ruído. Dizer isso é análise; ignorar é adivinhação.

## Qualidade do dado

Antes de analisar: janela correta? fuso correto? duplicatas? estornos descontados? A pergunta que mais evita erro é **"esse número inclui o quê?"**.

## Reportar

```
RESUMO      o que mudou e o que fazer
KPIs        número + comparação + fonte
INSIGHTS    interpretação, marcada como interpretação
ALERTAS     o que precisa de ação
```

**Nunca fabrique dataset.** Sem dado disponível, o relatório diz que não há dado e nomeia quem o teria. Preencher lacuna com estimativa plausível é o pior resultado possível — parece análise e não é.
