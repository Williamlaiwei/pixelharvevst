"""Optional Playwright DOM rendering behind the HTTPX policy gateway.

Browser requests are fulfilled from bounded HTTPX responses. Browser-native
redirects cannot silently bypass the transport allowlist or authentication scope.
"""

from .auth import allowed
from .transport import HaltRun, RequestRefused


class BrowserFetcher:
    def __init__(self, config, transport, factory=None):
        self.config, self.transport, self.factory = config, transport, factory
        self.manager = self.browser = self.context = None
        self.denial = None
        self.document = None

    def _start(self):
        if self.context:
            return
        if self.factory is None:
            from playwright.sync_api import sync_playwright

            self.factory = sync_playwright
        self.manager = self.factory()
        pw = self.manager.__enter__()
        options = {"headless": self.config["page"]["headless"]}
        if self.config["page"].get("browser_channel"):
            options["channel"] = self.config["page"]["browser_channel"]
        self.browser = pw.chromium.launch(**options)
        self.context = self.browser.new_context(
            java_script_enabled=self.config["page"]["render_mode"] == "rendered",
            service_workers="block",
            user_agent=self.config["http"]["user_agent"],
        )
        cookies = self.transport.auth.browser_cookies()
        if cookies:
            self.context.add_cookies(cookies)
        self.context.route("**/*", self._route)
        self.context.route_web_socket("**/*", lambda route: route.close())
        self.page = self.context.new_page()

    def _route(self, route):
        request = route.request
        main = request.resource_type == "document" and request.frame.parent_frame is None
        if not self.transport.host_allowed(request.url):
            if main:
                self.denial = RequestRefused("browser_host_not_allowed")
            route.abort()
            return
        if (
            request.method != "GET"
            or request.resource_type in ("image", "media", "font")
            or (self.config["page"]["render_mode"] == "document" and not main)
            or (request.resource_type == "document" and not main)
        ):
            route.abort()
            return
        try:
            if main and self.document and request.url == self.document[0]:
                _, code, body = self.document
                self.document = None
                route.fulfill(status=code, content_type="text/html; charset=utf-8", body=body)
                return
            # Only the scoped HTTPX jar sends credentials. Adopt JavaScript-created
            # cookies solely for an explicitly authenticated page host.
            if allowed(request.url, self.config["page_auth"]["allowed_domains"]):
                for cookie in self.context.cookies([request.url]):
                    self.transport.auth.cookies.set(
                        cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"]
                    )
            response, final_url = self.transport.open(request.url)
            try:
                if response.status_code in (401, 403, 407, 429) or (
                    500 <= response.status_code < 600 and response.headers.get("retry-after")
                ):
                    from .transport import parse_retry_after

                    raise HaltRun(
                        f"http_{response.status_code}", parse_retry_after(response.headers.get("retry-after"))
                    )
                # Additional document navigation must preserve the document URL;
                # the initial navigation is canonicalized before the browser starts.
                if main and final_url != request.url:
                    raise RequestRefused("browser_secondary_navigation_redirect")
                data = bytearray()
                for chunk in response.iter_bytes(8192):
                    data.extend(chunk)
                    if len(data) > self.config["page"]["max_html_bytes"]:
                        raise RequestRefused("browser_resource_too_large")
                headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower()
                    not in (
                        "content-encoding",
                        "content-length",
                        "transfer-encoding",
                        "set-cookie",
                        "location",
                    )
                }
                route.fulfill(status=response.status_code, headers=headers, body=bytes(data))
            finally:
                response.close()
        except (HaltRun, RequestRefused) as error:
            self.denial = error
            route.abort()
        except Exception:
            self.denial = RequestRefused("browser_resource_error")
            route.abort()

    def fetch(self, url):
        self.denial = None
        # All redirects, status handling and HTML limits run through the same
        # transport as plain HTTP, once. The browser receives the final document.
        code, final_url, html = self.transport.text(url)
        if code != 200:
            return code, final_url, html
        self.document = (final_url, code, html)
        self._start()
        try:
            self.page.goto(
                final_url,
                wait_until="domcontentloaded",
                timeout=int(self.config["http"]["timeout_seconds"] * 1000),
            )
            if self.config["page"]["render_mode"] == "rendered":
                self.page.wait_for_timeout(self.config["page"]["render_wait_ms"])
        except Exception:
            if self.denial:
                raise self.denial from None
            raise RequestRefused("browser_navigation_error") from None
        if self.denial:
            raise self.denial
        content = self.page.content()
        if len(content.encode()) > self.config["page"]["max_html_bytes"]:
            raise RequestRefused("html_too_large")
        return code, self.page.url, content

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.manager:
                self.manager.__exit__(None, None, None)
