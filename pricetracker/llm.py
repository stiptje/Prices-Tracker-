"""Optional LLM-assisted identification (only used when ANTHROPIC_API_KEY is set).

The LLM only *proposes* candidate models, canonical names, alternate names and model numbers.
The user still confirms one before anything is searched, and prices never come from the LLM.
"""
from __future__ import annotations

import json
import re

import requests

from . import config

SYSTEM = (
    "You identify consumer-electronics products for a European price-comparison tool. "
    "Given the user's keywords, return up to 5 candidate products as JSON only: "
    '{"candidates":[{"brand":"","name":"exact retail model name without brand","year":2024,'
    '"category":"smartphone","aliases":["alternate names / spellings used by European shops"],'
    '"model_numbers":["manufacturer model codes, only if you are certain"],'
    '"storage_gb":[128,256]}]}. '
    "Only list products that really exist; never invent model numbers. No prose."
)


def available() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def identify(query: str, timeout: float = 20) -> list[dict]:
    if not available():
        return []
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": config.LLM_MODEL, "max_tokens": 900, "system": SYSTEM,
                  "messages": [{"role": "user", "content": query[:300]}]},
            timeout=timeout,
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        return []
    out = []
    for c in data.get("candidates", [])[:5]:
        name = str(c.get("name", "")).strip()
        if not name:
            continue
        brand = str(c.get("brand", "")).strip()
        out.append({
            "kind": "llm", "id": "llm-" + re.sub(r"\W+", "-", f"{brand}-{name}".lower()),
            "confidence": 0.5,
            "display": f"{brand} {name}".strip(), "brand": brand, "name": name,
            "year": c.get("year"), "category": c.get("category", ""),
            "storage_gb": [int(x) for x in c.get("storage_gb", []) if str(x).isdigit()],
            "aliases": [str(a) for a in c.get("aliases", [])][:6],
            "model_numbers": [str(a) for a in c.get("model_numbers", [])][:4],
            "allow_words": [],
            "queries": [],
        })
    return out
