import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from examples.local_site import jpeg
from pixelharvest.config import load_config


@pytest.fixture
def config(tmp_path):
    return load_config(
        overrides={
            "workspace": str(tmp_path / "workspace"),
            "allowed_domains": ["example.test", "cdn.example.test"],
            "image_domains": ["cdn.example.test"],
            "http": {"request_interval_seconds": 0, "respect_robots": False, "backoff_seconds": 0},
            "quality": {"min_width": 100, "min_height": 100},
        }
    )


@pytest.fixture(scope="session")
def picture():
    return jpeg(500, 400)


@pytest.fixture
def image_file(tmp_path, picture):
    path = tmp_path / "picture.jpg"
    path.write_bytes(picture)
    return path


def encoded_image(width, height, fmt="JPEG"):
    out = BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format=fmt)
    return out.getvalue()
