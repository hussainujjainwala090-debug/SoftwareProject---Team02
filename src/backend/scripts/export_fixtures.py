"""Save real backend responses as JSON fixtures for the Flutter app's tests.

The app's model tests parse these files, so they check the real JSON format,
not a copy written by hand. Run from src/backend (in an environment with
TensorFlow, so the trained classifier is used) after an API change:

    python scripts/export_fixtures.py <path to a tomato leaf photo>

Writes src/app/test/fixtures/*.json. Uses memory mode, fake weather and
development accounts only.
"""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.weather import FakeWeatherClient, HourlyWeather, WeatherReading  # noqa: E402
from app.config import Settings  # noqa: E402
from app.container import build_container  # noqa: E402
from app.main import create_app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "app" / "test" / "fixtures"


def main(photo: Path) -> None:
    import tempfile

    settings = Settings(_env_file=None, weather_provider="fake", admin_emails=["admin@example.com"],
                        local_storage_dir=tempfile.mkdtemp(), public_base_url="http://localhost:8000")
    # Fixed weather with a 24-hour forecast that gets cooler and more humid overnight.
    forecast = tuple(HourlyWeather(34.0 - h * 0.5, 60.0 + h, 0.0) for h in range(24))
    container = build_container(settings, weather=FakeWeatherClient(
        WeatherReading(temperature=34.0, humidity=78.0, rainfall=0.0, forecast=forecast)))
    OUT.mkdir(parents=True, exist_ok=True)
    saved = []

    def save(name: str, resp):
        assert resp.status_code < 300, (name, resp.status_code, resp.text)
        (OUT / f"{name}.json").write_text(json.dumps(resp.json(), indent=2), encoding="utf-8")
        saved.append(name)
        return resp.json()

    with TestClient(create_app(settings, container)) as c:
        farmer = {"Authorization": "Bearer dev:farmer1:farmer@example.com"}
        admin = {"Authorization": "Bearer dev:admin1:admin@example.com"}
        save("me", c.post("/api/v1/users/register", json={"name": "Aisha K.", "role": "farmer"}, headers=farmer))
        c.post("/api/v1/users/register", json={"name": "Admin"}, headers=admin)
        farm = save("farm", c.post("/api/v1/farms", headers=farmer, json={
            "name": "Al Ain palm farm", "latitude": 24.2075, "longitude": 55.7447,
            "crops": ["date_palm", "tomato"]}))
        form = {"farm_id": farm["farm_id"], "crop_type": "tomato"}
        image = {"image": (photo.name, photo.read_bytes(), "image/jpeg")}
        d = save("diagnosis_confirmed", c.post("/api/v1/scans", headers=farmer, data=form, files=image))
        save("diagnosis_uncertain", c.post("/api/v1/scans", headers=farmer, files=image,
                                           data={**form, "crop_type": "date_palm"}))
        save("spread_risk", c.get(f"/api/v1/diagnoses/{d['diagnosis_id']}/spread-risk", headers=farmer))
        c.post(f"/api/v1/diagnoses/{d['diagnosis_id']}/feedback", json={"correct": True}, headers=farmer)
        save("report", c.post(f"/api/v1/diagnoses/{d['diagnosis_id']}/reports", headers=farmer))
        save("history", c.get("/api/v1/diagnoses", headers=farmer))
        save("dashboard", c.get(f"/api/v1/farms/{farm['farm_id']}/dashboard", headers=farmer))
        save("diseases", c.get("/api/v1/diseases", params={"crop": "tomato"}, headers=farmer))
        save("users", c.get("/api/v1/admin/users", headers=admin))
        save("model_accuracy", c.get("/api/v1/admin/model-accuracy", headers=admin))
    print("Saved:", ", ".join(saved), "->", OUT)
    print("Classifier used:", type(container.classifier).__name__)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
