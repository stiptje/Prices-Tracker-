"""HTML → structured data.

Two jobs:
  1. `find_candidates(html, base_url)`  – product links found on a *search results* page.
  2. `extract_product(html, url)`       – the live price/availability/condition from a *product page*.

Price sources, in order of trust:
  JSON-LD schema.org Product/Offer  →  microdata (itemprop=price)  →  meta tags
  (product:price:amount, og:price:amount).  We never scrape prices out of free text,
  because shops show monthly instalments, "from" prices and accessories there.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urldefrag, urlparse

from bs4 import BeautifulSoup

from .textnorm import parse_price

# --------------------------------------------------------------------------- JSON-LD


def _json_blobs(soup: BeautifulSoup):
    for tag in soup.find_all("script"):
        t = (tag.get("type") or "").lower()
        raw = tag.string or tag.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        if "ld+json" in t or t == "application/json" or tag.get("id") == "__NEXT_DATA__":
            try:
                yield json.loads(raw)
            except Exception:
                # some shops emit trailing commas / HTML comments
                cleaned = re.sub(r"^<!--|-->$", "", raw).strip()
                try:
                    yield json.loads(cleaned)
                except Exception:
                    continue


def _walk(node):
    """Yield every dict inside an arbitrary JSON structure."""
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def _types(d: dict) -> set[str]:
    t = d.get("@type")
    if isinstance(t, str):
        return {t.split("/")[-1]}
    if isinstance(t, list):
        return {str(x).split("/")[-1] for x in t}
    return set()


def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


@dataclass
class Offer:
    price: float
    currency: str = "EUR"
    availability: str = ""
    condition: str = ""
    seller: str = ""
    url: str = ""


def _clean_availability(v) -> str:
    s = str(v or "").split("/")[-1].strip()
    mapping = {
        "InStock": "in stock", "OutOfStock": "out of stock", "PreOrder": "pre-order",
        "BackOrder": "backorder", "LimitedAvailability": "limited stock",
        "SoldOut": "sold out", "Discontinued": "discontinued", "OnlineOnly": "online only",
        "InStoreOnly": "in store only", "PreSale": "pre-sale",
    }
    return mapping.get(s, s)


def _clean_condition(v) -> str:
    s = str(v or "").split("/")[-1].lower()
    if "new" in s:
        return "new"
    if "refurb" in s or "used" in s or "damaged" in s:
        return "refurbished"
    return ""


def _offers_from(node) -> list[Offer]:
    out: list[Offer] = []
    for off in _as_list(node):
        if not isinstance(off, dict):
            continue
        types = _types(off)
        # nested offers (AggregateOffer.offers, offers inside offers)
        if "offers" in off:
            out += _offers_from(off["offers"])
        spec = off.get("priceSpecification")
        price = off.get("price")
        cur = off.get("priceCurrency")
        if price is None and isinstance(spec, (dict, list)):
            for sp in _as_list(spec):
                if isinstance(sp, dict) and sp.get("price") is not None:
                    price, cur = sp.get("price"), sp.get("priceCurrency", cur)
                    break
        if price is None and "AggregateOffer" in types:
            price = off.get("lowPrice")
        p = parse_price(price)
        if p is None or p <= 0:
            continue
        seller = off.get("seller")
        if isinstance(seller, dict):
            seller = seller.get("name", "")
        out.append(
            Offer(
                price=p,
                currency=(cur or "EUR").upper() if isinstance(cur, str) or cur is None else "EUR",
                availability=_clean_availability(off.get("availability")),
                condition=_clean_condition(off.get("itemCondition")),
                seller=str(seller or ""),
                url=str(off.get("url") or ""),
            )
        )
    return out


@dataclass
class ProductInfo:
    name: str = ""
    url: str = ""
    brand: str = ""
    sku: str = ""
    gtin: str = ""
    image: str = ""
    offers: list[Offer] = field(default_factory=list)
    source: str = ""            # jsonld | microdata | meta
    page_title: str = ""

    def best_offer(self) -> Offer | None:
        """Lowest-priced offer, preferring ones that are actually available."""
        if not self.offers:
            return None
        avail = [o for o in self.offers if o.availability not in ("out of stock", "sold out", "discontinued")]
        pool = avail or self.offers
        return min(pool, key=lambda o: o.price)


def extract_product(html: str, url: str = "") -> ProductInfo | None:
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "")
    h1 = soup.find("h1")

    # 1) JSON-LD / embedded JSON: schema.org Product with offers
    best: ProductInfo | None = None
    for blob in _json_blobs(soup):
        for d in _walk(blob):
            if "Product" in _types(d) or "ProductGroup" in _types(d) or "IndividualProduct" in _types(d):
                offers = _offers_from(d.get("offers"))
                if not offers and "hasVariant" in d:
                    for v in _as_list(d["hasVariant"]):
                        if isinstance(v, dict):
                            offers += _offers_from(v.get("offers"))
                if not offers:
                    continue
                brand = d.get("brand")
                if isinstance(brand, dict):
                    brand = brand.get("name", "")
                img = d.get("image")
                if isinstance(img, list):
                    img = img[0] if img else ""
                if isinstance(img, dict):
                    img = img.get("url", "")
                info = ProductInfo(
                    name=str(d.get("name") or ""),
                    url=str(d.get("url") or url or ""),
                    brand=str(brand or ""),
                    sku=str(d.get("sku") or ""),
                    gtin=str(d.get("gtin13") or d.get("gtin") or d.get("gtin14") or d.get("ean") or ""),
                    image=str(img or ""),
                    offers=offers,
                    source="jsonld",
                    page_title=title,
                )
                if not info.name and h1:
                    info.name = h1.get_text(" ", strip=True)
                # prefer the product whose url equals the page url, else the first with offers
                if best is None or (url and info.url.rstrip("/") == url.rstrip("/")):
                    best = info
    if best:
        return best

    # 2) microdata
    prod = soup.find(attrs={"itemtype": re.compile(r"schema.org/Product", re.I)})
    scope = prod or soup
    price_el = scope.find(attrs={"itemprop": "price"})
    if price_el is not None:
        val = price_el.get("content") or price_el.get_text(strip=True)
        p = parse_price(val)
        if p:
            cur_el = scope.find(attrs={"itemprop": "priceCurrency"})
            cur = (cur_el.get("content") or cur_el.get_text(strip=True)) if cur_el else "EUR"
            name_el = scope.find(attrs={"itemprop": "name"})
            avail_el = scope.find(attrs={"itemprop": "availability"})
            avail = (avail_el.get("href") or avail_el.get("content") or "") if avail_el else ""
            return ProductInfo(
                name=(name_el.get("content") or name_el.get_text(" ", strip=True)) if name_el
                else (h1.get_text(" ", strip=True) if h1 else title),
                url=url,
                offers=[Offer(price=p, currency=(cur or "EUR").upper(), availability=_clean_availability(avail))],
                source="microdata",
                page_title=title,
            )

    # 3) meta tags
    def meta(*names):
        for n in names:
            el = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if el and el.get("content"):
                return el["content"]
        return None

    amount = meta("product:price:amount", "og:price:amount", "product:sale_price:amount")
    p = parse_price(amount)
    if p:
        cur = meta("product:price:currency", "og:price:currency") or "EUR"
        avail = meta("product:availability", "og:availability") or ""
        return ProductInfo(
            name=meta("og:title") or (h1.get_text(" ", strip=True) if h1 else title),
            url=url,
            offers=[Offer(price=p, currency=cur.upper(), availability=_clean_availability(avail.replace(" ", "")))],
            source="meta",
            page_title=title,
        )
    return None


# --------------------------------------------------------------------------- search page candidates

_TITLE_KEYS = ("name", "title", "productName", "product_name", "label", "displayName")
_URL_KEYS = ("url", "href", "link", "productUrl", "product_url", "canonicalUrl", "canonical_url", "uri")
_PRICE_KEYS = ("price", "salePrice", "currentPrice", "sellingPrice", "priceValue", "lowPrice")

_NOISE_PATH = re.compile(
    r"(/cart|/basket|/panier|/winkelwagen|/warenkorb|/login|/account|/mon-compte|/help|/contact|"
    r"/privacy|/cookie|/terms|/conditions|/wishlist|/compare|javascript:|mailto:|tel:)", re.I)


@dataclass
class Candidate:
    title: str
    url: str
    price: float | None = None     # price shown in the listing – NOT trusted until the product page confirms it
    via: str = ""                  # jsonld | embedded | anchor


def _abs(base: str, href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
        return None
    u = urldefrag(urljoin(base, href))[0]
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return u


def find_candidates(html: str, base_url: str, limit: int = 400) -> list[Candidate]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, Candidate] = {}

    def add(title, url, price=None, via=""):
        title = " ".join(str(title or "").split())
        u = _abs(base_url, url) if url else None
        if not title or not u or _NOISE_PATH.search(u):
            return
        key = u.split("?")[0].rstrip("/") if "?" in u and len(urlparse(u).query) > 80 else u.rstrip("/")
        cur = found.get(key)
        if cur is None or (len(title) > len(cur.title) and via == cur.via):
            found[key] = Candidate(title=title, url=u, price=price, via=via)
        elif cur and cur.price is None and price is not None:
            cur.price = price

    # 1+2) structured data: ItemList / Product / embedded state
    for blob in _json_blobs(soup):
        for d in _walk(blob):
            types = _types(d)
            if "ListItem" in types and isinstance(d.get("item"), dict):
                it = d["item"]
                add(it.get("name"), it.get("url") or it.get("@id"), _first_price(it), "jsonld")
            elif "Product" in types:
                add(d.get("name"), d.get("url") or d.get("@id"), _first_price(d), "jsonld")
            else:
                title = next((d[k] for k in _TITLE_KEYS if isinstance(d.get(k), str)), None)
                url = next((d[k] for k in _URL_KEYS if isinstance(d.get(k), str)), None)
                if title and url and len(title) > 6 and ("/" in url):
                    add(title, url, _first_price(d), "embedded")

    # 3) plain anchors – product cards on server-rendered pages
    for a in soup.find_all("a", href=True):
        texts = [
            a.get("title"), a.get("aria-label"),
            (a.find("img") or {}).get("alt") if a.find("img") else None,
        ]
        heading = a.find(["h2", "h3", "h4"])
        if heading:
            texts.insert(0, heading.get_text(" ", strip=True))
        inner = a.get_text(" ", strip=True)
        if inner:
            texts.append(inner[:220])
        # an anchor wrapping only an image has its alt text as title
        for t in texts:
            if t and len(str(t).strip()) > 6:
                add(t, a["href"], None, "anchor")
        # product cards sometimes put the title in a sibling heading rather than the link
        parent = a.parent
        if parent is not None and parent.name in ("div", "li", "article"):
            h = parent.find(["h2", "h3", "h4"])
            if h and h.get_text(strip=True):
                add(h.get_text(" ", strip=True), a["href"], None, "anchor")

    return list(found.values())[:limit]


def _first_price(d: dict) -> float | None:
    offers = _offers_from(d.get("offers")) if "offers" in d else []
    if offers:
        return min(o.price for o in offers)
    for k in _PRICE_KEYS:
        v = d.get(k)
        if isinstance(v, dict):
            v = v.get("value") or v.get("amount") or v.get("current")
        p = parse_price(v)
        if p:
            return p
    return None


# --------------------------------------------------------------------------- blocked / empty detection

_BLOCK_MARKERS = (
    "captcha", "are you a robot", "robot check", "unusual traffic", "access denied",
    "request blocked", "just a moment", "cf-chl", "datadome", "px-captcha", "perimeterx",
    "verifying you are human", "pardon our interruption", "bot detection", "akamai",
    "ihre anfrage wurde blockiert", "vous avez été bloqué", "attention required",
    "enable javascript and cookies to continue",
)


def looks_blocked(status: int, html: str) -> bool:
    if status in (401, 403, 407, 429, 451, 503):
        return True
    head = (html or "")[:6000].lower()
    if len(html or "") < 20000 and any(m in head for m in _BLOCK_MARKERS):
        return True
    return False
