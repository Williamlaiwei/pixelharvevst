"""Run the full pipeline against a temporary synthetic loopback site."""

import argparse
import logging
from pathlib import Path

from examples.local_site import html_response, image_response, jpeg, serve
from pixelharvest.config import load_config
from pixelharvest.pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=".pixelharvest/demo")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    large = jpeg()
    routes = {
        "/robots.txt": (200, {}, b"User-agent: *\nAllow: /\n"),
        "/gallery": html_response(
            '<title>Synthetic gallery</title><figure><img src="/large.jpg" alt="Generated texture"><figcaption>Seeded random RGB pixels</figcaption></figure><img src="/small.jpg"><img src="/copy.jpg">'
        ),
        "/large.jpg": image_response(large),
        "/copy.jpg": image_response(large),
        "/small.jpg": image_response(jpeg(320, 240)),
    }
    with serve(routes) as (base, hits, _, _):
        config = load_config(
            overrides={
                "workspace": str(Path(args.workspace).resolve()),
                "allowed_domains": ["127.0.0.1"],
                "image_domains": ["127.0.0.1"],
                "http": {"request_interval_seconds": 0},
                "page": {"renderer": "browser" if args.browser else "http"},
            }
        )
        # A fresh run each invocation; shared workspace cache remains available.
        from uuid import uuid4

        pipeline = Pipeline(config, "demo-" + uuid4().hex[:8])
        try:
            pipeline.create("page", [base + "/gallery"])
            report = pipeline.execute()
            print(report)
            print("Local requests:", dict(hits))
            assert report["counts"] == {"done": 3, "rejected": 1}
            assert report["unique_files"] == 1
        finally:
            pipeline.close()


if __name__ == "__main__":
    main()
