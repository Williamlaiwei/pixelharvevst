# Security

## Private operational data

Keep cookie exports, environment variables, proxy credentials, authenticated HTML, SQLite state, downloaded images and run reports outside Git. `.pixelharvest/`, `.env*` except `.env.example`, profiles, databases and temporary files are ignored. A config outside those directories can still contain sensitive URLs or names: review before adding it. Never attach an entire workspace to a public issue.

Page and image sessions are separate. Private headers use environment variable references; cookies require explicit auth domains. URL user information is rejected. Redirect destinations are checked before HTTPX sends them. No system proxy is inherited; an explicitly configured missing/invalid proxy fails rather than falling back to a direct connection. Browser rendering routes supported GET requests through the same HTTPX gateway and blocks media, frames, service workers, WebSockets and non-GET requests.

Robots and request spacing are on by default. Access denial stops the run; rate responses save a retry deadline. Authentication support is for authorized sessions and does not bypass access controls.

## Reviewing a release

1. Inspect all tracked files with `git ls-files` and `git diff --cached`.
2. Run `python scripts/scan_secrets.py --staged`. It reports rule/file/line, never the secret value.
3. Review generated reports, examples and package contents manually. The scanner is intentionally limited to tracked text; it rejects tracked binary/runtime artifacts and does not inspect ignored private data.
4. Confirm that the code owner permits publication and approve the actual license. Dependency license metadata is an inventory, not ownership evidence.
5. Test the exact commit and inspect wheel/source archive contents before pushing.

The scanner is dependency-free and checks common provider tokens, private keys, credential URLs, literal credentials, personal paths, hardcoded IPv4 addresses, and prohibited artifact types. It cannot detect every credential syntax or determine content rights. It is not a dependency vulnerability audit.

## Reporting issues

Do not put credentials, private URLs, images, HTML or customer data in a public issue. Send a minimal synthetic reproduction through the repository owner's private security reporting channel if available. If no private channel exists, contact the owner to arrange one before sending sensitive details. No dedicated security email or disclosure service is claimed.
