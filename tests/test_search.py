import threading

from pricetracker import search as srch
from pricetracker.discover import discover_search_url
from pricetracker.matcher import ModelSpec

SPEC = ModelSpec(name="iPhone 15 Pro", brand="Apple", aliases=["Apple iPhone 15 Pro"], storage_gb=256)


def run(shops, spec=SPEC, **opt):
    events = []
    opts = srch.Options(persist_discovery=False, **opt)
    reports = srch.run_search(spec, list(shops), events.append, opts, queries=["iPhone 15 Pro"])
    results = [e["result"] for e in events if e["type"] == "result"]
    return events, {r.retailer_id: r for r in reports}, results


def test_alpha_only_exact_model_with_live_product_page_price(shops):
    ev, reps, res = run([shops["alpha"]])
    assert [r["title"] for r in res] == ["Apple iPhone 15 Pro 256GB Zwart"]       # not Max, not case, not 128GB, not refurb
    r = res[0]
    assert r["verified"] and r["currency"] == "EUR" and r["source"].startswith("product page")
    assert r["price"] != 1099.0            # the listing said 1.099,00; the product page is what counts
    assert reps["alpha"].status == "ok"


def test_every_search_is_live_no_caching(shops):
    p1 = run([shops["alpha"]])[2][0]["price"]
    p2 = run([shops["alpha"]])[2][0]["price"]
    assert p2 < p1                          # the fake shop lowers the price on every request


def test_embedded_state_and_microdata_comma_price(shops):
    _, reps, res = run([shops["beta"]])
    assert len(res) == 1 and res[0]["price"] == 1049.0 and res[0]["availability"] == "in stock"


def test_itemlist_search_and_meta_tag_price(shops):
    _, _, res = run([shops["delta"]])
    assert len(res) == 1 and res[0]["price"] == 1079.5 and res[0]["source"].endswith("(meta)")


def test_blocked_shop_is_reported_not_faked(shops):
    _, reps, res = run([shops["gamma"]])
    assert res == [] and reps["gamma"].status == "blocked"


def test_no_match_shop(shops):
    _, reps, res = run([shops["epsilon"]])
    assert res == [] and reps["epsilon"].status == "no_match"


def test_storage_must_be_confirmed(shops):
    _, reps, res = run([shops["eta"]])
    assert res == [] and "storage" in reps["eta"].message
    _, _, res2 = run([shops["eta"]], spec=ModelSpec(name="iPhone 15 Pro", brand="Apple"))   # storage = any
    assert len(res2) == 1 and res2[0]["price"] == 899.0


def test_refurbished_toggle(shops):
    spec = ModelSpec(name="iPhone 15 Pro", brand="Apple", storage_gb=256, allow_refurbished=True)
    _, _, res = run([shops["alpha"]], spec=spec)
    conds = sorted(r["condition"] for r in res)
    assert conds == ["new", "refurbished"]


def test_search_url_discovery_via_form(shops):
    tpl, how, _ = discover_search_url(shops["zeta"].website, "NL")
    assert how == "search form" and "keyword={q}" in tpl and "lang=nl" in tpl
    _, reps, res = run([shops["zeta"]], spec=ModelSpec(name="iPhone 15 Pro", brand="Apple"))
    assert len(res) == 1 and res[0]["price"] == 1000.0


def test_parallel_all_shops_and_event_stream(shops):
    events, reps, res = run(list(shops.values()))
    types = [e["type"] for e in events]
    assert types[0] == "start" and types[-1] == "done"
    assert sum(1 for t in types if t == "retailer_done") == len(shops)
    # zeta/eta pages never state a storage size, so with 256 GB requested they are (correctly) rejected
    assert {r["retailer_id"] for r in res} == {"alpha", "beta", "delta"}
    assert reps["zeta"].status == "no_match" and reps["gamma"].status == "blocked"


def test_recheck_blocks_foreign_domains(shops):
    out = srch.recheck(shops["alpha"], SPEC, "http://evil.example/x")
    assert out["ok"] is False and "domain" in out["error"]
