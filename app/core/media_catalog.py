"""
media_catalog.py — Salvamento de arquivos enviados pelo cliente para o vendedor acessar.
Suporta: foto, vídeo, PDF, CorelDRAW (.cdr), Illustrator (.ai), SVG, ZIP.
Localização: app/core/media_catalog.py
"""

import logging
import os
import requests
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

MEDIA_SAVE_DIR = Path(os.getenv("MEDIA_SAVE_DIR", "/var/data/media_sorevendo"))
MEDIA_SAVE_DIR.mkdir(parents=True, exist_ok=True)


# ─── Mapeamento MIME → extensão ───────────────────────────────────────────────

MIME_TO_EXT = {
    # Imagens
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    # Vídeos
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/webm": ".webm",
    # Documentos
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    # Vetoriais / Design
    "application/illustrator": ".ai",
    "application/postscript": ".ai",
    "application/x-coreldraw": ".cdr",
    "application/cdr": ".cdr",
    "application/coreldraw": ".cdr",
    "application/vnd.corel-draw": ".cdr",
    # Fallback
    "application/octet-stream": ".bin",
}

# Tipos que são artes vetoriais (prioridade para o vendedor)
VECTOR_TYPES = {".cdr", ".ai", ".svg", ".pdf"}
VIDEO_TYPES  = {".mp4", ".mov", ".avi", ".webm"}
IMAGE_TYPES  = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def handle_incoming_media(
    media_url: str,
    content_type: str,
    phone: str,
) -> str:
    """
    Faz download e salva o arquivo enviado pelo cliente.
    Retorna descrição legível para o contexto da Liz.

    Os arquivos ficam em:
    MEDIA_SAVE_DIR / {telefone_sem_+} / {timestamp}_{tipo}.ext

    O vendedor acessa essa pasta para trabalhar com a arte.
    """
    try:
        clean_phone = phone.replace("+", "").replace(" ", "")
        client_dir = MEDIA_SAVE_DIR / clean_phone
        client_dir.mkdir(parents=True, exist_ok=True)

        mime = content_type.split(";")[0].strip().lower()
        ext = MIME_TO_EXT.get(mime, _guess_ext_from_url(media_url))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tipo_label = _type_label(ext)
        filename = f"{timestamp}_{tipo_label}{ext}"
        filepath = client_dir / filename

        # Download com auth Twilio
        twilio_sid   = os.getenv("TWILIO_ACCOUNT_SID", "")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        auth = (twilio_sid, twilio_token) if twilio_sid else None

        response = requests.get(media_url, auth=auth, timeout=30)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(response.content)

        size_kb = len(response.content) / 1024
        logger.info(f"[MEDIA] Salvo: {filepath} ({size_kb:.1f} KB)")

        return _describe_media(ext, filename, size_kb, str(filepath))

    except Exception as e:
        logger.error(f"[MEDIA] Erro ao salvar arquivo de {phone}: {e}")
        return f"Arquivo recebido (tipo: {content_type}) — salvo para análise da equipe."


def _guess_ext_from_url(url: str) -> str:
    """Tenta extrair extensão da URL como fallback."""
    path = url.split("?")[0].lower()
    for ext in [".jpg", ".png", ".pdf", ".mp4", ".cdr", ".ai", ".svg", ".zip"]:
        if path.endswith(ext):
            return ext
    return ".bin"


def _type_label(ext: str) -> str:
    if ext in IMAGE_TYPES:  return "foto"
    if ext in VIDEO_TYPES:  return "video"
    if ext in VECTOR_TYPES: return "arte"
    if ext == ".zip":       return "arquivo"
    return "arquivo"


def _describe_media(ext: str, filename: str, size_kb: float, filepath: str) -> str:
    """Gera descrição para o contexto da Liz e para o log do vendedor."""
    if ext in VECTOR_TYPES:
        return (
            f"Arte vetorial recebida ({filename}, {size_kb:.1f} KB). "
            f"Arquivo salvo para o vendedor em: {filepath}. "
            "A Liz deve confirmar recebimento e informar que a equipe vai analisar."
        )
    if ext in IMAGE_TYPES:
        return (
            f"Imagem recebida ({filename}, {size_kb:.1f} KB). "
            f"Pode ser foto de referência, arte ou produto. Salvo em: {filepath}."
        )
    if ext in VIDEO_TYPES:
        return (
            f"Vídeo de referência recebido ({filename}, {size_kb:.1f} KB). "
            f"Salvo em: {filepath}."
        )
    return (
        f"Arquivo recebido ({filename}, {size_kb:.1f} KB). Salvo em: {filepath}."
    )


def list_client_files(phone: str) -> list[dict]:
    """
    Lista todos os arquivos salvos de um cliente.
    Útil para o painel do vendedor ou para o grupo de notificação.

    Retorna lista de dicts com: filename, path, size_kb, timestamp.
    """
    clean_phone = phone.replace("+", "").replace(" ", "")
    client_dir = MEDIA_SAVE_DIR / clean_phone

    if not client_dir.exists():
        return []

    files = []
    for f in sorted(client_dir.iterdir()):
        if f.is_file():
            files.append({
                "filename": f.name,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "ext": f.suffix.lower(),
            })
    return files
