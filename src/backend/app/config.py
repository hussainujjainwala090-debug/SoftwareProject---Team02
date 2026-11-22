"""Application settings, read from environment variables or a local .env file.

No secret has a default value. In "memory" mode the backend runs without any
Firebase project: data is kept in memory and files are written to a local folder.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGRISCAN_", env_file=".env", extra="ignore")

    # "memory": in-memory data, local files, dev tokens (no secrets needed).
    # "firebase": Firestore, Cloud Storage, FCM and Firebase ID tokens.
    mode: Literal["memory", "firebase"] = "memory"

    # Firebase (only used in firebase mode). Path to a service-account JSON file,
    # kept outside the repository.
    firebase_credentials: str = ""
    firebase_storage_bucket: str = ""

    # Base URL that clients use to reach this server (used for local file links).
    public_base_url: str = "http://localhost:8000"
    local_storage_dir: str = ".local_storage"

    # Scan rules (FR-03, FR-05, FR-06, NFR-02)
    max_image_bytes: int = 1_000_000
    blur_threshold: float = 60.0
    confidence_threshold: float = 0.70
    severity_medium_from_pct: float = 15.0
    severity_high_from_pct: float = 40.0

    # Weather (FR-14, NFR-09): reuse a record younger than refresh_minutes,
    # fall back to one younger than cache_max_hours when the service is down.
    weather_provider: Literal["open-meteo", "fake"] = "open-meteo"
    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_refresh_minutes: int = 30
    weather_cache_max_hours: int = 6

    # Climate alerts (FR-11): minutes between automatic checks, 0 = off.
    alert_interval_minutes: int = 0

    # ML (FR-04): trained classifier file, produced by src/ml/classifier/train.py.
    classifier_model_path: str = "../ml/models/classifier.keras"
    classifier_labels_path: str = "../ml/models/labels.json"

    # Emails that get the admin role when they register (first admin of a new
    # deployment). Comma-separated JSON list in the environment, e.g.
    # AGRISCAN_ADMIN_EMAILS='["admin@example.com"]'.
    admin_emails: list[str] = []

    # Load demo knowledge-base entries at start-up (memory mode).
    seed_demo_data: bool = True

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
