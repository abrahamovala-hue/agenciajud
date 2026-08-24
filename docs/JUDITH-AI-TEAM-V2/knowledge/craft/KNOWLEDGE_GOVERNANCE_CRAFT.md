# Knowledge Governance Craft — proveniência, frescor e conflito

> `GENERAL / REUSABLE`. Não contém o registro de fontes da Bem me Qué.

## Governar conhecimento não é decidir a verdade

Quem administra conhecimento cuida de **origem, estado e acesso**. Não decide qual fato de negócio é verdadeiro — isso é do dono do negócio. Essa fronteira é a regra mais importante da função.

## Proveniência

Toda fonte responde: de onde veio, quem é dono, quando foi validada, quanto se pode confiar.

| Estado | Significado | Serve para decisão? |
|---|---|---|
| vigente | referência estável | sim |
| snapshot | retrato de um momento | não como dado atual |
| template / rascunho | não validado pelo dono | não como verdade |
| ressalva | parte do documento é incerta | não naquele ponto |
| indisponível | não existe | nunca |

A ressalva **viaja junto do trecho**. Marcar o documento e deixar o agente citar sem a ressalva não protege ninguém.

## Autoridade

Nem toda fonte tem o mesmo peso. Ordem típica: documento oficial validado, depois documento oficial não validado, depois registro observado, depois inferência.

Inferência de LLM **nunca** é fonte de fato de negócio. Ela organiza e extrai; não valida.

## Frescor

Cada tipo de conhecimento vence num ritmo diferente: preço e política vencem rápido; posicionamento e voz vencem devagar; auditoria pontual vence na data em que foi feita.

Documento sem data de revisão é dívida silenciosa — parece atual e não é.

## Conflito entre fontes

Procedimento:
1. **nomeie** o conflito em uma frase;
2. mostre os dois trechos com a confiabilidade de cada um;
3. diga qual é a leitura mais provável e por quê;
4. **escale para quem tem autoridade** sobre o fato.

Nunca resolva silenciosamente. Escolher um lado sem autoridade cria uma verdade nova que ninguém aprovou — e ela se propaga.

## Versionamento e depreciação

Mudança de fato relevante gera versão nova, não edição silenciosa: sem histórico não se explica por que uma resposta antiga estava certa na época.

Depreciar é melhor que apagar: fonte marcada como obsoleta ainda explica decisões passadas.

## Acesso

Cada papel enxerga o que a função justifica. Whitelist explícita, e o que não é necessário fica fora — inclusive dado técnico sensível (identificadores, credenciais, chaves), que nunca entra em base consultável.

## Qualidade de recuperação

Uma base é boa quando a busca devolve o trecho certo. Sinais de problema: sempre o mesmo documento, nunca o documento óbvio, resultado sem a seção que responde.

**Busca que não encontra nada precisa dizer isso explicitamente.** Resultado vazio convida quem consulta a preencher a lacuna sozinho.
