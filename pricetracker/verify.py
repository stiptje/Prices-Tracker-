"""Verify / refresh the retailer database against the live web.

    python -m pricetracker.verify                      # dry run, prints a table
    python -m pricetracker.verify --write              # also store status in data/retailers.json
    python -m pricetracker.verify --country NL --discover --write
    python -m pricetracker.verify --id coolblue-nl --write

For each retailer it checks: homepage reachable? still on the registered domain? does the search URL
return a page that looks like search results for a test query? (--discover also hunts for a working
search URL when none is known or the known one fails.)
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

from . import config, retailers as rdb
from .discover import discover_search_url, expand, looks_like_search_page, TEST_QUERY
from .fetcher import fetch


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def verify_one(r: rdb.Retailer, discover: bool = False) -> dict:
    out = {"id": r.id, "name": r.name, "country": r.country}
    page = fetch(r.website, r.country)
    r.last_checked = now()
    r.http_status = page.status or None
    r.final_url = page.final_url or None
    if page.error in ("network", "timeout"):
        r.status = "unreachable"
    elif page.error == "blocked":
        r.status = "blocked"          # the site exists but refuses automated access
    elif page.ok:
        host = (urlparse(page.final_url).hostname or "").lower()
        same = host == r.domain or host.endswith("." + r.domain)
        r.status = "online" if same else "redirected"
    else:
        r.status = "unreachable"
    out["status"], out["http"] = r.status, r.http_status

    # search URL
    if r.status in ("online", "redirected", "blocked"):
        if r.search_url:
            sp = fetch(expand(r.search_url, TEST_QUERY), r.country)
            r.search_ok = looks_like_search_page(sp) if sp.ok else (None if sp.error == "blocked" else False)
            r.search_checked = now()
            if r.search_ok:
                r.search_confidence = "verified"
        if discover and not r.search_ok and r.status != "blocked":
            tpl, how, note = discover_search_url(r.website, r.country)
            if tpl:
                r.search_url, r.search_confidence, r.search_ok = tpl, "discovered", True
                r.search_checked = now()
                out["discovered"] = tpl
    out["search_ok"] = r.search_ok
    return out


def verify_many(shops: list[rdb.Retailer], discover: bool = False, workers: int = 12, emit=None) -> list[dict]:
    results = []

    def work(r):
        res = verify_one(r, discover)
        if emit:
            emit(res)
        return res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(work, shops))
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--country", action="append", help="BE/FR/NL/DE (repeatable)")
    ap.add_argument("--id", action="append", help="retailer id (repeatable)")
    ap.add_argument("--discover", action="store_true", help="try to find a working search URL when missing/failing")
    ap.add_argument("--write", action="store_true", help="persist results into data/retailers.json")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args(argv)

    allr = rdb.load_all()
    shops = rdb.select(allr, countries=a.country, ids=a.id)
    print(f"verifying {len(shops)} retailers …", file=sys.stderr)
    t0 = time.time()
    rows = verify_many(shops, a.discover, a.workers,
                       emit=lambda x: print(f"  {x['id']:<26} {x['status']:<12} search_ok={x['search_ok']}", file=sys.stderr))
    from collections import Counter

    print(dict(Counter(r["status"] for r in rows)), f"in {time.time()-t0:.0f}s")
    if a.write:
        rdb.save_all(allr)
        print(f"saved to {config.RETAILERS_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
