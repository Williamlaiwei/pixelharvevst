# Prepublication review

Review date: 2026-11-24 (Australia/Sydney).

## Publication status

**Prepared locally; NOT uploaded.** The owner-provided target is [Williamlaiwei/pixelharvevst](https://github.com/Williamlaiwei/pixelharvevst). Read-only GitHub verification found an existing public empty repository with no default branch. The remote spelling is retained as supplied; project/package name is PixelHarvest. No remote settings, branch, commit, release or package publication has been changed.

An independent main-branch initial commit is prepared locally. Confirm its identity with `git log -1 --oneline`; the commit contains this review. No predecessor Git history was imported.

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

- 55 test cases passed, 0 failed, 0 errors, 0 skipped, with real Chromium tests enabled on Windows / Python 3.12.2.
- Ruff lint and formatting passed. Unit/integration commands match the configured CI split. GitHub-hosted CI has not run because no push has occurred.
- HTTP and browser local demos passed. Two identical eligible image URLs produce one SHA256 file; the undersized image is rejected.
- Wheel and source distribution built locally with locked tools; archive member review excludes operational/private artifacts. Archives are not staged or uploaded.
- 80 predecessor baseline files match their original SHA256 hashes; no source/configuration/test/documentation/environment file in that baseline changed.
- Production Python: 1,625 physical lines, 1,474 nonblank lines across 14 modules. Tests: 716 physical lines across 8 files.
- Conservative direct textual reuse: 183 / 1,032 normalized production body lines = 17.73%. Selected predecessor core bodies retain 183 / 190 normalized lines = 96.32%. Rewritten orchestration receives no reuse credit; see [engineering-metrics.json](engineering-metrics.json) for the exact method.
- Actual loopback benchmark: full body consumption 14,725,353 bytes versus 3,491,723; both reject 6 images. Saved 11,233,630 bytes (76.288%). Elapsed times 0.480957 versus 0.300010 seconds. Dataset intentionally favors early rejection; these are application-body measurements, not wire traffic or representative source performance. See [raw results](../benchmarks/results.json).

## Secret and content review

The final staged-content scanner result is [security-scan.json](security-scan.json): zero findings. It covers every listed publication file. Rules check common provider tokens, private keys, literal credentials, credential URLs, personal paths, hardcoded IPs and prohibited runtime/binary artifacts. A separate source-specific naming check returned no matches. Staged text and package members were reviewed; only generated synthetic examples are included.

This is a bounded rule-based publication scan, not a guarantee that all possible secrets are detectable, a dependency vulnerability audit, or evidence of content ownership. No real credentials were placed in the scanner/tests. The local private source baseline contains hashes only and is not published.

## Intellectual property and licensing: OWNER CONFIRMATION REQUIRED

1. **Extracted code:** confirm that you own or are authorized to publish all selected predecessor code, including any employer/client/contractor interests, coauthor contributions and upstream obligations. Possession of local source is not evidence of release rights.
2. **Project license:** approve MIT or specify another license. `LICENSE-MIT.proposed` is expressly not effective yet. Package metadata uses `LicenseRef-Pending-Owner-Approval` until approval; no MIT grant has been asserted for unconfirmed code.
3. **Dependencies:** review [DEPENDENCIES.md](DEPENDENCIES.md) and [dependency-licenses.json](dependency-licenses.json). Installed metadata includes MIT/CMU, BSD variants, Apache, PSF, MPL and bundled numerical-library expressions. Broad labels and bundled notices still require review when redistributing packages or browser binaries. No third-party implementation/binaries are vendored here, and the project license does not replace upstream terms.
4. **Data/content:** no source-site images, HTML or customer materials are being published. Future users remain responsible for their source access and content redistribution rights.

No technical secret-scan failure is outstanding. Publication rights and the effective license remain unresolved owner decisions.

## Known implementation limits

- Single active worker per workspace; no distributed coordination or byte-range resume.
- Browser rendering uses the HTTPX policy gateway; it is not browser-native networking/fingerprint emulation. Rendered mode permits only supported GET resources on allowed hosts.
- CSS extraction cannot promise every image in interactive galleries or proprietary data structures.
- Cache entries have no automatic expiry. Use a fresh workspace for changed content.
- SHA256 storage dedup is automatic; pHash is a standalone O(n?) advisory report and never deletes images.
- FFT/Laplacian/upscale flags are heuristics, not proof of native resolution or a creation-type classifier.
- Host allowlists include ports and are not an OS/network sandbox. Reports and cached pages are private operational data.

## Actions after explicit owner approval

Adopt the confirmed LICENSE and package metadata, remove staging-only statements, update the dependency/review records as appropriate, rerun the affected release checks and review the final diff. Then push the approved main branch to the existing supplied repository and verify GitHub CI. No new repository is needed.

Proposed remote description:

> A configurable Python toolkit for web image acquisition, streaming validation, quality assessment, perceptual deduplication, and resumable batch processing.

Proposed topics: `python`, `image-processing`, `data-engineering`, `web-scraping`, `image-downloader`, `image-quality`, `deduplication`, `computer-vision`, `data-pipeline`.

The owner's task explicitly requires displaying the file list, scan result and unresolved IP items and obtaining confirmation before uploading. This report is the review artifact for that confirmation.
