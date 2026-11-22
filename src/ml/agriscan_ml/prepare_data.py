"""Extract the PlantVillage classes AgriScan uses from the official zip.

The zip ("Plant_leaf_diseases_dataset_without_augmentation.zip", Mendeley Data,
doi:10.17632/tywbtsjrjv.1) is what TensorFlow Datasets downloads for
"plant_village". TFDS's own extraction fails on Windows when paths pass 260
characters, so this script extracts only the classes in labels.py into a short
folder, one sub-folder per class.

Usage (from src/ml):
    python -m agriscan_ml.prepare_data <path-to-zip> C:/Users/<you>/agriscan-data/pv
"""
import sys
import zipfile
from pathlib import Path, PurePosixPath

from agriscan_ml.labels import CLASS_MAP


def extract(zip_path: str, out_dir: str) -> dict[str, int]:
    out = Path(out_dir).resolve()
    counts = {c: 0 for c in CLASS_MAP}
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            parts = PurePosixPath(info.filename).parts
            if info.is_dir() or len(parts) != 3 or parts[1] not in CLASS_MAP:
                continue
            target = (out / parts[1] / parts[2]).resolve()
            if out not in target.parents:  # refuse path traversal
                raise ValueError(f"Unsafe path in zip: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            counts[parts[1]] += 1
    return counts


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    result = extract(sys.argv[1], sys.argv[2])
    for name, n in result.items():
        print(f"{n:6d}  {name}")
    print(f"{sum(result.values()):6d}  total")
