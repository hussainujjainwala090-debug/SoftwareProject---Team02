"""Builds the services for the configured mode (dependency wiring).

memory mode  : MemoryRepository, LocalFileStorage, dev tokens, FakeMessenger.
firebase mode: Firestore, Cloud Storage, Firebase ID tokens, Cloud Messaging.
Tests pass their own fakes through `overrides`.
"""
from dataclasses import dataclass
from typing import Any

from app.adapters import auth, messaging, storage, weather
from app.clock import Clock
from app.config import Settings
from app.ml import ColourSegmenter, RuleSpreadRiskModel, load_classifier
from app.repository import FirestoreRepository, MemoryRepository
from app.services.dashboard import DashboardService
from app.services.farms import FarmService
from app.services.forecast import ForecastService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.reports import ReportService
from app.services.scans import ScanService
from app.services.users import UserService


@dataclass
class Container:
    settings: Settings
    repo: Any
    storage: Any
    verifier: Any
    accounts: Any
    messenger: Any
    weather: Any
    classifier: Any
    segmenter: Any
    risk_model: Any
    clock: Clock
    users: UserService
    farms: FarmService
    kb: KnowledgeBaseService
    forecast: ForecastService
    scans: ScanService
    reports: ReportService
    dashboard: DashboardService


def _firebase_parts(settings: Settings) -> dict:
    import firebase_admin
    from firebase_admin import credentials, firestore

    cred = (credentials.Certificate(settings.firebase_credentials)
            if settings.firebase_credentials else credentials.ApplicationDefault())
    fb_app = firebase_admin.initialize_app(
        cred, {"storageBucket": settings.firebase_storage_bucket}, name="agriscan")
    return {
        "repo": FirestoreRepository(firestore.client(fb_app)),
        "storage": storage.FirebaseStorage(fb_app, settings.firebase_storage_bucket),
        "verifier": auth.FirebaseTokenVerifier(fb_app),
        "accounts": auth.FirebaseAccountAdmin(fb_app),
        "messenger": messaging.FcmMessenger(fb_app),
    }


def _memory_parts(settings: Settings) -> dict:
    accounts = auth.FakeAccountAdmin()
    return {
        "repo": MemoryRepository(),
        "storage": storage.LocalFileStorage(settings.local_storage_dir, settings.public_base_url),
        "verifier": auth.DevTokenVerifier(accounts),
        "accounts": accounts,
        "messenger": messaging.FakeMessenger(),
    }


def build_container(settings: Settings, **overrides: Any) -> Container:
    parts = _firebase_parts(settings) if settings.mode == "firebase" else _memory_parts(settings)
    parts.update({
        "weather": (weather.FakeWeatherClient() if settings.weather_provider == "fake"
                    else weather.OpenMeteoClient(settings.weather_base_url)),
        "clock": Clock(),
    })
    for name in ("classifier", "segmenter", "risk_model"):
        if name not in overrides:
            parts[name] = {
                "classifier": lambda: load_classifier(settings.classifier_model_path,
                                                      settings.classifier_labels_path),
                "segmenter": ColourSegmenter,
                "risk_model": RuleSpreadRiskModel,
            }[name]()
    parts.update(overrides)
    if isinstance(parts["verifier"], auth.DevTokenVerifier) and settings.mode == "firebase":
        raise RuntimeError("Development tokens must never be accepted in firebase mode")

    p = parts
    users = UserService(p["repo"], p["accounts"], settings.admin_emails)
    farms = FarmService(p["repo"])
    kb = KnowledgeBaseService(p["repo"])
    forecast = ForecastService(p["repo"], p["weather"], p["risk_model"], p["messenger"],
                               farms, p["clock"], settings)
    scans = ScanService(p["repo"], p["storage"], p["classifier"], p["segmenter"], kb, farms,
                        forecast, p["clock"], settings)
    reports = ReportService(p["repo"], p["storage"], scans, kb, forecast, p["clock"])
    dashboard = DashboardService(p["repo"], farms, forecast, p["clock"])
    return Container(settings=settings, users=users, farms=farms, kb=kb, forecast=forecast,
                     scans=scans, reports=reports, dashboard=dashboard, **p)
