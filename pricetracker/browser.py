"""Optional headless-Chromium fetcher (enable with PT_BROWSER=1 and `pip install playwright`).

Used only when plain HTTP is blocked or returns an empty JavaScript shell. Playwright's sync API
must stay on one thread, so all browser work is funnelled through a single worker thread.
"""
from __future__ import annotations

import queue
import threading
import time

from . import config
from .fetcher import Page

try:  # pragma: no cover - optional dependency
    from playwright.sync_api import sync_playwright

    _HAVE = True
except Exception:  # pragma: no cover
    _HAVE = False

_jobs: "queue.Queue" = queue.Queue()
_thread: threading.Thread | None = None
_lock = threading.Lock()


def available() -> bool:
    return _HAVE


def _worker():  # pragma: no cover - needs a browser
    with sync_playwright() as pw:
        import os

        exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
        browser = pw.chromium.launch(headless=True, executable_path=exe) if exe else pw.chromium.launch(headless=True)
        while True:
            url, country, timeout, out = _jobs.get()
            page = Page(url=url, via="browser")
            ctx = None
            try:
                ctx = browser.new_context(
                    user_agent=config.USER_AGENT,
                    locale={"BE": "nl-BE", "FR": "fr-FR", "NL": "nl-NL", "DE": "de-DE"}.get(country, "en-GB"),
                )
                pg = ctx.new_page()
                t0 = time.time()
                resp = pg.goto(url, wait_until="domcontentloaded", timeout=int(timeout * 1000))
                try:
                    pg.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    pass
                page.status = resp.status if resp else 0
                page.final_url = pg.url
                page.html = pg.content()
                page.elapsed_ms = int((time.time() - t0) * 1000)
                page.fetched_at = time.time()
                if page.status >= 400:
                    page.error = "http_error"
            except Exception as e:
                page.error = "timeout" if "Timeout" in type(e).__name__ else "network"
            finally:
                if ctx:
                    ctx.close()
            out.put(page)


def fetch(url: str, country: str, timeout: float) -> Page:  # pragma: no cover
    global _thread
    with _lock:
        if _thread is None:
            _thread = threading.Thread(target=_worker, daemon=True, name="pt-browser")
            _thread.start()
    out: "queue.Queue" = queue.Queue()
    _jobs.put((url, country, timeout, out))
    try:
        return out.get(timeout=timeout + 30)
    except queue.Empty:
        return Page(url=url, error="timeout", via="browser")
