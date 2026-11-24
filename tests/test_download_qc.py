import httpx
import numpy as np
import pytest
from conftest import encoded_image
from test_transport import transport

from pixelharvest.downloader import Downloader
from pixelharvest.image_qc import high_freq_ratio, inspect_image, laplacian_var
from pixelharvest.transport import HaltRun


class CountingStream(httpx.SyncByteStream):
    def __init__(self, data):
        self.data = data
        self.consumed = 0
        self.closed = False

    def __iter__(self):
        for offset in range(0, len(self.data), 8192):
            block = self.data[offset : offset + 8192]
            self.consumed += len(block)
            yield block

    def close(self):
        self.closed = True


def test_early_dimension_rejection_stops_stream(config, tmp_path):
    # Tall/short geometry with enough real pixel data to span many network chunks.
    from examples.local_site import jpeg

    data = jpeg(2000, 80)
    stream = CountingStream(data)
    t = transport(
        config,
        lambda req: httpx.Response(200, headers={"content-type": "image/jpeg"}, stream=stream),
        "image",
    )
    part = tmp_path / "test.part"
    result = Downloader(config, t).fetch("https://cdn.example.test/small", part)
    assert result["status"] == "skipped_actual_dimensions"
    assert result["actual_height"] == 80
    assert result["dimension_known_at_bytes"] <= 8192
    assert stream.consumed < len(data) and stream.closed and not part.exists()
    t.close()


@pytest.mark.parametrize(
    "body,content_type,reason",
    [
        (b"not an image", "image/jpeg", "decode_or_file_error"),
        (b"<html>blocked</html>", "text/html", "not_image_content_type"),
    ],
)
def test_wrong_content(config, tmp_path, body, content_type, reason):
    t = transport(
        config, lambda req: httpx.Response(200, headers={"content-type": content_type}, content=body), "image"
    )
    part = tmp_path / "test.part"
    result = Downloader(config, t).fetch("https://cdn.example.test/a", part)
    assert result["reason"].startswith(reason) and not part.exists()
    t.close()


def test_transient_retry_and_file_integrity(config, tmp_path, picture):
    calls = []
    sleeps = []

    def handler(req):
        calls.append(req)
        return (
            httpx.Response(503)
            if len(calls) == 1
            else httpx.Response(200, headers={"content-type": "image/jpeg"}, content=picture)
        )

    t = transport(config, handler, "image")
    t.sleep = sleeps.append
    part = tmp_path / "good.part"
    result = Downloader(config, t).fetch("https://cdn.example.test/a", part)
    assert result["status"] == "downloaded" and result["attempts"] == 2 and part.read_bytes() == picture
    assert len(sleeps) == 1
    t.close()


def test_auth_denial_stops_without_retry(config, tmp_path):
    calls = []
    t = transport(config, lambda req: calls.append(req) or httpx.Response(403), "image")
    with pytest.raises(HaltRun):
        Downloader(config, t).fetch("https://cdn.example.test/a", tmp_path / "x.part")
    assert len(calls) == 1
    t.close()


def test_truncated_and_pixel_limit(config, tmp_path, picture, image_file):
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(picture[:10000])
    assert inspect_image(broken, config["quality"]).status == "rejected"
    config["quality"]["max_pixels"] = 100
    assert "DecompressionBomb" in inspect_image(image_file, config["quality"]).reasons[0]


def test_format_limits_and_aspect(config, tmp_path, image_file):
    qc = config["quality"]
    qc["allowed_formats"] = ["PNG"]
    assert inspect_image(image_file, qc).status == "rejected"
    qc["allowed_formats"] = ["JPEG"]
    qc["max_aspect_ratio"] = 1.1
    qc["reject_extreme_aspect"] = True
    assert "aspect_ratio_exceeded" in inspect_image(image_file, qc).reasons


def test_metrics_and_blank(config, tmp_path, image_file):
    result = inspect_image(image_file, config["quality"])
    assert result.status in ("pass", "review") and "laplacian_var" in result.metrics
    blank = tmp_path / "blank.jpg"
    blank.write_bytes(encoded_image(200, 200))
    assert "blank_image" in inspect_image(blank, config["quality"]).reasons
    assert laplacian_var(np.ones((1, 1))) == 0
    assert high_freq_ratio(np.ones((10, 10))) == 0


def test_decoded_format_controls_extension(config, tmp_path):
    path = tmp_path / "misleading.jpg"
    path.write_bytes(encoded_image(200, 200, "PNG"))
    config["quality"]["heuristics"] = False
    assert inspect_image(path, config["quality"]).ext == "png"


@pytest.mark.parametrize(
    "setting,headers,reason",
    [
        (100, {"content-type": "image/jpeg", "content-length": "1000"}, "file_too_large"),
        (100, {"content-type": "image/jpeg"}, "file_too_large"),
        (1000000, {"content-type": "image/jpeg", "content-length": "999999"}, "incomplete_response"),
    ],
)
def test_file_caps_and_incomplete_response(config, tmp_path, picture, setting, headers, reason):
    config["http"]["max_file_bytes"] = setting
    t = transport(
        config, lambda req: httpx.Response(200, headers=headers, stream=CountingStream(picture)), "image"
    )
    part = tmp_path / "limited.part"
    result = Downloader(config, t).fetch("https://cdn.example.test/image", part)
    assert result["reason"] == reason and not part.exists()
    t.close()


def test_bomb_header_never_finishes_download(config, tmp_path, picture):
    config["quality"]["max_pixels"] = 100
    stream = CountingStream(picture)
    t = transport(
        config,
        lambda req: httpx.Response(200, headers={"content-type": "image/jpeg"}, stream=stream),
        "image",
    )
    part = tmp_path / "unsafe.part"
    assert (
        Downloader(config, t).fetch("https://cdn.example.test/image", part)["reason"] == "decompression_bomb"
    )
    assert stream.closed and stream.consumed < len(picture) and not part.exists()
    t.close()
