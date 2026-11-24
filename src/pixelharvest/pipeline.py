"""One execution path for crawl, download, resume, QC, CAS and checkpointing."""

from __future__ import annotations

import csv
import json
import logging
import re
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from .auth import public_url
from .cache import Cache, cache_key
from .dedup import compute_phash, sha256_file
from .downloader import Downloader
from .image_qc import inspect_image
from .page_fetchers import BrowserFetcher
from .parser import normalize_url, parse_images
from .state import State, workspace_lock
from .transport import HaltRun, RequestRefused, Transport

log = logging.getLogger(__name__)


def read_input(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                url = row.get("url") or row.get("image_url")
                if not url:
                    raise ValueError("CSV needs a url or image_url column")
                yield {**row, "url": normalize_url(url)}
    else:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                yield {"url": normalize_url(line.strip())}


class Pipeline:
    def __init__(
        self, config, run_id, *, page_transport=None, image_transport=None, browser_factory=None, on_task=None
    ):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
            raise ValueError("run-id must contain only letters, digits, underscores or hyphens")
        self.config, self.run_id = config, run_id
        self.state = State(config["workspace"])
        self.cache = Cache(self.state)
        self.page_transport, self.image_transport = page_transport, image_transport
        self.owns_page, self.owns_image = page_transport is None, image_transport is None
        self.browser, self.browser_factory = None, browser_factory
        self.on_task = on_task

    def create(self, kind, inputs):
        self.state.create(self.run_id, self.config)
        for item in inputs:
            item = {"url": item} if isinstance(item, str) else item
            self.state.enqueue(
                self.run_id, kind, normalize_url(item["url"]), item if kind == "image" else None
            )

    def _transport(self, kind):
        if kind == "page":
            if self.page_transport is None:
                self.page_transport = Transport(self.config, "page")
            return self.page_transport
        if self.image_transport is None:
            self.image_transport = Transport(self.config, "image")
        return self.image_transport

    def _page(self, task):
        transport = self._transport("page")
        key = cache_key(task["url"], transport.auth, json.dumps(self.config["page"], sort_keys=True))
        html_file, meta_file = self.cache.page_paths(key)
        cached = html_file.exists() and meta_file.exists()
        if cached:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if sha256_file(html_file) != meta["sha256"]:
                raise ValueError("Cached HTML integrity check failed")
            final_url, html = meta["final_url"], html_file.read_text(encoding="utf-8")
        else:
            if self.config["page"]["renderer"] == "browser":
                self.browser = self.browser or BrowserFetcher(self.config, transport, self.browser_factory)
                code, final_url, html = self.browser.fetch(task["url"])
            else:
                for attempt in range(self.config["http"]["max_attempts"]):
                    try:
                        code, final_url, html = transport.text(task["url"])
                        if code < 500 or attempt + 1 == self.config["http"]["max_attempts"]:
                            break
                    except httpx.TransportError:
                        if attempt + 1 == self.config["http"]["max_attempts"]:
                            raise
                    transport.sleep(self.config["http"]["backoff_seconds"] * 2**attempt)
            if code != 200:
                return "failed", {"reason": f"http_{code}", "http_status": code}
            from bs4 import BeautifulSoup

            title = BeautifulSoup(html, "lxml").title
            if title and re.search(
                r"captcha|verify you are human|access denied|just a moment", title.get_text(), re.I
            ):
                raise HaltRun("challenge_detected")
            temporary = html_file.with_suffix(".html.tmp")
            temporary.write_text(html, encoding="utf-8", newline="\n")
            temporary.replace(html_file)
            meta_file.write_text(
                json.dumps({"final_url": final_url, "sha256": sha256_file(html_file)}), encoding="utf-8"
            )
        images = parse_images(html, final_url, self.config["selectors"])
        accepted = 0
        for image in images:
            # Page and image domain scopes are independent.
            from .auth import allowed

            if allowed(image["url"], self.config["image_domains"]):
                self.state.enqueue(self.run_id, "image", image["url"], image)
                accepted += 1
        return "done", {"images": accepted, "cache_hit": cached, "url": public_url(final_url)}

    def _image(self, task):
        transport = self._transport("image")
        if not transport.host_allowed(task["url"]):
            raise RequestRefused("host_or_scheme_not_allowed")
        key = cache_key(task["url"], transport.auth)
        cached = self.cache.lookup(key)
        if cached:
            path, previous = cached
            quality = inspect_image(path, self.config["quality"])
            result = {**previous, "cache_hit": True, "bytes_received": 0, "quality": asdict(quality)}
            return ("rejected" if quality.status == "rejected" else "done"), result
        directory = self.state.root / "tmp" / self.run_id
        directory.mkdir(parents=True, exist_ok=True)
        part = directory / f"{task['id']}.part"
        try:
            received = Downloader(self.config, transport).fetch(task["url"], part)
            received.pop("final_url", None)
            if received["status"] != "downloaded":
                status = (
                    "rejected"
                    if received["status"].startswith("skipped")
                    or received.get("reason") == "decompression_bomb"
                    else "failed"
                )
                return status, received
            quality = inspect_image(part, self.config["quality"])
            result = {**received, "quality": asdict(quality), "cache_hit": False}
            if quality.status == "rejected":
                return "rejected", result
            digest = sha256_file(part)
            result.update(sha256=digest, phash=compute_phash(part))
            relative = self.cache.store(key, part, digest, quality.ext, result)
            result["file_path"] = relative
            # Store the final relative path in the persistent URL cache.
            self.state.db.execute("UPDATE cache SET result=? WHERE key=?", (json.dumps(result), key))
            self.state.db.commit()
            return "done", result
        finally:
            part.unlink(missing_ok=True)

    def execute(self, retry_failed=False):
        with workspace_lock(self.state.root):
            self.state.recover(self.run_id)
            directory = self.state.root / "tmp" / self.run_id
            if directory.exists():
                for part in directory.glob("*.part"):
                    part.unlink()
            if retry_failed:
                self.state.db.execute(
                    "UPDATE tasks SET status='pending' WHERE run_id=? AND status='failed'", (self.run_id,)
                )
            future = self.state.db.execute(
                "SELECT retry_at FROM tasks WHERE run_id=? AND status='deferred' AND retry_at>?",
                (self.run_id, time.time()),
            ).fetchone()
            blocked = self.state.db.execute(
                "SELECT 1 FROM tasks WHERE run_id=? AND status='blocked'", (self.run_id,)
            ).fetchone()
            self.state.db.execute(
                "UPDATE tasks SET status='pending' WHERE run_id=? AND status='deferred' AND retry_at<=?",
                (self.run_id, time.time()),
            )
            self.state.db.commit()
            if future or blocked:
                return self.report()
            self.state.db.execute("UPDATE runs SET status='running' WHERE id=?", (self.run_id,))
            self.state.db.commit()
            try:
                while True:
                    tasks = self.state.db.execute(
                        "SELECT * FROM tasks WHERE run_id=? AND status='pending' ORDER BY CASE kind WHEN 'page' THEN 0 ELSE 1 END,id LIMIT ?",
                        (self.run_id, self.config["batch_size"]),
                    ).fetchall()
                    if not tasks:
                        break
                    for task in tasks:
                        self.state.db.execute(
                            "UPDATE tasks SET status='in_progress',attempts=attempts+1 WHERE id=?",
                            (task["id"],),
                        )
                        self.state.db.commit()
                        try:
                            status, result = self._page(task) if task["kind"] == "page" else self._image(task)
                            self.state.finish(task["id"], status, result)
                        except HaltRun as error:
                            deferred = error.retry_after is not None or "429" in error.reason
                            wait = (
                                error.retry_after
                                if error.retry_after is not None
                                else self.config["http"]["default_retry_after_seconds"]
                            )
                            self.state.finish(
                                task["id"],
                                "deferred" if deferred else "blocked",
                                {"reason": error.reason},
                                time.time() + wait if deferred else None,
                            )
                            self.state.db.execute(
                                "UPDATE runs SET status=? WHERE id=?",
                                ("deferred" if deferred else "blocked", self.run_id),
                            )
                            self.state.db.commit()
                            log.warning("Run stopped: %s", error.reason)
                            return self.report()
                        except (RequestRefused, httpx.HTTPError) as error:
                            reason = str(error) if isinstance(error, RequestRefused) else type(error).__name__
                            self.state.finish(task["id"], "failed", {"reason": reason})
                        self._progress(task["kind"])
                        if self.on_task:
                            self.on_task(dict(task))
                self.state.db.execute("UPDATE runs SET status='complete' WHERE id=?", (self.run_id,))
                self.state.db.commit()
            except BaseException:
                self.state.recover(self.run_id)
                self.state.db.execute("UPDATE runs SET status='interrupted' WHERE id=?", (self.run_id,))
                self.state.db.commit()
                self.report()
                raise
            return self.report()

    def _progress(self, kind):
        rows = self.state.db.execute(
            "SELECT status,COUNT(*) n FROM tasks WHERE run_id=? AND kind=? GROUP BY status",
            (self.run_id, kind),
        ).fetchall()
        counts = {r["status"]: r["n"] for r in rows}
        total = sum(counts.values())
        done = total - counts.get("pending", 0) - counts.get("in_progress", 0)
        log.info("[%6.2f%%] %s %d/%d", 100 * done / max(1, total), kind, done, total)

    def report(self):
        run = self.state.db.execute("SELECT status FROM runs WHERE id=?", (self.run_id,)).fetchone()
        if not run:
            raise ValueError("Unknown run-id")
        rows = self.state.db.execute(
            "SELECT * FROM tasks WHERE run_id=? ORDER BY id", (self.run_id,)
        ).fetchall()
        counts = {}
        records = []
        transferred = 0
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
            result = json.loads(row["result"] or "{}")
            transferred += result.get("bytes_received", 0)
            if row["kind"] == "image":
                origins = self.state.db.execute(
                    "SELECT metadata FROM origins WHERE run_id=? AND image_url=?", (self.run_id, row["url"])
                ).fetchall()
                source = []
                for origin in origins:
                    item = json.loads(origin["metadata"])
                    source.append(
                        {
                            "page_url": public_url(item["source_url"]) if item.get("source_url") else None,
                            "title": item.get("title", ""),
                            "alt": item.get("alt", ""),
                            "caption": item.get("caption", ""),
                        }
                    )
                records.append(
                    {
                        "image_url": public_url(row["url"]),
                        "status": row["status"],
                        "sources": source,
                        **result,
                    }
                )
        output = self.state.root / "runs" / self.run_id
        output.mkdir(parents=True, exist_ok=True)
        (output / "metadata.jsonl.tmp").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
        )
        (output / "metadata.jsonl.tmp").replace(output / "metadata.jsonl")
        summary = {
            "run_id": self.run_id,
            "status": run["status"],
            "tasks": len(rows),
            "counts": counts,
            "bytes_received": transferred,
            "unique_files": len({r.get("sha256") for r in records if r.get("file_path")}),
            "metadata_file": str(output / "metadata.jsonl"),
        }
        (output / "report.json.tmp").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (output / "report.json.tmp").replace(output / "report.json")
        return summary

    def close(self):
        if self.browser:
            self.browser.close()
        if self.owns_page and self.page_transport:
            self.page_transport.close()
        if self.owns_image and self.image_transport:
            self.image_transport.close()
        self.state.close()
