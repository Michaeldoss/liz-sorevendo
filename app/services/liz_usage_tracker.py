"""
Rastreamento de custo de API — Liz Bot (So Revendo)
───────────────────────────────────────────────────
Adaptado da mesma logica usada no Bruno IA (Doss Group), ajustado para
a arquitetura sincrona da Liz e o modelo Opus 4.5.
"""

import logging
from app.models.database import SessionLocal, UsageLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PRECOS — Anthropic (USD por milhao de tokens), Junho/2026
# ---------------------------------------------------------------------------
PRECOS_ANTHROPIC = {
    "claude-opus-4-5": {
        "input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50,
    },
}

# ---------------------------------------------------------------------------
# PRECOS — Twilio WhatsApp (USD por mensagem, Brasil)
# ---------------------------------------------------------------------------
PRECO_TWILIO_MSG_USD = 0.0085

# ---------------------------------------------------------------------------
# CUSTOS FIXOS MENSAIS — ajustar conforme o plano real da Liz
# ---------------------------------------------------------------------------
CUSTOS_FIXOS_MENSAIS_USD = {
    "render": 7.00,
    "supabase": 0.00,   # ajustar se o plano Supabase for pago
    "github": 0.00,
}


def calcular_custo_anthropic(model: str, input_tokens: int, output_tokens: int,
                              cache_creation_tokens: int = 0, cache_read_tokens: int = 0) -> float:
    precos = PRECOS_ANTHROPIC.get(model)
    if not precos:
        logger.warning(f"[USAGE] Modelo Anthropic desconhecido: {model}")
        return 0.0
    custo = (
        (input_tokens / 1_000_000) * precos["input"] +
        (output_tokens / 1_000_000) * precos["output"] +
        (cache_creation_tokens / 1_000_000) * precos["cache_write"] +
        (cache_read_tokens / 1_000_000) * precos["cache_read"]
    )
    return round(custo, 6)


def registrar_uso_anthropic(model: str, usage, agente: str = "liz"):
    """Registra uso de tokens Claude. Nunca quebra o fluxo principal (falha silenciosa)."""
    db = None
    try:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

        custo = calcular_custo_anthropic(model, input_tokens, output_tokens, cache_creation, cache_read)

        db = SessionLocal()
        db.add(UsageLog(
            agente=agente,
            servico="anthropic",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
            quantidade=0,
            custo_usd=custo,
        ))
        db.commit()
    except Exception as e:
        logger.error(f"[USAGE] Erro ao registrar uso Anthropic (nao bloqueante): {e}")
    finally:
        if db:
            db.close()


def registrar_uso_twilio(agente: str = "liz", quantidade_mensagens: int = 1):
    """Registra envio de mensagem(ns) via Twilio WhatsApp."""
    db = None
    try:
        custo = round(PRECO_TWILIO_MSG_USD * quantidade_mensagens, 6)
        db = SessionLocal()
        db.add(UsageLog(
            agente=agente,
            servico="twilio",
            model="whatsapp",
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            quantidade=quantidade_mensagens,
            custo_usd=custo,
        ))
        db.commit()
    except Exception as e:
        logger.error(f"[USAGE] Erro ao registrar uso Twilio (nao bloqueante): {e}")
    finally:
        if db:
            db.close()
