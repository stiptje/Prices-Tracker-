"""Text normalisation shared by the matcher, the catalog and the extractors.

Titles are lower-cased, de-accented and split on every letter/digit boundary so that
"Flip6", "Flip 6" and "flip-6" all become the same tokens, and "256GB" == "256 GB".
"""
from __future__ import annotations

import re
import unicodedata

_PLUS = re.compile(r"\+")
_NONALNUM = re.compile(r"[^a-z0-9]+")
_ALPHA_DIGIT = re.compile(r"(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """Lower-case, de-accent, '+'→' plus ', split letter/digit boundaries, collapse spaces."""
    if not text:
        return ""
    s = strip_accents(str(text)).lower()
    s = s.replace("ß", "ss")
    s = _PLUS.sub(" plus ", s)
    s = _NONALNUM.sub(" ", s)
    s = _ALPHA_DIGIT.sub(" ", s)
    return " ".join(s.split())


def tokens(text: str) -> list[str]:
    n = normalize(text)
    return n.split() if n else []


def find_sequence(haystack: list[str], needle: list[str]) -> int:
    """Index of the first contiguous occurrence of `needle` in `haystack`, else -1."""
    n = len(needle)
    if n == 0 or n > len(haystack):
        return -1
    for i in range(len(haystack) - n + 1):
        if haystack[i : i + n] == needle:
            return i
    return -1


_PRICE_CLEAN = re.compile(r"[^\d,.\-]")


def parse_price(raw) -> float | None:
    """Parse '1.299,00', '1,299.00', '1299', 1299.0, '€ 1.299,-' … into a float."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if raw >= 0 else None
    s = _PRICE_CLEAN.sub("", str(raw)).strip("-.,")
    if not s:
        return None
    if "," in s and "." in s:
        # whichever separator comes last is the decimal separator
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = head.replace(",", "") + "." + tail if len(tail) in (1, 2) else s.replace(",", "")
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if len(tail) == 3 and head and head.replace(".", "").isdigit() and len(head) <= 3:
            s = s.replace(".", "")          # 1.299 → 1299
        elif s.count(".") > 1:
            s = s.replace(".", "")
    try:
        val = float(s)
    except ValueError:
        return None
    return val if val >= 0 else None
