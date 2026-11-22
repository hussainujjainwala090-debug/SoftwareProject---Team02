"""TC-04: classifier wrapper and label map (FR-04). The model test needs TensorFlow."""
import pytest

from agriscan_ml.labels import CLASS_MAP
from images import leaf_png


def test_every_disease_label_exists_in_the_knowledge_base_seed():
    from app.seed_data import SEED_DISEASES

    seeded = {(d.crop_type.value, d.name) for d in SEED_DISEASES}
    for crop, label in CLASS_MAP.values():
        assert label == "healthy" or (crop, label) in seeded, label


def test_wrapper_returns_label_crop_and_confidence(tmp_path):
    keras = pytest.importorskip("keras")
    pytest.importorskip("tensorflow")
    from agriscan_ml.classifier import IMG_SIZE, KerasClassifier

    inp = keras.Input((IMG_SIZE, IMG_SIZE, 3))
    x = keras.layers.GlobalAveragePooling2D()(inp)
    out = keras.layers.Dense(2, activation="softmax", kernel_initializer="zeros",
                             bias_initializer=keras.initializers.Constant([0.0, 3.0]))(x)
    path = tmp_path / "tiny.keras"
    keras.Model(inp, out).save(path)

    labels = [{"class": "Tomato___healthy", "crop": "tomato", "label": "healthy"},
              {"class": "Tomato___Early_blight", "crop": "tomato", "label": "Tomato early blight"}]
    result = KerasClassifier(str(path), labels).classify(leaf_png(), "tomato")
    assert result.label == "Tomato early blight" and result.crop == "tomato"
    assert result.confidence == pytest.approx(0.9526, abs=1e-3)  # softmax of [0, 3]
