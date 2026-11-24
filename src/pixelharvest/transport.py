"""HTTPX streaming, explicit host checks, robots, redirects and rate limiting."""

from __future__ import annotations

import email.utils
import os
import time
from datetime import datetime, timezone
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import httpx

from .auth import Auth, allowed


class RequestRefused(Exception):
    pass


class HaltRun(Exception):
    def __init__(self, reason, retry_after=None):
        super().__init__(reason)
        self.reason, self.retry_after = reason, retry_after


def parse_retry_after(value):
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            date = email.utils.parsedate_to_datetime(value)
            return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def proxy_url(config):
    name = config["http"].get("proxy_env")
    if not name:
        return None
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Configured proxy environment variable is missing: {name}")
    try:
        parts = urlsplit(value)
        valid = parts.scheme in ("http", "https") and parts.hostname and parts.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Invalid proxy configuration")
    return value


class Transport:
    def __init__(self, config, purpose="image", *, client=None, sleep=time.sleep, clock=time.monotonic):
        self.config, self.cfg = config, config["http"]
        self.domains = config["allowed_domains" if purpose == "page" else "image_domains"]
        self.auth = Auth(config["page_auth" if purpose == "page" else "image_auth"])
        self.sleep, self.clock, self.last = sleep, clock, None
        self.robots, self.requests = {}, []
        self.owns_client = client is None
        self.client = client or httpx.Client(
            proxy=proxy_url(config),
            trust_env=False,
            follow_redirects=False,
            timeout=self.cfg["timeout_seconds"],
            headers={"User-Agent": self.cfg["user_agent"], "Accept": "*/*"},
        )
        self.client.event_hooks.setdefault("request", []).append(self._request)
        self.client.event_hooks.setdefault("response", []).append(self.auth.remember)

    def _request(self, request):
        self.auth.apply(request)
        self.requests.append(
            {"method": request.method, "host": request.url.host, "cookie_sent": "cookie" in request.headers}
        )

    def host_allowed(self, url):
        try:
            parts = urlsplit(url)
            return (
                parts.scheme in ("http", "https")
                and not parts.username
                and not parts.password
                and allowed(url, self.domains)
            )
        except ValueError:
            return False

    def wait_turn(self):
        now = self.clock()
        if self.last is not None:
            delay = self.cfg["request_interval_seconds"] - (now - self.last)
            if delay > 0:
                self.sleep(delay)
        self.last = self.clock()

    def robots_ok(self, url):
        if not self.cfg["respect_robots"]:
            return True
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robots:
            self.wait_turn()
            with self.client.stream("GET", origin + "/robots.txt") as response:
                if response.status_code in (401, 403):
                    raise HaltRun(f"robots_http_{response.status_code}")
                if response.status_code == 429:
                    raise HaltRun("robots_http_429", parse_retry_after(response.headers.get("retry-after")))
                parser = robotparser.RobotFileParser()
                if response.status_code in (404, 410):
                    parser.allow_all = True
                elif response.status_code == 200:
                    data = bytearray()
                    for chunk in response.iter_bytes(8192):
                        data.extend(chunk)
                        if len(data) > 256_000:
                            raise RequestRefused("robots_too_large")
                    parser.parse(data.decode("utf-8", errors="replace").splitlines())
                else:
                    parser.disallow_all = True
                self.robots[origin] = parser
        return self.robots[origin].can_fetch(self.cfg["user_agent"], url)

    def open(self, url):
        current = url
        for _ in range(self.cfg["max_redirects"] + 1):
            if not self.host_allowed(current):
                raise RequestRefused("host_or_scheme_not_allowed")
            if not self.robots_ok(current):
                raise RequestRefused("robots_disallow")
            self.wait_turn()
            response = self.client.send(self.client.build_request("GET", current), stream=True)
            if response.status_code in (301, 302, 303, 307, 308) and response.headers.get("location"):
                location = response.headers["location"]
                response.close()
                current = urljoin(current, location)
                continue
            return response, current
        raise RequestRefused("too_many_redirects")

    def text(self, url, max_bytes=None):
        response, final_url = self.open(url)
        try:
            if response.status_code in (401, 403, 407):
                raise HaltRun(f"http_{response.status_code}")
            if response.status_code == 429:
                raise HaltRun("http_429", parse_retry_after(response.headers.get("retry-after")))
            if 500 <= response.status_code < 600 and response.headers.get("retry-after"):
                raise HaltRun(
                    f"http_{response.status_code}", parse_retry_after(response.headers["retry-after"])
                )
            if response.status_code != 200:
                return response.status_code, final_url, ""
            if not any(
                t in response.headers.get("content-type", "").lower()
                for t in ("text/html", "application/xhtml+xml")
            ):
                raise RequestRefused("not_html")
            data = bytearray()
            for chunk in response.iter_bytes(8192):
                data.extend(chunk)
                if len(data) > (max_bytes or self.config["page"]["max_html_bytes"]):
                    raise RequestRefused("html_too_large")
            return (
                response.status_code,
                final_url,
                data.decode(response.encoding or "utf-8", errors="replace"),
            )
        finally:
            response.close()

    def close(self):
        self.client.event_hooks["request"].remove(self._request)
        self.client.event_hooks["response"].remove(self.auth.remember)
        if self.owns_client:
            self.client.close()
