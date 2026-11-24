import pytest

from pixelharvest.config import load_config
from pixelharvest.parser import normalize_url, parse_images, srcset_candidates
from pixelharvest.pipeline import read_input


def test_queries_and_commas_preserved():
    assert srcset_candidates("/a?crop=2,3 500w, /b?x=3,4 1200w")[-1][2] == "/b?x=3,4"
    assert normalize_url("/b?x=3,4#top", "https://example.test/story") == "https://example.test/b?x=3,4"


def test_selector_picture_lazy_metadata():
    html = '<title>Gallery</title><img src="/excluded"><main><figure><picture><source srcset="/large?crop=2,3 1200w"><img data-src="/small" alt="Texture"></picture><figcaption>Generated</figcaption></figure></main>'
    images = parse_images(html, "https://example.test/page", ["main img"])
    assert len(images) == 1
    assert images[0]["url"].endswith("/large?crop=2,3")
    assert images[0]["title"] == "Gallery" and images[0]["caption"] == "Generated"


@pytest.mark.parametrize(
    "url", ["file:///tmp/a", "https://person:password@example.test/a", "data:image/png,AA"]
)
def test_bad_url(url):
    with pytest.raises(ValueError):
        normalize_url(url)


@pytest.mark.parametrize(
    "override",
    [
        {},
        {"allowed_domains": ["*.example.test"], "image_domains": ["example.test"]},
        {"http": {"max_attempts": 1.5}},
        {"http": {"request_interval_seconds": float("nan")}},
        {"quality": {"min_width": -1}},
        {"batch_size": 0},
        {"unknown": True},
        {"page_auth": {"headers": {"Cookie": "placeholder"}}},
        {"page_auth": {"headers_env": {"Authorization": "TEST_TOKEN"}}},
    ],
)
def test_invalid_config(override):
    if override:
        override = {"allowed_domains": ["example.test"], "image_domains": ["example.test"], **override}
    with pytest.raises(ValueError):
        load_config(overrides=override)


def test_csv_and_txt_inputs(tmp_path):
    path = tmp_path / "urls.csv"
    path.write_text('url,title\n"https://example.test/image?crop=1,2","A, B"\n')
    assert list(read_input(path))[0]["title"] == "A, B"
    path = tmp_path / "urls.txt"
    path.write_text("# comment\nhttps://example.test/image?crop=1,2\n")
    assert list(read_input(path))[0]["url"].endswith("crop=1,2")
