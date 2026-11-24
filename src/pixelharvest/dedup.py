"""Exact hashes, perceptual hashes and deterministic retention recommendations."""

import hashlib
from dataclasses import asdict
from pathlib import Path

import imagehash
from PIL import Image

from .config import DEFAULTS
from .image_qc import inspect_image


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_phash(path: str | Path) -> str | None:
    try:
        with Image.open(path) as im:
            if im.width * im.height > 40000000:
                return None
            return str(imagehash.phash(im.convert("RGB")))
    except Exception:
        return None


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def quality_key(img) -> tuple:
    flags = img["qc_flags"] or ""
    px = (img["width"] or 0) * (img["height"] or 0)
    return (
        0 if "suspect_upscaled" in flags else 1,
        px,
        0 if "possibly_blurry" in flags else 1,
        1 if img["source_quality"] == "heuristic_ok" else 0,
        1 if (img["format"] or "") in ("PNG", "AVIF", "WEBP") else 0,
        -img["id"],
    )


def find_duplicates(paths, config, quality_config=None):
    records, exact, near = [], [], []
    quality_config = quality_config or {**DEFAULTS["quality"], "min_width": 0, "min_height": 0}
    invalid = []
    seen = {}
    for number, path in enumerate(sorted(map(Path, paths)), 1):
        digest = sha256_file(path)
        quality = inspect_image(path, quality_config)
        if quality.width is None or quality.height is None:
            invalid.append({"path": str(path), "quality": asdict(quality)})
            continue
        width, height, fmt = quality.width, quality.height, quality.format
        row = {
            "id": number,
            "path": str(path),
            "sha256": digest,
            "phash": compute_phash(path),
            "width": width,
            "height": height,
            "format": fmt,
            "qc_flags": ",".join(quality.flags),
            "source_quality": quality.source_quality,
        }
        if digest in seen:
            exact.append({"keep": seen[digest]["path"], "duplicate": row["path"], "sha256": digest})
        else:
            seen[digest] = row
        records.append(row)
    for i, a in enumerate(records):
        for b in records[i + 1 :]:
            if a["sha256"] == b["sha256"] or not a["phash"] or not b["phash"]:
                continue
            distance = hamming(a["phash"], b["phash"])
            ra, rb = a["width"] / a["height"], b["width"] / b["height"]
            if (
                distance <= config["phash_threshold"]
                and abs(ra - rb) / max(ra, rb) <= config["aspect_tolerance"]
            ):
                keep, other = (
                    (a, b) if config["keep"] == "first" or quality_key(a) >= quality_key(b) else (b, a)
                )
                near.append(
                    {"recommended_keep": keep["path"], "candidate": other["path"], "distance": distance}
                )
    return {
        "files": len(records),
        "exact_duplicates": exact,
        "similar_pairs": near,
        "files_removed": 0,
        "invalid_files": invalid,
        "note": "Similarity is advisory; no files are deleted.",
    }
