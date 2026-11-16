import os
import sys
from pathlib import Path

os.environ["PT_ALLOW_PRIVATE_HOSTS"] = "1"           # local fixture shops live on 127.0.0.1
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import fakeshop
from pricetracker.retailers import Retailer


@pytest.fixture(scope="session")
def shop_port():
    srv, port = fakeshop.start()
    yield port
    srv.shutdown()


def make(rid, port, search, kind="online_electronics", cond="new", country="NL"):
    return Retailer(
        id=rid, name=rid.title(), country=country, website=f"http://127.0.0.1:{port}/{rid}/", domain="127.0.0.1",
        kind=kind, hq_country="NL", search_url=(f"http://127.0.0.1:{port}/{search}" if search else None),
        search_confidence="known" if search else "unknown", condition=cond,
    )


@pytest.fixture()
def shops(shop_port):
    p = shop_port
    return {
        "alpha": make("alpha", p, "alpha/search?q={q}"),
        "beta": make("beta", p, "beta/zoeken?query={q}"),
        "gamma": make("gamma", p, "gamma/search?q={q}"),
        "delta": make("delta", p, "delta/search?q={q}"),
        "epsilon": make("epsilon", p, "epsilon/search?q={q}"),
        "zeta": make("zeta", p, None),
        "eta": make("eta", p, "eta/search?q={q}"),
    }
