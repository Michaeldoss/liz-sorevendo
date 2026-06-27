"""
group_notify.py — Notificação enriquecida no grupo WhatsApp interno da So Revendo.
Localização: app/services/group_notify.py
"""

import logging
import os
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM         = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
GROUP_NOTIFY_NUMBER = os.getenv("GROUP_NOTIFY_NUMBER", "")

HOT_LEAD_TRIGGERS = [
    "orçamento", "orcamento", "pedido", "confirmar", "confirmado",
    "fechar", "quantidade", "quantas peças", "me passa", "vou montar",
    "arte recebida", "montar o orçamento", "montar certinho",
    "qual o valor", "quanto fica", "quero fazer", "quero encomendar",
]


def is_hot_lead(liz_reply: str) -> bool:
    reply_lower = liz_reply.lower()
    return any(t in reply_lower for t in HOT_LEAD_TRIGGERS)


def notify_group(
    client_phone: str,
    client_name: str,
    status: str = "orcamento",
    quantidade: str = "",
    tamanho: str = "",
    tem_estrelas: bool = False,
    arte_status: str = "aguardando",
    valor_estimado: float = 0,
    mensagens_hoje: int = 0,
    origem: str = "",
    obs: str = "",
):
    if not GROUP_NOTIFY_NUMBER:
        logger.warning("[GROUP] GROUP_NOTIFY_NUMBER não configurado.")
        return

    status_label = {
        "orcamento":        "🟡 ORÇAMENTO",
        "pedido_confirmado": "🟢 PEDIDO CONFIRMADO",
        "arte_recebida":    "🎨 ARTE RECEBIDA",
    }.get(status, f"🔵 {status.upper()}")

    # Linha de valor
    if valor_estimado > 0:
        valor_linha = f"R$ {valor_estimado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        entrada_linha = f"R$ {valor_estimado/2:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        valor_str = f"💰 Valor estimado: *{valor_linha}* (entrada: {entrada_linha})"
    else:
        valor_str = "💰 Valor: aguardando tamanho e quantidade"

    # Monta mensagem
    linhas = [
        f"*[LIZ — So Revendo]*",
        f"",
        f"{status_label}",
        f"━━━━━━━━━━━━━━━━━━━",
        f"👤 *{client_name or 'Não informado'}*",
        f"📱 {client_phone}",
    ]

    if origem:
        origens = {
            "instagram": "📸 Instagram",
            "facebook": "👍 Facebook",
            "google": "🔍 Google",
            "whatsapp": "💬 WhatsApp",
        }
        linhas.append(f"📣 Origem: {origens.get(origem.lower(), origem)}")

    linhas.append(f"━━━━━━━━━━━━━━━━━━━")
    linhas.append(f"📦 Produto: Patch 3D")

    if quantidade:
        linhas.append(f"🔢 Quantidade: {quantidade}")
    if tamanho:
        linhas.append(f"📐 Tamanho: {tamanho}")
    if tem_estrelas:
        linhas.append(f"⭐ Arte com estrelas: +R$1,50/peça")

    linhas.append(f"")
    linhas.append(valor_str)
    linhas.append(f"")
    linhas.append(f"🎨 Arte: {'✅ Recebida' if arte_status == 'recebida' else '⏳ Aguardando'}")

    if mensagens_hoje > 0:
        linhas.append(f"💬 Mensagens hoje: {mensagens_hoje}")

    if obs:
        linhas.append(f"📝 Obs: {obs}")

    linhas.append(f"━━━━━━━━━━━━━━━━━━━")
    linhas.append(f"_Gerado pela Liz — So Revendo_")

    try:
        TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN).messages.create(
            from_=TWILIO_FROM,
            to=GROUP_NOTIFY_NUMBER,
            body="\n".join(linhas),
        )
        logger.info(f"[GROUP] Notificação enviada: {status} — {client_phone}")
    except Exception as e:
        logger.error(f"[GROUP] Erro ao notificar: {e}")
