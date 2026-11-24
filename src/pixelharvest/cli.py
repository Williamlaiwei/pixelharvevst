"""The public CLI; logging is used for progress and diagnostics."""

import argparse
import json
import logging
import uuid
from dataclasses import asdict
from pathlib import Path

from .config import load_config
from .dedup import find_duplicates
from .image_qc import inspect_image
from .pipeline import Pipeline, read_input
from .state import State

log = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pixelharvest")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("crawl", "download"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        p.add_argument("--run-id")
        p.add_argument("--input", required=name == "download")
    for name in ("resume", "report"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", default=".pixelharvest")
        p.add_argument("--run-id", required=True)
        if name == "resume":
            p.add_argument("--retry-failed", action="store_true")
    for name in ("inspect", "dedup"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        p.add_argument("--input", required=True)
        p.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    pipeline = None
    try:
        if args.command in ("crawl", "download"):
            config = load_config(args.config)
            run_id = args.run_id or uuid.uuid4().hex[:12]
            pipeline = Pipeline(config, run_id)
            inputs = list(read_input(args.input)) if args.input else config["urls"]
            if not inputs:
                raise ValueError("No input URLs")
            pipeline.create("page" if args.command == "crawl" else "image", inputs)
            result = pipeline.execute()
        elif args.command in ("resume", "report"):
            state = State(Path(args.workspace).resolve())
            try:
                config = state.config(args.run_id)
            finally:
                state.close()
            pipeline = Pipeline(config, args.run_id)
            result = pipeline.execute(args.retry_failed) if args.command == "resume" else pipeline.report()
        else:
            config = load_config(args.config)
            path = Path(args.input)
            paths = (
                [path]
                if path.is_file()
                else sorted(
                    p
                    for p in path.rglob("*")
                    if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".avif")
                )
            )
            if args.command == "inspect":
                result = {
                    "images": [{"path": str(p), **asdict(inspect_image(p, config["quality"]))} for p in paths]
                }
            else:
                result = find_duplicates(paths, config["dedup"], config["quality"])
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, indent=2), encoding="utf-8")
        log.info("%s", json.dumps(result, ensure_ascii=True))
        return (
            2
            if result.get("status") in ("blocked", "deferred", "interrupted")
            or result.get("counts", {}).get("failed")
            else 0
        )
    except KeyboardInterrupt:
        log.warning("Interrupted; checkpoints saved. Use resume with the same run-id.")
        return 130
    except Exception as error:
        # Third-party messages can contain request URLs, credentials or local paths.
        log.error(
            "Operation failed (%s). Check configuration and the private workspace report.",
            type(error).__name__,
        )
        return 2
    finally:
        if pipeline:
            pipeline.close()
