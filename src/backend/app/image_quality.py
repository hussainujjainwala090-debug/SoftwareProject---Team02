"""Server-side image checks (FR-03, NFR-02; ScanController.checkImageQuality).

The app already compresses to 1 MB or less and checks blur before upload; the
backend checks again because a client cannot be trusted.
"""
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, UnidentifiedImageError

MIN_BRIGHTNESS = 40.0  # mean grey level 0-255; below this the photo is too dark


@dataclass(frozen=True)
class QualityResult:
    ok: bool
    reason: str | None
    blur_score: float
    brightness: float


def blur_score(gray: np.ndarray) -> float:
    """Variance of the Laplacian: low values mean a blurry image."""
    g = gray.astype(np.float32)
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    return float(lap.var())


def check(image: bytes, blur_threshold: float) -> QualityResult:
    try:
        img = Image.open(io.BytesIO(image))
        img.load()
    except (UnidentifiedImageError, OSError):
        return QualityResult(False, "The file is not a readable image.", 0.0, 0.0)
    img = img.convert("L")
    img.thumbnail((512, 512))
    gray = np.asarray(img)
    if min(gray.shape) < 32:
        return QualityResult(False, "The image is too small.", 0.0, 0.0)
    score = blur_score(gray)
    brightness = float(gray.mean())
    if brightness < MIN_BRIGHTNESS:
        return QualityResult(False, "The image is too dark. Please retake in better light.", score, brightness)
    if score < blur_threshold:
        return QualityResult(False, "Image is blurry. Please retake.", score, brightness)
    return QualityResult(True, None, score, brightness)
