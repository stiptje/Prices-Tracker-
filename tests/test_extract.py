from pricetracker.extract import extract_product, find_candidates, looks_blocked
from pricetracker.textnorm import parse_price


def test_parse_price_formats():
    for raw, want in [("1.299,00", 1299), ("1,299.00", 1299), ("€ 1.299,-", 1299), ("899.99", 899.99),
                      ("1 099,00", 1099), (1299, 1299), ("12,5", 12.5)]:
        assert parse_price(raw) == want


def test_jsonld_offer_variants():
    html = '''<script type="application/ld+json">{"@graph":[{"@type":"BreadcrumbList"},
      {"@type":"Product","name":"X","offers":[{"@type":"Offer","price":"1.049,00","priceCurrency":"EUR","availability":"https://schema.org/OutOfStock"},
      {"@type":"Offer","price":1099,"priceCurrency":"EUR","availability":"https://schema.org/InStock"}]}]}</script>'''
    info = extract_product(html)
    assert info and info.source == "jsonld"
    assert info.best_offer().price == 1099         # prefers an offer that is actually available


def test_aggregate_offer_and_price_specification():
    html = '''<script type="application/ld+json">{"@type":"Product","name":"X","offers":{"@type":"AggregateOffer","lowPrice":"799.00","priceCurrency":"EUR"}}</script>'''
    assert extract_product(html).best_offer().price == 799
    html = '''<script type="application/ld+json">{"@type":"Product","name":"X","offers":{"@type":"Offer","priceSpecification":{"price":"650","priceCurrency":"EUR"}}}</script>'''
    assert extract_product(html).best_offer().price == 650


def test_no_price_means_none():
    assert extract_product("<html><body><h1>iPhone</h1><p>Vanaf € 29,- per maand</p></body></html>") is None


def test_candidates_anchor_and_embedded():
    html = '''<a href="/p/1" title="Apple iPhone 15 Pro 256GB">img</a>
      <script id="__NEXT_DATA__" type="application/json">{"a":{"title":"Apple iPhone 15 Pro 128GB","url":"/p/2","price":{"value":"999"}}}</script>'''
    c = {x.url: x for x in find_candidates(html, "https://shop.example/search?q=x")}
    assert "https://shop.example/p/1" in c and c["https://shop.example/p/2"].price == 999


def test_blocked_detection():
    assert looks_blocked(403, "")
    assert looks_blocked(200, "<html>Please solve this captcha</html>")
    assert not looks_blocked(200, "<html>" + "x" * 30000 + "captcha</html>")
