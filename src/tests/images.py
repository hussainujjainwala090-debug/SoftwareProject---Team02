"""Synthetic leaf photos for tests (no real farm data needed)."""
import io

import numpy as np
from PIL import Image, ImageFilter

SIZE = 256


def leaf_arrays(lesion_radius: int = 0, seed: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (rgb, leaf_mask, lesion_mask) for a green leaf on a grey background."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    leaf = ((xx - 128) / 100) ** 2 + ((yy - 128) / 70) ** 2 <= 1
    lesion = np.zeros_like(leaf)
    if lesion_radius:
        for cx, cy in ((95, 115), (160, 140)):
            lesion |= (xx - cx) ** 2 + (yy - cy) ** 2 <= lesion_radius ** 2
        lesion &= leaf
    rgb = np.empty((SIZE, SIZE, 3), dtype=np.float32)
    rgb[:] = (125, 125, 125)  # grey background (not saturated)
    rgb[leaf] = (55, 145, 45)  # healthy green
    rgb[lesion] = (125, 70, 25)  # brown lesion
    rgb += rng.normal(0, 10, rgb.shape)  # texture so the image is sharp
    return np.clip(rgb, 0, 255).astype(np.uint8), leaf, lesion


def encode(rgb: np.ndarray, fmt: str = "PNG", blur: float = 0.0) -> bytes:
    img = Image.fromarray(rgb)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    out = io.BytesIO()
    img.save(out, format=fmt, quality=90)
    return out.getvalue()


def leaf_png(lesion_radius: int = 25, **kw) -> bytes:
    return encode(leaf_arrays(lesion_radius)[0], **kw)


def leaf_jpeg(lesion_radius: int = 25, **kw) -> bytes:
    return encode(leaf_arrays(lesion_radius)[0], fmt="JPEG", **kw)
