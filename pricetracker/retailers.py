"""Retailer database: loading, policy enforcement, filtering, persistence.

Policy (enforced here, not just in the data):
  * a retailer must be *based in Europe*: either headquartered in a European country, or
    operated in-market through a registered European entity ("eu_subsidiary", e.g. Amazon.de,
    Apple Store DE). Shops that sit outside Europe and merely ship in (AliExpress, Temu,
    Banggood, …) are rejected on load, and their domains are on a block-list.
  * every record needs a country in {BE, FR, NL, DE}, a website and a domain.
"""
from __future__ import annotations

import csv
import json
import threading
from dataclasses import dataclass, field, asdict
from typing import Iterable
from urllib.parse import urlparse

from . import config

COUNTRIES = ("BE", "FR", "NL", "DE")

EUROPE = {
    "AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE",
    "GR", "HU", "IS", "IE", "IT", "XK", "LV", "LI", "LT", "LU", "MT", "MD", "MC", "ME", "NL",
    "MK", "NO", "PL", "PT", "RO", "SM", "RS", "SK", "SI", "ES", "SE", "CH", "UA", "GB", "VA",
}

KINDS = {
    "electronics_chain": "Electronics chain",
    "online_electronics": "Online electronics shop",
    "computer_specialist": "Computer / IT specialist",
    "marketplace": "Marketplace",
    "general_retail": "Hypermarket / department / general retail",
    "telecom_operator": "Telecom operator shop",
    "brand_store": "Brand store",
    "refurbished": "Refurbished specialist",
}

_lock = threading.RLock()


@dataclass
class Retailer:
    id: str
    name: str
    country: str                      # storefront country: BE | FR | NL | DE
    website: str                      # homepage of this storefront
    domain: str                       # registrable domain used for the host allow-list
    kind: str
    hq_country: str                   # ISO code of the group's headquarters
    entity_basis: str = "headquartered"   # headquartered | eu_subsidiary
    group: str = ""
    search_url: str | None = None     # template with {q} / {q_path} / {q_dash}; None = auto-discover
    search_confidence: str = "unknown"    # known | unverified | discovered | unknown
    condition: str = "new"            # new | refurbished | mixed
    sells: list[str] = field(default_factory=lambda: ["smartphones", "electronics"])
    notes: str = ""
    # --- verification state (written by pricetracker.verify) -----------------------------
    status: str = "unverified"        # unverified | online | blocked | unreachable | redirected
    last_checked: str | None = None
    http_status: int | None = None
    final_url: str | None = None
    search_ok: bool | None = None
    search_checked: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class PolicyError(ValueError):
    pass


def validate(r: Retailer, blocked_domains: Iterable[str] = ()) -> None:
    if r.country not in COUNTRIES:
        raise PolicyError(f"{r.id}: country {r.country!r} not in {COUNTRIES}")
    if r.hq_country not in EUROPE and r.entity_basis != "eu_subsidiary":
        raise PolicyError(f"{r.id}: HQ {r.hq_country} is outside Europe and no EU entity is declared")
    if r.hq_country in EUROPE and r.entity_basis != "headquartered":
        raise PolicyError(f"{r.id}: European HQ must use entity_basis='headquartered'")
    if r.kind not in KINDS:
        raise PolicyError(f"{r.id}: unknown kind {r.kind!r}")
    if not r.website.startswith("https://") and not r.website.startswith("http://"):
        raise PolicyError(f"{r.id}: website must be a full URL")
    host = (urlparse(r.website).hostname or "").lower()
    if not (host == r.domain or host.endswith("." + r.domain)):
        raise PolicyError(f"{r.id}: website host {host} is not under domain {r.domain}")
    for b in blocked_domains:
        if r.domain == b or r.domain.endswith("." + b):
            raise PolicyError(f"{r.id}: {r.domain} is on the non-European block-list")


def load_excluded() -> list[dict]:
    try:
        with open(config.EXCLUDED_FILE, encoding="utf-8") as f:
            return json.load(f)["excluded"]
    except FileNotFoundError:
        return []


def blocked_domains() -> set[str]:
    return {d for e in load_excluded() for d in e.get("domains", [])}


def load_all(path=None) -> list[Retailer]:
    path = path or config.RETAILERS_FILE
    with _lock, open(path, encoding="utf-8") as f:
        raw = json.load(f)
    blocked = blocked_domains()
    fields = set(Retailer.__dataclass_fields__)
    out, ids = [], set()
    for item in raw["retailers"]:
        r = Retailer(**{k: v for k, v in item.items() if k in fields})
        validate(r, blocked)
        if r.id in ids:
            raise PolicyError(f"duplicate id {r.id}")
        ids.add(r.id)
        out.append(r)
    return out


def save_all(retailers: list[Retailer], path=None, meta: dict | None = None) -> None:
    path = path or config.RETAILERS_FILE
    with _lock:
        doc = {"meta": meta or _read_meta(path), "retailers": [r.to_dict() for r in retailers]}
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
        import os

        os.replace(tmp, path)
        write_csv(retailers, str(path).replace(".json", ".csv"))


def _read_meta(path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("meta", {})
    except Exception:
        return {}


def write_csv(retailers: list[Retailer], path: str) -> None:
    cols = ["id", "name", "country", "website", "domain", "kind", "group", "hq_country",
            "entity_basis", "condition", "search_url", "search_confidence", "status",
            "last_checked", "notes"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in retailers:
            d = r.to_dict()
            w.writerow([d.get(c, "") if d.get(c) is not None else "" for c in cols])


def select(
    retailers: list[Retailer],
    countries: Iterable[str] | None = None,
    kinds: Iterable[str] | None = None,
    include_eu_subsidiaries: bool = True,
    include_refurbished_shops: bool = True,
    ids: Iterable[str] | None = None,
) -> list[Retailer]:
    cs = set(countries) if countries else set(COUNTRIES)
    ks = set(kinds) if kinds else None
    idset = set(ids) if ids else None
    out = []
    for r in retailers:
        if r.country not in cs:
            continue
        if ks is not None and r.kind not in ks:
            continue
        if not include_eu_subsidiaries and r.entity_basis != "headquartered":
            continue
        if not include_refurbished_shops and r.condition == "refurbished":
            continue
        if idset is not None and r.id not in idset:
            continue
        out.append(r)
    return out


def allowed_domains(retailers: Iterable[Retailer]) -> set[str]:
    return {r.domain for r in retailers}
