"""Receiver extracted from the predecessor; HTTPX remains the download engine."""

import warnings
from datetime import datetime, timezone

import httpx
from PIL import Image, ImageFile

from .transport import HaltRun, RequestRefused, parse_retry_after


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _receive(polite, url, part, settings, minimum):
    result = {
        "status": "failed",
        "bytes_received": 0,
        "dimension_known_at_bytes": None,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        response, final_url = polite.open(url)
        try:
            result.update(http_status=response.status_code, final_url=final_url)
            result["retry_after"] = parse_retry_after(response.headers.get("retry-after"))
            result["response_headers"] = {
                k: response.headers[k]
                for k in (
                    "content-type",
                    "content-length",
                    "content-encoding",
                    "etag",
                    "last-modified",
                    "vary",
                    "cache-control",
                )
                if k in response.headers
            }
            if response.status_code != 200:
                result["reason"] = f"http_{response.status_code}"
                return result
            if not response.headers.get("content-type", "").lower().startswith("image/"):
                result["reason"] = "not_image_content_type"
                return result
            length = _int(response.headers.get("content-length"))
            maximum = settings["http"]["max_file_bytes"]
            if length > maximum:
                result["reason"] = "file_too_large"
                return result
            parser = ImageFile.Parser()
            header_known = False
            with part.open("wb") as f:
                for chunk in response.iter_bytes(8192):
                    result["bytes_received"] += len(chunk)
                    if result["bytes_received"] > maximum:
                        result["reason"] = "file_too_large"
                        return result
                    f.write(chunk)
                    if parser is not None and (not header_known):
                        try:
                            parser.feed(chunk)
                        except (OSError, ValueError):
                            parser = None
                        if parser is not None and parser.image is not None:
                            width, height = parser.image.size
                            header_known = True
                            if width * height > settings["qc"].get("max_pixels", 40000000):
                                raise Image.DecompressionBombError("pixel_limit")
                            result.update(
                                actual_width=width,
                                actual_height=height,
                                dimension_known_at_bytes=result["bytes_received"],
                            )
                            if (
                                min(width, height) < minimum
                                or width < settings["qc"].get("min_width", 0)
                                or height < settings["qc"].get("min_height", 0)
                            ):
                                result.update(
                                    status="skipped_actual_dimensions",
                                    reason="short_side_below_minimum",
                                    size_decision_stage="during_get",
                                )
                                return result
            if (
                length
                and (not response.headers.get("content-encoding"))
                and (result["bytes_received"] != length)
            ):
                result["reason"] = "incomplete_response"
                return result
        finally:
            response.close()
        with Image.open(part) as image:
            image.verify()
        with Image.open(part) as image:
            image.load()
            width, height = image.size
            fmt = image.format
        result.update(actual_width=width, actual_height=height, format=fmt)
        if not header_known:
            result["dimension_known_at_bytes"] = result["bytes_received"]
        if fmt not in settings["qc"]["allowed_formats"]:
            result["reason"] = "unsupported_format"
        elif (
            min(width, height) < minimum
            or width < settings["qc"].get("min_width", 0)
            or height < settings["qc"].get("min_height", 0)
        ):
            result.update(
                status="skipped_actual_dimensions",
                reason="short_side_below_minimum",
                size_decision_stage="after_get_decode",
            )
        else:
            result.update(status="downloaded", reason="", size_decision_stage="after_get_decode")
    except RequestRefused as e:
        result["reason"] = "request_refused:" + str(e)
    except httpx.HTTPError as e:
        result["reason"] = "network_error:" + type(e).__name__
    except (OSError, ValueError) as e:
        result["reason"] = "decode_or_file_error:" + type(e).__name__
    return result


class Downloader:
    def __init__(self, config, transport):
        self.config, self.transport = config, transport

    def fetch(self, url, part):
        settings = {"http": self.config["http"], "qc": self.config["quality"]}
        transferred = 0
        for attempt in range(1, self.config["http"]["max_attempts"] + 1):
            part.unlink(missing_ok=True)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    result = _receive(self.transport, url, part, settings, settings["qc"]["min_short_side"])
            except (Image.DecompressionBombError, Image.DecompressionBombWarning):
                result = {"status": "failed", "reason": "decompression_bomb", "bytes_received": 0}
            except BaseException:
                part.unlink(missing_ok=True)
                raise
            transferred += result.get("bytes_received", 0)
            result.update(attempts=attempt, bytes_received=transferred)
            code = result.get("http_status")
            if code in (401, 403, 407, 429):
                part.unlink(missing_ok=True)
                raise HaltRun(f"http_{code}", result.get("retry_after"))
            if code and 500 <= code < 600 and result.get("retry_after") is not None:
                part.unlink(missing_ok=True)
                raise HaltRun(f"http_{code}", result["retry_after"])
            retry = (code is not None and 500 <= code < 600) or result.get("reason", "").startswith(
                "network_error:"
            )
            if result["status"] == "downloaded":
                return result
            part.unlink(missing_ok=True)
            if not retry or attempt == self.config["http"]["max_attempts"]:
                return result
            self.transport.sleep(self.config["http"]["backoff_seconds"] * 2 ** (attempt - 1))
        raise RuntimeError("unreachable")
