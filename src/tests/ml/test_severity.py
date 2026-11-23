"""TC-06 / TC-07: severity segmentation and overlay (FR-06, FR-07)."""
import io

import numpy as np
import pytest
from PIL import Image

from agriscan_ml import severity
from images import encode, leaf_arrays, leaf_png


@pytest.mark.parametrize("radius", [15, 25, 35])
@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_affected_area_matches_known_lesion_area(radius, fmt):
    rgb, leaf, lesion = leaf_arrays(radius)
    truth = lesion.sum() / leaf.sum() * 100
    est = severity.estimate(encode(rgb, fmt=fmt))
    assert est.affected_area_pct == pytest.approx(truth, abs=2.0)


def test_brown_background_is_not_counted_as_lesion():
    """Soil or a brown table around the leaf must not raise the affected area."""
    rgb, leaf, lesion = leaf_arrays(25)
    rgb[~leaf] = (150, 110, 70)  # saturated brown background
    truth = lesion.sum() / leaf.sum() * 100
    est = severity.estimate(encode(rgb))
    assert est.affected_area_pct == pytest.approx(truth, abs=3.0)


def test_healthy_leaf_has_no_affected_area():
    assert severity.estimate(leaf_png(lesion_radius=0)).affected_area_pct == 0.0


def test_mask_iou_on_synthetic_leaf_meets_nfr04_target():
    rgb, _, lesion = leaf_arrays(25)
    est = severity.estimate(encode(rgb, fmt="JPEG"))
    assert severity.mean_iou(est.lesion_mask, lesion) >= 0.70


def test_overlay_is_png_of_same_size_and_marks_lesions_red():
    rgb, _, _ = leaf_arrays(25)
    est = severity.estimate(encode(rgb))
    img = Image.open(io.BytesIO(est.overlay_png))
    assert img.format == "PNG" and img.size == (256, 256)
    px = img.convert("RGB").getpixel((95, 115))  # centre of a lesion
    assert px[0] > px[1] and px[0] > px[2]


def test_no_leaf_in_photo_gives_zero():
    grey = Image.new("RGB", (128, 128), (120, 120, 120))
    out = io.BytesIO()
    grey.save(out, format="PNG")
    assert severity.estimate(out.getvalue()).affected_area_pct == 0.0


def test_mean_iou_perfect_and_disjoint():
    a = np.zeros((4, 4), bool)
    a[:2] = True
    assert severity.mean_iou(a, a) == 1.0
    assert severity.mean_iou(a, ~a) == 0.0
