"""
webhooks.py — Webhook WhatsApp com CRM Supabase e notificação enriquecida.
Localização: app/api/webhooks.py
"""

import logging
import re
from fastapi import APIRouter, Request, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from app.services.buffer_service import BufferService
from app.services.claude_client import get_liz_response
from app.services.group_notify import notify_group, is_hot_lead
from app.services.crm_service import (
    get_or_create_customer,
    save_message,
    get_conversation_history,
    count_messages_today,
    create_order,
    update_customer,
    calcular_valor,
)
from app.core.media_catalog import handle_incoming_media

logger = logging.getLogger(__name__)
router = APIRouter()
buffer_service = BufferService()


def _extrair_dados_conversa(texto: str) -> dict:
    """
    Extrai quantidade, tamanho e estrelas do texto da conversa.
    Usado para enriquecer CRM e notificação.
    """
    dados = {"quantidade": "", "tamanho": "", "tem_estrelas": False}

    # Quantidade: "50 peças", "100 unidades", "umas 30"
    qtd = re.search(r'(\d+)\s*(peças?|unidades?|und|pcs|brasões?)?', texto, re.IGNORECASE)
    if qtd:
        dados["quantidade"] = qtd.group(0).strip()

    # Tamanho: "8x6", "10cm", "8 por 6", "tamanho 8"
    tam = re.search(r'(\d+[\.,]?\d*)\s*(x|por|cm)?\s*(\d+[\.,]?\d*)?\s*cm?', texto, re.IGNORECASE)
    if tam:
        dados["tamanho"] = tam.group(0).strip()

    # Estrelas
    if re.search(r'estr[ea]l', texto, re.IGNORECASE):
        dados["tem_estrelas"] = True

    return dados


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
    logger.info(f"[WEBHOOK] {phone} | '{Body[:60]}' | mídias: {NumMedia}")

    # CRM — busca ou cria cliente
    customer = get_or_create_customer(
        phone=phone,
        name=ProfileName or "",
        source="whatsapp",
    )
    name = ProfileName or customer.get("name", "Cliente")

    # Processa mídia
    media_descriptions = []
    arte_recebida = False
    if NumMedia > 0 and MediaUrl0:
        desc = handle_incoming_media(
            media_url=MediaUrl0,
            content_type=MediaContentType0 or "",
            phone=phone,
        )
        media_descriptions.append(desc)
        arte_recebida = True
        logger.info(f"[WEBHOOK] Mídia recebida de {phone}")

    user_message = Body.strip() if Body.strip() else "[Cliente enviou imagem/arquivo sem texto.]"

    # Buffer
    should_respond = buffer_service.add_message(phone, user_message)
    twiml = MessagingResponse()

    if not should_respond:
        return Response(content=str(twiml), media_type="application/xml")

    full_message = buffer_service.flush(phone) or user_message

    # Histórico do Supabase
    conversation_history = get_conversation_history(phone)

    # Contexto do cliente
    customer_context = {
        "name": name,
        "phone": phone,
        "source": customer.get("source", "whatsapp"),
        "orders": "Ver histórico no CRM",
        "notes": customer.get("notes", ""),
    }

    # Resposta da Liz
    liz_reply = get_liz_response(
        user_message=full_message,
        customer_context=customer_context,
        conversation_history=conversation_history,
        media_descriptions=media_descriptions,
    )

    # Salva no Supabase
    save_message(phone=phone, role="user", content=full_message)
    save_message(phone=phone, role="assistant", content=liz_reply)

    # Extrai dados da conversa para CRM e notificação
    texto_completo = full_message + " " + liz_reply
    dados = _extrair_dados_conversa(texto_completo)

    # Calcula valor estimado
    valor = 0
    if dados["quantidade"] and dados["tamanho"]:
        qtd_nums = re.findall(r'\d+', dados["quantidade"])
        qtd_int = int(qtd_nums[0]) if qtd_nums else 0
        valor = calcular_valor(dados["tamanho"], qtd_int, dados["tem_estrelas"])

    # Notifica grupo se lead quente
    if is_hot_lead(liz_reply) or arte_recebida:
        mensagens_hoje = count_messages_today(phone)
        arte_status = "recebida" if arte_recebida else "aguardando"

        # Cria ou atualiza pedido no CRM
        if dados["quantidade"] or arte_recebida:
            create_order(
                phone=phone,
                quantidade=dados["quantidade"],
                tamanho=dados["tamanho"],
                tem_estrelas=dados["tem_estrelas"],
                arte_status=arte_status,
            )
            update_customer(phone=phone, status="orcamento")

        notify_group(
            client_phone=phone,
            client_name=name,
            status="arte_recebida" if arte_recebida else "orcamento",
            quantidade=dados["quantidade"],
            tamanho=dados["tamanho"],
            tem_estrelas=dados["tem_estrelas"],
            arte_status=arte_status,
            valor_estimado=valor,
            mensagens_hoje=mensagens_hoje,
            origem=customer.get("source", ""),
        )

    twiml.message(liz_reply)
    return Response(content=str(twiml), media_type="application/xml")


@router.get("/health")
async def health_check():
    return {"status": "ok", "bot": "Liz", "empresa": "So Revendo"}
