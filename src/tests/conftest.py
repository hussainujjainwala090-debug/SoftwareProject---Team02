import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))  # for tests/images.py

from app.adapters.auth import DevTokenVerifier, FakeAccountAdmin  # noqa: E402
from app.adapters.messaging import FakeMessenger  # noqa: E402
from app.adapters.weather import FakeWeatherClient  # noqa: E402
from app.clock import FixedClock  # noqa: E402
from app.config import Settings  # noqa: E402
from app.container import build_container  # noqa: E402
from app.main import create_app  # noqa: E402
from app.ml import Prediction  # noqa: E402

ADMIN_EMAIL = "admin@test.com"
NOW = datetime(2026, 11, 21, 9, 30, tzinfo=UTC)


class FakeClassifier:
    """Returns whatever the test sets in .prediction."""

    def __init__(self) -> None:
        self.prediction = Prediction(label="Tomato early blight", crop="tomato", confidence=0.91)

    def classify(self, image: bytes, crop: str) -> Prediction:
        return self.prediction


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, mode="memory", weather_provider="fake",
                    local_storage_dir=str(tmp_path / "files"), admin_emails=[ADMIN_EMAIL],
                    seed_demo_data=True, public_base_url="http://testserver")


@pytest.fixture
def container(settings):
    accounts = FakeAccountAdmin()
    return build_container(
        settings, accounts=accounts, verifier=DevTokenVerifier(accounts),
        weather=FakeWeatherClient(), messenger=FakeMessenger(),
        classifier=FakeClassifier(), clock=FixedClock(NOW))


@pytest.fixture
def client(settings, container):
    with TestClient(create_app(settings, container)) as test_client:
        yield test_client


def auth(uid: str, email: str | None = None) -> dict:
    return {"Authorization": f"Bearer dev:{uid}:{email or uid + '@test.com'}"}


def register(client, uid: str, role: str = "farmer", email: str | None = None) -> dict:
    headers = auth(uid, email)
    resp = client.post("/api/v1/users/register", json={"name": uid.title(), "role": role},
                       headers=headers)
    assert resp.status_code == 201, resp.text
    return headers


@pytest.fixture
def farmer(client):
    return register(client, "farmer1")


@pytest.fixture
def admin(client):
    return register(client, "admin1", email=ADMIN_EMAIL)


@pytest.fixture
def agronomist(client):
    return register(client, "agro1", role="agronomist")


@pytest.fixture
def farm(client, farmer):
    resp = client.post("/api/v1/farms", headers=farmer, json={
        "name": "Al Ain palm farm", "latitude": 24.2075, "longitude": 55.7447,
        "crops": ["date_palm", "tomato"]})
    assert resp.status_code == 201, resp.text
    return resp.json()
