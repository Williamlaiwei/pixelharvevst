import json
from pathlib import Path

import httpx
import pytest
from test_transport import transport

from examples.local_site import html_response, image_response, serve
from pixelharvest.config import load_config
from pixelharvest.pipeline import Pipeline


def test_exact_dedup_cache_and_provenance(config, picture):
    seen = []
    html = '<title>Fixture</title><figure><img src="https://cdn.example.test/a?signature=private"><figcaption>Generated</figcaption></figure><img src="https://cdn.example.test/b">'
    page = transport(
        config, lambda req: httpx.Response(200, headers={"content-type": "text/html"}, text=html)
    )
    image = transport(
        config,
        lambda req: (
            seen.append(str(req.url))
            or httpx.Response(200, headers={"content-type": "image/jpeg"}, content=picture)
        ),
        "image",
    )
    p = Pipeline(config, "first", page_transport=page, image_transport=image)
    p.create("page", ["https://example.test/story?token=private"])
    report = p.execute()
    assert report["counts"] == {"done": 3} and report["unique_files"] == 1
    metadata = open(report["metadata_file"], encoding="utf-8").read()
    assert "signature=" not in metadata and "token=" not in metadata
    record = json.loads(metadata.splitlines()[0])
    assert record["sources"][0]["title"] == "Fixture"
    assert record["status"] == "done" and record["transfer_status"] == "downloaded"
    assert len(seen) == 2
    p.close()
    p = Pipeline(config, "second", page_transport=page, image_transport=image)
    p.create("page", ["https://example.test/story?token=private"])
    assert p.execute()["bytes_received"] == 0 and len(seen) == 2
    p.close()
    page.close()
    image.close()


def test_interruption_resume_only_unfinished(config, picture):
    seen = []
    image = transport(
        config,
        lambda req: (
            seen.append(req.url.path)
            or httpx.Response(200, headers={"content-type": "image/jpeg"}, content=picture)
        ),
        "image",
    )

    def stop(task):
        raise KeyboardInterrupt

    p = Pipeline(config, "resume", image_transport=image, on_task=stop)
    p.create("image", ["https://cdn.example.test/a", "https://cdn.example.test/b"])
    with pytest.raises(KeyboardInterrupt):
        p.execute()
    assert p.report()["status"] == "interrupted"
    p.close()
    p = Pipeline(config, "resume", image_transport=image)
    assert p.execute()["counts"] == {"done": 2}
    assert seen == ["/a", "/b"]
    p.close()
    image.close()


@pytest.mark.parametrize("code,status", [(403, "blocked"), (429, "deferred"), (503, "deferred")])
def test_server_halt_is_durable_no_early_retry(config, code, status):
    seen = []
    image = transport(
        config,
        lambda req: (
            seen.append(req) or httpx.Response(code, headers={"retry-after": "600"} if code != 403 else {})
        ),
        "image",
    )
    p = Pipeline(config, "halt", image_transport=image)
    p.create("image", ["https://cdn.example.test/a", "https://cdn.example.test/b"])
    assert p.execute()["status"] == status
    assert p.execute(retry_failed=True)["status"] == status and len(seen) == 1
    p.close()
    image.close()


def test_cache_corruption_detected(config, picture):
    image = transport(
        config,
        lambda req: httpx.Response(200, headers={"content-type": "image/jpeg"}, content=picture),
        "image",
    )
    p = Pipeline(config, "one", image_transport=image)
    p.create("image", ["https://cdn.example.test/a"])
    p.execute()
    path = next((p.state.root / "images").rglob("*.jpg"))
    path.write_bytes(b"corrupted")
    p.close()
    p = Pipeline(config, "two", image_transport=image)
    p.create("image", ["https://cdn.example.test/a"])
    with pytest.raises(ValueError, match="integrity"):
        p.execute()
    p.close()
    image.close()


@pytest.mark.integration
def test_real_local_http_pipeline(tmp_path, picture):
    routes = {
        "/page": html_response('<title>Local</title><img src="/a.jpg">'),
        "/a.jpg": image_response(picture),
    }
    with serve(routes) as (base, hits, _, _):
        cfg = load_config(
            overrides={
                "workspace": str(tmp_path / "work"),
                "allowed_domains": ["127.0.0.1"],
                "image_domains": ["127.0.0.1"],
                "http": {"request_interval_seconds": 0},
                "quality": {"min_width": 100, "min_height": 100},
            }
        )
        p = Pipeline(cfg, "local")
        p.create("page", [base + "/page"])
        try:
            assert p.execute()["counts"] == {"done": 2}
            assert hits["/page"] == 1 and hits["/a.jpg"] == 1
        finally:
            p.close()


def test_interrupt_during_body_cleans_part_and_recovers(config, picture):
    class InterruptedStream(httpx.SyncByteStream):
        def __iter__(self):
            yield picture[:8192]
            raise KeyboardInterrupt

    image = transport(
        config,
        lambda req: httpx.Response(200, headers={"content-type": "image/jpeg"}, stream=InterruptedStream()),
        "image",
    )
    p = Pipeline(config, "midbody", image_transport=image)
    p.create("image", ["https://cdn.example.test/a"])
    with pytest.raises(KeyboardInterrupt):
        p.execute()
    assert p.report()["counts"] == {"pending": 1}
    assert not list(p.state.root.rglob("*.part"))
    p.close()
    image.close()
    image = transport(
        config,
        lambda req: httpx.Response(200, headers={"content-type": "image/jpeg"}, content=picture),
        "image",
    )
    p = Pipeline(config, "midbody", image_transport=image)
    assert p.execute()["counts"] == {"done": 1}
    assert p.state.db.execute("SELECT attempts FROM tasks").fetchone()[0] == 2
    p.close()
    image.close()


def test_process_recovery_removes_stale_part(config, picture):
    image = transport(
        config,
        lambda req: httpx.Response(200, headers={"content-type": "image/jpeg"}, content=picture),
        "image",
    )
    p = Pipeline(config, "recovery", image_transport=image)
    p.create("image", ["https://cdn.example.test/a"])
    p.state.db.execute("UPDATE tasks SET status='in_progress'")
    p.state.db.commit()
    folder = p.state.root / "tmp" / "recovery"
    folder.mkdir(parents=True)
    stale = folder / "1.part"
    stale.write_bytes(b"unfinished")
    assert p.execute()["counts"] == {"done": 1} and not stale.exists()
    p.close()
    image.close()


def test_metadata_preserves_quality_rejection_after_successful_transfer(config, tmp_path):
    from conftest import encoded_image

    body = encoded_image(500, 400)
    image = transport(
        config, lambda req: httpx.Response(200, headers={"content-type": "image/jpeg"}, content=body), "image"
    )
    p = Pipeline(config, "quality-rejection", image_transport=image)
    p.create("image", ["https://cdn.example.test/blank"])
    try:
        summary = p.execute()
        record = json.loads(Path(summary["metadata_file"]).read_text(encoding="utf-8"))
        assert summary["counts"] == {"rejected": 1}
        assert record["status"] == "rejected"
        assert record["transfer_status"] == "downloaded"
        assert record["quality"]["status"] == "rejected"
        assert "file_path" not in record
    finally:
        p.close()
        image.close()
