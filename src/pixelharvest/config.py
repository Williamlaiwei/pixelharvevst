"""Small validated YAML configuration; credentials are referenced, not embedded."""

from __future__ import annotations

import copy
import math
from pathlib import Path

import soupsieve
import yaml

DEFAULTS = {
    "workspace": ".pixelharvest",
    "urls": [],
    "allowed_domains": [],
    "image_domains": [],
    "selectors": ["img"],
    "batch_size": 100,
    "page": {
        "renderer": "http",
        "render_mode": "document",
        "headless": True,
        "browser_channel": None,
        "render_wait_ms": 1000,
        "max_html_bytes": 5_000_000,
    },
    "http": {
        "user_agent": "PixelHarvest/0.1",
        "request_interval_seconds": 3.0,
        "timeout_seconds": 20.0,
        "max_redirects": 3,
        "max_attempts": 2,
        "backoff_seconds": 2.0,
        "default_retry_after_seconds": 60.0,
        "respect_robots": True,
        "max_file_bytes": 52_428_800,
        "proxy_env": None,
    },
    "page_auth": {"cookie_file": None, "headers_env": {}, "headers": {}, "allowed_domains": []},
    "image_auth": {"cookie_file": None, "headers_env": {}, "headers": {}, "allowed_domains": []},
    "quality": {
        "min_width": 1024,
        "min_height": 1024,
        "min_short_side": 0,
        "max_pixels": 40_000_000,
        "allowed_formats": ["JPEG", "PNG", "WEBP", "AVIF"],
        "max_aspect_ratio": 3.5,
        "reject_extreme_aspect": False,
        "upscale_hf_ratio_threshold": 0.005,
        "blur_laplacian_threshold": 20.0,
        "white_page_fraction": 0.85,
        "heuristics": True,
    },
    "dedup": {"phash_threshold": 8, "aspect_tolerance": 0.02, "keep": "best"},
}


def merge(base, override):
    if not isinstance(override, dict):
        raise ValueError("Configuration sections must be mappings")
    if not base:
        return copy.deepcopy(override)
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key not in base:
            raise ValueError(f"Unknown configuration key: {key}")
        result[key] = merge(base[key], value) if isinstance(base[key], dict) else value
    return result


def validate(config):
    if not config["allowed_domains"] or not config["image_domains"]:
        raise ValueError("Explicit allowed_domains and image_domains are required")
    for name in ("allowed_domains", "image_domains"):
        if not isinstance(config[name], list) or any(
            not isinstance(h, str) or not h or any(c in h for c in "/:@* ") for h in config[name]
        ):
            raise ValueError(f"{name} must contain exact hostnames, without ports or wildcards")
    if not config["selectors"] or not all(isinstance(s, str) for s in config["selectors"]):
        raise ValueError("selectors must contain CSS selectors")
    for selector in config["selectors"]:
        soupsieve.compile(selector)
    for key in ("max_attempts", "max_redirects", "max_file_bytes"):
        if type(config["http"][key]) is not int:
            raise ValueError(f"http.{key} must be an integer")
    for key in (
        "request_interval_seconds",
        "backoff_seconds",
        "default_retry_after_seconds",
        "timeout_seconds",
    ):
        if not isinstance(config["http"][key], (int, float)) or not math.isfinite(config["http"][key]):
            raise ValueError(f"http.{key} must be a finite number")
    if config["page"]["renderer"] not in ("http", "browser"):
        raise ValueError("page.renderer must be http or browser")
    if config["page"]["render_mode"] not in ("document", "rendered"):
        raise ValueError("page.render_mode must be document or rendered")
    if not isinstance(config["batch_size"], int) or config["batch_size"] < 1:
        raise ValueError("batch_size must be a positive integer")
    for key in ("request_interval_seconds", "backoff_seconds", "default_retry_after_seconds"):
        if not isinstance(config["http"][key], (int, float)) or config["http"][key] < 0:
            raise ValueError(f"http.{key} must be nonnegative")
    if config["http"]["timeout_seconds"] <= 0 or config["http"]["max_attempts"] < 1:
        raise ValueError("Timeout and attempt limit must be positive")
    if config["http"]["max_redirects"] < 0 or config["http"]["max_file_bytes"] < 1:
        raise ValueError("Invalid redirect or file-size limit")
    for key in ("min_width", "min_height", "min_short_side"):
        if not isinstance(config["quality"][key], int) or config["quality"][key] < 0:
            raise ValueError(f"quality.{key} must be a nonnegative integer")
    if config["quality"]["max_pixels"] < 1 or config["quality"]["max_aspect_ratio"] < 1:
        raise ValueError("Invalid image safety limits")
    if set(config["quality"]["allowed_formats"]) - {"JPEG", "PNG", "WEBP", "AVIF"}:
        raise ValueError("Unsupported allowed_formats entry")
    for section in ("page_auth", "image_auth"):
        auth = config[section]
        if any(
            h not in config["allowed_domains" if section == "page_auth" else "image_domains"]
            for h in auth["allowed_domains"]
        ):
            raise ValueError("Authentication domains must be a subset of transport domains")
        if any(k.lower() in ("cookie", "authorization", "proxy-authorization") for k in auth["headers"]):
            raise ValueError("Use cookie_file or headers_env for credentials")
        if (auth["cookie_file"] or auth["headers_env"]) and not auth["allowed_domains"]:
            raise ValueError(f"{section}.allowed_domains is required for authentication")
        if any(k.lower() in ("cookie", "proxy-authorization") for k in auth["headers_env"]):
            raise ValueError("Use scoped cookie_file; proxy credentials belong in proxy_env")
    if config["dedup"]["keep"] not in ("best", "first"):
        raise ValueError("dedup.keep must be best or first")
    return config


def load_config(path=None, overrides=None):
    base = Path.cwd()
    data = {}
    if path:
        path = Path(path).resolve()
        base = path.parent
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a YAML mapping")
    config = merge(DEFAULTS, data)
    if overrides:
        config = merge(config, overrides)
    config["workspace"] = str((base / config["workspace"]).resolve())
    for section in ("page_auth", "image_auth"):
        cookie = config[section]["cookie_file"]
        if cookie:
            config[section]["cookie_file"] = str((base / cookie).resolve())
    return validate(config)
