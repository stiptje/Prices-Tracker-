"""Product identification: free-text keywords → candidate models the user can confirm."""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field, asdict
from functools import lru_cache

from . import config
from .matcher import ModelSpec
from .textnorm import normalize, tokens


@dataclass
class Product:
    id: str
    brand: str
    name: str
    aliases: list[str] = field(default_factory=list)
    model_numbers: list[str] = field(default_factory=list)
    storage_gb: list[int] = field(default_factory=list)
    year: int | None = None
    category: str = "smartphone"
    allow_words: list[str] = field(default_factory=list)

    def display(self) -> str:
        return f"{self.brand} {self.name}" if self.brand and not self.name.lower().startswith(self.brand.lower()) else self.name

    def spec(self, storage_gb: int | None = None, allow_refurbished: bool = False) -> ModelSpec:
        return ModelSpec(
            name=self.name, brand=self.brand, aliases=list(self.aliases),
            model_numbers=list(self.model_numbers), storage_gb=storage_gb,
            allow_refurbished=allow_refurbished, allow_words=list(self.allow_words),
        )


@lru_cache(maxsize=1)
def load() -> list[Product]:
    with open(config.CATALOG_FILE, encoding="utf-8") as f:
        raw = json.load(f)["products"]
    fields = set(Product.__dataclass_fields__)
    return [Product(**{k: v for k, v in p.items() if k in fields}) for p in raw]


_BRANDS = {"apple", "samsung", "google", "xiaomi", "redmi", "poco", "oneplus", "nothing", "motorola",
           "fairphone", "sony", "honor", "oppo", "asus", "huawei", "realme", "lg", "nokia", "hmd"}


def _names(p: Product) -> list[str]:
    return [p.name, p.display()] + p.aliases + p.model_numbers


def _score(qt: list[str], qn: str, p: Product) -> float:
    best = 0.0
    qset = set(qt)
    for n in _names(p):
        nt = tokens(n)
        if not nt:
            continue
        nset = set(nt)
        inter = len(qset & nset)
        if not inter:
            continue
        prec = inter / len(nset)
        rec = inter / len(qset)
        f1 = 2 * prec * rec / (prec + rec)
        # numbers must agree: query "15" must not match a "14" model
        q_nums, n_nums = {t for t in qset if t.isdigit()}, {t for t in nset if t.isdigit()}
        mult = 1.0
        if q_nums and n_nums and not (q_nums & n_nums):
            mult = 0.4                      # "15" must not match a "17" model
        elif q_nums and not n_nums:
            mult = 0.7
        ratio = difflib.SequenceMatcher(None, qn, " ".join(nt)).ratio()
        best = max(best, f1 * mult, ratio * 0.92 * mult)
        if " ".join(nt) in qn:                # whole model name contained in the query
            best = max(best, 0.55 + 0.4 * (len(nt) / max(len(qt), 1)))
    return best


def identify(query: str, limit: int = 6) -> list[dict]:
    """Return ranked candidate products for a keyword string. Always ends with a 'search as typed' option."""
    qn = normalize(query)
    qt = qn.split()
    if not qt:
        return []
    scored = []
    for p in load():
        s = _score(qt, qn, p)
        if s >= 0.5:
            scored.append((s, p))
    scored.sort(key=lambda x: (-x[0], -(x[1].year or 0), len(x[1].name)))
    out = []
    for s, p in scored[:limit]:
        spec = p.spec()
        out.append({
            "kind": "catalog", "id": p.id, "confidence": round(s, 2),
            "display": p.display(), "brand": p.brand, "name": p.name, "year": p.year,
            "category": p.category, "storage_gb": p.storage_gb,
            "aliases": p.aliases, "model_numbers": p.model_numbers, "allow_words": p.allow_words,
            "queries": spec.search_queries(8),
        })
    # fallback / extra option: exactly what the user typed
    brand = next((t for t in qt if t in _BRANDS), "")
    out.append({
        "kind": "custom", "id": "custom", "confidence": 0.0,
        "display": f"Search exactly: “{query.strip()}”", "brand": brand.title() if brand else "",
        "name": query.strip(), "year": None, "category": "custom", "storage_gb": [],
        "aliases": [], "model_numbers": [], "allow_words": [],
        "queries": [query.strip()],
    })
    return out
