"""Train the disease classifier (FR-04, NFR-03): MobileNetV2 transfer learning.

Data: PlantVillage (Mendeley Data, doi:10.17632/tywbtsjrjv.1, the same zip TFDS
uses), tomato and bell pepper classes only (see labels.py), extracted with
agriscan_ml.prepare_data. Within each class the sorted files are split by
index into 80% train / 10% validation / 10% test, the same split every run.

Method (simplest working form): the ImageNet MobileNetV2 base is frozen; its
pooled features are computed once and a small softmax head is trained on them.
The saved model contains rescaling + base + head, so it takes 0-255 RGB input.

Run from src/ml with the ML environment:
    python -m agriscan_ml.train --image-dir C:/Users/<you>/agriscan-data/pv
Outputs (git-ignored): models/classifier.keras, models/labels.json, models/eval.json
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from agriscan_ml.classifier import IMG_SIZE
from agriscan_ml.labels import CLASS_MAP

SEED = 42


def load_split(image_dir: str):
    """Per class, sorted file list; file index % 10: 0-7 train, 8 val, 9 test."""
    import tensorflow as tf

    parts: dict[str, tuple[list[str], list[int]]] = {"train": ([], []), "val": ([], []), "test": ([], [])}
    for label, cls in enumerate(CLASS_MAP):
        files = sorted(str(p) for p in (Path(image_dir) / cls).iterdir() if p.is_file())
        if not files:
            raise SystemExit(f"No images for class {cls} in {image_dir}")
        for i, f in enumerate(files):
            name = "train" if i % 10 < 8 else "val" if i % 10 == 8 else "test"
            parts[name][0].append(f)
            parts[name][1].append(label)

    def load(path, label):
        img = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
        return tf.image.resize(img, (IMG_SIZE, IMG_SIZE)), label

    return tuple(
        tf.data.Dataset.from_tensor_slices((files, labels)).map(load, num_parallel_calls=tf.data.AUTOTUNE)
        for files, labels in parts.values())


def features(base, ds, batch: int = 64) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for images, labels in ds.batch(batch):
        xs.append(base(images, training=False).numpy())
        ys.append(labels.numpy())
    return np.concatenate(xs), np.concatenate(ys)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", required=True,
                        help="Folder with one sub-folder per class (made by agriscan_ml.prepare_data)")
    parser.add_argument("--out", default="models")
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()

    import keras
    import tensorflow as tf

    keras.utils.set_random_seed(SEED)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    classes = list(CLASS_MAP)

    t0 = time.time()
    train_ds, val_ds, test_ds = load_split(args.image_dir)
    inp = keras.Input((IMG_SIZE, IMG_SIZE, 3))
    scaled = keras.layers.Rescaling(1 / 127.5, offset=-1)(inp)
    backbone = keras.applications.MobileNetV2(include_top=False, weights="imagenet",
                                              input_shape=(IMG_SIZE, IMG_SIZE, 3), pooling="avg")
    backbone.trainable = False
    base = keras.Model(inp, backbone(scaled, training=False))

    x_tr, y_tr = features(base, train_ds)
    x_va, y_va = features(base, val_ds)
    x_te, y_te = features(base, test_ds)
    print(f"features: train {len(y_tr)}, val {len(y_va)}, test {len(y_te)} "
          f"({time.time() - t0:.0f}s)")

    head = keras.Sequential([
        keras.Input((x_tr.shape[1],)),
        keras.layers.Dropout(0.3),
        keras.layers.Dense(len(classes), activation="softmax"),
    ])
    head.compile(optimizer=keras.optimizers.Adam(1e-3),
                 loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    head.fit(x_tr, y_tr, validation_data=(x_va, y_va), epochs=args.epochs, batch_size=64,
             callbacks=[keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True)],
             verbose=2)

    probs = head.predict(x_te, verbose=0)
    pred = probs.argmax(1)
    conf = np.zeros((len(classes), len(classes)), int)
    for t, p in zip(y_te, pred):
        conf[t, p] += 1
    per_class = {}
    for i, name in enumerate(classes):
        tp = conf[i, i]
        per_class[name] = {
            "support": int(conf[i].sum()),
            "precision": round(float(tp / max(conf[:, i].sum(), 1)), 3),
            "recall": round(float(tp / max(conf[i].sum(), 1)), 3),
        }
    report = {
        "dataset": "PlantVillage (doi:10.17632/tywbtsjrjv.1), tomato + bell pepper classes",
        "split": "per class, sorted file index % 10: 0-7 train, 8 validation, 9 test",
        "train_images": int(len(y_tr)), "val_images": int(len(y_va)), "test_images": int(len(y_te)),
        "test_accuracy": round(float((pred == y_te).mean()), 4),
        "nfr03_target": 0.85,
        "share_of_test_images_above_0.70_confidence": round(float((probs.max(1) >= 0.70).mean()), 4),
        "accuracy_on_those_images": round(float((pred == y_te)[probs.max(1) >= 0.70].mean()), 4),
        "per_class": per_class,
        "classes": classes,
        "confusion_matrix": conf.tolist(),
        "tensorflow": tf.__version__,
        "minutes": round((time.time() - t0) / 60, 1),
    }

    full = keras.Model(inp, head(base(inp)))
    full.save(out / "classifier.keras")
    (out / "labels.json").write_text(json.dumps(
        [{"class": c, "crop": CLASS_MAP[c][0], "label": CLASS_MAP[c][1]} for c in classes],
        indent=2), encoding="utf-8")
    (out / "eval.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("per_class", "confusion_matrix", "classes")}, indent=2))


if __name__ == "__main__":
    main()
