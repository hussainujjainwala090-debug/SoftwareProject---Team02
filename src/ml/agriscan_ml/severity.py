"""Severity segmentation (FR-06, FR-07), simplest working version.

Colour rule in HSV space:
  * green pixels  = healthy-green hue, saturated and not too dark;
  * leaf outline  = convex hull of the green pixels, so a coloured background
                    (soil, a brown table) outside the leaf is not counted;
  * lesion pixels = saturated, non-green pixels (yellow, brown, orange, red)
                    inside the outline;
  * leaf pixels   = green or lesion pixels.
affected_area_pct = lesion pixels / leaf pixels * 100.

Limits (to be stated in the report): pale or grey lesions are missed, coloured
background inside the outline (e.g. between deep lobes) can be counted, and
NFR-04 (mean IoU >= 0.70) cannot be measured until the team labels masks for
real farm photos. The interface stays the same if this rule is replaced by a
trained segmentation network.
"""
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MEDIAN_SIZE = 5
# PIL HSV channels are 0-255. Hue 45-110 is about 63-155 degrees (healthy green).
GREEN_HUE_MIN = 45
GREEN_HUE_MAX = 110
LEAF_MIN_SATURATION = 60
LEAF_MIN_VALUE = 40
MIN_LEAF_FRACTION = 0.01
MIN_ROW_PIXELS = 3  # ignore rows with only a few stray green pixels
OVERLAY_COLOUR = np.array([255, 0, 0], dtype=np.float32)
OVERLAY_ALPHA = 0.55


@dataclass(frozen=True)
class SeverityEstimate:
    affected_area_pct: float
    overlay_png: bytes
    leaf_mask: np.ndarray
    lesion_mask: np.ndarray


def _load(image_bytes: bytes, max_side: int) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((max_side, max_side))
    return img


def masks(img: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    # A median filter removes camera noise, which would otherwise make single
    # background pixels look saturated (and count as leaf or lesion).
    smooth = img.filter(ImageFilter.MedianFilter(MEDIAN_SIZE))
    hsv = np.asarray(smooth.convert("HSV"), dtype=np.int16)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    coloured = (s >= LEAF_MIN_SATURATION) & (v >= LEAF_MIN_VALUE)
    green = coloured & (h >= GREEN_HUE_MIN) & (h <= GREEN_HUE_MAX)
    outline = _hull_mask(green)
    lesion = coloured & ~green & outline
    return green | lesion, lesion


def _hull_mask(points: np.ndarray) -> np.ndarray:
    """Filled convex hull of the True pixels (all False if there are too few)."""
    rows = np.flatnonzero(points.sum(axis=1) >= MIN_ROW_PIXELS)
    if len(rows) < 3:
        return np.zeros_like(points)
    # The left- and right-most pixel of each row are enough to find the hull.
    pts = set()
    for y in rows:
        xs = np.flatnonzero(points[y])
        pts.add((int(xs[0]), int(y)))
        pts.add((int(xs[-1]), int(y)))
    hull = _convex_hull(sorted(pts))
    canvas = Image.new("1", (points.shape[1], points.shape[0]), 0)
    ImageDraw.Draw(canvas).polygon(hull, fill=1, outline=1)
    return np.asarray(canvas, dtype=bool)


def _convex_hull(pts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Andrew's monotone chain; pts must be sorted."""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    upper: list = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def overlay(img: Image.Image, lesion: np.ndarray) -> bytes:
    rgb = np.asarray(img, dtype=np.float32).copy()
    rgb[lesion] = rgb[lesion] * (1 - OVERLAY_ALPHA) + OVERLAY_COLOUR * OVERLAY_ALPHA
    out = io.BytesIO()
    Image.fromarray(rgb.astype(np.uint8)).save(out, format="PNG")
    return out.getvalue()


def estimate(image_bytes: bytes, max_side: int = 512) -> SeverityEstimate:
    img = _load(image_bytes, max_side)
    leaf, lesion = masks(img)
    leaf_px = int(leaf.sum())
    if leaf_px < MIN_LEAF_FRACTION * leaf.size:
        pct = 0.0
    else:
        pct = round(float(lesion.sum()) / leaf_px * 100.0, 1)
    return SeverityEstimate(
        affected_area_pct=min(max(pct, 0.0), 100.0),
        overlay_png=overlay(img, lesion),
        leaf_mask=leaf,
        lesion_mask=lesion,
    )


def mean_iou(pred: np.ndarray, truth: np.ndarray) -> float:
    """Mean IoU over the lesion and non-lesion classes, for NFR-04 evaluation."""
    ious = []
    for cls in (True, False):
        p, t = pred == cls, truth == cls
        union = np.logical_or(p, t).sum()
        if union:
            ious.append(np.logical_and(p, t).sum() / union)
    return float(np.mean(ious)) if ious else 1.0
