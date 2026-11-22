"""The three ML components behind small interfaces (Class Diagram A).

The Scan service only talks to these protocols, so each model can be replaced
(NFR-16) and the tests can use fakes without TensorFlow installed.
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agriscan_ml import severity as severity_rules
from agriscan_ml import spread_risk as spread_rules

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Prediction:
    """label is a Diseases.name, "healthy", or None when the model cannot decide."""

    label: str | None
    crop: str | None
    confidence: float


@dataclass(frozen=True)
class SeverityResult:
    affected_area_pct: float
    overlay_png: bytes


@dataclass(frozen=True)
class RiskResult:
    level: str
    explanation: str


class DiseaseClassifier(Protocol):
    def classify(self, image: bytes, crop: str) -> Prediction: ...


class SeveritySegmenter(Protocol):
    def segment(self, image: bytes) -> SeverityResult: ...


class SpreadRiskModel(Protocol):
    def predict(self, disease: str | None, crop: str, severity_level: str | None,
                temperature: float, humidity: float, rainfall: float) -> RiskResult: ...


class NoModelClassifier:
    """Used until a trained model file exists: every scan goes to 'Uncertain'."""

    def classify(self, image: bytes, crop: str) -> Prediction:
        return Prediction(label=None, crop=None, confidence=0.0)


class ColourSegmenter:
    def segment(self, image: bytes) -> SeverityResult:
        est = severity_rules.estimate(image)
        return SeverityResult(affected_area_pct=est.affected_area_pct, overlay_png=est.overlay_png)


class RuleSpreadRiskModel:
    def predict(self, disease, crop, severity_level, temperature, humidity, rainfall) -> RiskResult:
        r = spread_rules.predict(disease, crop, severity_level, temperature, humidity, rainfall)
        return RiskResult(level=r.level, explanation=r.explanation)


def load_classifier(model_path: str, labels_path: str) -> DiseaseClassifier:
    """Load the trained CNN if it and TensorFlow are available, else NoModelClassifier."""
    if not (Path(model_path).is_file() and Path(labels_path).is_file()):
        log.warning("No classifier model at %s; all scans will be 'Uncertain'.", model_path)
        return NoModelClassifier()
    try:
        from agriscan_ml.classifier import KerasClassifier  # needs tensorflow
    except ImportError as exc:
        log.warning("TensorFlow classifier not available (%s); using NoModelClassifier.", exc)
        return NoModelClassifier()
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    return KerasClassifier(model_path, labels)
