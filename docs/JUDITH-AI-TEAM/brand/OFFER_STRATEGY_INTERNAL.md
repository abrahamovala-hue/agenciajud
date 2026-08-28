# Estratégia de Oferta — INTERNO

> `content_access: INTERNAL_ONLY`
>
> **Nada neste documento é fato comercial.** Nada aqui está implementado. Nada aqui
> pode ser dito a uma cliente, nem em resumo.
>
> Condição comercial real: `OFFERS.md`. Identidade do produto: `PRODUCTS.md`.

Este documento existe porque a versão anterior de `OFFERS.md` — a fonte canônica de
preço — misturava preços reais com ideias de marketing na mesma página. Um agente
buscando "tem combo com desconto?" recuperava uma sugestão não implementada e um
preço hipotético como se fossem oferta ativa.

O conteúdo foi **movido, não apagado**: continua auditável, longe do preço.

---

## Ideias propostas — NUNCA IMPLEMENTADAS

Origem: auditoria de copy de 07/08/2026. Status de todas: **PROPOSTA**.

| # | Ideia | Status | Observação |
|---|---|---|---|
| 1 | Oferta de combo/coleção com desconto adicional | `PROPOSTA` | Não existe. Ver `OFFERS.md` → `bundle: UNAVAILABLE`. |
| 2 | Countdown timer para urgência | `PROPOSTA` | **Nunca existiu no site.** Não é campanha ativa. |
| 3 | Depoimentos reais de alunos | `PROPOSTA` | Não há depoimento identificado publicado. |
| 4 | Order bump / upsell no checkout | ✅ `JÁ IMPLEMENTADO` | Ver correção abaixo. |
| 5 | Preço psicológico | `DEPRECATED` | Ver abaixo. |
| 6 | Número de alunos como prova social | `PROPOSTA` | Não há número apurado. Afirmar seria inventar prova. |

---

## Correção do item 4 — o order bump JÁ EXISTE (2026-08-28)

A versão anterior deste documento afirmava *"Não existe no checkout"*. **Estava errado.**

O erro foi de método, e vale registrar: eu verifiquei as páginas do site e concluí a
partir delas. O order bump não vive no site — vive **dentro do checkout**, que é outra
superfície. Não tinha olhado lá.

Abrindo `pay.kiwify.com.br/8GRurLG` em BRL:

| Order bump ofertado | Preço exibido |
|---|---|
| Recheios Profissionais | 3x de R$ 13,20 |
| Casquinhas Profissionais | 3x de R$ 10,35 |

Ou seja: a Judith **já faz** cross-sell no checkout. A "proposta" era descrição de algo
implementado. Registrado em `OFFERS.md` como fato comercial.

**Lição para as próximas verificações:** o site não é a única superfície comercial. O
checkout é o que a cliente vê com o cartão na mão, e ele tem conteúdo próprio.

---

## Item 5 — o valor hipotético, marcado como morto

A auditoria de 07/08/2026 sugeriu testar um preço psicológico terminado em `,90`
para O Segredo do Chocolate.

**Status: `DEPRECATED`. Nunca foi praticado. Nunca foi publicado.**

O valor numérico foi deliberadamente **removido** deste documento em vez de ser
registrado com um aviso ao lado. Motivo: retrieval lexical recupera trechos, não
avisos. Enquanto o número existisse escrito aqui — mesmo rotulado como hipótese, e
mesmo dentro de uma frase explicando que ele nunca valeu — uma busca por aquele
valor o traria de volta com aparência de oferta. Um número citado é um número
recuperável.

O preço vigente é o de `OFFERS.md`, e é o único.

---

## Gatilhos observados na página de venda

Descrição do que o site **já faz** hoje. Análise, não recomendação — e nenhum
destes itens é preço:

- **Prova social** — estrelas decorativas e "muito bem avaliado pelos alunos"
  (sem lastro numérico; ver `OFFERS.md`).
- **Autoridade** — "Judith Kolker, Chocolatier, especialista em chocolate artesanal premium".
- **Segurança** — "Compra segura", garantia de 7 dias.
- **Ancoragem** — preço "de/por" e tag "Oferta".
- **Facilidade** — "Acesso imediato", "sem equipamentos profissionais".
- **Escassez branda** — "pode sair do ar a qualquer momento" (sem prazo publicado).

---

## Achados técnicos abertos (2026-08-27)

1. **`schema.org` de O Segredo do Chocolate publica `25.00`** enquanto a página e o
   checkout mostram R$ 47,00. Resolvido como conhecimento (o checkout decidiu), mas
   **continua sendo bug do site**: afeta o rich snippet do Google.
2. **Descrição `schema.org` de O Segredo do Chocolate está errada:** "Sem
   conservantes, nutritivo, saudável e vegano" — não corresponde ao produto.
3. **O PDF do site foi gerado de `localhost:8080`**, não do domínio publicado. O
   conteúdo comercial confere com o site ao vivo; os links internos, não.

---

*Criado em 2026-08-27 (F2.7) para receber o conteúdo estratégico removido de `OFFERS.md`.*
