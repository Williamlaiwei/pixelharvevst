"""SQLite checkpoints and a workspace lock for one active worker."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utcnow():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def workspace_lock(root):
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    with (path / ".worker.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b" ")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("Another worker is using this workspace") from None
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class State:
    def __init__(self, workspace):
        self.root = Path(workspace)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "state.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, config TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', result TEXT, attempts INTEGER DEFAULT 0,
            retry_at REAL, UNIQUE(run_id,kind,url));
          CREATE TABLE IF NOT EXISTS origins (
            run_id TEXT NOT NULL, image_url TEXT NOT NULL, page_url TEXT NOT NULL, metadata TEXT NOT NULL,
            UNIQUE(run_id,image_url,page_url));
          CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY, file_path TEXT NOT NULL, sha256 TEXT NOT NULL, result TEXT NOT NULL);
        """)
        self.db.commit()

    def create(self, run_id, config):
        encoded = json.dumps(config, sort_keys=True)
        old = self.db.execute("SELECT config FROM runs WHERE id=?", (run_id,)).fetchone()
        if old and old["config"] != encoded:
            raise ValueError("Run configuration differs; use resume or a new run-id")
        self.db.execute("INSERT OR IGNORE INTO runs VALUES (?,?,'pending',?)", (run_id, encoded, utcnow()))
        self.db.commit()

    def config(self, run_id):
        row = self.db.execute("SELECT config FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise ValueError("Unknown run-id")
        return json.loads(row["config"])

    def enqueue(self, run_id, kind, url, origin=None):
        self.db.execute("INSERT OR IGNORE INTO tasks(run_id,kind,url) VALUES (?,?,?)", (run_id, kind, url))
        if origin is not None:
            self.db.execute(
                "INSERT OR IGNORE INTO origins VALUES (?,?,?,?)",
                (run_id, url, origin.get("source_url", ""), json.dumps(origin)),
            )
        self.db.commit()

    def finish(self, task_id, status, result, retry_at=None):
        self.db.execute(
            "UPDATE tasks SET status=?,result=?,retry_at=? WHERE id=?",
            (status, json.dumps(result), retry_at, task_id),
        )
        self.db.commit()

    def recover(self, run_id):
        self.db.execute(
            "UPDATE tasks SET status='pending' WHERE run_id=? AND status='in_progress'", (run_id,)
        )
        self.db.commit()

    def close(self):
        self.db.close()
