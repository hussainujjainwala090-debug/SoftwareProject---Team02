"""TC-03: image checks before diagnosis (FR-03)."""
import io

from PIL import Image

from app.image_quality import check
from images import leaf_jpeg, leaf_png


def test_sharp_photo_passes():
    assert check(leaf_jpeg(), 60).ok


def test_blurry_photo_is_rejected_with_retake_message():
    result = check(leaf_png(blur=4), 60)
    assert not result.ok and "blurry" in result.reason


def test_dark_photo_is_rejected():
    out = io.BytesIO()
    Image.new("RGB", (200, 200), (10, 10, 10)).save(out, format="PNG")
    result = check(out.getvalue(), 60)
    assert not result.ok and "dark" in result.reason


def test_non_image_is_rejected():
    assert not check(b"not an image", 60).ok
