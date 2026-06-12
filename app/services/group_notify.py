"""
group_notify.py — Notificação no grupo WhatsApp interno da So Revendo.
Localização: app/services/group_notify.py
"""

import logging
import os
from twilio.rest import Client as TwilioClient
from app.core.media_catalog import list_client_files

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM         = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
GROUP_NOTIFY_NUMBER = os.getenv("GROUP_NOTIFY_NUMBER", "")

HOT_LEAD_TRIGGERS = [
    "orçamento", "orcamento", "pedido", "confirmar", "confirmado",
    "fechar", "quantidade", "quantas peças", "me passa", "vou montar",
    "arte recebida", "montar o orçamento", "montar certinho",
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
    arte_status: str = "aguardando",
    obs: str = "",
):
    if not GROUP_NOTIFY_NUMBER:
        logger.warning("[GROUP] GROUP_NOTIFY_NUMBER não configurado.")
        return

    status_label = {
        "orcamento": "🟡 ORÇAMENTO",
        "pedido_confirmado": "🟢 PEDIDO CONFIRMADO",
        "arte_recebida": "🎨 ARTE RECEBIDA",
    }.get(status, f"🔵 {status.upper()}")

    linhas = [
        "*[LIZ — So Revendo]*",
        "",
        status_label,
        f"Cliente: {client_name or 'Não informado'}",
        f"Tel: {client_phone}",
        f"Produto: Patch 3D",
    ]

    if quantidade: linhas.append(f"Qtd: {quantidade}")
    if tamanho:    linhas.append(f"Tamanho: {tamanho}")

    linhas.append(f"Arte: {'✅ Recebida' if arte_status == 'recebida' else '⏳ Aguardando'}")

    # Lista arquivos recebidos do cliente
    files = list_client_files(client_phone)
    if files:
        linhas.append("")
        linhas.append("*Arquivos salvos:*")
        for f in files[-5:]:  # últimos 5
            linhas.append(f"• {f['filename']} ({f['size_kb']} KB)")

    if obs: linhas.append(f"Obs: {obs}")

    try:
        TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN).messages.create(
            from_=TWILIO_FROM,
            to=GROUP_NOTIFY_NUMBER,
            body="\n".join(linhas),
        )
        logger.info(f"[GROUP] Notificação enviada: {status} — {client_phone}")
    except Exception as e:
        logger.error(f"[GROUP] Erro: {e}")
