"""Live search orchestration.

For every selected retailer, at the moment you press search:
  Stage 1  fetch the shop's search page for the model name (then aliases / model numbers)
           and keep only listings that strictly match the confirmed model;
  Stage 2  fetch each matching *product page* and read the price from its structured data.
A price is shown as verified only when it came from the product page itself, fetched just now.
Nothing is cached anywhere in this program.
"""
from __future__ import annotations

import difflib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from . import config, retailers as rdb
from .discover import discover_search_url, expand
from .extract import Candidate, ProductInfo, extract_product, find_candidates
from .fetcher import Page, fetch, host_allowed
from .matcher import ModelSpec, judge
from .textnorm import normalize

Emit = Callable[[dict], None]


@dataclass
class Options:
    all_aliases: bool = False          # search every alias at every shop (default: stop at first hit)
    include_unverified: bool = False   # also return listing-only prices that could not be confirmed
    strict_storage: bool = True        # require storage to be confirmed when the user picked one
    max_product_pages: int = config.MAX_PRODUCT_PAGES
    max_queries: int = config.MAX_QUERIES
    persist_discovery: bool = True     # write discovered search URLs back into the database


@dataclass
class Report:
    retailer_id: str
    status: str = "pending"    # ok | no_match | blocked | timeout | unreachable | error | skipped
    message: str = ""
    candidates: int = 0
    matched: int = 0
    results: int = 0
    queries: list[str] = field(default_factory=list)
    elapsed_ms: int = 0


def iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time(), tz=timezone.utc).isoformat(timespec="seconds")


_STATUS_FROM_ERROR = {
    "blocked": "blocked", "timeout": "timeout", "network": "unreachable",
    "http_error": "error", "unsafe_url": "error", "too_large": "error",
}


def _rank(spec: ModelSpec, c: Candidate) -> tuple:
    sim = difflib.SequenceMatcher(None, normalize(c.title), normalize(spec.name)).ratio()
    via = {"jsonld": 0, "embedded": 1, "anchor": 2}.get(c.via, 3)
    return (-round(sim, 2), via, len(c.title))


def _storage_confirmed(spec: ModelSpec, info: ProductInfo, page: Page, name: str) -> bool:
    """When the user picked a storage size, make sure *this page* is that variant."""
    if not spec.storage_gb:
        return True
    from .matcher import parse_storage_values

    blob = " ".join([name, info.sku, info.page_title, page.final_url or page.url])
    return spec.storage_gb in parse_storage_values(normalize(blob))


def result_from_page(r: rdb.Retailer, spec: ModelSpec, page: Page, opts: Options,
                     fallback_title: str = "") -> tuple[dict | None, str]:
    """Judge one live product page. Returns (result | None, reason)."""
    info = extract_product(page.html, page.final_url or page.url)
    if info is None:
        return None, "no price data on product page"
    offer = info.best_offer()
    if offer is None:
        return None, "no offer on product page"
    if offer.currency != "EUR":
        return None, f"price in {offer.currency}, not EUR"
    name = info.name or fallback_title
    # the page's own name and the page <title> must both be the right model
    verdict = judge(spec, name, retailer_condition=r.condition if r.condition != "mixed" else "new")
    if not verdict.ok:
        return None, f"product page is a different item: {verdict.reason}"
    condition = offer.condition or verdict.condition
    if r.condition == "refurbished":
        condition = "refurbished"
    if condition == "refurbished" and not spec.allow_refurbished:
        return None, "refurbished (not requested)"
    if opts.strict_storage and not _storage_confirmed(spec, info, page, name):
        return None, "storage size not confirmed on product page"
    url = page.final_url or page.url
    return {
        "retailer_id": r.id,
        "retailer": r.name,
        "country": r.country,
        "kind": r.kind,
        "title": name,
        "price": round(offer.price, 2),
        "currency": offer.currency,
        "availability": offer.availability,
        "condition": condition,
        "seller": offer.seller,
        "storage_gb": verdict.storage_gb,
        "url": url,
        "verified": True,
        "source": f"product page ({info.source})",
        "fetched_at": iso(page.fetched_at),
        "elapsed_ms": page.elapsed_ms,
        "via": page.via,
        "entity_basis": r.entity_basis,
    }, "ok"


def search_retailer(r: rdb.Retailer, spec: ModelSpec, queries: list[str], opts: Options,
                    emit: Emit, cancel: threading.Event | None = None) -> Report:
    t0 = time.time()
    rep = Report(retailer_id=r.id)
    cancel = cancel or threading.Event()
    emit({"type": "retailer_start", "retailer_id": r.id})

    def done(status: str, msg: str = "") -> Report:
        rep.status, rep.message = status, msg
        rep.elapsed_ms = int((time.time() - t0) * 1000)
        emit({"type": "retailer_done", "retailer_id": r.id, "report": rep.__dict__.copy()})
        return rep

    # ---- search URL template --------------------------------------------------------
    template = r.search_url
    if not template:
        emit({"type": "note", "retailer_id": r.id, "message": "discovering search URL…"})
        template, how, note = discover_search_url(r.website, r.country)
        if not template:
            return done("error", f"could not find a search URL ({note})")
        r.search_url, r.search_confidence = template, "discovered"
        if opts.persist_discovery:
            _persist_template(r.id, template)

    # ---- Stage 1: search pages --------------------------------------------------------
    matched: dict[str, Candidate] = {}
    seen_cands = 0
    last_error = ""
    rediscovered = False
    for q in queries[: opts.max_queries]:
        if cancel.is_set():
            return done("skipped", "cancelled")
        rep.queries.append(q)
        page = fetch(expand(template, q), r.country)
        if page.error == "http_error" and page.status in (404, 410) and not rediscovered and r.search_confidence != "discovered":
            rediscovered = True
            tpl2, _, _ = discover_search_url(r.website, r.country)
            if tpl2:
                template = r.search_url = tpl2
                r.search_confidence = "discovered"
                if opts.persist_discovery:
                    _persist_template(r.id, tpl2)
                page = fetch(expand(template, q), r.country)
        if not page.ok:
            last_error = page.error or "error"
            if page.error in ("blocked", "unreachable", "network", "timeout"):
                continue
            continue
        cands = find_candidates(page.html, page.final_url or page.url)
        seen_cands += len(cands)
        for c in cands:
            v = judge(spec, c.title, retailer_condition=r.condition if r.condition != "mixed" else "new")
            if v.ok:
                key = c.url.split("#")[0]
                if key not in matched:
                    matched[key] = c
        if matched and not opts.all_aliases:
            break

    rep.candidates, rep.matched = seen_cands, len(matched)
    if not matched:
        if last_error and not seen_cands:
            return done(_STATUS_FROM_ERROR.get(last_error, "error"), _explain(last_error))
        return done("no_match", f"{seen_cands} listings scanned, none is exactly '{spec.name}'")

    # ---- Stage 2: verify on the product pages -------------------------------------------
    ranked = sorted(matched.values(), key=lambda c: _rank(spec, c))[: opts.max_product_pages]
    reasons = []
    seen_urls: set[str] = set()
    for c in ranked:
        if cancel.is_set():
            return done("skipped", "cancelled")
        page = fetch(c.url, r.country)
        if not page.ok:
            reasons.append(f"{page.error or page.status}")
            if opts.include_unverified and c.price:
                emit({"type": "result", "result": _listing_result(r, c, spec)})
                rep.results += 1
            continue
        res, why = result_from_page(r, spec, page, opts, fallback_title=c.title)
        if res is None:
            reasons.append(why)
            if opts.include_unverified and c.price and why.startswith("no price data"):
                emit({"type": "result", "result": _listing_result(r, c, spec)})
                rep.results += 1
            continue
        if res["url"] in seen_urls:
            continue
        seen_urls.add(res["url"])
        emit({"type": "result", "result": res})
        rep.results += 1

    if rep.results:
        return done("ok", f"{rep.results} verified price(s)")
    return done("no_match", "matching listings found but none could be verified: " + "; ".join(sorted(set(reasons))[:3]))


def _listing_result(r: rdb.Retailer, c: Candidate, spec: ModelSpec) -> dict:
    return {
        "retailer_id": r.id, "retailer": r.name, "country": r.country, "kind": r.kind,
        "title": c.title, "price": round(c.price, 2), "currency": "EUR", "availability": "",
        "condition": "refurbished" if r.condition == "refurbished" else "new", "seller": "",
        "storage_gb": None, "url": c.url, "verified": False,
        "source": "search listing (not confirmed on product page)", "fetched_at": iso(),
        "elapsed_ms": 0, "via": "http", "entity_basis": r.entity_basis,
    }


def _explain(err: str) -> str:
    return {
        "blocked": "the shop blocked automated access (bot protection) – open the shop manually or enable the browser mode",
        "timeout": "the shop did not answer in time",
        "network": "the shop could not be reached (DNS / connection error)",
        "unreachable": "the shop could not be reached (DNS / connection error)",
        "http_error": "the shop returned an HTTP error for the search page",
    }.get(err, err)


def _persist_template(rid: str, template: str) -> None:
    try:
        with rdb._lock:
            allr = rdb.load_all()
            for x in allr:
                if x.id == rid:
                    x.search_url, x.search_confidence = template, "discovered"
            rdb.save_all(allr)
    except Exception:
        pass


def run_search(spec: ModelSpec, shops: list[rdb.Retailer], emit: Emit, opts: Options | None = None,
               queries: list[str] | None = None, cancel: threading.Event | None = None) -> list[Report]:
    opts = opts or Options()
    queries = queries or spec.search_queries(opts.max_queries)
    cancel = cancel or threading.Event()
    started = time.time()
    emit({"type": "start", "retailers": len(shops), "queries": queries, "model": spec.name,
          "started_at": iso(started)})
    reports: list[Report] = []
    with ThreadPoolExecutor(max_workers=min(config.MAX_WORKERS, max(1, len(shops)))) as ex:
        futs = {ex.submit(_safe, r, spec, queries, opts, emit, cancel): r for r in shops}
        for f in as_completed(futs):
            reports.append(f.result())
    emit({"type": "done", "elapsed_ms": int((time.time() - started) * 1000), "finished_at": iso(),
          "ok": sum(1 for x in reports if x.status == "ok"), "total": len(reports)})
    return reports


def _safe(r, spec, queries, opts, emit, cancel) -> Report:
    try:
        return search_retailer(r, spec, queries, opts, emit, cancel)
    except Exception as e:  # never let one shop take the whole search down
        rep = Report(retailer_id=r.id, status="error", message=f"internal error: {type(e).__name__}: {e}")
        emit({"type": "retailer_done", "retailer_id": r.id, "report": rep.__dict__.copy()})
        return rep


def recheck(r: rdb.Retailer, spec: ModelSpec, url: str, opts: Options | None = None) -> dict:
    """Re-fetch one product page right now and return the fresh result (or the reason it failed)."""
    opts = opts or Options()
    if not host_allowed(url, {r.domain}):
        return {"ok": False, "error": "URL is not on this retailer's domain"}
    page = fetch(url, r.country)
    if not page.ok:
        return {"ok": False, "error": _explain(page.error or str(page.status))}
    res, why = result_from_page(r, spec, page, opts)
    if res is None:
        return {"ok": False, "error": why}
    return {"ok": True, "result": res}
