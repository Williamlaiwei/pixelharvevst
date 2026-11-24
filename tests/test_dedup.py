from PIL import Image

from pixelharvest.dedup import compute_phash, find_duplicates, hamming


def test_exact_and_near_resized_keep_best(image_file, tmp_path):
    copy = tmp_path / "copy.jpg"
    copy.write_bytes(image_file.read_bytes())
    large = tmp_path / "large.png"
    with Image.open(image_file) as image:
        image.resize((1000, 800)).save(large)
    result = find_duplicates(
        [image_file, copy, large], {"phash_threshold": 8, "aspect_tolerance": 0.02, "keep": "best"}
    )
    assert len(result["exact_duplicates"]) == 1 and result["files_removed"] == 0
    assert result["similar_pairs"] and all(
        item["recommended_keep"] == str(large) for item in result["similar_pairs"]
    )
    assert hamming(compute_phash(image_file), compute_phash(large)) <= 8


def test_aspect_guard(image_file, tmp_path):
    stretched = tmp_path / "stretched.jpg"
    with Image.open(image_file) as image:
        image.resize((1000, 200)).save(stretched)
    result = find_duplicates(
        [image_file, stretched], {"phash_threshold": 64, "aspect_tolerance": 0.02, "keep": "first"}
    )
    assert not result["similar_pairs"]
