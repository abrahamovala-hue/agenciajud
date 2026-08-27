# Business Rules — V2

> Consolidação de regras de negócio que já existiam espalhadas nos documentos V1
> (`agents/BRAND_REVIEWER.md`, `agents/PRODUCT_MARKETING.md`, `agents/TREND_RESEARCH.md`,
> `agents/AGENT_COLLABORATION_PROTOCOL.md`) mais as regras novas exigidas pela expansão V2
> (vendas, CRM, suporte). Este documento é Core Knowledge para praticamente todo agente —
> por isso existe centralizado, em vez de duplicado em cada ficha.

---

## Publicação e aprovação

1. **Nenhum conteúdo é publicado sem aprovação explícita da Judith.** (herdado do V1, regra de ouro)
2. Nenhum agente pula a Brand Reviewer antes de qualquer entrega ir para aprovação humana.
3. Rejeição precisa vir com motivo específico e evidência (referência a doc), nunca "não gostei".

## Preço, produto e ofertas

4. **Um dado volátil tem um dono canônico só.** Preço, desconto, checkout, status de
   oferta e garantia comercial vêm **exclusivamente de `brand/OFFERS.md`**. Identidade
   do produto (nome, subtítulo, formato, escopo, páginas, receitas, bônus comprovado)
   vem **exclusivamente de `brand/PRODUCTS.md`**. Nunca inventados, nunca de memória,
   e nunca "de OFFERS **ou** PRODUCTS" — a alternativa é o que deixou dois preços
   divergentes conviverem.
5. Conhecimento técnico autoral (receitas, métodos, curvas) vem dos ebooks primários
   (L1, acesso pago) e está sujeito ao Disclosure Gate. FAQ é resumo derivado e
   **não** é fonte de preço: FAQ referencia `OFFERS.md`.
6. Nunca prometer resultado de saúde ou efeito não comprovado do chocolate/produto (proibido: claims de saúde não validados).
7. Nunca inventar depoimento, review ou resultado de cliente que não existe.
   **Estrela decorativa não é avaliação verificada:** não afirmar nota média, número
   de alunos ou quantidade de avaliações sem lastro publicado.
8. Garantia de devolução é sempre a política real (**7 dias**, conforme `brand/OFFERS.md`,
   verificada no site oficial e no `schema.org`) — nunca alterar prazo/condição em
   texto de vendas.
9. **Linguagem de marketing do próprio material não vira fato.** "Lucrativo", "fácil
   de vender", "mercado em crescimento" e afins são `MARKETING_CLAIM` /
   `AUTHORIAL_CLAIM` mesmo vindo de fonte primária autorizada, e não podem ser
   convertidos em "você vai lucrar", "você vai vender" ou "resultado garantido".
   Autorização da Judith prova o que ela ensina, não o que o mundo faz.
10. **Promoção cruzada não é fonte canônica do outro produto.** A descrição de um
    produto vem do PDF dele, nunca do bloco promocional dentro de outro ebook.

## Vendas e conversão (novo em V2)

11. Nenhuma tática agressiva ou enganosa de venda (falsa escassez, urgência fabricada, comparação desonesta com concorrente).
    **Urgência só pode reproduzir o que o site publica.** O site não publica prazo
    nem contador: afirmar "só até domingo" é urgência fabricada.
12. Toda alegação de conversão/oferta em DM ou comentário precisa ser consistente com o que está publicado nas páginas oficiais.
13. Desconto ou condição especial só pode ser oferecida se existir em `brand/OFFERS.md` — nenhum agente cria desconto ad-hoc.
    **Combo/coleção não existe** enquanto `OFFERS.md` marcar `bundle: UNAVAILABLE`;
    somar os preços individuais não cria uma oferta.
14. **Conteúdo pago não vira resposta.** Receita, formula com gramagens e método
    completo dos ebooks exigem compra verificada. Suporte pode diagnosticar e
    explicar o conceito; não pode entregar o produto. A checagem é o Disclosure
    Gate, e ela é determinística — não depende do agente lembrar desta regra.

## Suporte e CRM (novo em V2)

15. Reembolso fora da política padrão (garantia de 7 dias) é sempre escalado para humano — nenhum agente aprova exceção sozinho.
16. Dado de cliente (nome, e-mail, histórico de compra) só é armazenado/consultado com o consentimento implícito do contexto da conversa (cliente iniciou contato) — nunca usado para contato não solicitado sem base de consentimento.
17. Reclamação com tom de ameaça legal ou risco de imagem pública é sempre escalada para humano, nunca respondida automaticamente.

## Conteúdo e marca

18. Tom de voz segue `brand/VOICE.md`; linguagem segue `brand/AUDIENCE.md`; pilares seguem `brand/CONTENT_PILLARS.md`.
19. Nenhuma alegação, estatística ou "trend" é publicada sem fonte (dado público real, verificável).
20. Identidade visual (`brand/VISUAL_IDENTITY.md`) é vinculante para qualquer peça visual.

## Dados e privacidade

21. Pesquisa de tendências usa apenas dados públicos (herdado de `VIRAL_RESEARCH_AGENT.md` V1) — nunca dado privado ou protegido.
22. DMs e comentários usados como Knowledge/insight são sempre anonimizados antes de virar exemplo/gold example.

## Aprendizado e mudança de comportamento

23. Nenhum agente edita a própria instructions, prompt, guardrail, tool ou Knowledge crítico. (ver `models/LEARNING_EVALS_MODEL.md`)
24. Toda proposta de melhoria de agente passa por avaliação de regressão e aprovação humana antes de virar versão nova.

---

*Versão: 2.0*
*Fonte: consolidação de regras já presentes no V1 + regras novas para os domínios de V2 (vendas, CRM, suporte)*
