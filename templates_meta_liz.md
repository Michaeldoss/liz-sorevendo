# Templates de Mensagem Meta — Liz So Revendo

Templates precisam ser aprovados pelo Meta antes de usar.
Cadastre em: Twilio Console → Messaging → Content Template Builder

---

## TEMPLATE 1 — FOLLOW-UP (cliente que não respondeu)
Nome: liz_followup_patch
Categoria: MARKETING
Idioma: pt_BR

Corpo:
"Oi, {{1}}! Aqui é a Liz, da So Revendo 👋
Vi que você se interessou pelo nosso patch 3D. Ficou alguma dúvida?
Me manda a arte ou referência que mostro como fica em relevo!"

Variáveis:
- {{1}} = nome do cliente

---

## TEMPLATE 2 — ORÇAMENTO PRONTO
Nome: liz_orcamento_pronto
Categoria: UTILITY
Idioma: pt_BR

Corpo:
"Olá, {{1}}! Seu orçamento do patch 3D está pronto 🎨

📦 Produto: Patch 3D personalizado
🔢 Quantidade: {{2}}
📐 Tamanho: {{3}}
💰 Valor total: R$ {{4}}
💳 Entrada (50%): R$ {{5}}

Prazo: 3 a 4 dias úteis após aprovação da arte.
Para fechar, é só confirmar aqui! ✅"

Variáveis:
- {{1}} = nome
- {{2}} = quantidade
- {{3}} = tamanho
- {{4}} = valor total
- {{5}} = valor entrada

---

## TEMPLATE 3 — PEDIDO EM PRODUÇÃO
Nome: liz_pedido_producao
Categoria: UTILITY
Idioma: pt_BR

Corpo:
"{{1}}, sua arte foi aprovada e o pedido entrou em produção! 🚀

Previsão de entrega: {{2}} dias úteis.
Assim que ficar pronto, aviso aqui.

— Liz, So Revendo"

Variáveis:
- {{1}} = nome
- {{2}} = prazo

---

## TEMPLATE 4 — PEDIDO PRONTO
Nome: liz_pedido_pronto
Categoria: UTILITY
Idioma: pt_BR

Corpo:
"Boa notícia, {{1}}! Seu patch 3D está pronto! ✅

Para finalizar, precisamos do pagamento do saldo restante (50%).
PIX: [CHAVE_PIX]

Após confirmação, combinamos a entrega/retirada. 😊"

Variáveis:
- {{1}} = nome

---

## COMO CADASTRAR NO TWILIO

1. Acessa: console.twilio.com → projeto So_Revendo_Liz_ia
2. Menu: Messaging → Content Template Builder
3. Clica em "Create new template"
4. Preenche nome, categoria, idioma e corpo
5. Submete para aprovação Meta (leva 1-3 dias úteis)

Após aprovação, o SID do template fica disponível para uso na API.
