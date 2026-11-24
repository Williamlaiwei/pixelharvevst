# Extraction and design record

## Scope

This is a whitelist extraction into a new sibling repository. The predecessor remains read-only. No previous Git history, operational datasets, source HTML, databases, cookies, image sets, client delivery conventions or account/proxy configuration are imported.

The old application combined source-specific catalog discovery, article parsing, browser sessions, image downloading and a custom delivery workflow, with more than one historical pipeline. This project exposes one generic execution path and a small set of standalone analysis commands.

| Before | PixelHarvest |
| --- | --- |
| Website-specific catalog/API collection | Caller supplies page URLs or image URL text/CSV. No catalog API. |
| Dedicated article/CDN parser and URL transformations | CSS selectors, standard srcset/lazy attributes, preserve supplied queries. |
| Source-bound session and download setup | Separate scoped `page_auth` and `image_auth`; optional explicit proxy environment reference. |
| Streaming receiver inside source workflow | Extracted `_int`/`_receive`, bounded generic wrapper and HTTPX gateway. |
| Generic quality algorithms with application settings | Preserved FFT/Laplacian/integrity logic, configurable format/dimension/pixel guards. |
| Dedup functions mixed with application database routines | Extracted SHA256/pHash/Hamming/quality ranking; integrated SHA256 CAS and standalone near-duplicate review. |
| Custom output classification/delivery and archive reports | Generic JSONL provenance plus SQLite recovery/report commands. |

## Preserved versus adapted

`image_qc.py` retains the working Pillow verification, FFT frequency ratio, Laplacian variance, white-page/border, color-mode and upscale-warning algorithms. It adds explicit max-pixel and per-dimension constraints and supports disabling advisory heuristics.

`downloader.py` directly extracts the predecessor's streaming receiver and integer helper rather than replacing HTTPX. Added code handles generic configuration, cleanup, bounded retries and stopping/defer policy. `dedup.py` retains SHA256, perceptual hash, Hamming distance and retention-ranking functions. Source-specific database mutations were not copied.

The old domain/CDN URL normalizer was inspected but excluded because it encoded source assumptions. Generic normalization rejects user information and unsafe schemes, resolves relative paths, preserves queries and removes fragments. HTTP rate limiting/retry/allowlist design is retained in a smaller generic transport. New state/cache/CLI wiring replaces source-bound orchestration; no framework was introduced.

Perceptual clustering was not moved into the hot download path: it remains an independent report command so a false match cannot silently remove an acquired image. Exact SHA256 storage deduplication is integrated. This is a deliberate bounded extraction, not a claim that every historical pipeline branch was preserved.

## Public source provenance and rights

Only generic code selected from the owner-supplied predecessor is included, with synthetic replacement fixtures. No external implementation source was downloaded or vendored. The local origin alone does not establish copyright ownership. Before publication the owner must confirm employee/client/contractor rights, coauthor permission, any upstream obligations and approval of the proposed license. Dependency metadata is separately recorded; it does not resolve ownership of extracted code.

Exact conservative reuse counts and source read-only verification are in `engineering-metrics.json`. The local baseline contains original relative names and hashes only and is excluded from Git; no original file paths or source-specific naming are needed in the public metrics.
