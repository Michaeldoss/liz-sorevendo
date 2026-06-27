"""
shipping_service.py — Frete via melhor-envio.onrender.com (endpoint /api/quote correto).
Localização: app/services/shipping_service.py
"""

import re
import json
import logging
import requests

logger = logging.getLogger(__name__)

FREIGHT_API_URL        = "https://melhor-envio.onrender.com"
ORIGIN_CEP             = "89226435"   # So Revendo — Joinville SC
CNPJ_REQUIRED_CARRIERS = {"arlete", "expresso", "são miguel", "sao miguel", "ssw"}

CEP_RE  = re.compile(r'\b(\d{5})-?(\d{3})\b')
CNPJ_RE = re.compile(r'\b\d{2}[\.\-]?\d{3}[\.\-]?\d{3}[\/\-]?\d{4}[\-]?\d{2}\b')
CPF_RE  = re.compile(r'\b\d{3}[\.\-]?\d{3}[\.\-]?\d{3}[\-]?\d{2}\b')


# ─── Detecção ─────────────────────────────────────────────────────────────────

def extract_cep(text: str) -> str | None:
    m = CEP_RE.search(text)
    return (m.group(1) + m.group(2)) if m else None


def extract_document(text: str) -> dict:
    if CNPJ_RE.search(text):
        return {"type": "cnpj", "value": re.sub(r'\D', '', CNPJ_RE.search(text).group())}
    if CPF_RE.search(text):
        return {"type": "cpf",  "value": re.sub(r'\D', '', CPF_RE.search(text).group())}
    return {"type": None, "value": None}


def has_cnpj(text: str) -> bool:
    return bool(CNPJ_RE.search(text))


# ─── Embalagem ────────────────────────────────────────────────────────────────

def get_product_packages(product: dict) -> list[dict]:
    """
    Retorna lista de embalagens do produto.
    Usa dimensões cadastradas no painel (pkg_*).
    Se multi_package=True, usa packages_json.
    """
    if product.get("multi_package") and product.get("packages_json"):
        try:
            pkgs = json.loads(product["packages_json"])
            if pkgs:
                return pkgs
        except Exception:
            pass

    # Fallback: dimensões do produto ou padrão mínimo
    return [{
        "label":     product.get("name", "Pacote"),
        "weight_kg": float(product.get("pkg_weight_kg") or 0.3),
        "height_cm": int(product.get("pkg_height_cm") or 5),
        "width_cm":  int(product.get("pkg_width_cm")  or 20),
        "length_cm": int(product.get("pkg_length_cm") or 20),
    }]


def build_package_description(product: dict) -> str:
    """Texto descritivo de embalagem para o prompt da Liz."""
    pkgs = get_product_packages(product)
    name = product.get("name", "Produto")
    if len(pkgs) == 1:
        p = pkgs[0]
        return (
            f"{name}: 1 embalagem — "
            f"{p['weight_kg']}kg, {p['height_cm']}×{p['width_cm']}×{p['length_cm']}cm. "
            f"{product.get('pkg_notes','')}"
        )
    lines = [f"{name}: {len(pkgs)} embalagens separadas:"]
    for i, p in enumerate(pkgs, 1):
        lines.append(
            f"  Caixa {i} ({p.get('label','')}) — "
            f"{p['weight_kg']}kg, {p['height_cm']}×{p['width_cm']}×{p['length_cm']}cm"
        )
    if product.get("pkg_notes"):
        lines.append(f"  Obs: {product['pkg_notes']}")
    return "\n".join(lines)


def build_packaging_prompt_section(products: list[dict]) -> str:
    """Seção de embalagem para o system prompt da Liz."""
    lines_com_dim = [p for p in products if p.get("pkg_weight_kg") or p.get("packages_json")]
    if not lines_com_dim:
        return ""
    lines = [
        "━━━━━━━━━━━━━━━━━━━",
        "EMBALAGEM E FRETE",
        "━━━━━━━━━━━━━━━━━━━",
        "Origem: Joinville SC — CEP 89226-435",
        "",
        "Dimensões por produto:",
    ]
    for p in lines_com_dim:
        lines.append(build_package_description(p))
    lines += [
        "",
        "Transportadoras:",
        "- Melhor Envio (Total Express, Jadlog, Correios, Azul, etc.): CPF ou CNPJ",
        "- Expresso São Miguel / Arlete: apenas clientes com CNPJ",
        "",
        "Regras de frete:",
        "- Peça o CEP quando o cliente estiver próximo de fechar",
        "- O sistema cota automaticamente ao receber o CEP",
        "- NUNCA invente valores — aguarde a cotação automática",
        "- Se o cliente não tiver CNPJ: informar que as opções são via Melhor Envio",
    ]
    return "\n".join(lines)


# ─── Cotação ──────────────────────────────────────────────────────────────────

def _call_api(payload: dict) -> list[dict]:
    """Chama /api/quote e retorna lista de opções disponíveis."""
    try:
        r = requests.post(
            f"{FREIGHT_API_URL}/api/quote",
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()

        options = data.get("available_options", [])
        return [
            {
                "carrier":  q.get("company_name", ""),
                "service":  q.get("service_name", ""),
                "price":    float(q.get("price", 0)),
                "deadline": q.get("delivery_label", "—"),
                "provider": q.get("provider", ""),
            }
            for q in options
            if not q.get("error") and q.get("price")
        ]
    except requests.Timeout:
        logger.error("[FRETE] Timeout na API")
        return []
    except Exception as e:
        logger.error(f"[FRETE] Erro: {e}")
        return []


def quote_freight(
    to_cep: str,
    product: dict = None,
    declared_value: float = 100.0,
    client_has_cnpj: bool = False,
    recipient_doc: str = "",
) -> list[dict]:
    """
    Cota frete usando dimensões reais do produto cadastrado.
    Suporta multi-pacote (soma fretes por transportadora).
    Filtra transportadoras que exigem CNPJ se cliente não tem.
    """
    pkgs = get_product_packages(product) if product else [{
        "weight_kg": 0.3, "height_cm": 5, "width_cm": 20, "length_cm": 20
    }]

    if len(pkgs) == 1:
        p = pkgs[0]
        payload = {
            "from_postal_code": ORIGIN_CEP,
            "to_postal_code":   to_cep.replace("-", ""),
            "insurance_value":  declared_value,
            "recipient_doc":    recipient_doc,
            "receipt":  False,
            "own_hand": False,
            "custom_volumes": [{
                "height":   int(p.get("height_cm", p.get("pkg_height_cm", 5))),
                "width":    int(p.get("width_cm",  p.get("pkg_width_cm",  20))),
                "length":   int(p.get("length_cm", p.get("pkg_length_cm", 20))),
                "weight":   float(p.get("weight_kg", p.get("pkg_weight_kg", 0.3))),
                "quantity": 1,
            }],
        }
        quotes = _call_api(payload)

    else:
        # Multi-pacote: cota cada caixa e soma por transportadora
        combined: dict[str, dict] = {}
        for pkg in pkgs:
            payload = {
                "from_postal_code": ORIGIN_CEP,
                "to_postal_code":   to_cep.replace("-", ""),
                "insurance_value":  round(declared_value / len(pkgs), 2),
                "recipient_doc":    recipient_doc,
                "receipt": False, "own_hand": False,
                "custom_volumes": [{
                    "height":   int(pkg.get("height_cm", 5)),
                    "width":    int(pkg.get("width_cm",  20)),
                    "length":   int(pkg.get("length_cm", 20)),
                    "weight":   float(pkg.get("weight_kg", 0.3)),
                    "quantity": 1,
                }],
            }
            for q in _call_api(payload):
                key = f"{q['carrier']}|{q['service']}"
                if key in combined:
                    combined[key]["price"] += q["price"]
                else:
                    combined[key] = q.copy()
        quotes = list(combined.values())

    # Filtra transportadoras que exigem CNPJ
    if not client_has_cnpj:
        quotes = [
            q for q in quotes
            if not any(c in q["carrier"].lower() for c in CNPJ_REQUIRED_CARRIERS)
        ]

    quotes.sort(key=lambda x: x["price"])
    return quotes[:8]


# ─── Formatação ───────────────────────────────────────────────────────────────

def format_freight_message(quotes: list[dict], to_cep: str, num_packages: int = 1) -> str:
    if not quotes:
        return (
            f"Não consegui cotar o frete para o CEP {to_cep[:5]}-{to_cep[5:]} agora. "
            "Vou verificar e já te passo os valores! 🚚"
        )

    cep_fmt  = f"{to_cep[:5]}-{to_cep[5:]}"
    pkg_info = f" ({num_packages} volumes)" if num_packages > 1 else ""
    lines    = [f"Frete para {cep_fmt}{pkg_info}:\n"]

    for q in quotes:
        lines.append(f"• *{q['carrier']}* — {q['service']}: R$ {q['price']:.2f} ({q['deadline']})")

    lines.append("\nQual opção prefere?")
    return "\n".join(lines)
