"""Claude CLI subprocess wrapper for RSA ad copy generation (Swedish + English).

Shells out to the locally-installed `claude` CLI in non-interactive mode
(`-p --output-format json --json-schema ...`). Authentication is whatever
session the user already has via Claude Code OAuth — no Anthropic API key.

Failure is non-fatal: every error path returns empty lists so the caller
in `ad_copy_generator` can top up with deterministic templates.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any

from src.models.catalog import Product
from src.models.client import ClientProfile, GeoTarget

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "haiku"
CLAUDE_TIMEOUT_SEC = 60
CLAUDE_MAX_BUDGET_USD = 0.10

MAX_HEADLINES = 15
MAX_DESCRIPTIONS = 4
HEADLINE_LIMIT = 30
DESCRIPTION_LIMIT = 90

_AD_COPY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headlines": {
            "type": "array",
            "items": {"type": "string", "maxLength": HEADLINE_LIMIT, "minLength": 1},
            "maxItems": MAX_HEADLINES,
        },
        "descriptions": {
            "type": "array",
            "items": {"type": "string", "maxLength": DESCRIPTION_LIMIT, "minLength": 1},
            "maxItems": MAX_DESCRIPTIONS,
        },
    },
    "required": ["headlines", "descriptions"],
    "additionalProperties": False,
}


def is_enabled() -> bool:
    """LLM enrichment runs unless SEM_DISABLE_LLM=1 or claude CLI is missing."""
    if os.getenv("SEM_DISABLE_LLM") == "1":
        return False
    return shutil.which("claude") is not None


def _format_product_context(product: Product) -> str:
    lines = [f"PRODUCT: {product.name} ({product.sku})"]
    for k, v in product.attributes.items():
        if v is None:
            continue
        if k == "discount_pct" and isinstance(v, (int, float)):
            pct = v * 100 if v <= 1 else v
            lines.append(f"DISCOUNT: {int(round(pct))}%")
        elif k.endswith("_price") or k == "price":
            lines.append(f"FROM PRICE: ${v}")
        else:
            lines.append(f"{k.upper()}: {v}")
    return "\n".join(lines)


def _build_prompt_sv(
    client: ClientProfile,
    theme: str,
    keywords: list[str],
    target_geo: GeoTarget | None,
    product: Product | None,
    variant_role: str | None = None,
) -> str:
    if target_geo is not None:
        geo_line = f"ORT: {target_geo.name} (annonsen visas endast i detta område)"
    else:
        cities = [g.name for g in client.geographic_targets[:3]] or ["Sverige"]
        geo_line = f"ORTER: {', '.join(cities)}"

    services = client.products_services[:5] or [theme]
    kw_sample = keywords[:10]
    voice = client.brand_voice.strip() or "Saklig, förtroendeingivande, konkret."
    product_block = _format_product_context(product) + "\n" if product else ""

    return (
        "Du är svensk Google Ads-copywriter. Skriv rubriker och beskrivningar för en "
        "Responsive Search Ad på svenska.\n\n"
        f"FÖRETAG: {client.business_name}\n"
        f"BRANSCH: {client.industry}\n"
        f"TJÄNSTER/PRODUKTER: {', '.join(services)}\n"
        f"ANNONSGRUPPSTEMA: {theme}\n"
        f"{product_block}"
        f"NYCKELORD: {', '.join(kw_sample)}\n"
        f"{geo_line}\n"
        f"VARUMÄRKESRÖST: {voice}\n\n"
        "REGLER:\n"
        f"- Svenska. Tilltala alltid med \"du\", aldrig \"ni\".\n"
        f"- Rubriker: max {HEADLINE_LIMIT} tecken vardera, åtgärdsdrivna, varierade.\n"
        f"- Beskrivningar: max {DESCRIPTION_LIMIT} tecken vardera, inkludera USP + CTA.\n"
        "- Prisformat: \"1 299 kr\" (mellanslag som tusentalsavgränsare).\n"
        "- Inga emojis. Inga superlativ som Google Ads förbjuder (\"bäst\", \"billigast\" "
        "utan bevis). Inga utropstecken i rubriker.\n"
        "- Undvik upprepningar. Variera vinklarna: pris, brådska, expertis, garanti, lokalt.\n\n"
        f"Returnera EXAKT denna JSON-struktur (inga kommentarer, ingen markdown):\n"
        f"{{\"headlines\": [...max {MAX_HEADLINES} strängar], "
        f"\"descriptions\": [...max {MAX_DESCRIPTIONS} strängar]}}"
    )


_VARIANT_PROMPTS: dict[str, dict[str, str]] = {
    "price_led": {
        "lever": "specificity + friction removal",
        "instruction": (
            "Lead with the FROM PRICE in at least 3 headlines. Anchor on the "
            "specific dollar number. Mention 'compare 800+ airlines' for proof. "
            "No vague price claims."
        ),
    },
    "discount_led": {
        "lever": "loss aversion + scarcity + specificity",
        "instruction": (
            "CRITICAL: at least 3 headlines AND at least 2 descriptions MUST "
            "include the literal discount percent (e.g. '38%'). Phrasings like "
            "'-38%', 'Save 38%', '38% off' are acceptable. Mention the percent "
            "LITERALLY. Do NOT use 'was full price' as an anchor — if you "
            "reference a before-price, use the concrete computed amount the "
            "generator injects (e.g. 'Was $480, now $299'). Cap repetition: "
            "no more than 5 of the 15 headlines may carry the percent — "
            "fill the rest with proof and friction-removal angles."
        ),
    },
    "social_proof": {
        "lever": "authority + social proof + risk reversal",
        "instruction": (
            "Use only REAL proof points: 800+ airlines, 1.5M+ travelers/year, "
            "Trustpilot 4.5/5, IATA-accredited, 24h free cancellation. "
            "DO NOT invent or imply ATOL, ABTA, or other UK/EU consumer "
            "protection schemes the agency is not under. No 'top-rated' or "
            "'best-in-class' adjective puffery. Include a refund/cancel mention."
        ),
    },
    "urgency": {
        "lever": "scarcity + friction removal",
        "instruction": (
            "Real urgency only. The OTA-specific differentiator is live "
            "pricing — 'fares update every hour', 'real-time airline "
            "inventory'. NO fake countdowns, NO 'Final seats', NO 'Last-minute' "
            "without genuine low-inventory data. Lead with the verb and "
            "destination."
        ),
    },
    "loss_aversion": {
        "lever": "loss aversion + pain",
        "instruction": (
            "Anchor on the cost of waiting: 'stop overpaying', 'prices rise "
            "weekly', 'don't pay full fare', 'skip the OTA markup', "
            "'Pay the airline price, not the markup'. Make the pain "
            "concrete. Keep CTA tied to seeing the real price."
        ),
    },
}


def _build_prompt_en(
    client: ClientProfile,
    theme: str,
    keywords: list[str],
    target_geo: GeoTarget | None,
    product: Product | None,
    variant_role: str | None = None,
) -> str:
    if target_geo is not None:
        geo_line = f"LOCATION: {target_geo.name} (ad only shown in this area)"
    else:
        cities = [g.name for g in client.geographic_targets[:3]] or ["worldwide"]
        geo_line = f"LOCATIONS: {', '.join(cities)}"

    services = client.products_services[:5] or [theme]
    kw_sample = keywords[:10]
    voice = client.brand_voice.strip() or "Confident, helpful, specific."
    product_block = _format_product_context(product) + "\n" if product else ""

    variant_block = ""
    if variant_role and variant_role in _VARIANT_PROMPTS:
        meta = _VARIANT_PROMPTS[variant_role]
        variant_block = (
            f"VARIANT ROLE: {variant_role}\n"
            f"LEVER STACK: {meta['lever']}\n"
            f"VARIANT INSTRUCTION: {meta['instruction']}\n\n"
        )

    return (
        "You are a senior English-language Google Ads copywriter for an OTA "
        "(online travel agency). Write Responsive Search Ad copy that beats "
        "Tier-2 agency output. Target the expert tier described in the "
        "sem-ad-copy skill: every headline earns its 30 chars on specificity, "
        "lever, or pattern interrupt — never adjective stacking.\n\n"
        f"COMPANY: {client.business_name}\n"
        f"INDUSTRY: {client.industry}\n"
        f"PRODUCTS/SERVICES: {', '.join(services)}\n"
        f"AD GROUP THEME: {theme}\n"
        f"{product_block}"
        f"KEYWORDS: {', '.join(kw_sample)}\n"
        f"{geo_line}\n"
        f"BRAND VOICE: {voice}\n\n"
        f"{variant_block}"
        "HARD RULES:\n"
        f"- English. Address the user as 'you'.\n"
        f"- Headlines: max {HEADLINE_LIMIT} characters each (count every char).\n"
        f"- Descriptions: max {DESCRIPTION_LIMIT} characters each, with USP + CTA.\n"
        "- Price format: '$1,299' with commas as thousand separators.\n"
        "- Banned phrases (auto-reject): best-in-class, world-class, "
        "industry-leading, top-rated (without source), 'top-rated travel agent', "
        "trusted partner, tailored / customized solutions, comprehensive "
        "solutions, hassle-free, look no further, get started today, "
        "contact us for a free quote, transform your X, take your X to the "
        "next level, passionate about, drive growth/results, unlock your "
        "potential, 'ATOL-style', 'ATOL-style protection', 'cheap flights' "
        "(literal phrase only — keyword 'cheap flights to {name}' is fine), "
        "'price drop alerts free' (Title-Case button label — write 'Free price "
        "drop alerts' instead), 'Was full price' (use a real computed anchor "
        "instead), 'Today only' (without a real deadline), 'Final seats', "
        "'Last-minute' (without real low-inventory data).\n"
        "- No exclamation marks in headlines. No em-dashes (U+2014). "
        "No hyphen-as-em-dash either: do not use ' - ' as a sentence pause; "
        "use ',' instead.\n"
        "- Avoid headline-to-headline repetition. Vary structure: "
        "fragment, number-led, verb-led, pain-led, question.\n"
        "- First-three-words doctrine: front-load keyword, number, or verb.\n"
        "- For non-household airport codes (anything outside LAX/JFK/LHR/CDG/"
        "NRT/DXB/etc.), DO NOT use the IATA code in customer-facing copy. "
        "Use the destination NAME. The generator will substitute the SKU only "
        "in the URL display path and in long-name fallback contexts.\n"
        + ("- Reference the destination NAME verbatim where it fits.\n" if product else "")
        + "\n"
        f"Return EXACTLY this JSON (no comments, no markdown):\n"
        f"{{\"headlines\": [...max {MAX_HEADLINES} strings], "
        f"\"descriptions\": [...max {MAX_DESCRIPTIONS} strings]}}"
    )


def _build_prompt(
    client: ClientProfile,
    theme: str,
    keywords: list[str],
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
    variant_role: str | None = None,
) -> str:
    if client.language == "en":
        return _build_prompt_en(
            client, theme, keywords, target_geo, product, variant_role,
        )
    return _build_prompt_sv(
        client, theme, keywords, target_geo, product, variant_role,
    )


def _invoke_claude(prompt: str) -> dict[str, Any] | None:
    """Run `claude -p` and return the parsed inner JSON payload, or None on failure."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return None

    cmd = [
        claude_bin,
        "-p", prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(_AD_COPY_SCHEMA),
        "--model", CLAUDE_MODEL,
        "--no-session-persistence",
        "--max-budget-usd", str(CLAUDE_MAX_BUDGET_USD),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SEC,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        logger.warning("claude CLI timed out after %ds", CLAUDE_TIMEOUT_SEC)
        return None
    except (OSError, FileNotFoundError) as exc:
        logger.warning("claude CLI invocation failed: %s", exc)
        return None

    if result.returncode != 0:
        logger.warning(
            "claude CLI exited %d: %s",
            result.returncode, (result.stderr or "")[:500],
        )
        return None

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        logger.warning("claude CLI returned non-JSON envelope: %s", exc)
        return None

    if envelope.get("is_error"):
        logger.warning("claude CLI reported error: %s", envelope.get("result"))
        return None

    inner = envelope.get("result")
    if isinstance(inner, (dict, list)):
        return inner if isinstance(inner, dict) else None

    if not isinstance(inner, str):
        logger.warning("claude CLI 'result' field has unexpected type %s", type(inner).__name__)
        return None

    try:
        parsed = json.loads(inner)
    except json.JSONDecodeError as exc:
        logger.warning("claude inner result was not parseable JSON: %s", exc)
        return None

    if not isinstance(parsed, dict):
        logger.warning("claude inner result was not a JSON object")
        return None
    return parsed


def _clean_strings(values: Any, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        if not isinstance(v, str):
            continue
        text = v.strip().strip("\"'")
        if not text or len(text) > limit or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def generate_llm_ad_copy(
    client: ClientProfile,
    theme: str,
    keywords: list[str],
    target_geo: GeoTarget | None = None,
    product: Product | None = None,
    variant_role: str | None = None,
) -> tuple[list[str], list[str]]:
    """Return (headlines, descriptions) from the claude CLI; empty lists on failure.

    `variant_role` is the multi-RSA variant tag (e.g. 'discount_led') that biases
    the prompt toward one psychological lever. None falls back to the
    generic-variant prompt used by the legacy single-RSA path.
    """
    if not is_enabled():
        return [], []

    prompt = _build_prompt(client, theme, keywords, target_geo, product, variant_role)
    payload = _invoke_claude(prompt)
    if not payload:
        return [], []

    headlines = _clean_strings(payload.get("headlines"), HEADLINE_LIMIT)[:MAX_HEADLINES]
    descriptions = _clean_strings(payload.get("descriptions"), DESCRIPTION_LIMIT)[:MAX_DESCRIPTIONS]
    logger.info(
        "claude CLI produced %d headlines / %d descriptions for theme '%s' (variant=%s)",
        len(headlines), len(descriptions), theme, variant_role or "default",
    )
    return headlines, descriptions
