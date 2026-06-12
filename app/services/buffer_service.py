"""
buffer_service.py — Agrupa mensagens rápidas do mesmo cliente antes de responder.
Evita que a Liz responda fragmentos de mensagem separadamente.
So Revendo / Liz Bot
"""

import threading
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

BUFFER_WINDOW_SECONDS = 3.0  # aguarda 3s de silêncio antes de liberar


class BufferService:
    """
    Buffer por telefone: acumula mensagens e libera após janela de silêncio.
    Thread-safe com Lock por cliente.
    """

    def __init__(self, window_seconds: float = BUFFER_WINDOW_SECONDS):
        self.window = window_seconds
        self._buffers: dict[str, list[str]] = defaultdict(list)
        self._timers: dict[str, threading.Timer] = {}
        self._ready: dict[str, bool] = defaultdict(bool)
        self._lock = threading.Lock()

    def add_message(self, phone: str, message: str) -> bool:
        """
        Adiciona mensagem ao buffer do cliente.
        Reinicia o timer de janela a cada nova mensagem.

        Returns:
            True se o buffer está pronto para ser processado (timer expirou).
            False se ainda está acumulando.
        """
        with self._lock:
            self._buffers[phone].append(message)
            self._ready[phone] = False

            # Cancela timer anterior se existir
            if phone in self._timers and self._timers[phone].is_alive():
                self._timers[phone].cancel()

            # Cria novo timer
            timer = threading.Timer(self.window, self._mark_ready, args=[phone])
            self._timers[phone] = timer
            timer.start()

        # Aguarda brevemente e verifica se o timer já disparou
        time.sleep(self.window + 0.1)

        with self._lock:
            return self._ready.get(phone, False)

    def _mark_ready(self, phone: str):
        with self._lock:
            self._ready[phone] = True
            logger.debug(f"[BUFFER] Buffer de {phone} marcado como pronto.")

    def flush(self, phone: str) -> str | None:
        """
        Retorna todas as mensagens do buffer concatenadas e limpa o estado.
        """
        with self._lock:
            messages = self._buffers.pop(phone, [])
            self._ready.pop(phone, None)
            if phone in self._timers:
                self._timers[phone].cancel()
                del self._timers[phone]

        if not messages:
            return None

        combined = " ".join(messages)
        logger.info(f"[BUFFER] Flush de {phone}: {len(messages)} mensagem(ns) → '{combined[:80]}'")
        return combined

    def is_ready(self, phone: str) -> bool:
        with self._lock:
            return self._ready.get(phone, False)
