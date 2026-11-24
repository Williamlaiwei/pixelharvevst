"""Measured HTTP-body bytes, never an estimated transfer calculation."""

import argparse
import importlib.metadata
import json
import platform
import tempfile
import time
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from examples.local_site import image_response, jpeg, serve
from pixelharvest.config import load_config
from pixelharvest.downloader import Downloader
from pixelharvest.transport import Transport


def run():
    # Reject geometry deliberately varied: panoramas can be large files but short in pixels.
    bodies = [jpeg(4096, 512, seed=i) for i in range(6)] + [jpeg(1600, 1200, seed=20 + i) for i in range(2)]
    routes = {f"/{i}.jpg": image_response(body) for i, body in enumerate(bodies)}
    measurements = {}
    with serve(routes) as (base, _, sent, _), tempfile.TemporaryDirectory() as directory:
        config = load_config(
            overrides={
                "workspace": directory,
                "allowed_domains": ["127.0.0.1"],
                "image_domains": ["127.0.0.1"],
                "http": {"request_interval_seconds": 0, "respect_robots": False},
            }
        )
        for mode in ("full_download", "streaming_early_rejection"):
            before = sum(sent.values())
            transferred = 0
            rejected = 0
            started = time.perf_counter()
            if mode == "full_download":
                with httpx.Client(trust_env=False, timeout=20) as client:
                    for name in routes:
                        data = client.get(base + name).content
                        transferred += len(data)
                        with Image.open(BytesIO(data)) as image:
                            small = image.width < 1024 or image.height < 1024
                            if not small:
                                image.verify()
                        if not small:
                            with Image.open(BytesIO(data)) as image:
                                image.load()
                        rejected += int(small)
            else:
                transport = Transport(config)
                try:
                    downloader = Downloader(config, transport)
                    for i, name in enumerate(routes):
                        part = Path(directory) / f"{i}.part"
                        result = downloader.fetch(base + name, part)
                        transferred += result["bytes_received"]
                        rejected += int(result["status"] == "skipped_actual_dimensions")
                        part.unlink(missing_ok=True)
                finally:
                    transport.close()
            measurements[mode] = {
                "body_bytes_consumed": transferred,
                "rejected_images": rejected,
                "elapsed_seconds": round(time.perf_counter() - started, 6),
                "server_write_bytes_observed": sum(sent.values()) - before,
            }
    full = measurements["full_download"]["body_bytes_consumed"]
    early = measurements["streaming_early_rejection"]["body_bytes_consumed"]
    assert (
        measurements["full_download"]["rejected_images"]
        == measurements["streaming_early_rejection"]["rejected_images"]
        == 6
    )
    assert early < full
    return {
        "dataset": {
            "generator": "seeded uniform RGB, JPEG quality 90; no padding",
            "images": 8,
            "rejected_geometry": "6 x 4096x512",
            "accepted_geometry": "2 x 1600x1200",
            "minimum_width": 1024,
            "minimum_height": 1024,
        },
        "environment": {
            "python": platform.python_version(),
            "os": platform.system(),
            "machine": platform.machine(),
            "httpx": importlib.metadata.version("httpx"),
            "Pillow": importlib.metadata.version("Pillow"),
        },
        "measurements": measurements,
        "bytes_saved": full - early,
        "body_bytes_saved_percent": round((full - early) * 100 / full, 3),
        "methodology": "One sequential round per method against a loopback HTTP server. Both check actual dimensions; accepted files verify and decode. FFT/pHash/QC are excluded from both timings. Application body bytes are measured; server/kernel read-ahead and protocol overhead are not wire-byte savings. Geometry intentionally favors rejection; not a representative website workload.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="benchmarks/results.json")
    args = parser.parse_args()
    result = run()
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
