# 🤖 Liz Bot — So Revendo

Assistente comercial WhatsApp para a **So Revendo**, gráfica especializada em adesivos, lonas, DTF têxtil, DTF UV, patch 3D, wind banner e bandeiras.

Baseado na arquitetura do **Bruno IA** (FastAPI + Python + Twilio + Claude/Anthropic).

---

## 📁 Estrutura de arquivos

```
liz_bot/
├── main.py              # Entry point FastAPI
├── prompt.py            # Persona e system prompt da Liz
├── claude_client.py     # Cliente Anthropic (substitui openai_client.py do Bruno)
├── webhooks.py          # Endpoint POST /webhook/whatsapp
├── buffer_service.py    # Agrupamento de mensagens rápidas
├── followup_service.py  # Follow-up automático de leads
├── crm_service.py       # CRM SQLite (clientes, mensagens, pedidos)
├── media_catalog.py     # Catálogo de produtos + handler de mídias recebidas
├── requirements.txt
└── .env.example
```

> ❌ **Removidos** em relação ao Bruno: `serasa_client.py`, `uniplus_client.py`

---

## ⚙️ Instalação

```bash
# 1. Clone / copie a pasta
cd liz_bot

# 2. Instale dependências
pip install -r requirements.txt

# 3. Configure variáveis de ambiente
cp .env.example .env
# Edite o .env com suas chaves

# 4. Inicie o servidor
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 🔌 Configuração Twilio

1. No painel Twilio, vá em **Messaging → WhatsApp Sandbox** (ou número aprovado).
2. Configure o Webhook para: `https://SEU_DOMINIO/webhook/whatsapp`
3. Método: `HTTP POST`

---

## 💳 Condição de Pagamento

A Liz informa automaticamente:
- **50% de entrada** na aprovação do pedido (PIX)
- **50% na retirada/entrega**

A chave PIX é configurada via variável de ambiente `PIX_KEY`.

---

## 📲 Canais de origem de leads

A Liz qualifica e registra clientes provenientes de:
- Instagram
- Facebook
- Google

O campo `source` no CRM é preenchido automaticamente quando o cliente informa de onde veio.

---

## 🔄 Follow-up automático

Sequência após silêncio do cliente:
| Tempo | Mensagem |
|-------|----------|
| 2h    | Verificação de dúvidas sobre orçamento |
| 24h   | Lembrete da proposta + convite para fechar |
| 72h   | Última mensagem + convite aberto para futuro |

Para cancelar o follow-up de um cliente (ex: pedido fechado), chame:
```python
followup_service.cancel(phone)
```

---

## 📦 Produtos no catálogo

| Produto       | Aplicação principal                          |
|---------------|----------------------------------------------|
| Adesivos      | Veículos, vitrines, fachadas, embalagens     |
| Lonas         | Faixas, banners, toldos, fachadas            |
| DTF Têxtil    | Camisetas, moletons, bonés, bolsas           |
| DTF UV        | MDF, acrílico, metal, vidro, cerâmica        |
| Patch 3D      | Uniformes, bonés, brindes corporativos       |
| Wind Banner   | Eventos, fachadas externas                   |
| Bandeiras     | Empresas, times, eventos, países             |

---

## 🛠 Personalização futura sugerida

- [ ] Integrar com planilha/Airtable para preços por m²
- [ ] Webhook de status de pedido (igual ao Bruno com Trello)
- [ ] Painel web de CRM (visualização de leads e pedidos)
- [ ] Aprovação de arte via WhatsApp (cliente responde "aprovar")
