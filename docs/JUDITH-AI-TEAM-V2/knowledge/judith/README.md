# Judith-specific Knowledge — estrutura para ingestão

> **Natureza:** `JUDITH_SPECIFIC`. Fatos do negócio da Bem me Qué.
> **Status desta pasta: VAZIA, aguardando material da Judith.**

## Por que esta pasta existe vazia

A auditoria da Agent Foundation V2 procurou conteúdo técnico real no repositório — temperagem, ganaches, caramelos, casquinhas, drageados, praliné, validade, armazenamento, ingredientes, equipamentos, troubleshooting.

**Resultado: os termos aparecem como tópico, mas não há nenhum conteúdo técnico.** Zero temperatura, zero gramatura, zero passo-a-passo, zero lista de ingredientes.

Os ebooks reais não estão no projeto. Eles **não foram reconstruídos de memória**, e não devem ser: uma receita gerada por LLM não é a receita da Judith, mesmo que pareça correta. Se chegasse numa cliente como se fosse conteúdo do produto, seria informação falsa sobre um produto pago.

A estrutura fica pronta para receber o material real.

## Estrutura prevista

```
knowledge/judith/
  products/          # ficha de cada produto digital
  ebooks/            # conteúdo real, por ebook
  recipes/           # receitas individuais
  techniques/        # temperagem, montagem, acabamento
  troubleshooting/   # sintoma -> causa -> correção
  faq/               # perguntas reais e respostas aprovadas
  policies/          # garantia, acesso, entrega, reembolso
  examples/          # peças aprovadas e rejeitadas (gold sources)
```

Regra de ingestão: **um arquivo por unidade de conhecimento**. Um ebook inteiro num arquivo só é impossível de citar com precisão e impossível de versionar por receita.

## Metadata obrigatória

Cada unidade nasce com frontmatter. Campo desconhecido fica vazio — **nunca preenchido por inferência**:

```yaml
---
title:              # nome da receita/técnica/política
category:           # recipe | technique | troubleshooting | faq | policy | product
source:             # arquivo/página de origem
source_product:     # qual ebook ou produto
version:            # versão do material de origem
status:             # DRAFT | TO_VALIDATE | CONFIRMED | DEPRECATED
validated_by:       # quem validou (só a Judith valida fato de negócio)
validated_at:       # data real da validação, nunca estimada
last_reviewed_at:
caveat:             # ressalva conhecida
---
```

### Sobre `status`

| Status | Significa | Pode ser citado como verdade? |
|---|---|---|
| `DRAFT` | extraído, não revisado | não |
| `TO_VALIDATE` | organizado, aguardando a Judith | não — só com ressalva explícita |
| `CONFIRMED` | validado pela Judith | sim |
| `DEPRECATED` | substituído, mantido por histórico | não |

**Nada entra como `CONFIRMED` sem a Judith.** Claude organiza e extrai; a Judith valida fato de negócio.

## Fluxo de ingestão

```
material original (PDF, doc, site)
  -> extração estruturada          [Claude]
  -> DRAFT com metadata            [Claude]
  -> detecção de lacuna/contradição [Claude]
  -> validação                     [JUDITH]
  -> CONFIRMED
  -> entra na whitelist do agente que precisa
  -> teste
  -> canal real
```

## O que ainda precisa vir da Judith

Ver `docs/JUDITH-AI-TEAM-V2/KNOWLEDGE_GAP_REGISTRY.md`, seção `MISSING_JUDITH_SOURCE`.

## Nota de segurança

Conteúdo de produto pago é material da Judith. Ele entra aqui como Knowledge consultável **interno** — não para ser reproduzido integralmente numa resposta a quem não comprou. Suporte usa para orientar quem já é cliente; vendas usa para descrever o que o produto ensina, não para entregar o conteúdo.

*Versão: 1.0 — Agent Foundation V2*
