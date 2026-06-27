"""
claude_client.py — Prompt dinâmico com conhecimento de embalagem e frete.
Localização: app/services/claude_client.py
"""

import anthropic
import logging
import os
import time
from supabase import create_client
from app.services.shipping_service import build_packaging_prompt_section

logger = logging.getLogger(__name__)
client = anthropic.Anthropic()
MODEL      = "claude-opus-4-5"
MAX_TOKENS = 1024
CACHE_TTL  = 60

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_cache     = None
_cache_ts  = 0


def _get_sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _load_config() -> dict:
    global _cache, _cache_ts
    now = time.time()
    if _cache and (now - _cache_ts) < CACHE_TTL:
        return _cache
    try:
        sb = _get_sb()
        _cache = {
            "config":   (sb.table("bot_config").select("*").limit(1).execute().data or [{}])[0],
            "products": sb.table("products").select("*, price_rules(*)").eq("active", True).order("sort_order").execute().data or [],
            "examples": sb.table("conversation_examples").select("*").eq("active", True).order("created_at").execute().data or [],
        }
        _cache_ts = now
        return _cache
    except Exception as e:
        logger.error(f"[CLAUDE] Erro config: {e}")
        return {"config": {}, "products": [], "examples": []}


def _build_products_section(products: list) -> str:
    if not products:
        return "Nenhum produto cadastrado."
    lines = []
    for p in products:
        unit  = p.get("price_unit", "unidade")
        label = p.get("price_label", "Preço")
        price = p.get("price_per_m2", 0)
        extras = []
        for r in (p.get("price_rules") or []):
            if r.get("active"):
                tipo = {"per_unit": "por unidade", "fixed": "fixo", "per_m2": f"por {unit}"}.get(r["extra_type"], "")
                extras.append(f"  • {r['description']}: +R${r['extra_cost']:.2f} {tipo}".strip())

        block = [f"▸ {p['name']}"]
        if p.get("sku"):          block.append(f"  Código: {p['sku']}")
        if p.get("description"):  block.append(f"  Descrição: {p['description']}")
        if p.get("technical_info"): block.append(f"  Técnico: {p['technical_info']}")
        if p.get("limitations"):  block.append(f"  Limitações: {p['limitations']}")
        if p.get("variations"):   block.append(f"  Variações: {p['variations']}")
        if p.get("stock_info"):   block.append(f"  Estoque: {p['stock_info']}")
        if price:                 block.append(f"  {label}: R$ {price:.2f}/{unit}")
        if p.get("min_quantity",1) > 1: block.append(f"  Mínimo: {p['min_quantity']} {unit}(s)")
        if p.get("production_days"): block.append(f"  Prazo: {p['production_days']}")
        if p.get("shipping_info"): block.append(f"  Envio: {p['shipping_info']}")
        if extras:                block.append("  Acréscimos:\n" + "\n".join(extras))
        if p.get("sales_rules"):  block.append(f"  Como vender: {p['sales_rules']}")
        if p.get("keywords"):     block.append(f"  Palavras-chave: {p['keywords']}")
        if p.get("faq"):          block.append(f"  FAQ:\n{p['faq']}")

        lines.append("\n".join(block))
    return "\n\n".join(lines)


def _build_prompt(customer_context: dict, conversation_history: list) -> str:
    data     = _load_config()
    cfg      = data.get("config", {})
    products = data.get("products", [])
    examples = data.get("examples", [])

    bot_name    = cfg.get("bot_name", "Assistente")
    company     = cfg.get("company_name", "a empresa")
    role        = cfg.get("bot_role", "consultor de vendas")
    tone        = cfg.get("bot_tone", "Profissional e simpático")
    opening     = cfg.get("opening_message", "Como posso ajudar?")
    payment     = cfg.get("payment_terms", "À combinar")
    extra_rules = cfg.get("rules", "")

    examples_text = ""
    for ex in examples:
        title = ex.get("title") or ex.get("context") or "Exemplo"
        examples_text += f"\n--- {title} ---\n{ex.get('conversation', '')}\n"

    history_text = "Nenhum histórico anterior."
    if conversation_history:
        history_text = "\n".join(
            f"{'Cliente' if m['role']=='user' else bot_name}: {m['content']}"
            for m in conversation_history[-20:]
        )

    ctx_text = (
        f"Nome: {customer_context.get('name','Não informado')}\n"
        f"Telefone: {customer_context.get('phone','')}\n"
        f"Origem: {customer_context.get('source','')}\n"
        f"Documento: {customer_context.get('doc_type','não informado')}\n"
        f"Observações: {customer_context.get('notes','')}"
    )

    # Seção de embalagem (só produtos com dimensões cadastradas)
    packaging_section = build_packaging_prompt_section(products)

    return f"""Você é {bot_name}, {role} da {company}.
Seu objetivo é conduzir o cliente até a compra de forma direta e natural.

━━━━━━━━━━━━━━━━━━━
IDENTIDADE
━━━━━━━━━━━━━━━━━━━
- Nome: {bot_name} | Empresa: {company}
- Tom: {tone}
- NUNCA diga que é uma IA.
- Emojis: máximo 1 por mensagem, nunca no início.

━━━━━━━━━━━━━━━━━━━
PORTFÓLIO
━━━━━━━━━━━━━━━━━━━
{_build_products_section(products)}

━━━━━━━━━━━━━━━━━━━
PAGAMENTO
━━━━━━━━━━━━━━━━━━━
{payment}

{packaging_section}

━━━━━━━━━━━━━━━━━━━
REGRAS DE VENDA
━━━━━━━━━━━━━━━━━━━
- NUNCA use "como posso ajudar"
- NUNCA dê preço sem qualificar o pedido
- SEMPRE conduza com perguntas
- Abertura padrão: "{opening}"
- Produto fora do portfólio: "No momento não trabalhamos com isso, mas posso te ajudar com [produto próximo]."
{extra_rules}

━━━━━━━━━━━━━━━━━━━
EXEMPLOS DE CONVERSA
━━━━━━━━━━━━━━━━━━━
{examples_text if examples_text else 'Nenhum exemplo cadastrado ainda.'}

━━━━━━━━━━━━━━━━━━━
CONTEXTO DO CLIENTE
━━━━━━━━━━━━━━━━━━━
{ctx_text}

━━━━━━━━━━━━━━━━━━━
HISTÓRICO
━━━━━━━━━━━━━━━━━━━
{history_text}"""


def get_liz_response(
    user_message: str,
    customer_context: dict = None,
    conversation_history: list = None,
    media_descriptions: list = None,
) -> str:
    customer_context     = customer_context or {}
    conversation_history = conversation_history or []
    media_descriptions   = media_descriptions or []

    system_prompt = _build_prompt(customer_context, conversation_history)

    content_parts = []
    if media_descriptions:
        content_parts.append({"type": "text", "text": "O cliente enviou:\n" + "\n".join(f"- {d}" for d in media_descriptions)})
    content_parts.append({"type": "text", "text": user_message})

    messages = [{"role": m["role"], "content": m["content"]} for m in conversation_history[-10:]]
    messages.append({"role": "user", "content": content_parts if len(content_parts) > 1 else user_message})

    try:
        resp = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=system_prompt, messages=messages)
        reply = resp.content[0].text.strip()
        logger.info(f"[BOT] {reply[:80]}...")
        return reply
    except anthropic.APIStatusError as e:
        logger.error(f"[BOT] API error: {e.status_code}")
        return "Oi! Tive um probleminha aqui. Pode mandar de novo? 😊"
    except anthropic.APIConnectionError:
        logger.error("[BOT] Conexão falhou")
        return "Ops, problema de conexão! Tenta de novo em instantes. 🙏"
