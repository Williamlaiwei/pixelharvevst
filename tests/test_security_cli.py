import subprocess
import sys

from scripts.scan_secrets import findings


def test_scanner_detects_secrets_without_printing_values():
    key = "ghp_" + "a" * 36
    text = "https://" + "user:password@" + "proxy.invalid:8000/\n" + key
    results = findings(text)
    assert {r["rule"] for r in results} == {"url-credentials", "github-token"}
    assert key not in str(results)


def test_cli_help_and_bad_config(tmp_path):
    result = subprocess.run([sys.executable, "-m", "pixelharvest", "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and "resume" in result.stdout
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("unknown: true")
    result = subprocess.run(
        [sys.executable, "-m", "pixelharvest", "crawl", "--config", str(cfg)], capture_output=True, text=True
    )
    assert result.returncode == 2 and "Traceback" not in result.stderr
