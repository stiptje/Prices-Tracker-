"""A tiny multi-shop HTTP server used to test the live engine without touching real retailers."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HITS: dict[str, int] = {}


def page(body: str, head: str = "") -> bytes:
    return f"<!doctype html><html><head><title>shop</title>{head}</head><body>{body}</body></html>".encode()


def jsonld_product(name, price, avail="InStock", cond="NewCondition", cur="EUR", url=""):
    return ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "Product", "name": name, "url": url,
        "offers": {"@type": "Offer", "price": price, "priceCurrency": cur,
                   "availability": f"https://schema.org/{avail}", "itemCondition": f"https://schema.org/{cond}"},
    }) + "</script>")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path
        HITS[path] = HITS.get(path, 0) + 1
        n = HITS[path]

        # ---------- alpha: server-rendered cards, product pages with JSON-LD, price changes on every hit
        if path == "/alpha/search":
            cards = [
                ("/alpha/p/15pro256", "Apple iPhone 15 Pro 256GB Zwart", "1.099,00"),
                ("/alpha/p/15promax", "Apple iPhone 15 Pro Max 256GB", "1.299,00"),
                ("/alpha/p/case", "Hoesje voor iPhone 15 Pro siliconen", "19,95"),
                ("/alpha/p/15pro128", "Apple iPhone 15 Pro 128GB", "999,00"),
                ("/alpha/p/15pro256-refurb", "Apple iPhone 15 Pro 256GB Refurbished", "899,00"),
            ]
            html = "".join(f'<div class="card"><a href="{h}"><h3>{t}</h3></a><span class="price">€ {p}</span></div>' for h, t, p in cards)
            return self._send(200, page(f"<ul>{html}</ul>"))
        if path == "/alpha/p/15pro256":
            price = 1089 - n          # 1088, 1087, … : proves every call is live
            return self._send(200, page("<h1>Apple iPhone 15 Pro 256GB Zwart</h1>",
                                        jsonld_product("Apple iPhone 15 Pro 256GB Zwart", price)))
        if path == "/alpha/p/15pro256-refurb":
            return self._send(200, page("<h1>x</h1>", jsonld_product("Apple iPhone 15 Pro 256GB Refurbished", 899, cond="RefurbishedCondition")))
        if path.startswith("/alpha/p/"):
            return self._send(200, page("<h1>other</h1>", jsonld_product("Something else", 5)))

        # ---------- beta: JS-state search page (__NEXT_DATA__), product page with microdata + comma price
        if path == "/beta/zoeken":
            state = {"props": {"pageProps": {"products": [
                {"title": "Apple iPhone 15 Pro (256 GB) - Natuurlijk titanium", "url": "/beta/product/abc", "price": {"value": "1.059,00"}},
                {"title": "Apple iPhone 15 Pro Max (256 GB)", "url": "/beta/product/xyz", "price": {"value": "1.249,00"}},
            ]}}}
            return self._send(200, page("<div id='app'>loading…</div>",
                                        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>'))
        if path == "/beta/product/abc":
            body = ('<div itemscope itemtype="https://schema.org/Product"><h1 itemprop="name">Apple iPhone 15 Pro (256 GB) - Natuurlijk titanium</h1>'
                    '<span itemprop="price" content="1049.00">€ 1.049,00</span><meta itemprop="priceCurrency" content="EUR">'
                    '<link itemprop="availability" href="https://schema.org/InStock"></div>')
            return self._send(200, page(body))

        # ---------- gamma: bot wall
        if path.startswith("/gamma/"):
            return self._send(403, page("<h1>Access denied</h1><p>Please complete the captcha</p>"))

        # ---------- delta: JSON-LD ItemList on search page, product page has only meta tags
        if path == "/delta/search":
            data = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "item": {"@type": "Product", "name": "iPhone 15 Pro 256 GB", "url": "http://%s/delta/item/1" % self.headers["Host"],
                                                               "offers": {"@type": "Offer", "price": "1111.00", "priceCurrency": "EUR"}}}]}
            return self._send(200, page("", f'<script type="application/ld+json">{json.dumps(data)}</script>'))
        if path == "/delta/item/1":
            head = ('<meta property="og:title" content="iPhone 15 Pro 256 GB"><meta property="product:price:amount" content="1079.50">'
                    '<meta property="product:price:currency" content="EUR">')
            return self._send(200, page("<h1>iPhone 15 Pro 256 GB</h1>", head))

        # ---------- epsilon: nothing relevant
        if path == "/epsilon/search":
            return self._send(200, page('<a href="/epsilon/p/1"><h3>Samsung Galaxy S24 Ultra</h3></a>'))

        # ---------- zeta: search URL unknown → discovery via <form>; real search at /zeta/zoek
        if path == "/zeta/":
            return self._send(200, page('<form action="/zeta/zoek" method="get" role="search"><input type="hidden" name="lang" value="nl">'
                                        '<input type="search" name="keyword"></form>'))
        if path == "/zeta/zoek":
            term = (q.get("keyword") or [""])[0]
            cards = "".join(f'<a href="/zeta/p/{i}"><h3>Apple iPhone 15 Pro {term} model {i}</h3></a>' for i in range(4))
            if "iphone" in term.lower():
                return self._send(200, page(cards))
            return self._send(200, page("<p>geen resultaten</p>"))
        if path == "/zeta/p/0":
            return self._send(200, page("<h1>x</h1>", jsonld_product("Apple iPhone 15 Pro", 1000)))

        # ---------- eta: storage not on page → must be rejected when storage is demanded
        if path == "/eta/search":
            return self._send(200, page('<a href="/eta/p/1" title="Apple iPhone 15 Pro">Apple iPhone 15 Pro</a>'))
        if path == "/eta/p/1":
            return self._send(200, page("<h1>Apple iPhone 15 Pro</h1>", jsonld_product("Apple iPhone 15 Pro", 899)))

        return self._send(404, page("not found"))


def start():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]
