# Evaluation Craft — rubrica, gold set e regressão

> `GENERAL / REUSABLE`. Não contém resultado de avaliação da Bem me Qué.

## Avaliar o quê

Antes de medir, decida a dimensão. Elas falham de formas diferentes:

| Dimensão | Pergunta |
|---|---|
| correção factual | o que afirmou é verdade e tem fonte |
| aderência ao escopo | fez o trabalho dele, não o de outro |
| processo | seguiu as etapas e os gates |
| segurança | recusou o que devia recusar |
| qualidade | serve para o objetivo |
| forma | tamanho, tom, estrutura |

Nota única esconde qual dimensão quebrou.

## Rubrica

Uma rubrica utilizável é **binária ou quase**. "Nota 7 de qualidade" não é acionável; "citou fonte que abriu: sim/não" é.

Escreva o critério **antes** de ver a resposta. Critério escrito depois vira justificativa da resposta que já existe.

## Gold set

Casos com resposta esperada conhecida. O que faz um bom conjunto:

- casos **reais**, não inventados para serem fáceis;
- os difíceis incluídos de propósito (ambíguo, fora de escopo, dado ausente);
- casos de **recusa** — o que o sistema deve negar é tão importante quanto o que deve fazer;
- resposta esperada validada por quem tem autoridade, não pelo próprio modelo.

Um gold set escrito pelo próprio sistema avaliado não mede nada.

## Taxonomia de falha

Classificar falha é o que transforma erro em melhoria:

| Tipo | Exemplo |
|---|---|
| alucinação factual | inventou preço |
| evidência ausente | afirmou sem consultar |
| evidência falsa | citou fonte que não abriu |
| invasão de escopo | fez o trabalho de outro papel |
| gate pulado | seguiu sem aprovação |
| forma | longo demais, tom errado |
| recusa indevida | negou algo legítimo |

Frequência por tipo diz onde mexer. Sem taxonomia, a reação é ajustar o prompt no escuro.

## Regressão

Toda mudança de comportamento roda o conjunto **inteiro** antes de valer. Ganhar num caso e perder em três é retrocesso — e sem regressão isso passa despercebido.

Compare candidata versus atual nos mesmos casos, e registre o resultado das duas.

## Promoção de versão

Critérios mínimos: sem regressão nas dimensões de segurança e correção; ganho mensurável no que motivou a mudança; mudança documentada.

> **O sistema não promove a si mesmo.** Proposta de melhoria é proposta; virar versão exige aprovação de quem responde pelo negócio. Automatizar esse passo remove o único ponto de controle real.

## Sinal qualitativo

Nem tudo é medível em escala. Correção humana recorrente no mesmo ponto é sinal forte, mesmo sem volume estatístico — trate como hipótese prioritária, não como prova.
