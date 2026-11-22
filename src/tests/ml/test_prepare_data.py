"""Dataset extraction: only AgriScan classes are extracted and unsafe paths are refused."""
import zipfile

import pytest

from agriscan_ml.prepare_data import extract

ROOT = "Plant_leave_diseases_dataset_without_augmentation"


def make_zip(path, names):
    with zipfile.ZipFile(path, "w") as zf:
        for n in names:
            zf.writestr(n, b"jpeg-bytes")
    return path


def test_extracts_only_tomato_and_pepper_classes(tmp_path):
    z = make_zip(tmp_path / "pv.zip", [
        f"{ROOT}/Tomato___Early_blight/image (1).JPG",
        f"{ROOT}/Pepper,_bell___healthy/image (2).JPG",
        f"{ROOT}/Apple___Apple_scab/image (3).JPG",
    ])
    counts = extract(str(z), str(tmp_path / "out"))
    assert counts["Tomato___Early_blight"] == 1 and counts["Pepper,_bell___healthy"] == 1
    assert (tmp_path / "out" / "Tomato___Early_blight" / "image (1).JPG").read_bytes() == b"jpeg-bytes"
    assert not (tmp_path / "out" / "Apple___Apple_scab").exists()


def test_refuses_path_traversal(tmp_path):
    z = make_zip(tmp_path / "bad.zip", [f"{ROOT}/Tomato___Early_blight/.."])
    with pytest.raises(ValueError):
        extract(str(z), str(tmp_path / "out"))
