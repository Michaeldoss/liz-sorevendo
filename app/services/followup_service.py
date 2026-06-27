"""
followup_service.py — Follow-up gerado por IA com base no contexto real da conversa.
Sequência: 30min → +2h → +4h → 24h após primeira mensagem
Horário: 08:00-12:00 e 13:30-18:00 (dias úteis)
Localização: app/services/followup_service.py
"""

import logging
import threading
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import anthropic
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Sao_Paulo")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM        = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

WINDOWS = [
    ((8, 0),  (12, 0)),
    ((13, 30), (18, 0)),
]

SEQUENCE_DELAYS = [
    (30,   "30min"),
    (150,  "2h30"),
    (390,  "6h30"),
    (1440, "24h"),   # em minutos — 24h será calculado desde a 1ª mensagem
]

_state: dict[str, dict] = {}
_lock = threading.Lock()
_anthropic = anthropic.Anthropic()


def _is_business_hours(dt: datetime) -> bool:
    if dt.weekday() >= 5:
        return False
    t = (dt.hour, dt.minute)
    for (start, end) in WINDOWS:
        if start <= t < end:
            return True
    return False


def _next_business_slot(dt: datetime) -> datetime:
    candidate = dt.replace(second=0, microsecond=0)
    for _ in range(14):
        if candidate.weekday() < 5:
            for (sh, sm), (eh, em) in WINDOWS:
                ws = candidate.replace(hour=sh, minute=sm, second=0)
                we = candidate.replace(hour=eh, minute=em, second=0)
                if ws <= candidate < we:
                    return candidate
                if candidate < ws:
                    return ws
        candidate = (candidate + timedelta(days=1)).replace(hour=8, minute=0, second=0)
    return candidate


def _load_bot_config() -> dict:
    """Carrega configuração do bot do Supabase."""
    try:
        from app.services.crm_service import _get_supabase
        sb = _get_supabase()
        res = sb.table("bot_config").select("bot_name,company_name,bot_role,bot_tone").limit(1).execute()
        return res.data[0] if res.data else {}
    except Exception:
        return {}


def _generate_followup_message(phone: str, sequence_number: int) -> str:
    """
    Gera mensagem de follow-up personalizada com IA,
    baseada no histórico real da conversa.
    """
    try:
        from app.services.crm_service import get_conversation_history
        history = get_conversation_history(phone, limit=30)

        if not history:
            return ""

        cfg = _load_bot_config()
        bot_name    = cfg.get("bot_name", "Liz")
        company     = cfg.get("company_name", "So Revendo")
        bot_role    = cfg.get("bot_role", "especialista em vendas")
        bot_tone    = cfg.get("bot_tone", "Profissional e simpática")

        # Monta histórico formatado
        history_text = "\n".join(
            f"{'Cliente' if m['role'] == 'user' else bot_name}: {m['content']}"
            for m in history
        )

        # Tom varia conforme o número do follow-up
        tom_map = {
            1: "sutil e amigável — apenas retomando a conversa com uma pergunta direta",
            2: "um pouco mais proativo — reforça o valor do produto e oferece ajuda concreta",
            3: "cria urgência suave — menciona prazo de produção ou disponibilidade",
            4: "última tentativa — encerra com gentileza, deixa a porta aberta para o futuro",
        }
        tom = tom_map.get(sequence_number, "amigável e direto")

        prompt = f"""Você é {bot_name}, {bot_role} da {company}.
Tom: {bot_tone}

O cliente parou de responder. Você precisa enviar uma mensagem de follow-up para retomar a conversa.

HISTÓRICO DA CONVERSA:
{history_text}

INSTRUÇÕES PARA O FOLLOW-UP #{sequence_number}:
- Tom: {tom}
- Analise o histórico e continue EXATAMENTE de onde a conversa parou
- Mencione especificamente o produto/detalhe que estava sendo discutido
- NÃO repita o que já foi dito — avance a conversa
- NÃO use "como posso ajudar?" ou frases genéricas
- Máximo 2-3 frases curtas — WhatsApp, não e-mail
- Use no máximo 1 emoji
- NÃO mencione que está fazendo follow-up ou que o cliente sumiu
- Escreva APENAS a mensagem, sem aspas nem prefixos

Escreva a mensagem de follow-up:"""

        response = _anthropic.messages.create(
            model="claude-opus-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        message = response.content[0].text.strip().strip('"').strip("'")
        logger.info(f"[FOLLOWUP] Mensagem gerada para {phone} (#{sequence_number}): {message[:80]}")
        return message

    except Exception as e:
        logger.error(f"[FOLLOWUP] Erro ao gerar mensagem IA: {e}")
        return ""


def _send_whatsapp(phone: str, message: str):
    if not message:
        logger.warning(f"[FOLLOWUP] Mensagem vazia para {phone} — não enviou")
        return
    try:
        TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN).messages.create(
            from_=TWILIO_FROM,
            to=f"whatsapp:{phone}",
            body=message,
        )
        logger.info(f"[FOLLOWUP] ✅ Enviado para {phone}")
    except Exception as e:
        logger.error(f"[FOLLOWUP] Erro Twilio para {phone}: {e}")


def _fire_followup(phone: str, sequence_number: int, label: str):
    """
    Verifica horário, checa se cliente respondeu,
    gera mensagem com IA e envia.
    """
    # Verifica se cliente respondeu desde o agendamento
    try:
        from app.services.crm_service import get_conversation_history
        history = get_conversation_history(phone, limit=2)
        if history and history[-1]["role"] == "user":
            logger.info(f"[FOLLOWUP] {phone} — cliente respondeu, cancelando {label}")
            return
    except Exception:
        pass

    # Verifica se ainda está no estado (não foi cancelado)
    with _lock:
        if phone not in _state:
            return

    # Verifica horário comercial
    now = datetime.now(TZ)
    slot = _next_business_slot(now)

    if slot > now:
        wait = (slot - now).total_seconds()
        logger.info(f"[FOLLOWUP] {phone} — fora do horário, aguardando {wait/60:.0f}min")
        t = threading.Timer(wait, lambda: _fire_followup(phone, sequence_number, label))
        t.daemon = True
        t.start()
        with _lock:
            if phone in _state:
                _state[phone]["timers"].append(t)
        return

    # Gera e envia
    message = _generate_followup_message(phone, sequence_number)
    _send_whatsapp(phone, message)


def _schedule_one(phone: str, delay_seconds: float, sequence_number: int, label: str):
    """Agenda um único follow-up."""
    t = threading.Timer(
        delay_seconds,
        _fire_followup,
        args=[phone, sequence_number, label]
    )
    t.daemon = True
    t.start()
    return t


def schedule(phone: str):
    """Agenda sequência completa de follow-up para o cliente."""
    cancel(phone)

    now = datetime.now(TZ)
    timers = []

    # 1 — 30min
    timers.append(_schedule_one(phone, 30 * 60, 1, "30min"))

    # 2 — +2h (2h30 total)
    timers.append(_schedule_one(phone, 150 * 60, 2, "2h30"))

    # 3 — +4h (6h30 total)
    timers.append(_schedule_one(phone, 390 * 60, 3, "6h30"))

    # 4 — 24h após primeira mensagem
    with _lock:
        first_msg_at = _state.get(phone, {}).get("first_message_at", now)

    target = first_msg_at + timedelta(hours=24)
    delay_24h = max(60, (target - now).total_seconds())  # mínimo 1min
    timers.append(_schedule_one(phone, delay_24h, 4, "24h"))

    with _lock:
        first_at = _state.get(phone, {}).get("first_message_at", now)
        _state[phone] = {
            "timers": timers,
            "first_message_at": first_at,
        }

    logger.info(f"[FOLLOWUP] Sequência agendada para {phone}: 30min / 2h30 / 6h30 / 24h")


def cancel(phone: str):
    """Cancela todos os follow-ups do cliente."""
    with _lock:
        entry = _state.pop(phone, None)
    if entry:
        for t in entry.get("timers", []):
            t.cancel()
        logger.info(f"[FOLLOWUP] Cancelados para {phone}")


def register_first_message(phone: str):
    """Registra o momento da primeira mensagem para o timer de 24h."""
    with _lock:
        if phone not in _state:
            _state[phone] = {}
        if "first_message_at" not in _state[phone]:
            _state[phone]["first_message_at"] = datetime.now(TZ)
            logger.info(f"[FOLLOWUP] Primeira mensagem registrada: {phone}")


def is_active(phone: str) -> bool:
    with _lock:
        return phone in _state
