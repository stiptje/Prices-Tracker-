import json

from fastapi.testclient import TestClient

from pricetracker import catalog
from pricetracker.server import app

client = TestClient(app)


def test_identify_ranks_exact_model_first():
    top = catalog.identify("iphone 15 pro")[0]
    assert top["display"] == "Apple iPhone 15 Pro" and top["confidence"] == 1.0
    assert catalog.identify("galaxy s24 ultra")[0]["name"] == "Galaxy S24 Ultra"
    assert catalog.identify("sm-s928b")[0]["name"] == "Galaxy S24 Ultra"       # model number lookup
    assert catalog.identify("iphon 16 pro max")[0]["name"] == "iPhone 16 Pro Max"  # typo tolerant


def test_identify_always_offers_search_as_typed():
    c = catalog.identify("some obscure gadget 3000")
    assert c[-1]["kind"] == "custom" and c[-1]["name"] == "some obscure gadget 3000"


def test_queries_contain_name_and_alternates():
    top = catalog.identify("galaxy s24 ultra")[0]
    q = [x.lower() for x in top["queries"]]
    assert "galaxy s24 ultra" in q and "samsung galaxy s24 ultra" in q and "sm-s928b" in q


def test_api_meta_and_identify_and_headers():
    m = client.get("/api/meta").json()
    assert m["total"] >= 140 and set(m["countries"]) == {"BE", "FR", "NL", "DE"}
    r = client.post("/api/identify", json={"query": "pixel 9 pro"})
    assert r.headers["cache-control"].startswith("no-store")
    assert r.json()["candidates"][0]["name"] == "Pixel 9 Pro"


def test_api_search_streams_ndjson(shops, monkeypatch):
    from pricetracker import retailers as rdb
    monkeypatch.setattr("pricetracker.server._all", lambda: [shops["alpha"], shops["beta"]])
    r = client.post("/api/search", json={
        "product": {"name": "iPhone 15 Pro", "brand": "Apple"}, "storage_gb": 256,
        "countries": ["NL"], "queries": ["iPhone 15 Pro"],
    })
    assert r.status_code == 200 and "ndjson" in r.headers["content-type"]
    events = [json.loads(l) for l in r.text.splitlines() if l.strip()]
    assert events[0]["type"] == "start" and events[-1]["type"] == "done"
    assert len([e for e in events if e["type"] == "result"]) == 2


def test_api_rejects_empty_selection(monkeypatch):
    monkeypatch.setattr("pricetracker.server._all", lambda: [])
    r = client.post("/api/search", json={"product": {"name": "x"}})
    assert r.status_code == 400
