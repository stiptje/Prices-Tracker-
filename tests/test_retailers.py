import json

import pytest

from pricetracker import retailers as rdb
from pricetracker.retailers import PolicyError, Retailer


def test_database_loads_and_obeys_policy():
    rs = rdb.load_all()
    assert len(rs) >= 140
    assert {r.country for r in rs} == set(rdb.COUNTRIES)
    blocked = rdb.blocked_domains()
    assert "aliexpress.com" in blocked and "temu.com" in blocked
    for r in rs:
        assert r.hq_country in rdb.EUROPE or r.entity_basis == "eu_subsidiary"
        assert not any(r.domain == b or r.domain.endswith("." + b) for b in blocked)


def test_non_european_shop_is_rejected():
    r = Retailer(id="x", name="X", country="NL", website="https://www.aliexpress.com/", domain="aliexpress.com",
                 kind="marketplace", hq_country="CN", entity_basis="eu_subsidiary")
    with pytest.raises(PolicyError):
        rdb.validate(r, rdb.blocked_domains())
    r2 = Retailer(id="y", name="Y", country="NL", website="https://shop.cn/", domain="shop.cn",
                  kind="online_electronics", hq_country="CN")           # outside Europe, no EU entity
    with pytest.raises(PolicyError):
        rdb.validate(r2)


def test_filters():
    rs = rdb.load_all()
    nl = rdb.select(rs, countries=["NL"])
    assert nl and all(r.country == "NL" for r in nl)
    strict = rdb.select(rs, include_eu_subsidiaries=False)
    assert strict and all(r.entity_basis == "headquartered" for r in strict)
    assert len(strict) < len(rs)
    assert not any(r.condition == "refurbished" for r in rdb.select(rs, include_refurbished_shops=False))


def test_every_known_search_template_has_placeholder():
    for r in rdb.load_all():
        if r.search_url:
            assert any(p in r.search_url for p in ("{q}", "{q_path}", "{q_dash}")), r.id
