"""
followup_service.py — Follow-up automático de leads da So Revendo
Localização: app/services/followup_service.py
"""

import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

FOLLOWUP_SEQUENCE = [
    {
        "delay_hours": 2,
        "message": (
            "Oi! 😊 Só passando para ver se ficou alguma dúvida sobre o orçamento que te enviei. "
            "Posso ajudar com mais alguma informação?"
        ),
    },
    {
        "delay_hours": 24,
        "message": (
            "Oi, tudo bem? 🎨 Aqui é a Liz, da So Revendo. "
            "Queria saber se você conseguiu avaliar nossa proposta — "
            "estamos prontos pra colocar seu pedido em produção assim que precisar!"
        ),
    },
    {
        "delay_hours": 72,
        "message": (
            "Olá! 👋 Última mensagem por aqui — não quero encher sua caixa! "
            "Se precisar de adesivos, lonas, DTF, patch 3D, wind banner ou bandeiras, "
            "é só chamar. Estarei aqui! 😊 — Liz, So Revendo."
        ),
    },
]


class FollowUpService:
    def __init__(self, send_fn: Callable[[str, str], None]):
        self.send_fn = send_fn
        self._active_timers: dict[str, list[threading.Timer]] = {}
        self._lock = threading.Lock()

    def schedule(self, phone: str, customer_name: str = ""):
        self.cancel(phone)
        timers = []
        for step in FOLLOWUP_SEQUENCE:
            delay_seconds = step["delay_hours"] * 3600
            timer = threading.Timer(
                delay_seconds,
                self._send_followup,
                args=[phone, step["message"], customer_name],
            )
            timer.daemon = True
            timer.start()
            timers.append(timer)
            logger.info(f"[FOLLOWUP] Agendado para {phone} em {step['delay_hours']}h")

        with self._lock:
            self._active_timers[phone] = timers

    def cancel(self, phone: str):
        with self._lock:
            timers = self._active_timers.pop(phone, [])
        for timer in timers:
            timer.cancel()
        if timers:
            logger.info(f"[FOLLOWUP] Cancelados {len(timers)} timers para {phone}")

    def _send_followup(self, phone: str, message: str, customer_name: str):
        try:
            personalized = message
            if customer_name:
                first = customer_name.split()[0]
                personalized = f"{first}, " + message[0].lower() + message[1:]
            self.send_fn(phone, personalized)
            logger.info(f"[FOLLOWUP] Enviado para {phone}")
        except Exception as e:
            logger.error(f"[FOLLOWUP] Erro ao enviar para {phone}: {e}")


def make_twilio_sender(account_sid: str, auth_token: str, from_number: str) -> Callable:
    """
    Cria função de envio via Twilio para injetar no FollowUpService.

    Uso em main.py ou onde o app for inicializado:
        from app.services.followup_service import FollowUpService, make_twilio_sender
        sender = make_twilio_sender(SID, TOKEN, "whatsapp:+5511999999999")
        followup = FollowUpService(send_fn=sender)
    """
    from twilio.rest import Client as TwilioClient
    twilio = TwilioClient(account_sid, auth_token)

    def send(phone: str, message: str):
        twilio.messages.create(
            from_=from_number,
            to=f"whatsapp:{phone}",
            body=message,
        )

    return send
