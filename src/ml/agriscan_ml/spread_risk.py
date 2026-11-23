"""Spread-risk model (FR-08, FR-11), rule-based version.

There is no labelled spread data yet, so the level is a transparent score of
known risk factors for fungal and bacterial leaf diseases: high humidity, rain
(leaf wetness), mild temperatures and how much of the leaf is already affected.
The same predict() signature can later be backed by a trained model.

Score: humidity >= 85% +2, >= 65% +1; rain >= 5 mm +2, > 0 mm +1;
15-30 C +1; severity high +2, medium +1.  Level: >= 4 high, >= 2 medium, else low.
"""
from dataclasses import dataclass

HIGH_FROM = 4
MEDIUM_FROM = 2


@dataclass(frozen=True)
class RiskResult:
    level: str  # "low" | "medium" | "high"
    score: int
    explanation: str


def predict(
    disease: str | None,
    crop: str,
    severity_level: str | None,
    temperature: float,
    humidity: float,
    rainfall: float,
) -> RiskResult:
    score = 0
    reasons: list[str] = []

    if humidity >= 85:
        score += 2
        reasons.append(f"very humid ({humidity:.0f}%)")
    elif humidity >= 65:
        score += 1
        reasons.append(f"humid ({humidity:.0f}%)")

    if rainfall >= 5:
        score += 2
        reasons.append(f"heavy rain ({rainfall:.1f} mm)")
    elif rainfall > 0:
        score += 1
        reasons.append(f"rain ({rainfall:.1f} mm)")

    if 15 <= temperature <= 30:
        score += 1
        reasons.append(f"mild temperature ({temperature:.0f} C)")

    if severity_level == "high":
        score += 2
        reasons.append("high severity on the leaf")
    elif severity_level == "medium":
        score += 1
        reasons.append("medium severity on the leaf")

    level = "high" if score >= HIGH_FROM else "medium" if score >= MEDIUM_FROM else "low"
    subject = disease or f"leaf diseases of {crop.replace('_', ' ')}"
    if reasons:
        explanation = f"{level.capitalize()} risk for {subject}: " + ", ".join(reasons) + "."
    else:
        explanation = f"Low risk for {subject}: current weather does not favour spread."
    return RiskResult(level=level, score=score, explanation=explanation)
