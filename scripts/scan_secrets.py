"""Dependency-free, fail-closed publication scan of git-indexed files.

This rule-based scanner is not a proof of absence of secrets. Review diffs too.
No untracked runtime data is read; tracked binary files are refused.
"""

import argparse
import ipaddress
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

RULES = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github-token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})"),
    "cloud-key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "personal-path": re.compile(r"(?:[A-Z]:[\\/]Users[\\/][^\s]+|/(?:home|Users)/[^\s]+)"),
}


def findings(text):
    found = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for name, rule in RULES.items():
            if rule.search(line):
                found.append({"line": line_no, "rule": name})
        for match in re.finditer(r"https?://[^\s\"'<>`]+", line):
            try:
                parts = urlsplit(match.group())
                reserved = parts.hostname in ("example.org", "example.com", "127.0.0.1", "localhost") or (
                    parts.hostname or ""
                ).endswith(".test")
                if (parts.username or parts.password) and not reserved:
                    found.append({"line": line_no, "rule": "url-credentials"})
            except ValueError:
                found.append({"line": line_no, "rule": "malformed-url"})
        for ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line):
            try:
                if not ipaddress.ip_address(ip).is_loopback:
                    found.append({"line": line_no, "rule": "hardcoded-ip"})
            except ValueError:
                pass
        if re.search(
            r"(?i)(?:api_key|password|access_token|proxy_password)\s*[:=]\s*[\"'](?!synthetic|placeholder|example|YOUR_|TEST_)[A-Za-z0-9_+/=-]{16,}",
            line,
        ):
            found.append({"line": line_no, "rule": "literal-credential"})
    return found


def scan(staged=False):
    files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    result = []
    count = 0
    for name in filter(None, files):
        path = Path(name)
        count += 1
        forbidden = path.suffix.lower() in (
            ".db",
            ".sqlite",
            ".sqlite3",
            ".jpg",
            ".png",
            ".webp",
            ".avif",
            ".har",
            ".html",
        ) or (path.name.startswith(".env") and path.name != ".env.example")
        if forbidden:
            result.append({"file": name, "rule": "runtime-or-binary-file"})
            continue
        try:
            raw = subprocess.check_output(["git", "show", f":{name}"]) if staged else path.read_bytes()
            if b"\0" in raw:
                raise UnicodeError
            text = raw.decode("utf-8-sig")
        except (UnicodeError, OSError):
            result.append({"file": name, "rule": "unreviewed-binary"})
            continue
        result.extend({"file": name, **item} for item in findings(text))
    return {
        "scanner": "PixelHarvest publication scanner v1",
        "scope": "git index content" if staged else "git-tracked working files",
        "files_scanned": count,
        "findings": result,
        "limitations": "Rules cover private keys, common provider tokens, URL credentials, literal credentials, personal paths, hardcoded IPs and excluded artifacts. They do not establish ownership or detect all possible secrets; manual review is required.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = scan(args.staged)
    if result["files_scanned"] == 0:
        raise SystemExit("No tracked files to scan")
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["findings"]))


if __name__ == "__main__":
    main()
