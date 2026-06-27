"""
webhooks.py — Com frete automático, CNPJ/CPF detection e multi-pacote.
Localização: app/api/webhooks.py
"""

import logging
import re
from fastapi import APIRouter, Request, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from app.services.buffer_service import BufferService
from app.services.claude_client import get_liz_response, _load_config
from app.services.group_notify import notify_group, is_hot_lead
from app.services.crm_service import (
    get_or_create_customer, save_message, get_conversation_history,
    count_messages_today, create_order, update_customer, calcular_valor,
)
from app.services.followup_service import schedule as schedule_followup, cancel as cancel_followup, register_first_message
from app.services.shipping_service import (
    extract_cep, extract_document, has_cnpj,
    quote_freight, format_freight_message, get_product_packages,
)
from app.core.media_catalog import handle_incoming_media

logger = logging.getLogger(__name__)
router = APIRouter()
buffer_service = BufferService()

_quoted_ceps: dict[str, str] = {}   # phone → last quoted CEP
_client_docs: dict[str, dict] = {}  # phone → {type, value}


def _detectar_origem(referrer="", body="") -> str:
    ref = (referrer or "").lower()
    bod = (body or "").lower()
    if "instagram" in ref: return "instagram"
    if "facebook" in ref or "fb.com" in ref: return "facebook"
    if "google" in ref or "gclid" in ref: return "google"
    if any(w in bod for w in ["insta", "instagram", "reels"]): return "instagram"
    if any(w in bod for w in ["face", "facebook"]): return "facebook"
    if any(w in bod for w in ["google", "pesquisei"]): return "google"
    return "whatsapp"


def _extrair_dados(texto: str) -> dict:
    dados = {"quantidade": "", "tamanho": "", "tem_estrelas": False}
    qtd = re.search(r'(\d+)\s*(peças?|unidades?|brasões?|litros?|kg|rolos?)?', texto, re.IGNORECASE)
    if qtd and int(qtd.group(1)) >= 1:
        dados["quantidade"] = qtd.group(0).strip()
    tam = re.search(r'(\d+[\.,]?\d*)\s*(x|por|cm)?\s*(\d+[\.,]?\d*)?\s*cm?', texto, re.IGNORECASE)
    if tam:
        dados["tamanho"] = tam.group(0).strip()
    if re.search(r'estr[ea]l', texto, re.IGNORECASE):
        dados["tem_estrelas"] = True
    return dados


def _get_first_product() -> dict | None:
    """Retorna o primeiro produto ativo para usar nas dimensões de frete."""
    try:
        data = _load_config()
        products = data.get("products", [])
        return products[0] if products else None
    except Exception:
        return None


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(default=""),
    NumMedia: int = Form(default=0),
    MediaUrl0: str = Form(default=None),
    MediaContentType0: str = Form(default=None),
    ProfileName: str = Form(default=""),
    ReferralNumMediaUrl: str = Form(default=""),
):
    phone = From.replace("whatsapp:", "").strip()
    logger.info(f"[WEBHOOK] {phone} | '{Body[:60]}'")

    cancel_followup(phone)

    referer = request.headers.get("referer", "")
    origem  = _detectar_origem(referer + " " + ReferralNumMediaUrl, Body)

    customer = get_or_create_customer(phone=phone, name=ProfileName or "", source=origem)
    name     = ProfileName or customer.get("name", "Cliente")
    if customer.get("source", "") in ("", "whatsapp") and origem not in ("", "whatsapp"):
        update_customer(phone=phone, source=origem)

    register_first_message(phone)

    media_descriptions = []
    arte_recebida = False
    if NumMedia > 0 and MediaUrl0:
        desc = handle_incoming_media(media_url=MediaUrl0, content_type=MediaContentType0 or "", phone=phone)
        media_descriptions.append(desc)
        arte_recebida = True

    user_message = Body.strip() if Body.strip() else "[Cliente enviou imagem/arquivo sem texto.]"

    # Detecta documento (CPF/CNPJ) se ainda não temos
    if phone not in _client_docs:
        doc = extract_document(user_message)
        if doc["type"]:
            _client_docs[phone] = doc
            logger.info(f"[DOC] {phone} → {doc['type']}: {doc['value']}")

    should_respond = buffer_service.add_message(phone, user_message)
    twiml = MessagingResponse()
    if not should_respond:
        return Response(content=str(twiml), media_type="application/xml")

    full_message = buffer_service.flush(phone) or user_message
    history      = get_conversation_history(phone)

    # Contexto incluindo tipo de documento
    doc_info = _client_docs.get(phone, {})
    customer_context = {
        "name":     name,
        "phone":    phone,
        "source":   origem,
        "notes":    customer.get("notes", ""),
        "doc_type": doc_info.get("type", "não informado"),
    }

    # ── Frete automático ─────────────────────────────────────────────────────
    cep           = extract_cep(full_message)
    freight_msg   = None
    client_has_cnpj = doc_info.get("type") == "cnpj"

    # Também verifica histórico por CNPJ já enviado anteriormente
    if not client_has_cnpj:
        for msg in history:
            if has_cnpj(msg.get("content", "")):
                client_has_cnpj = True
                break

    if cep and _quoted_ceps.get(phone) != cep:
        product = _get_first_product()
        pkgs    = get_product_packages(product) if product else [{}]
        quotes  = quote_freight(
            to_cep=cep,
            product=product,
            declared_value=100.0,
            client_has_cnpj=client_has_cnpj,
        )
        if quotes:
            freight_msg = format_freight_message(quotes, cep, num_packages=len(pkgs))
            _quoted_ceps[phone] = cep
            logger.info(f"[FRETE] {len(quotes)} opções → {phone}")

    # ── Resposta IA ───────────────────────────────────────────────────────────
    liz_reply = get_liz_response(
        user_message=full_message,
        customer_context=customer_context,
        conversation_history=history,
        media_descriptions=media_descriptions,
    )

    save_message(phone=phone, role="user",      content=full_message)
    save_message(phone=phone, role="assistant", content=liz_reply)
    schedule_followup(phone)

    # ── Notifica grupo ────────────────────────────────────────────────────────
    dados = _extrair_dados(full_message + " " + liz_reply)
    valor = 0
    if dados["quantidade"] and dados["tamanho"]:
        qtd_nums = re.findall(r'\d+', dados["quantidade"])
        qtd_int  = int(qtd_nums[0]) if qtd_nums else 0
        valor    = calcular_valor(dados["tamanho"], qtd_int, dados.get("tem_estrelas", False))

    if is_hot_lead(liz_reply) or arte_recebida:
        arte_status = "recebida" if arte_recebida else "aguardando"
        if dados["quantidade"] or arte_recebida:
            create_order(phone=phone, quantidade=dados["quantidade"], tamanho=dados["tamanho"],
                        tem_estrelas=dados.get("tem_estrelas", False), arte_status=arte_status)
            update_customer(phone=phone, status="orcamento")
        notify_group(
            client_phone=phone, client_name=name,
            status="arte_recebida" if arte_recebida else "orcamento",
            quantidade=dados["quantidade"], tamanho=dados["tamanho"],
            tem_estrelas=dados.get("tem_estrelas", False), arte_status=arte_status,
            valor_estimado=valor, mensagens_hoje=count_messages_today(phone),
            origem=origem,
        )

    twiml.message(liz_reply)
    if freight_msg:
        twiml.message(freight_msg)

    return Response(content=str(twiml), media_type="application/xml")


@router.get("/health")
async def health_check():
    return {"status": "ok", "bot": "Liz", "empresa": "So Revendo"}
