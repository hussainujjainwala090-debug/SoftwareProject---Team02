"""Severity segmentation (FR-06, FR-07), simplest working version.

Colour rule in HSV space:
  * leaf pixels   = saturated and not too dark (the plain, grey or dark
                    background of a close-up leaf photo is not saturated);
  * lesion pixels = leaf pixels whose hue is outside the healthy-green band
                    (yellow, brown, orange and red tissue).
affected_area_pct = lesion pixels / leaf pixels * 100.

Limits (to be stated in the report): soil or other coloured backgrounds count
as leaf, and NFR-04 (mean IoU >= 0.70) cannot be measured until the team labels
masks for real farm photos. The interface stays the same if this rule is
replaced by a trained segmentation network.
"""
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

MEDIAN_SIZE = 5
# PIL HSV channels are 0-255. Hue 45-110 is about 63-155 degrees (healthy green).
GREEN_HUE_MIN = 45
GREEN_HUE_MAX = 110
LEAF_MIN_SATURATION = 60
LEAF_MIN_VALUE = 40
MIN_LEAF_FRACTION = 0.01
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
    leaf = (s >= LEAF_MIN_SATURATION) & (v >= LEAF_MIN_VALUE)
    green = (h >= GREEN_HUE_MIN) & (h <= GREEN_HUE_MAX)
    lesion = leaf & ~green
    return leaf, lesion


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
