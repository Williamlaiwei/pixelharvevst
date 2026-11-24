import os

import pytest

from examples.local_site import html_response, image_response, serve
from pixelharvest.config import load_config
from pixelharvest.page_fetchers import BrowserFetcher
from pixelharvest.pipeline import Pipeline
from pixelharvest.transport import RequestRefused, Transport

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("PIXELHARVEST_BROWSER_TESTS") != "1",
        reason="Set PIXELHARVEST_BROWSER_TESTS=1 after installing Chromium",
    ),
]


def test_real_browser_dynamic_dom_and_image_isolation(tmp_path, picture):
    routes = {
        "/page": html_response(
            '<title>Local browser</title><script>document.addEventListener("DOMContentLoaded",()=>{document.body.innerHTML+=\'<img src="/image.jpg">\';});</script>'
        ),
        "/image.jpg": image_response(picture),
    }
    with serve(routes) as (base, hits, _, _):
        cfg = load_config(
            overrides={
                "workspace": str(tmp_path / "work"),
                "allowed_domains": ["127.0.0.1"],
                "image_domains": ["127.0.0.1"],
                "http": {"respect_robots": False, "request_interval_seconds": 0},
                "page": {"renderer": "browser", "render_mode": "rendered", "render_wait_ms": 100},
                "quality": {"min_width": 100, "min_height": 100},
            }
        )
        p = Pipeline(cfg, "browser")
        p.create("page", [base + "/page"])
        try:
            assert p.execute()["counts"] == {"done": 2}
            assert hits["/image.jpg"] == 1
        finally:
            p.close()


def test_browser_redirect_allowlist(tmp_path):
    routes = {"/redirect": (302, {"Location": "http://localhost:1/not-allowed"}, b"")}
    with serve(routes) as (base, hits, _, _):
        cfg = load_config(
            overrides={
                "workspace": str(tmp_path / "work"),
                "allowed_domains": ["127.0.0.1"],
                "image_domains": ["127.0.0.1"],
                "http": {"respect_robots": False, "request_interval_seconds": 0},
                "page": {"renderer": "browser"},
            }
        )
        transport = Transport(cfg, "page")
        browser = BrowserFetcher(cfg, transport)
        try:
            with pytest.raises(RequestRefused, match="host"):
                browser.fetch(base + "/redirect")
            assert hits["/redirect"] == 1
        finally:
            browser.close()
            transport.close()


def test_browser_authenticated_page_and_cookieless_image(tmp_path, picture, monkeypatch):
    monkeypatch.setenv("TEST_BROWSER_TOKEN", "synthetic-browser-token")
    routes = {
        "/page": (
            200,
            {"Content-Type": "text/html", "Set-Cookie": "local_session=synthetic; Path=/"},
            b'<title>Private local fixture</title><img src="/image.jpg">',
        ),
        "/image.jpg": image_response(picture),
    }
    with serve(routes) as (base, hits, _, seen):
        cfg = load_config(
            overrides={
                "workspace": str(tmp_path / "work"),
                "allowed_domains": ["127.0.0.1"],
                "image_domains": ["127.0.0.1"],
                "http": {"respect_robots": False, "request_interval_seconds": 0},
                "page": {"renderer": "browser"},
                "page_auth": {
                    "allowed_domains": ["127.0.0.1"],
                    "headers_env": {"X-Test-Auth": "TEST_BROWSER_TOKEN"},
                },
                "quality": {"min_width": 100, "min_height": 100},
            }
        )
        p = Pipeline(cfg, "auth-browser")
        p.create("page", [base + "/page"])
        try:
            assert p.execute()["counts"] == {"done": 2}
            page_headers = next(headers for path, headers in seen if path == "/page")
            image_headers = next(headers for path, headers in seen if path == "/image.jpg")
            assert page_headers["X-Test-Auth"] == "synthetic-browser-token"
            assert not any(key.lower() in ("cookie", "x-test-auth") for key in image_headers)
            assert hits["/page"] == 1
        finally:
            p.close()
