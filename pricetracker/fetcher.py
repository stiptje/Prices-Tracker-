"""Live HTTP fetching.

* No caching, ever: every call goes to the shop and carries no-cache request headers.
* Politeness: at most PER_HOST_CONCURRENCY simultaneous requests per domain.
* Safety: refuses private/loopback/link-local targets (unless PT_ALLOW_PRIVATE_HOSTS=1 for tests)
  and, via `host_allowed`, only talks to domains that are in the retailer database.
* Honest failures: blocked / timeout / http-error are returned as a status, never swallowed.
"""
from __future__ import annotations

import ipaddress
import socket
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from . import config
from .extract import looks_blocked

_host_sems: dict[str, threading.Semaphore] = {}
_host_lock = threading.Lock()


def _sem(host: str) -> threading.Semaphore:
    with _host_lock:
        if host not in _host_sems:
            _host_sems[host] = threading.Semaphore(config.PER_HOST_CONCURRENCY)
        return _host_sems[host]


@dataclass
class Page:
    url: str                 # requested URL
    final_url: str = ""      # after redirects
    status: int = 0
    html: str = ""
    error: str = ""          # "" | blocked | timeout | http_error | network | unsafe_url | too_large
    elapsed_ms: int = 0
    via: str = "http"        # http | browser
    fetched_at: float = 0.0  # unix time the response arrived

    @property
    def ok(self) -> bool:
        return not self.error and 200 <= self.status < 300 and bool(self.html)


def is_safe_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    if config.ALLOW_PRIVATE_HOSTS:
        return True
    host = p.hostname
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return True  # unresolved here → the request itself will fail with a clear network error
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def host_allowed(url: str, allowed_domains: set[str]) -> bool:
    """True when url's host is one of (or a subdomain of) the registered retailer domains."""
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


def _headers(country: str) -> dict[str, str]:
    return {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": config.ACCEPT_LANGUAGE.get(country, "en;q=0.8"),
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }


def fetch(url: str, country: str = "", *, timeout: float | None = None, retries: int = 1) -> Page:
    """Fetch `url` live. Falls back to the headless browser when enabled and the shop blocks plain HTTP."""
    page = _http_fetch(url, country, timeout or config.HTTP_TIMEOUT, retries)
    if config.USE_BROWSER and (page.error in ("blocked",) or (page.ok and _needs_js(page.html))):
        from . import browser

        if browser.available():
            bp = browser.fetch(url, country, timeout or config.HTTP_TIMEOUT)
            if bp.ok or not page.ok:
                return bp
    return page


def _needs_js(html: str) -> bool:
    low = html[:200000].lower()
    return len(html) < 4000 and ("enable javascript" in low or "<noscript" in low) or (
        "<div id=\"root\"></div>" in low or "<div id=\"app\"></div>" in low
    )


def _http_fetch(url: str, country: str, timeout: float, retries: int) -> Page:
    page = Page(url=url)
    if not is_safe_url(url):
        page.error = "unsafe_url"
        return page
    host = urlparse(url).hostname or ""
    sem = _sem(host)
    last_err = ""
    for attempt in range(retries + 1):
        t0 = time.time()
        with sem:
            try:
                r = requests.get(
                    url, headers=_headers(country), timeout=(min(8, timeout), timeout),
                    allow_redirects=True, stream=True,
                )
                chunks, size = [], 0
                for chunk in r.iter_content(65536):
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > config.MAX_BYTES:
                        break
                body = b"".join(chunks)
                enc = r.encoding or r.apparent_encoding or "utf-8"
                try:
                    html = body.decode(enc, errors="replace")
                except LookupError:
                    html = body.decode("utf-8", errors="replace")
                page.status = r.status_code
                page.final_url = r.url
                page.html = html
                page.elapsed_ms = int((time.time() - t0) * 1000)
                page.fetched_at = time.time()
                r.close()
                if looks_blocked(r.status_code, html):
                    page.error = "blocked"
                elif r.status_code >= 400:
                    page.error = "http_error"
                return page
            except requests.Timeout:
                last_err = "timeout"
            except requests.RequestException:  # DNS, TLS, connection reset …
                last_err = "network"
        time.sleep(0.4 * (attempt + 1))
    page.error = last_err or "network"
    page.fetched_at = time.time()
    return page
