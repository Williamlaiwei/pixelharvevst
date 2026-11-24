"""Synthetic fixtures and loopback-only HTTP server; no website data."""

from collections import Counter
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from threading import Thread

import numpy as np
from PIL import Image


def jpeg(width=1200, height=1100, seed=42):
    pixels = np.random.default_rng(seed).integers(0, 256, (height, width, 3), dtype=np.uint8)
    out = BytesIO()
    Image.fromarray(pixels).save(out, format="JPEG", quality=90)
    return out.getvalue()


@contextmanager
def serve(routes):
    """Routes: path -> (status, headers, bytes), or callable(handler)."""
    hits, sent, seen = Counter(), Counter(), []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] += 1
            seen.append((self.path, dict(self.headers)))
            route = routes.get(self.path, (404, {}, b""))
            status, headers, body = route(self) if callable(route) else route
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                for offset in range(0, len(body), 8192):
                    block = body[offset : offset + 8192]
                    self.wfile.write(block)
                    self.wfile.flush()
                    sent[self.path] += len(block)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", hits, sent, seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def image_response(body):
    return 200, {"Content-Type": "image/jpeg"}, body


def html_response(body):
    return 200, {"Content-Type": "text/html; charset=utf-8"}, body.encode()
