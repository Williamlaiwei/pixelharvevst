"""Private URL caches and content-addressed image storage."""

import hashlib
import json
import os

from .dedup import sha256_file


def cache_key(url, auth, extra=""):
    credentials = sorted((c.domain, c.path, c.name, c.value) for c in auth.cookies.jar)
    material = json.dumps([url, credentials, auth.headers, extra], sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()


class Cache:
    def __init__(self, state):
        self.state, self.root = state, state.root

    def lookup(self, key):
        row = self.state.db.execute("SELECT * FROM cache WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        path = (self.root / row["file_path"]).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            return None
        if sha256_file(path) != row["sha256"]:
            raise ValueError("Cached image failed its stored SHA256 integrity check")
        return path, json.loads(row["result"])

    def store(self, key, part, digest, extension, result):
        relative = f"images/{digest[:2]}/{digest}.{extension}"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256_file(target) != digest:
                raise ValueError("Existing content-addressed file is corrupt")
            part.unlink(missing_ok=True)
        else:
            os.replace(part, target)
        self.state.db.execute(
            "INSERT OR REPLACE INTO cache VALUES (?,?,?,?)", (key, relative, digest, json.dumps(result))
        )
        self.state.db.commit()
        return relative

    def page_paths(self, key):
        directory = self.root / "pages"
        directory.mkdir(exist_ok=True)
        return directory / f"{key}.html", directory / f"{key}.json"
