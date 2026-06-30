"""
main.py — Entry point da Liz Bot (So Revendo)
FastAPI + Twilio + Claude (Anthropic)
"""

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.webhooks import router as whatsapp_router
from app.api.usage_router import router as usage_router

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("liz_bot")

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Liz Bot — So Revendo",
    description="Assistente comercial WhatsApp para a gráfica So Revendo.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router)
app.include_router(usage_router)


@app.on_event("startup")
async def on_startup():
    logger.info("🚀 Liz Bot iniciada — So Revendo está online!")
    required_vars = ["ANTHROPIC_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.warning(f"⚠️  Variáveis de ambiente ausentes: {', '.join(missing)}")
    else:
        logger.info("✅ Todas as variáveis de ambiente configuradas.")
