"""Image integrity, pixel limits and advisory FFT/Laplacian metrics."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFile

try:
    import pillow_avif  # noqa: F401 -- registers optional Pillow codec
except ImportError:
    pass
ImageFile.LOAD_TRUNCATED_IMAGES = False
EXT_BY_FORMAT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "AVIF": "avif"}


@dataclass
class QCResult:
    status: str
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    format: str | None = None
    file_size: int = 0
    mode: str | None = None
    has_icc: bool = False
    source_quality: str = "unknown"
    metrics: dict = field(default_factory=dict)

    @property
    def ext(self) -> str:
        return EXT_BY_FORMAT.get(self.format or "", "bin")


def _gray_crop(img: Image.Image, size: int = 512) -> np.ndarray:
    g = img.convert("L")
    w, h = g.size
    if w > size and h > size:
        left, top = ((w - size) // 2, (h - size) // 2)
        g = g.crop((left, top, left + size, top + size))
    return np.asarray(g, dtype=np.float32)


def high_freq_ratio(gray: np.ndarray) -> float:
    h, w = gray.shape
    win = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)
    spec = np.abs(np.fft.fftshift(np.fft.fft2((gray - gray.mean()) * win))) ** 2
    yy, xx = np.indices(spec.shape)
    r = np.hypot((yy - h / 2) / (h / 2), (xx - w / 2) / (w / 2))
    total = spec[r > 0.05].sum()
    return float(spec[r > 0.6].sum() / total) if total > 0 else 0.0


def laplacian_var(gray: np.ndarray) -> float:
    if min(gray.shape) < 3:
        return 0.0
    lap = -4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
    return float(lap.var())


def inspect_image(path: str | Path, cfg: dict) -> QCResult:
    path = Path(path)
    res = QCResult(status="rejected", file_size=path.stat().st_size if path.exists() else 0)
    if res.file_size == 0:
        res.reasons.append("empty_file")
        return res
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as im:
                res.format = im.format
                if im.width * im.height > cfg.get("max_pixels", 40000000):
                    raise Image.DecompressionBombError("pixel_limit")
                im.verify()
            with Image.open(path) as im:
                im.load()
                res.width, res.height = im.size
                res.mode = im.mode
                res.has_icc = bool(im.info.get("icc_profile"))
                work = im.copy()
    except Exception as e:
        res.reasons.append(f"decode_error:{type(e).__name__}")
        return res
    if res.format not in cfg["allowed_formats"]:
        res.reasons.append(f"unsupported_format:{res.format}")
    short = min(res.width, res.height)
    if res.width < cfg.get("min_width", 0) or res.height < cfg.get("min_height", 0):
        res.reasons.append("dimensions_below_minimum")
    if cfg.get("reject_extreme_aspect") and max(res.width, res.height) / short > cfg["max_aspect_ratio"]:
        res.reasons.append("aspect_ratio_exceeded")
    if short < cfg["min_short_side"]:
        res.reasons.append(f"short_side_lt_{cfg['min_short_side']}")
    if res.reasons:
        return res
    if not cfg.get("heuristics", True):
        res.status = "pass"
        return res
    gray = _gray_crop(work)
    res.metrics["gray_std"] = round(float(gray.std()), 3)
    if gray.std() < 1.0:
        res.reasons.append("blank_image")
    if res.reasons:
        return res
    res.metrics["short_side"] = short
    ratio = max(res.width, res.height) / short
    res.metrics["aspect_ratio"] = round(ratio, 3)
    if ratio > cfg["max_aspect_ratio"]:
        res.flags.append("extreme_aspect_ratio")
    hf = high_freq_ratio(gray)
    res.metrics["hf_ratio"] = hf
    if hf < cfg["upscale_hf_ratio_threshold"]:
        res.flags.append("suspect_upscaled")
    lv = laplacian_var(gray)
    res.metrics["laplacian_var"] = round(lv, 2)
    if lv < cfg["blur_laplacian_threshold"]:
        res.flags.append("possibly_blurry")
    full = np.asarray(work.convert("L"), dtype=np.float32)
    if (full > 240).mean() > cfg["white_page_fraction"]:
        res.flags.append("possible_document_or_white_page")
    b = max(2, int(0.03 * min(full.shape)))
    strips = [full[:b, :], full[-b:, :], full[:, :b], full[:, -b:]]
    if all((s.std() < 3 and s.mean() > 235 for s in strips)):
        res.flags.append("white_border_possible_page_layout")
    if res.mode in ("CMYK", "P", "1"):
        res.flags.append(f"unusual_color_mode:{res.mode}")
    if res.flags:
        res.status = "review"
        res.source_quality = "suspect_upscaled" if "suspect_upscaled" in res.flags else "unverified"
    else:
        res.status = "pass"
        res.source_quality = "heuristic_ok"
    return res
