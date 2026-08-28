# Ofertas — Bem me Qué

> **Única fonte canônica de condição comercial atual.**
>
> Identidade do produto está em `PRODUCTS.md`. Ideias, roadmap e hipóteses de
> marketing estão em `OFFER_STRATEGY_INTERNAL.md` — **nada aqui é proposta**.

**Verificado ao vivo em 2026-08-27** em `https://aprenda.atelierbemmeque.com/`
(HTTP 200 na home e nas 3 páginas de produto).

---

## Preços vigentes

| Produto | Preço de referência exibido | Preço atual | Desconto (calculado) | Checkout |
|---|---|---|---|---|
| O Segredo do Chocolate | R$ 59,00 | **R$ 47,00** | 20,3% | [8GRurLG](https://pay.kiwify.com.br/8GRurLG) |
| Recheios Profissionais | R$ 67,00 | **R$ 37,00** | 44,8% | [Eu6Eb9p](https://pay.kiwify.com.br/Eu6Eb9p) |
| Casquinhas Profissionais | R$ 37,00 | **R$ 29,00** | 21,6% | [GlA8RXr](https://pay.kiwify.com.br/GlA8RXr) |

- `currency`: BRL
- `offer_status`: ACTIVE
- `valid_until`: **desconhecido** — o site diz "por tempo limitado" mas não publica
  data. O agente **nunca** deve inventar prazo ("até domingo", "só hoje").
- `derived_calculation`: **true** para a coluna de desconto — `(referência − atual) / referência`.
- `last_verified_at`: 2026-08-27
- `source`: site oficial ao vivo + snapshot em PDF fornecido pela Judith

> **Preço de referência ≠ preço anteriormente cobrado.** "De R$ 59" é âncora de
> marketing exibida na página. Não há evidência de que R$ 59 tenha sido praticado, e
> o agente não deve afirmar que foi.

---

## ✅ RESOLVIDO — preço de O Segredo do Chocolate

O site publicava dois valores para o mesmo produto: **R$ 47,00** no texto visível e
**25.00** no `schema.org`. Resolvido em 2026-08-28 pela fonte comercial definitiva —
**o próprio checkout da Kiwify**, consultado em BRL:

```
O Segredo do Chocolate ......... R$ 47,00
                                 (ou 2x de R$ 24,74 / 3x de R$ 16,77,
                                  parcelamento com acréscimo)
```

**R$ 47,00 é o preço.** O bloco `schema.org` do site está errado.

> 🐛 **Bug do site, não do conhecimento.** O mesmo bloco `schema.org` também carrega
> uma descrição que não corresponde ao produto ("sem conservantes, nutritivo, saudável
> e vegano"). Preço e descrição errados no mesmo bloco indicam sobra de outro produto.
> Afeta o rich snippet do Google, não a resposta do agente. Ver `OFFER_STRATEGY_INTERNAL.md`.

---

## Order bump no checkout — EXISTE

Ao comprar *O Segredo do Chocolate*, o checkout oferece os outros dois ebooks:

| Order bump | Preço no checkout |
|---|---|
| Recheios Profissionais | 3x de R$ 13,20 |
| Casquinhas Profissionais | 3x de R$ 10,35 |

Verificado no checkout `8GRurLG` em 2026-08-28.

> Estes são valores **parcelados com acréscimo**, exibidos dentro do checkout. Não são
> o preço à vista dos produtos individuais (R$ 37,00 e R$ 29,00 — ver tabela acima), e
> o agente não deve apresentá-los como se fossem.

---

## Checkouts aposentados — não usar

Estes links constavam nas versões anteriores deste documento e de `PRODUCTS.md`.
Ambos respondem **HTTP 200** mas exibem *"Produto não está mais disponível"*:

| Link antigo | Produto | Estado |
|---|---|---|
| `pay.kiwify.com.br/od97l73` | Recheios Profissionais | **INDISPONÍVEL** |
| `pay.kiwify.com.br/r8LmYVZ` | Casquinhas Profissionais | **INDISPONÍVEL** |

Os checkouts vigentes se chamam "Recheios 2" e "Casquinhas Profissionais 2" na
Kiwify — foram substituídos.

---

## Garantia

**7 dias, incondicional.** Verificado em três fontes independentes em 2026-08-27:

- site ao vivo, seção "Garantia incondicional";
- `schema.org` → `hasMerchantReturnPolicy.merchantReturnDays: 7` nos 3 produtos;
- Termos de Uso do site: "garantia incondicional de satisfação por 7 dias".

---

## Entrega e acesso

- Acesso liberado após confirmação do pagamento, pela plataforma parceira (Kiwify).
- "Acesso 100% online."
- **Acesso vitalício à área de membros:** comprovado pelo PDF apenas de
  *O Segredo do Chocolate*. O site afirma para os três — origem: site.

---

## Bônus anunciados

O site anuncia **"4 vídeos bônus gravados pela Judith em cada ebook"** e exibe o
badge "Inclui vídeos bônus" nos três produtos.

| Produto | Comprovado pelo PDF | Anunciado pelo site |
|---|---|---|
| O Segredo do Chocolate | ✅ 4 aulas, página 30 | ✅ |
| Recheios Profissionais | ❌ não consta | ✅ |
| Casquinhas Profissionais | ❌ não consta | ✅ |

Para os dois últimos a origem é **o site**, não o produto. `NEEDS_JUDITH`.

---

## Coleção / Combo

**Não existe como oferta comprável.** Verificado no site ao vivo e no snapshot:

- a seção "Coleção completa" existe e lista os 3 ebooks;
- **não tem preço próprio**;
- **não tem checkout próprio** — só os 3 links individuais;
- o botão "Quero a coleção" é âncora para a seção `#colecao`.

`bundle`: `UNAVAILABLE`.

> R$ 107 é a **soma** dos três preços individuais, não um combo. O agente não deve
> oferecer coleção, preço de coleção, nem desconto de coleção.

---

## Prova social

O site exibe "Muito bem avaliado pelos alunos" e estrelas nos cards.

- Classificação: **`DECORATIVE_RATING` + `MARKETING_CLAIM`**.
- O `schema.org` **não** traz `aggregateRating` nem `review` em nenhum dos produtos.
- Não há número de alunos, média, nem depoimento identificado publicado.

O agente **não** pode afirmar quantidade de alunos, nota média, nem "X pessoas
avaliaram". Pode repetir que a marca se descreve assim.

---

## Urgência

O site usa: *"pode sair do ar a qualquer momento"*, *"os bônus disponíveis nesta etapa
são limitados"*, *"Essa oferta pode não estar disponível depois"*.

Não há contador regressivo, data-limite nem estoque declarado. O agente pode
reproduzir a condição como está escrita e **nunca** inventar prazo ou escassez.

---

## CTAs vigentes

"Comprar agora" · "Garantir meu acesso agora" · "Ver detalhes do ebook" ·
"Quero a coleção" (âncora, não compra).

---

*Reconstruído em 2026-08-27 (F2.7). Versão anterior preservada no histórico do Brain.*
*Conteúdo de estratégia e roadmap movido para `OFFER_STRATEGY_INTERNAL.md`.*
