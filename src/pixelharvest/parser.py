"""Selector-based image discovery. Original URL query strings are preserved."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def normalize_url(url, base_url=None):
    value = urljoin(base_url or "", (url or "").strip())
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("Image URL must be http(s) without embedded credentials")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def srcset_candidates(value):
    # Delimit only after a descriptor, so query-string commas remain untouched.
    result = []
    for match in re.finditer(r"(?:^|,)\s*(\S+?)\s+(\d+(?:\.\d+)?)(w|x)(?=\s*(?:,|$))", value or ""):
        url, number, unit = match.groups()
        result.append((float(number), unit, url))
    return result


def parse_images(html, page_url, selectors):
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    found = {}
    for selector in selectors:
        for tag in soup.select(selector):
            candidates = []
            raw = tag.get("src") or tag.get("data-src")
            if raw:
                candidates.append((0, "w", raw))
            candidates.extend(srcset_candidates(tag.get("srcset") or tag.get("data-srcset")))
            if tag.name == "img" and tag.find_parent("picture"):
                for item in tag.find_parent("picture").find_all("source"):
                    candidates.extend(srcset_candidates(item.get("srcset")))
            if not candidates:
                continue
            # A descriptor is a selection hint; dimensions are verified from bytes.
            width = [c for c in candidates if c[1] == "w"]
            chosen = max(width or candidates, key=lambda c: c[0])
            try:
                url = normalize_url(chosen[2], page_url)
            except ValueError:
                continue
            figure = tag.find_parent("figure")
            caption = figure.find("figcaption") if figure else None
            found[url] = {
                "url": url,
                "source_url": page_url,
                "title": title,
                "alt": tag.get("alt", ""),
                "caption": caption.get_text(" ", strip=True) if caption else "",
                "width_hint": chosen[0] if chosen[1] == "w" else None,
            }
    return list(found.values())
