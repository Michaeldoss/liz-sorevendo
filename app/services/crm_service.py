"""
crm_service.py — CRM da Liz usando Supabase.
Localização: app/services/crm_service.py
"""

import logging
import os
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Preço base por m²
PRECO_POR_M2 = 1300.00
ACRESCIMO_ESTRELA = 1.50  # por peça


def _get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ─── CLIENTES ────────────────────────────────────────────────────────────────

def get_or_create_customer(phone: str, name: str = "", source: str = "") -> dict:
    """Busca cliente ou cria novo. Retorna dict com dados."""
    try:
        sb = _get_client()
        res = sb.table("customers").select("*").eq("phone", phone).execute()

        if res.data:
            customer = res.data[0]
            # Atualiza nome se chegou novo
            if name and not customer.get("name"):
                sb.table("customers").update({"name": name, "updated_at": "NOW()"}).eq("phone", phone).execute()
                customer["name"] = name
            return customer

        # Cria novo
        novo = {"phone": phone, "name": name, "source": source, "status": "novo"}
        res = sb.table("customers").insert(novo).execute()
        logger.info(f"[CRM] Novo cliente: {phone} ({name})")
        return res.data[0] if res.data else novo

    except Exception as e:
        logger.error(f"[CRM] Erro ao buscar/criar cliente {phone}: {e}")
        return {"phone": phone, "name": name, "source": source, "status": "novo"}


def update_customer(phone: str, **kwargs):
    """Atualiza campos do cliente."""
    allowed = {"name", "source", "status", "notes"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    try:
        _get_client().table("customers").update(fields).eq("phone", phone).execute()
    except Exception as e:
        logger.error(f"[CRM] Erro ao atualizar cliente {phone}: {e}")


def count_messages_today(phone: str) -> int:
    """Conta mensagens do cliente hoje — para enriquecer notificação."""
    try:
        res = _get_client().table("messages") \
            .select("id", count="exact") \
            .eq("phone", phone) \
            .gte("created_at", "NOW() - INTERVAL '1 day'") \
            .execute()
        return res.count or 0
    except Exception as e:
        logger.error(f"[CRM] Erro ao contar mensagens: {e}")
        return 0


# ─── MENSAGENS ───────────────────────────────────────────────────────────────

def save_message(phone: str, role: str, content: str):
    try:
        _get_client().table("messages").insert({
            "phone": phone, "role": role, "content": content
        }).execute()
    except Exception as e:
        logger.error(f"[CRM] Erro ao salvar mensagem: {e}")


def get_conversation_history(phone: str, limit: int = 30) -> list[dict]:
    try:
        res = _get_client().table("messages") \
            .select("role, content") \
            .eq("phone", phone) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return list(reversed(res.data)) if res.data else []
    except Exception as e:
        logger.error(f"[CRM] Erro ao buscar histórico: {e}")
        return []


# ─── PEDIDOS ─────────────────────────────────────────────────────────────────

def calcular_valor(tamanho: str, quantidade: int, tem_estrelas: bool = False) -> float:
    """
    Calcula valor estimado do patch.
    tamanho: string como '8x6', '10cm', '8x6cm'
    Retorna valor total ou 0 se não conseguir calcular.
    """
    try:
        # Tenta extrair dimensões do tamanho
        import re
        nums = re.findall(r'\d+\.?\d*', tamanho.replace(',', '.'))
        if len(nums) >= 2:
            largura, altura = float(nums[0]), float(nums[1])
        elif len(nums) == 1:
            # Assume quadrado
            largura = altura = float(nums[0])
        else:
            return 0

        area_cm2 = largura * altura
        area_m2 = area_cm2 / 10000
        valor_base = area_m2 * PRECO_POR_M2 * quantidade

        if tem_estrelas:
            valor_base += ACRESCIMO_ESTRELA * quantidade

        return round(valor_base, 2)
    except Exception:
        return 0


def create_order(phone: str, **kwargs) -> dict:
    """Cria orçamento/pedido. Retorna o registro criado."""
    try:
        quantidade_str = kwargs.get("quantidade", "")
        tamanho = kwargs.get("tamanho", "")
        tem_estrelas = kwargs.get("tem_estrelas", False)

        # Tenta extrair número de quantidade
        import re
        qtd_nums = re.findall(r'\d+', quantidade_str)
        qtd_int = int(qtd_nums[0]) if qtd_nums else 0

        valor = calcular_valor(tamanho, qtd_int, tem_estrelas) if qtd_int and tamanho else 0

        record = {
            "phone": phone,
            "produto": "Patch 3D",
            "quantidade": quantidade_str,
            "tamanho": tamanho,
            "tem_estrelas": tem_estrelas,
            "valor_estimado": valor,
            "valor_entrada": round(valor * 0.5, 2),
            "status": kwargs.get("status", "orcamento"),
            "arte_status": kwargs.get("arte_status", "aguardando"),
            "obs": kwargs.get("obs", ""),
        }

        res = _get_client().table("orders").insert(record).execute()
        logger.info(f"[CRM] Pedido criado para {phone}: R${valor}")
        return res.data[0] if res.data else record

    except Exception as e:
        logger.error(f"[CRM] Erro ao criar pedido: {e}")
        return {}


def get_orders(phone: str) -> list[dict]:
    try:
        res = _get_client().table("orders") \
            .select("*") \
            .eq("phone", phone) \
            .order("created_at", desc=True) \
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"[CRM] Erro ao buscar pedidos: {e}")
        return []


def update_order_status(order_id: int, status: str):
    try:
        _get_client().table("orders").update({"status": status}).eq("id", order_id).execute()
    except Exception as e:
        logger.error(f"[CRM] Erro ao atualizar pedido #{order_id}: {e}")
