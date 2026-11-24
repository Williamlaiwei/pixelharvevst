import json

import httpx
import pytest

from pixelharvest.transport import HaltRun, RequestRefused, Transport, parse_retry_after


def transport(config, handler, purpose="page"):
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    return Transport(config, purpose, client=client)


def test_cookie_session_and_image_isolation(config, tmp_path):
    cookies = tmp_path / "cookies.json"
    cookies.write_text(
        json.dumps([{"name": "test_session", "value": "synthetic", "domain": "example.test", "secure": True}])
    )
    config["page_auth"].update(cookie_file=str(cookies), allowed_domains=["example.test"])
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "set-cookie": "second=local; Path=/; Secure"},
            content=b"<html></html>",
        )

    page = transport(config, handler)
    page.text("https://example.test/a")
    page.text("https://example.test/b")
    page.text("https://cdn.example.test/c")
    image = transport(config, handler, "image")
    image.text("https://cdn.example.test/image")
    assert "test_session=synthetic" in seen[0].headers["cookie"]
    assert "second=local" in seen[1].headers["cookie"]
    assert "cookie" not in seen[2].headers and "cookie" not in seen[3].headers
    page.close()
    image.close()


def test_env_header_does_not_cross_scope(config, monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "synthetic-token")
    config["page_auth"].update(headers_env={"X-API-Token": "TEST_TOKEN"}, allowed_domains=["example.test"])
    seen = []
    t = transport(
        config,
        lambda req: seen.append(req) or httpx.Response(200, headers={"content-type": "text/html"}, text="ok"),
    )
    t.text("https://example.test/a")
    t.text("https://cdn.example.test/b")
    assert "x-api-token" in seen[0].headers and "x-api-token" not in seen[1].headers
    t.close()


def test_redirect_outside_allowlist_never_requested(config):
    seen = []
    t = transport(
        config,
        lambda req: (
            seen.append(req.url.host)
            or httpx.Response(302, headers={"location": "https://outside.test/private"})
        ),
    )
    with pytest.raises(RequestRefused, match="host"):
        t.text("https://example.test/a")
    assert seen == ["example.test"]
    t.close()


@pytest.mark.parametrize("status", [401, 403, 407, 429, 503])
def test_denial_and_retry_after_halt(config, status):
    t = transport(config, lambda req: httpx.Response(status, headers={"retry-after": "120"}))
    with pytest.raises(HaltRun) as exc:
        t.text("https://example.test/a")
    assert exc.value.reason == f"http_{status}"
    if status in (429, 503):
        assert exc.value.retry_after == 120
    t.close()


def test_robots_fetched_once_and_disallow(config):
    config["http"]["respect_robots"] = True
    seen = []

    def handler(req):
        seen.append(req.url.path)
        return httpx.Response(
            200, content=b"User-agent: *\nDisallow: /private\n", headers={"content-type": "text/plain"}
        )

    t = transport(config, handler)
    for _ in range(2):
        with pytest.raises(RequestRefused, match="robots"):
            t.text("https://example.test/private")
    assert seen == ["/robots.txt"]
    t.close()


def test_rate_limit_with_injected_clock(config):
    config["http"]["request_interval_seconds"] = 3
    now = [10.0]
    sleeps = []
    t = Transport(
        config,
        client=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200))),
        clock=lambda: now[0],
        sleep=lambda value: (sleeps.append(value), now.__setitem__(0, now[0] + value)),
    )
    t.wait_turn()
    t.wait_turn()
    assert sleeps == [3.0]
    t.close()


def test_retry_after_invalid_and_numeric():
    assert parse_retry_after("broken") is None
    assert parse_retry_after("-2") == 0
    assert parse_retry_after("60") == 60
