"""TC-08: spread-risk levels (FR-08)."""
import pytest

from agriscan_ml.spread_risk import predict


@pytest.mark.parametrize("temp,hum,rain,sev,level", [
    (38, 20, 0, None, "low"),        # hot and dry
    (38, 20, 0, "high", "medium"),   # dry, but leaf badly affected
    (25, 70, 0, None, "medium"),     # mild and humid
    (25, 90, 6, None, "high"),       # wet, very humid and mild
    (34, 78, 0, "medium", "medium"),  # the UI-4 example weather
    (34, 90, 1, "high", "high"),
])
def test_levels(temp, hum, rain, sev, level):
    assert predict("Tomato early blight", "tomato", sev, temp, hum, rain).level == level


def test_explanation_names_the_reasons():
    r = predict("Tomato early blight", "tomato", "high", 25, 90, 6)
    assert "Tomato early blight" in r.explanation
    assert "very humid" in r.explanation and "heavy rain" in r.explanation


def test_farm_level_explanation_uses_crop_name():
    r = predict(None, "date_palm", None, 40, 10, 0)
    assert r.level == "low" and "date palm" in r.explanation
