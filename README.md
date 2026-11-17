# Prices Tracker

Live price lookup for smartphones and electronics across **Belgium, France, the Netherlands and Germany**.

1. **Retailer database** – 150 storefronts (BE 26 · FR 41 · NL 32 · DE 51) in `data/retailers.json` / `.csv`, each with website, domain, type, HQ country and a re-verifiable search URL.
2. **App** – pick countries, type keywords, **confirm which exact model you mean**, then every selected shop is queried **live**.

```bash
pip install -r requirements.txt
python -m pricetracker            # → http://127.0.0.1:8000
python scripts/demo.py            # UI against local FAKE shops (red banner), works offline
python -m pytest tests            # 57 tests, no internet needed
```

## How a search works

| Step | What happens |
|---|---|
| Identify | Your keywords are matched against `data/catalog.json` (typo-tolerant, understands model numbers like `SM-S928B`). Optional: set `ANTHROPIC_API_KEY` and the app also asks Claude for candidates when the catalog has no confident hit. Anything unknown can be searched "exactly as typed". |
| Confirm | You pick one model, optionally a storage size, and edit the alternate names / model numbers that will be searched. Nothing is searched before you confirm. |
| Stage 1 | At each shop: search page for the exact name, then alternates / model numbers (first hit wins; tick *try every alternate name* to search all). Listings must strictly match: `iPhone 15 Pro` ≠ `15 Pro Max`/`15 Plus`, no cases/chargers/"for iPhone 15 Pro", new vs refurbished respected, storage respected. |
| Stage 2 | Each matching **product page is fetched right now** and the price is read from its schema.org/JSON-LD / microdata / meta tags. Only that is shown as **verified live**, with the time it was read. |
| After | **Re-check** re-reads one product page on demand. Nothing is cached (no-cache request headers, no server cache, `Cache-Control: no-store` on the API). |

Never faked: when a shop blocks bots, times out, has no exact match, or the price cannot be confirmed, the per-shop log says so.

## The "based in Europe" rule

A retailer is included only if it is headquartered in Europe **or** runs the local storefront through a European entity (`entity_basis: eu_subsidiary`: Amazon.de, Apple Store, Samsung DE, eBay …). Shops outside Europe that merely ship in (AliExpress, Temu, Banggood …) are listed in `data/excluded.json`; the loader **refuses** them (`pricetracker/retailers.py`, tested). The UI has a switch to also drop the EU storefronts of non-European groups.

## Keeping the database current

```bash
python -m pricetracker.verify --write                  # homepage + search URL check, all shops
python -m pricetracker.verify --country NL --discover --write   # also hunt for working search URLs
```
Also available as the *Verify* button in the UI. 97 of the 150 shops have no search URL yet; the app finds one on first use (OpenSearch → schema.org SearchAction → search form → common platform patterns), validates it, and saves it. Add shops by editing `data/retailers.json` (same fields; policy is checked on load). `scripts/seed_retailers.py --merge` and `scripts/build_catalog.py` regenerate the seed / catalog.

## Honest limitations

* **Not tested against the real shops.** The build sandbox blocked all retailer domains, so the extraction engine is tested against local fixture shops (server-rendered, JS-state, JSON-LD list, microdata, meta-tag, bot-wall, form-discovered), not against Coolblue, bol, etc. Expect to tune some shops after the first real run — start with `python -m pricetracker.verify --discover --write`.
* **Bot protection**: large shops (Amazon, MediaMarkt, Fnac, bol …) often block scripted requests. The app runs on your machine/IP, which helps; `pip install playwright && playwright install chromium` plus `PT_BROWSER=1` adds a headless-browser fallback.
* **"Exhaustive"**: this is a curated seed of national/pan-European chains, pure players, marketplaces, operators, brand stores and refurbishers. Thousands of small independent shops exist; add them as you find them.
* **Marketplaces** (bol, Amazon, eBay, Cdiscount, Rakuten, Kaufland) show the featured offer, not necessarily the lowest third-party one. **Telecom operators** are off by default because device prices are often bound to a subscription.
* Search URL patterns marked `known` come from memory and are unverified until you run the verifier.
* Respect each shop's terms of service; the app is rate-limited per domain (2 concurrent) and meant for personal price checks.

## Layout

```
data/            retailers.json/.csv · excluded.json · catalog.json
pricetracker/    matcher · extract · fetcher · discover · search · catalog · llm · verify · server · static/ (UI)
scripts/         seed_retailers.py · build_catalog.py · demo.py
tests/           fake shop server + 57 tests
```
Config via env: `PT_MAX_WORKERS`, `PT_PER_HOST`, `PT_HTTP_TIMEOUT`, `PT_MAX_PRODUCT_PAGES`, `PT_BROWSER`, `ANTHROPIC_API_KEY`, `PT_LLM_MODEL`.

## Claude Artifact version (visual app, no install)

`artifact/prices-tracker.html` is the same product as a single-page Claude Artifact (rebuild with `python scripts/build_artifact.py`).
An artifact page cannot fetch other websites itself, so it reads each shop through the **Claude desktop app's built-in browser**
(`host:claude_browser`, owner only). It opens the shop's search page, reads the page text, applies the same strict model matcher,
then tries to confirm the price on the product page. Prices must literally appear on the page; Claude is only a fallback reader and
its numbers are re-checked against the page text. Outside the desktop app it falls back to direct search links per shop.
Tests: `node artifact/test_core.js` (49 logic tests) and the UI suites `e2e_mock_main.js`, `e2e_cookies.js`, `e2e_redirect.js`, `e2e_coolblue_be.js`, `e2e_open_errors.js` (45 checks against `artifact/mock_bridge.js`, a *mock* of the desktop browser bridge modelled on the real app's messages: string tab ids, `navigate` refused, rate limits, "could not run on this page", redirects, thin `get_page_text`).
