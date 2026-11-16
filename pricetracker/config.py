"""Central configuration. Everything can be overridden through environment variables."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PT_DATA_DIR", ROOT / "data"))
STATIC_DIR = Path(__file__).resolve().parent / "static"

RETAILERS_FILE = DATA_DIR / "retailers.json"
EXCLUDED_FILE = DATA_DIR / "excluded.json"
CATALOG_FILE = DATA_DIR / "catalog.json"

# --- networking ---------------------------------------------------------
HTTP_TIMEOUT = float(os.environ.get("PT_HTTP_TIMEOUT", "20"))      # seconds per request
MAX_WORKERS = int(os.environ.get("PT_MAX_WORKERS", "16"))          # parallel retailers
PER_HOST_CONCURRENCY = int(os.environ.get("PT_PER_HOST", "2"))     # politeness per domain
MAX_PRODUCT_PAGES = int(os.environ.get("PT_MAX_PRODUCT_PAGES", "4"))  # verified per retailer
MAX_QUERIES = int(os.environ.get("PT_MAX_QUERIES", "4"))           # alias searches per retailer
MAX_BYTES = int(os.environ.get("PT_MAX_BYTES", str(4_000_000)))    # cap on downloaded HTML

USER_AGENT = os.environ.get(
    "PT_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)

# Optional headless browser (needs `pip install playwright && playwright install chromium`)
USE_BROWSER = os.environ.get("PT_BROWSER", "0") == "1"

# Tests spin up local fixture shops on 127.0.0.1; real deployments must keep this off
# so the server can never be used to reach private network addresses (SSRF guard).
ALLOW_PRIVATE_HOSTS = os.environ.get("PT_ALLOW_PRIVATE_HOSTS", "0") == "1"

DEMO = os.environ.get("PT_DEMO", "0") == "1"   # set by scripts/demo.py – never for real use

# Optional LLM-assisted product identification (falls back to the local catalog)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("PT_LLM_MODEL", "claude-haiku-5-5")

ACCEPT_LANGUAGE = {
    "BE": "nl-BE,nl;q=0.9,fr-BE;q=0.8,fr;q=0.7,en;q=0.5",
    "FR": "fr-FR,fr;q=0.9,en;q=0.5",
    "NL": "nl-NL,nl;q=0.9,en;q=0.5",
    "DE": "de-DE,de;q=0.9,en;q=0.5",
}

COUNTRY_NAMES = {"BE": "Belgium", "FR": "France", "NL": "Netherlands", "DE": "Germany"}
