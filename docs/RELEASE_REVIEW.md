# Release review and authorization record

Review date: 2026-11-24 (Australia/Sydney).

## Publication status

The owner explicitly confirmed publication and adoption of MIT on November 24, 2026, after receiving the file list, scan result and rights/license review. The approved target is [Williamlaiwei/pixelharvevst](https://github.com/Williamlaiwei/pixelharvevst), using branch `main`. The remote spelling is retained as supplied; the project/package name is PixelHarvest.

An independent initial commit was created locally, followed by this owner-approved release update. No predecessor Git history was imported. This publication covers source/documentation only; no package or binary release is uploaded. Current hosted validation is visible in [GitHub Actions](https://github.com/Williamlaiwei/pixelharvevst/actions/workflows/ci.yml).

## Exact candidate file list

[PUBLICATION_FILES.txt](PUBLICATION_FILES.txt) lists every tracked file, including this review and the list itself. It is generated from the Git index, not from a recursive copy of the predecessor.

| Candidate content | Included |
| --- | --- |
| Runtime | 14 Python modules: configuration, CLI, scoped auth/transport, parser, optional browser renderer, stream receiver, QC, dedup, state, cache and pipeline |
| Tests | 8 Python files; all fixtures are generated/synthetic |
| Examples/benchmarks | Loopback demo/server, seeded image generator and measured benchmark summary |
| Documentation | English README with two Mermaid diagrams, security/contribution instructions, extraction record, dependency inventory, engineering metrics and publication review |
| Build/CI | pyproject, hashed runtime/development locks, source manifest, YAML example, placeholder environment example, ignore/line-ending rules and GitHub Actions |

Excluded: all original downloads, authenticated HTML, SQLite databases, source account/API keys, cookies, proxy credentials/IPs/vendors, browser profiles, debug bundles, client delivery conventions, original configurations and previous Git history. Generated demo data, local virtual environments, distribution archives and the original source hash baseline remain ignored.

## Verified results

- 56 test cases passed, 0 failed, 0 errors, 0 skipped, with real Chromium tests enabled on Windows / Python 3.12.2.
- Ruff lint and formatting passed. Unit/integration commands match the configured CI split. Hosted CI runs on publication; check the linked workflow for current results.
- HTTP and browser local demos passed. Two identical eligible image URLs produce one SHA256 file; the undersized image is rejected.
- Wheel and source distribution built locally with locked tools; archive member review excludes operational/private artifacts. Archives are not staged or uploaded.
- 80 predecessor baseline files match their original SHA256 hashes; no source/configuration/test/documentation/environment file in that baseline changed.
- Production Python: 1,626 physical lines, 1,475 nonblank lines across 14 modules. Tests: 741 physical lines across 8 files.
- Conservative direct textual reuse: 183 / 1,032 normalized production body lines = 17.73%. Selected predecessor core bodies retain 183 / 190 normalized lines = 96.32%. Rewritten orchestration receives no reuse credit; see [engineering-metrics.json](engineering-metrics.json) for the exact method.
- Actual loopback benchmark: full body consumption 14,725,353 bytes versus 3,491,723; both reject 6 images. Saved 11,233,630 bytes (76.288%). Elapsed times 0.480957 versus 0.300010 seconds. Dataset intentionally favors early rejection; these are application-body measurements, not wire traffic or representative source performance. See [raw results](../benchmarks/results.json).

## Secret and content review

The final staged-content scanner result is [security-scan.json](security-scan.json): zero findings. It covers every listed publication file. Rules check common provider tokens, private keys, literal credentials, credential URLs, personal paths, hardcoded IPs and prohibited runtime/binary artifacts. A separate source-specific naming check returned no matches. Staged text and package members were reviewed; only generated synthetic examples are included.

This is a bounded rule-based publication scan, not a guarantee that all possible secrets are detectable, a dependency vulnerability audit, or evidence of content ownership. No real credentials were placed in the scanner/tests. The local private source baseline contains hashes only and is not published.

## Intellectual property and licensing: owner approved

1. **Extracted code:** the owner confirmed publication in response to the request to verify their right to release the selected code, including employer/client/contractor interests, coauthor permission and upstream obligations. This is an owner authorization record, not an independent legal ownership audit.
2. **Project license:** MIT was approved and adopted in `LICENSE` and package metadata. The staging-only proposed license was removed from the current tree.
3. **Dependencies:** [DEPENDENCIES.md](DEPENDENCIES.md) and [dependency-licenses.json](dependency-licenses.json) retain the metadata inventory and notice considerations. Broad metadata labels/bundled licenses still require review if redistributing packages or browser binaries. No dependency implementation or binaries are vendored; MIT does not replace upstream terms.
4. **Data/content:** no source-site images, authenticated HTML or customer material are published. Future users remain responsible for their source access and content redistribution rights.

No technical secret-scan failure or owner publication/license confirmation remains outstanding for this source release.

## Known implementation limits

- Single active worker per workspace; no distributed coordination or byte-range resume.
- Browser rendering uses the HTTPX policy gateway; it is not browser-native networking/fingerprint emulation. Rendered mode permits only supported GET resources on allowed hosts.
- CSS extraction cannot promise every image in interactive galleries or proprietary data structures.
- Cache entries have no automatic expiry. Use a fresh workspace for changed content.
- SHA256 storage dedup is automatic; pHash is a standalone O(n?) advisory report and never deletes images.
- FFT/Laplacian/upscale flags are heuristics, not proof of native resolution or a creation-type classifier.
- Host allowlists include ports and are not an OS/network sandbox. Reports and cached pages are private operational data.

## Approved release contents and verification

- Adopted the effective MIT license and removed staging-only statements.
- Added the detailed [Technical and Operations Guide](TECHNICAL_GUIDE.md), linked from README, covering setup, architecture, size decisions, authentication/proxy isolation, schema, recovery, troubleshooting and extension boundaries.
- Corrected image metadata to preserve the durable task status separately from `transfer_status`, so successful reception cannot overwrite a later quality rejection. Added a regression test.
- Re-ran local tests/lint/build, refreshed metrics and the exact file manifest, scanned the final staged tree, and inspected package members.
- Publication targets the supplied existing repository; no additional repository is created. Current push/CI evidence is available in its commit history and workflow runs.

Approved remote description:

> A configurable Python toolkit for web image acquisition, streaming validation, quality assessment, perceptual deduplication, and resumable batch processing.

Approved topics: `python`, `image-processing`, `data-engineering`, `web-scraping`, `image-downloader`, `image-quality`, `deduplication`, `computer-vision`, `data-pipeline`.

The original requirement to obtain approval before uploading was satisfied by the owner's explicit confirmation. No operational credentials, data collections or predecessor history are included.
