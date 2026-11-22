"""Evaluate the saved classifier file exactly as the backend uses it (NFR-03, TC-21).

Runs every test-split image (per class, sorted file index % 10 == 9, as in
train.py) through KerasClassifier, the wrapper the backend loads, and reports
accuracy overall, per class, and for the results above the backend's
confidence threshold (lower ones are shown as "Uncertain", FR-05).

Usage (from src/ml):
    python -m agriscan_ml.evaluate --image-dir C:/Users/<you>/agriscan-data/pv
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from agriscan_ml.classifier import KerasClassifier
from agriscan_ml.labels import CLASS_MAP


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--models", default="models")
    parser.add_argument("--threshold", type=float, default=0.70)
    args = parser.parse_args()

    labels = json.loads((Path(args.models) / "labels.json").read_text(encoding="utf-8"))
    clf = KerasClassifier(str(Path(args.models) / "classifier.keras"), labels)

    total = correct = confident = confident_correct = 0
    per_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for cls, (crop, label) in CLASS_MAP.items():
        files = sorted(p for p in (Path(args.image_dir) / cls).iterdir() if p.is_file())
        for f in files[9::10]:
            p = clf.predict(f.read_bytes())
            ok = p.label == label and p.crop == crop
            total += 1
            correct += ok
            per_class[cls][0] += 1
            per_class[cls][1] += ok
            if p.confidence >= args.threshold:
                confident += 1
                confident_correct += ok

    print(f"Test images: {total}")
    print(f"Accuracy (all predictions): {correct / total:.4f}   NFR-03 target: 0.85")
    print(f"Confidence >= {args.threshold}: {confident / total:.4f} of images, "
          f"accuracy on them {confident_correct / confident:.4f}")
    print(f"Shown as 'Uncertain' (below threshold): {1 - confident / total:.4f}")
    print("\nRecall per class:")
    for cls, (n, ok) in per_class.items():
        print(f"  {ok / n:.3f}  ({ok}/{n})  {cls}")


if __name__ == "__main__":
    main()
