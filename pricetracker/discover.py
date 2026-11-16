"""Find (and validate) a shop's search-URL template.

Order of evidence:
  1. OpenSearch description   <link rel="search" type="application/opensearchdescription+xml">
  2. schema.org WebSite → potentialAction → SearchAction.target
  3. the page's own GET search <form>
  4. common platform patterns (Shopify, WooCommerce, Magento, Shopware, OpenCart, generic)

A candidate is accepted only if, for a test query, the page it returns actually contains several
product-looking links whose titles mention the test word – i.e. it behaves like a search page.
"""
from __future__ import annotations

import re
from typing import Callable
from urllib.parse import urljoin, urlparse, quote_plus, urlencode

from bs4 import BeautifulSoup

from .extract import _json_blobs, _walk, _types, find_candidates
from .fetcher import Page, fetch
from .textnorm import tokens

TEST_QUERY = "iphone"
SEARCH_FIELD_NAMES = {
    "q", "query", "s", "search", "searchtext", "search_query", "searchterm", "keyword",
    "keywords", "k", "text", "term", "ssearch", "suche", "zoeken", "recherche", "searchvalue",
    "search_value", "tr", "_nkw", "wd", "qs", "terms", "stext", "string", "find",
}

PLATFORM_PATTERNS = [
    "/search?q={q}",
    "/zoeken?q={q}",
    "/zoeken?query={q}",
    "/search?query={q}",
    "/recherche?q={q}",
    "/suche?q={q}",
    "/search?search={q}",             # Shopware 6
    "/search?sSearch={q}",            # Shopware 5
    "/catalogsearch/result/?q={q}",   # Magento
    "/search?type=product&q={q}",     # Shopify
    "/?s={q}&post_type=product",      # WooCommerce
    "/index.php?route=product/search&search={q}",   # OpenCart
    "/search.html?query={q}",
    "/s?k={q}",
    "/search/?q={q}",
    "/zoeken/?q={q}",
]

FetchFn = Callable[..., Page]


def _form_templates(soup: BeautifulSoup, base: str) -> list[str]:
    out = []
    for form in soup.find_all("form"):
        method = (form.get("method") or "get").lower()
        if method != "get":
            continue
        field = None
        for inp in form.find_all("input"):
            nm = (inp.get("name") or "").lower()
            typ = (inp.get("type") or "text").lower()
            if typ == "search" or (typ in ("text", "") and nm in SEARCH_FIELD_NAMES) or nm in SEARCH_FIELD_NAMES:
                field = inp.get("name")
                break
        if not field:
            continue
        action = urljoin(base, form.get("action") or base)
        hidden = []
        for inp in form.find_all("input", attrs={"type": "hidden"}):
            if inp.get("name") and inp.get("name") != field:
                hidden.append((inp["name"], inp.get("value", "")))
        sep = "&" if "?" in action else "?"
        qs = urlencode(hidden)
        tpl = f"{action}{sep}" + (qs + "&" if qs else "") + f"{field}={{q}}"
        out.append(tpl)
    return out


def _jsonld_templates(soup: BeautifulSoup, base: str) -> list[str]:
    out = []
    for blob in _json_blobs(soup):
        for d in _walk(blob):
            if "SearchAction" in _types(d):
                tgt = d.get("target")
                if isinstance(tgt, dict):
                    tgt = tgt.get("urlTemplate")
                if isinstance(tgt, str) and "{" in tgt:
                    tgt = re.sub(r"\{[^}]+\}", "{q}", tgt)
                    out.append(urljoin(base, tgt))
    return out


def _opensearch_templates(soup: BeautifulSoup, base: str, fetch_fn: FetchFn, country: str) -> list[str]:
    out = []
    for link in soup.find_all("link", rel=lambda v: v and "search" in v):
        if "opensearch" in (link.get("type") or "") and link.get("href"):
            p = fetch_fn(urljoin(base, link["href"]), country)
            if p.ok:
                for m in re.finditer(r'<Url[^>]+type="text/html"[^>]+template="([^"]+)"', p.html, re.I):
                    t = m.group(1).replace("&amp;", "&")
                    t = re.sub(r"\{searchTerms\??\}", "{q}", t)
                    t = re.sub(r"\{[^}]+\?\}", "", t)   # optional params
                    out.append(t)
    return out


def looks_like_search_page(page: Page, word: str = TEST_QUERY) -> bool:
    if not page.ok:
        return False
    cands = find_candidates(page.html, page.final_url or page.url)
    w = tokens(word)
    hits = [c for c in cands if all(t in tokens(c.title) for t in w)]
    urls = {c.url.split("?")[0] for c in hits}
    return len(urls) >= 3


def discover_search_url(site_url: str, country: str = "", fetch_fn: FetchFn = fetch):
    """Return (template | None, how, note). Does at most ~10 live requests."""
    home = fetch_fn(site_url, country)
    origin = f"{urlparse(home.final_url or site_url).scheme}://{urlparse(home.final_url or site_url).netloc}"
    candidates: list[tuple[str, str]] = []
    if home.ok:
        soup = BeautifulSoup(home.html, "lxml")
        base = home.final_url or site_url
        candidates += [(t, "opensearch") for t in _opensearch_templates(soup, base, fetch_fn, country)]
        candidates += [(t, "schema.org SearchAction") for t in _jsonld_templates(soup, base)]
        candidates += [(t, "search form") for t in _form_templates(soup, base)]
    elif home.error:
        return None, "", f"homepage not reachable ({home.error})"
    # keep the site's language prefix (e.g. /nl-be) when the homepage URL has one
    path_prefix = urlparse(site_url).path.rstrip("/")
    for pat in PLATFORM_PATTERNS:
        candidates.append((origin + pat, "common pattern"))
        if path_prefix and len(path_prefix) > 1:
            candidates.append((origin + path_prefix + pat, "common pattern"))

    seen, tried = set(), 0
    for tpl, how in candidates:
        if tpl in seen or "{q}" not in tpl:
            continue
        seen.add(tpl)
        if tried >= 12:
            break
        tried += 1
        page = fetch_fn(expand(tpl, TEST_QUERY), country)
        if looks_like_search_page(page):
            return tpl, how, f"validated with test query '{TEST_QUERY}'"
    return None, "", f"no working search URL found after {tried} attempts"


def expand(template: str, query: str) -> str:
    """Fill {q} (plus-encoded), {q_path} (%20-encoded), {q_dash} (dash-joined)."""
    return (
        template.replace("{q_path}", quote_plus(query).replace("+", "%20"))
        .replace("{q_dash}", "-".join(tokens(query)) or quote_plus(query))
        .replace("{q}", quote_plus(query))
    )
