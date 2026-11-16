"""FastAPI app: static UI + JSON/NDJSON API.

Run:  python -m pricetracker            (http://127.0.0.1:8000)
"""
from __future__ import annotations

import json
import queue
import threading

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, catalog, config, llm, retailers as rdb, search as srch, verify as vfy
from .matcher import ModelSpec

app = FastAPI(title="Prices Tracker", version=__version__)


@app.middleware("http")
async def no_store(request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/api"):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


def _all() -> list[rdb.Retailer]:
    return rdb.load_all()


# ------------------------------------------------------------------ models
class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(default="", max_length=60)
    aliases: list[str] = Field(default_factory=list, max_length=12)
    model_numbers: list[str] = Field(default_factory=list, max_length=8)
    allow_words: list[str] = Field(default_factory=list, max_length=8)
    exclude_terms: list[str] = Field(default_factory=list, max_length=8)


class SearchIn(BaseModel):
    product: ProductIn
    storage_gb: int | None = None
    allow_refurbished: bool = False
    countries: list[str] = Field(default_factory=lambda: list(rdb.COUNTRIES))
    kinds: list[str] | None = None
    retailer_ids: list[str] | None = None
    include_eu_subsidiaries: bool = True
    all_aliases: bool = False
    include_unverified: bool = False
    strict_storage: bool = True
    queries: list[str] | None = None        # override search strings (UI lets the user edit aliases)


def _spec(p: ProductIn, storage_gb, allow_refurb) -> ModelSpec:
    return ModelSpec(
        name=p.name.strip(), brand=p.brand.strip(), aliases=[a.strip() for a in p.aliases if a.strip()],
        model_numbers=[m.strip() for m in p.model_numbers if m.strip()], storage_gb=storage_gb,
        allow_refurbished=allow_refurb, exclude_terms=p.exclude_terms, allow_words=p.allow_words,
    )


# ------------------------------------------------------------------ API
@app.get("/api/meta")
def meta():
    allr = _all()
    return {
        "version": __version__,
        "countries": {c: config.COUNTRY_NAMES[c] for c in rdb.COUNTRIES},
        "kinds": rdb.KINDS,
        "counts": {c: sum(1 for r in allr if r.country == c) for c in rdb.COUNTRIES},
        "total": len(allr),
        "llm": llm.available(),
        "browser_mode": config.USE_BROWSER,
        "demo": config.DEMO,
        "excluded": rdb.load_excluded(),
    }


@app.get("/api/retailers")
def list_retailers(country: str | None = None, kind: str | None = None):
    rs = rdb.select(_all(), countries=country.split(",") if country else None,
                    kinds=kind.split(",") if kind else None)
    return [r.to_dict() for r in rs]


@app.get("/api/retailers.csv")
def retailers_csv():
    import io, csv
    rs = _all()
    buf = io.StringIO()
    cols = ["id", "name", "country", "website", "kind", "group", "hq_country", "entity_basis",
            "condition", "search_url", "status", "last_checked", "notes"]
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rs:
        d = r.to_dict()
        w.writerow([d.get(c) or "" for c in cols])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=retailers.csv"})


class IdentifyIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)


@app.post("/api/identify")
def identify(body: IdentifyIn):
    cands = catalog.identify(body.query)
    extra = []
    # LLM assist only when the catalog has no confident hit
    if llm.available() and not any(c["confidence"] >= 0.85 for c in cands if c["kind"] == "catalog"):
        for c in llm.identify(body.query):
            spec = _spec(ProductIn(name=c["name"], brand=c["brand"], aliases=c["aliases"],
                                   model_numbers=c["model_numbers"]), None, False)
            c["queries"] = spec.search_queries(8)
            extra.append(c)
    # keep the 'search as typed' option last
    custom = [c for c in cands if c["kind"] == "custom"]
    rest = [c for c in cands if c["kind"] != "custom"]
    return {"query": body.query, "candidates": rest + extra + custom, "llm_used": bool(extra)}


def _ndjson(run, cancel: threading.Event):
    """Run `run(emit)` in a thread and stream every emitted event as one JSON line."""
    q: "queue.Queue" = queue.Queue()
    SENT = object()

    def emit(ev):
        q.put(ev)

    def worker():
        try:
            run(emit)
        except Exception as e:  # pragma: no cover
            q.put({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            q.put(SENT)

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        try:
            while True:
                try:
                    ev = q.get(timeout=15)
                except queue.Empty:
                    yield b'{"type":"ping"}\n'
                    continue
                if ev is SENT:
                    break
                yield (json.dumps(ev, ensure_ascii=False) + "\n").encode()
        finally:
            cancel.set()                      # client went away → stop fetching

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/api/search")
def do_search(body: SearchIn):
    bad = [c for c in body.countries if c not in rdb.COUNTRIES]
    if bad:
        raise HTTPException(400, f"unknown country {bad}")
    shops = rdb.select(_all(), countries=body.countries, kinds=body.kinds,
                       include_eu_subsidiaries=body.include_eu_subsidiaries, ids=body.retailer_ids)
    if not shops:
        raise HTTPException(400, "no retailers match the selected filters")
    spec = _spec(body.product, body.storage_gb, body.allow_refurbished)
    opts = srch.Options(all_aliases=body.all_aliases, include_unverified=body.include_unverified,
                        strict_storage=body.strict_storage)
    queries = [q.strip() for q in (body.queries or []) if q.strip()] or spec.search_queries(opts.max_queries)
    cancel = threading.Event()
    return _ndjson(lambda emit: srch.run_search(spec, shops, emit, opts, queries, cancel), cancel)


class RecheckIn(BaseModel):
    retailer_id: str
    url: str
    product: ProductIn
    storage_gb: int | None = None
    allow_refurbished: bool = False


@app.post("/api/recheck")
def recheck(body: RecheckIn):
    r = next((x for x in _all() if x.id == body.retailer_id), None)
    if r is None:
        raise HTTPException(404, "unknown retailer")
    return JSONResponse(srch.recheck(r, _spec(body.product, body.storage_gb, body.allow_refurbished), body.url),
                        headers={"Cache-Control": "no-store"})


class VerifyIn(BaseModel):
    countries: list[str] | None = None
    retailer_ids: list[str] | None = None
    discover: bool = False
    write: bool = True


@app.post("/api/verify")
def verify(body: VerifyIn):
    allr = _all()
    shops = rdb.select(allr, countries=body.countries, ids=body.retailer_ids)
    cancel = threading.Event()

    def run(emit):
        emit({"type": "start", "total": len(shops)})
        vfy.verify_many(shops, body.discover, emit=lambda x: emit({"type": "verified", **x}))
        if body.write:
            rdb.save_all(allr)
        emit({"type": "done"})

    return _ndjson(run, cancel)


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})
