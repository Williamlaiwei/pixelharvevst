"""Scoped cookie files and environment-backed headers, separate for pages and images."""

from __future__ import annotations

import http.cookiejar
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def allowed(url, domains):
    return (urlsplit(url).hostname or "").lower() in {h.lower() for h in domains}


def public_url(url):
    parts = urlsplit(url)
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if parts.port:
        host += f":{parts.port}"
    return f"{parts.scheme}://{host}{parts.path}"


class Auth:
    def __init__(self, config):
        self.config = config
        self.cookies = httpx.Cookies()
        cookie_file = config.get("cookie_file")
        if cookie_file:
            path = Path(cookie_file)
            if path.suffix.lower() == ".json":
                rows = json.loads(path.read_text(encoding="utf-8"))
                jar = http.cookiejar.CookieJar()
                for row in rows:
                    domain = row["domain"]
                    cookie = http.cookiejar.Cookie(
                        0,
                        row["name"],
                        row["value"],
                        None,
                        False,
                        domain,
                        True,
                        domain.startswith("."),
                        row.get("path", "/"),
                        True,
                        row.get("secure", True),
                        (row.get("expires") if (row.get("expires") or -1) > 0 else None),
                        False,
                        None,
                        None,
                        {},
                        False,
                    )
                    jar.set_cookie(cookie)
            else:
                jar = http.cookiejar.MozillaCookieJar(str(path))
                jar.load(ignore_discard=True, ignore_expires=False)
            self.cookies = httpx.Cookies(jar)
        self.headers = dict(config.get("headers", {}))
        for header, name in config.get("headers_env", {}).items():
            value = os.environ.get(name)
            if not value:
                raise ValueError(f"Required authentication environment variable is missing: {name}")
            self.headers[header] = value

    def apply(self, request):
        for header in ("cookie", "authorization", "proxy-authorization"):
            request.headers.pop(header, None)
        if allowed(str(request.url), self.config.get("allowed_domains", [])):
            self.cookies.set_cookie_header(request)
            request.headers.update(self.headers)
        else:
            request.headers.update(self.config.get("headers", {}))

    def remember(self, response):
        if allowed(str(response.url), self.config.get("allowed_domains", [])):
            self.cookies.extract_cookies(response)

    def browser_cookies(self):
        result = []
        domains = self.config.get("allowed_domains", [])
        for cookie in self.cookies.jar:
            if not any(
                h.lower() == cookie.domain.lstrip(".").lower()
                or (cookie.domain.startswith(".") and h.lower().endswith(cookie.domain.lower()))
                for h in domains
            ):
                continue
            row = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "secure": cookie.secure,
            }
            if cookie.expires is not None:
                row["expires"] = float(cookie.expires)
            result.append(row)
        return result
