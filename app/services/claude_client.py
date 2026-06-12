"""
claude_client.py — Cliente Anthropic para a Liz (So Revendo)
Localização: app/services/claude_client.py
"""

import anthropic
import logging
from app.core.prompt import LIZ_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY do ambiente

MODEL = "claude-opus-4-5"
MAX_TOKENS = 1024


def build_system_prompt(customer_context: dict, conversation_history: list[dict]) -> str:
    history_text = ""
    if conversation_history:
        lines = []
        for msg in conversation_history[-20:]:
            role = "Cliente" if msg["role"] == "user" else "Liz"
            lines.append(f"{role}: {msg['content']}")
        history_text = "\n".join(lines)
    else:
        history_text = "Nenhum histórico anterior."

    context_text = ""
    if customer_context:
        context_text = (
            f"Nome: {customer_context.get('name', 'Não informado')}\n"
            f"Telefone: {customer_context.get('phone', 'Não informado')}\n"
            f"Canal de origem: {customer_context.get('source', 'Não informado')}\n"
            f"Pedidos anteriores: {customer_context.get('orders', 'Nenhum')}\n"
            f"Observações: {customer_context.get('notes', 'Nenhuma')}"
        )
    else:
        context_text = "Novo cliente — sem histórico no CRM."

    return LIZ_SYSTEM_PROMPT.format(
        customer_context=context_text,
        conversation_history=history_text,
    )


def get_liz_response(
    user_message: str,
    customer_context: dict = None,
    conversation_history: list[dict] = None,
    media_descriptions: list[str] = None,
) -> str:
    customer_context = customer_context or {}
    conversation_history = conversation_history or []
    media_descriptions = media_descriptions or []

    system_prompt = build_system_prompt(customer_context, conversation_history)

    content_parts = []
    if media_descriptions:
        media_text = "O cliente enviou os seguintes arquivos/mídias:\n" + "\n".join(
            f"- {desc}" for desc in media_descriptions
        )
        content_parts.append({"type": "text", "text": media_text})
    content_parts.append({"type": "text", "text": user_message})

    messages_for_api = []
    for msg in conversation_history[-10:]:
        messages_for_api.append({"role": msg["role"], "content": msg["content"]})

    messages_for_api.append({
        "role": "user",
        "content": content_parts if len(content_parts) > 1 else user_message,
    })

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages_for_api,
        )
        reply = response.content[0].text.strip()
        logger.info(f"[LIZ] Resposta gerada para {customer_context.get('phone', 'unknown')}: {reply[:80]}...")
        return reply

    except anthropic.APIStatusError as e:
        logger.error(f"[LIZ] Erro na API Anthropic: {e.status_code} — {e.message}")
        return "Oi! Tive um probleminha aqui, mas já estou resolvendo. Pode me mandar sua mensagem de novo? 😊"

    except anthropic.APIConnectionError:
        logger.error("[LIZ] Erro de conexão com a API Anthropic.")
        return "Ops, problema de conexão! Tenta de novo em instantes. 🙏"
