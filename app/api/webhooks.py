"""
webhooks.py — Endpoints FastAPI para receber mensagens do WhatsApp via Twilio
Localização: app/api/webhooks.py

Diferenças desta versão (So Revendo / Liz):
- Sem CRM externo — histórico em memória simples
- Notificação automática no grupo WhatsApp interno quando lead quente
"""

import logging
from collections import defaultdict
from fastapi import APIRouter, Request, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from app.services.buffer_service import BufferService
from app.services.claude_client import get_liz_response
from app.services.group_notify import notify_group, is_hot_lead
from app.core.media_catalog import handle_incoming_media

logger = logging.getLogger(__name__)
router = APIRouter()

buffer_service = BufferService()

# ─── Histórico em memória (sem CRM por enquanto) ──────────────────────────────
# Estrutura: { phone: [ {role, content}, ... ] }
_conversation_history: dict[str, list[dict]] = defaultdict(list)
_client_names: dict[str, str] = {}

MAX_HISTORY = 30  # mensagens por cliente


def _save_message(phone: str, role: str, content: str):
    history = _conversation_history[phone]
    history.append({"role": role, "content": content})
    # Mantém apenas as últimas MAX_HISTORY mensagens
    if len(history) > MAX_HISTORY:
        _conversation_history[phone] = history[-MAX_HISTORY:]


def _get_history(phone: str) -> list[dict]:
    return _conversation_history[phone].copy()


# ─── Webhook principal ────────────────────────────────────────────────────────

@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(default=""),
    NumMedia: int = Form(default=0),
    MediaUrl0: str = Form(default=None),
    MediaContentType0: str = Form(default=None),
    ProfileName: str = Form(default=""),
):
    phone = From.replace("whatsapp:", "").strip()
    name  = ProfileName or _client_names.get(phone, "Cliente")

    # Salva nome na primeira vez
    if ProfileName and phone not in _client_names:
        _client_names[phone] = ProfileName

    logger.info(f"[WEBHOOK] {phone} ({name}) | '{Body[:60]}' | mídias: {NumMedia}")

    # Processa mídia
    media_descriptions = []
    if NumMedia > 0 and MediaUrl0:
        desc = handle_incoming_media(
            media_url=MediaUrl0,
            content_type=MediaContentType0 or "",
            phone=phone,
        )
        media_descriptions.append(desc)
        logger.info(f"[WEBHOOK] Mídia: {desc}")

    user_message = Body.strip() if Body.strip() else "[Cliente enviou imagem/arquivo sem texto.]"

    # Buffer — aguarda mensagens fragmentadas
    should_respond = buffer_service.add_message(phone, user_message)

    twiml = MessagingResponse()

    if not should_respond:
        return Response(content=str(twiml), media_type="application/xml")

    full_message = buffer_service.flush(phone) or user_message

    # Contexto simples do cliente (sem CRM)
    customer_context = {
        "name": name,
        "phone": phone,
        "source": "whatsapp",
        "orders": "Sem pedidos registrados",
        "notes": "",
    }

    # Gera resposta da Liz
    liz_reply = get_liz_response(
        user_message=full_message,
        customer_context=customer_context,
        conversation_history=_get_history(phone),
        media_descriptions=media_descriptions,
    )

    # Salva no histórico em memória
    _save_message(phone, "user", full_message)
    _save_message(phone, "assistant", liz_reply)

    # Notifica grupo interno se for lead quente
    if is_hot_lead(liz_reply):
        arte = "recebida" if media_descriptions else "aguardando"
        notify_group(
            client_phone=phone,
            client_name=name,
            status="orcamento",
            arte_status=arte,
        )

    twiml.message(liz_reply)
    return Response(content=str(twiml), media_type="application/xml")


@router.get("/health")
async def health_check():
    return {"status": "ok", "bot": "Liz", "empresa": "So Revendo"}
