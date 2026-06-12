"""
media_catalog.py — Recebimento de mídias enviadas pelo cliente.
Sem salvamento local — Cloudinary será integrado futuramente.
Localização: app/core/media_catalog.py
"""

MIME_TO_TYPE = {
    "image/jpeg": "imagem",
    "image/jpg": "imagem",
    "image/png": "imagem",
    "image/webp": "imagem",
    "image/svg+xml": "arquivo vetorial",
    "video/mp4": "vídeo",
    "video/quicktime": "vídeo",
    "application/pdf": "PDF",
    "application/zip": "arquivo ZIP",
    "application/illustrator": "arquivo AI (Illustrator)",
    "application/postscript": "arquivo AI (Illustrator)",
    "application/x-coreldraw": "arquivo CorelDRAW",
    "application/cdr": "arquivo CorelDRAW",
    "application/coreldraw": "arquivo CorelDRAW",
    "application/vnd.corel-draw": "arquivo CorelDRAW",
}


def handle_incoming_media(
    media_url: str,
    content_type: str,
    phone: str,
) -> str:
    """
    Processa notificação de mídia recebida pelo cliente.
    Retorna descrição para o contexto da Liz.
    Salvamento físico será implementado com Cloudinary.
    """
    mime = content_type.split(";")[0].strip().lower()
    tipo = MIME_TO_TYPE.get(mime, "arquivo")

    return (
        f"O cliente enviou um {tipo} como arte ou referência. "
        "Confirmar recebimento e informar que a equipe vai analisar."
    )


def list_client_files(phone: str) -> list:
    """Placeholder — será implementado com Cloudinary."""
    return []
