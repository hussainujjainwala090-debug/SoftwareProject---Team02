"""Disease classifier wrapper used by the backend (FR-04). Needs TensorFlow.

The model file is produced by agriscan_ml.train. It takes RGB images of
IMG_SIZE x IMG_SIZE with values 0-255 (rescaling is inside the model) and
returns class probabilities in the order of labels.json.
"""
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image

IMG_SIZE = 224


@dataclass(frozen=True)
class RawPrediction:
    label: str
    crop: str
    confidence: float


def to_array(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((IMG_SIZE, IMG_SIZE))
    return np.asarray(img, dtype=np.float32)[None, ...]


class KerasClassifier:
    def __init__(self, model_path: str, labels: list[dict]) -> None:
        import keras

        self.model = keras.models.load_model(model_path)
        self.labels = labels

    def predict(self, image_bytes: bytes) -> RawPrediction:
        probs = self.model.predict(to_array(image_bytes), verbose=0)[0]
        best = int(np.argmax(probs))
        entry = self.labels[best]
        return RawPrediction(entry["label"], entry["crop"], float(probs[best]))

    def classify(self, image: bytes, crop: str):
        """Backend interface: returns app.ml.Prediction-compatible fields."""
        from types import SimpleNamespace

        p = self.predict(image)
        return SimpleNamespace(label=p.label, crop=p.crop, confidence=p.confidence)
