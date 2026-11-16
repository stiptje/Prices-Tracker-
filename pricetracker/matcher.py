"""Strict product matching.

The user confirms ONE exact model (plus optional storage). A listing only counts if
  * one of the model's names/aliases appears as a contiguous token sequence,
  * the next token is not a variant word that would make it a *different* model
    ("iPhone 15 Pro" must not match "iPhone 15 Pro Max", "Pixel 9" not "Pixel 9 Pro XL"),
  * it is not an accessory (case, charger, screen protector, "for iPhone 15" …),
  * it satisfies the chosen storage size and condition (new / refurbished).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .textnorm import find_sequence, tokens

# Words that, directly following a model name, turn it into a different product.
VARIANT_WORDS = {
    "pro", "max", "plus", "ultra", "mini", "fe", "lite", "edge", "neo", "air", "xl",
    "fold", "flip", "se", "e", "t", "s", "r", "x", "gt", "turbo", "note", "go", "play",
    "prime", "core", "power", "active", "classic", "slim", "spro", "ce", "c", "a", "i",
    "v", "k",
}

# Reject a listing if any of these appears anywhere in its title.
ACCESSORY_WORDS = {
    # EN
    "case", "cases", "cover", "covers", "bumper", "screenprotector", "protector",
    "protectors", "tempered", "charger", "cable", "adapter", "adaptor", "holder",
    "mount", "lanyard", "powerbank", "sleeve", "wallet", "pouch", "stylus", "dock",
    "magsafe", "replacement", "repair", "tripod", "gimbal", "headphones",
    # NL
    "hoes", "hoesje", "hoesjes", "beschermglas", "beschermfolie", "oplader",
    "kabel", "houder", "telefoonhoesje", "reparatie",
    # FR
    "coque", "etui", "housse", "chargeur", "protege", "rechange", "reparation", "cordon",
    # DE
    "hulle", "huelle", "schutzhulle", "schutzfolie", "panzerglas", "ladegerat",
    "ladekabel", "halterung", "displayschutz", "tasche", "ersatzteil", "armband",
    "ersatz", "reparatur",
}
# Words that also occur in ordinary spec lines; only count when right next to the model name.
WEAK_ACCESSORY_WORDS = {
    "screen", "glass", "film", "skin", "lens", "battery", "stand", "strap", "support",
    "verre", "trempe", "ecran", "scherm", "schutz", "folie", "bescherming", "charging",
    "housse", "display",
}

# A model name preceded (within a few tokens) by one of these ⇒ the item is "for" the phone.
FOR_WORDS = {
    "voor", "pour", "fur", "for", "compatible", "compatibel", "kompatibel",
    "geschikt", "compatibles", "kompatible", "fits", "fit", "passend", "adapte",
    "avec", "mit", "with", "met", "ersatz", "pour", "und",
}

REFURB_WORDS = {
    "refurbished", "refurb", "renewed", "reconditionne", "reconditionnee",
    "reconditionnes", "gebraucht", "aufbereitet", "generaluberholt", "tweedehands",
    "gerenoveerd", "refurbed", "preowned", "occasion", "used",
}
REFURB_PHRASES = [
    ["second", "hand"], ["remis", "a", "neuf"], ["pre", "owned"],
    ["tres", "bon", "etat"], ["comme", "neuf"],
]

STORAGE_RE = re.compile(r"\b(\d{1,4}) ?(gb|go|tb|to)\b")


@dataclass
class ModelSpec:
    """What the user confirmed."""

    name: str                                   # canonical display name
    brand: str = ""
    aliases: list[str] = field(default_factory=list)
    model_numbers: list[str] = field(default_factory=list)   # e.g. SM-S928B
    storage_gb: int | None = None               # confirmed storage (GB) or None = any
    allow_refurbished: bool = False
    exclude_terms: list[str] = field(default_factory=list)
    allow_words: list[str] = field(default_factory=list)   # accessory-looking words that are legit for this product

    def name_sequences(self) -> list[list[str]]:
        names = [self.name] + list(self.aliases)
        if self.brand:
            names += [f"{self.brand} {self.name}"]
        seqs, seen = [], set()
        for n in names:
            t = tokens(n)
            if t and tuple(t) not in seen:
                seen.add(tuple(t))
                seqs.append(t)
        # longest first so "galaxy s24 ultra" wins over "s24 ultra"
        seqs.sort(key=len, reverse=True)
        return seqs

    def model_number_sequences(self) -> list[list[str]]:
        return [t for t in (tokens(m) for m in self.model_numbers) if t]

    def search_queries(self, limit: int = 4) -> list[str]:
        """Ordered search strings: exact name first, then brand+name, aliases, model numbers."""
        cand = []
        if self.brand and not self.name.lower().startswith(self.brand.lower()):
            cand.append(f"{self.brand} {self.name}")
        cand.append(self.name)
        cand += self.aliases
        cand += self.model_numbers
        out, seen = [], set()
        for c in cand:
            k = " ".join(tokens(c))
            if k and k not in seen:
                seen.add(k)
                out.append(c.strip())
        return out[:limit]


@dataclass
class Verdict:
    ok: bool
    reason: str = ""
    condition: str = "new"          # new | refurbished
    storage_gb: int | None = None


def detect_condition(toks: list[str], text_norm: str) -> str:
    if any(t in REFURB_WORDS for t in toks):
        return "refurbished"
    for ph in REFURB_PHRASES:
        if find_sequence(toks, ph) >= 0:
            return "refurbished"
    return "new"


def parse_storage_values(text_norm: str) -> set[int]:
    out = set()
    for num, unit in STORAGE_RE.findall(text_norm):
        n = int(num)
        out.add(n * 1024 if unit in ("tb", "to") else n)
    return out


def judge(spec: ModelSpec, title: str, *, retailer_condition: str = "new") -> Verdict:
    """Decide whether `title` is exactly the confirmed model."""
    toks = tokens(title)
    if not toks:
        return Verdict(False, "empty title")
    text_norm = " ".join(toks)

    # --- exclude terms chosen by the user / catalog -----------------------
    for ex in spec.exclude_terms:
        et = tokens(ex)
        if et and find_sequence(toks, et) >= 0:
            return Verdict(False, f"contains excluded term '{ex}'")

    # --- find the model name ---------------------------------------------
    pos, matched = -1, None
    for seq in spec.name_sequences():
        i = find_sequence(toks, seq)
        if i >= 0:
            pos, matched = i, seq
            break
    via_model_number = False
    if pos < 0:
        for seq in spec.model_number_sequences():
            i = find_sequence(toks, seq)
            if i >= 0:
                pos, matched, via_model_number = i, seq, True
                break
    if pos < 0:
        return Verdict(False, "model name not in title")

    end = pos + len(matched)

    # --- variant guard: next token must not create a different model ------
    own = set(tokens(spec.name))
    if not via_model_number and end < len(toks):
        nxt = toks[end]
        # "iphone 15 pro" followed by "max"; "pixel 9" followed by "pro"; "16" + "e"
        if nxt in VARIANT_WORDS and nxt not in _own_tail_allowed(spec, matched):
            # single letters t/s/e/a/c/i/v/k/r/x only matter right after a number
            if len(nxt) > 1 or (end > 0 and toks[end - 1].isdigit()):
                # "5 g", "4 g" is connectivity, not a variant — 'g' is not in VARIANT_WORDS
                return Verdict(False, f"different variant (…{matched[-1]} {nxt})")
        # "iphone 15" + "plus" handled above; "s24" + "plus" etc.
        if nxt == "plus" and "plus" not in own:
            return Verdict(False, "different variant (plus)")

    # --- accessory guard ---------------------------------------------------
    pre = toks[max(0, pos - 4) : pos]
    if any(t in FOR_WORDS for t in pre):
        return Verdict(False, "accessory ('for <model>')")
    allow = {t for w in spec.allow_words for t in tokens(w)}
    real = [t for t in toks if t in ACCESSORY_WORDS and t not in own and t not in allow]
    if real:
        return Verdict(False, f"accessory word '{real[0]}'")
    near = toks[max(0, pos - 2) : pos] + toks[end : end + 1]
    weak = [t for t in near if t in WEAK_ACCESSORY_WORDS and t not in own and t not in allow]
    if weak:
        return Verdict(False, f"accessory word '{weak[0]}' next to model")

    # --- condition ---------------------------------------------------------
    cond = "refurbished" if retailer_condition == "refurbished" else detect_condition(toks, text_norm)
    if cond == "refurbished" and not spec.allow_refurbished:
        return Verdict(False, "refurbished/used (not requested)")

    # --- storage -----------------------------------------------------------
    sizes = parse_storage_values(text_norm)
    storage = None
    if spec.storage_gb:
        if sizes and spec.storage_gb not in sizes:
            return Verdict(False, f"other storage ({sorted(sizes)} GB)")
        storage = spec.storage_gb if spec.storage_gb in sizes else None
        # unknown storage in the title ⇒ keep, the product page will be re-judged
    elif sizes:
        # largest value ≥ 32 GB is almost always the storage, RAM is smaller/earlier
        storage = max(sizes)
    return Verdict(True, "match", condition=cond, storage_gb=storage)


def _own_tail_allowed(spec: ModelSpec, matched: list[str]) -> set[str]:
    """Variant words the user's own model name already ends with are never 'extra'."""
    return {matched[-1]} if matched and matched[-1] in VARIANT_WORDS else set()
