#!/usr/bin/env python3
"""Run the UI against local FAKE shops (no internet, no real prices) to try the whole flow.

    python scripts/demo.py            # http://127.0.0.1:8001

A red banner is shown in the UI the whole time so demo prices can never be mistaken for real ones.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="pt-demo-"))
os.environ.update(PT_DATA_DIR=str(tmp), PT_ALLOW_PRIVATE_HOSTS="1", PT_DEMO="1")
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

import fakeshop                                     # noqa: E402
import uvicorn                                      # noqa: E402
from pricetracker.retailers import Retailer, save_all  # noqa: E402

srv, port = fakeshop.start()
shopdefs = [("alpha", "NL", "alpha/search?q={q}"), ("beta", "BE", "beta/zoeken?query={q}"), ("gamma", "FR", "gamma/search?q={q}"),
            ("delta", "DE", "delta/search?q={q}"), ("epsilon", "NL", "epsilon/search?q={q}"), ("zeta", "DE", None), ("eta", "FR", "eta/search?q={q}")]
shops = [Retailer(id=i, name=f"Demo {i.title()}", country=cc, website=f"http://127.0.0.1:{port}/{i}/", domain="127.0.0.1",
                  kind="online_electronics", hq_country="NL", search_url=(f"http://127.0.0.1:{port}/{s}" if s else None),
                  search_confidence="known" if s else "unknown") for i, cc, s in shopdefs]
save_all(shops, path=tmp / "retailers.json", meta={})
shutil.copy(ROOT / "data" / "catalog.json", tmp / "catalog.json")
shutil.copy(ROOT / "data" / "excluded.json", tmp / "excluded.json")
print(f"\n  DEMO (fake shops) → http://127.0.0.1:8001   data dir: {tmp}\n")
uvicorn.run("pricetracker.server:app", host="127.0.0.1", port=8001, log_level="warning")
