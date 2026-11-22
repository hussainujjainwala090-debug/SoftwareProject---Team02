"""Scan service: the diagnosis workflow (FR-03 to FR-07, FR-10, FR-16; SD-1, SD-2).

SD-1: check image quality -> classify -> if confidence is below the threshold,
mark "Uncertain" (no segmentation) -> otherwise segment, rate severity, get the
spread risk and store the diagnosis.

Keys: diagnosis_id equals scan_id and feedback is stored under the diagnosis_id,
so Firestore itself refuses a second Diagnosis per Scan or a second Feedback
per Diagnosis (1:1 links in DB-1). The app may send its own scan_id: if an
offline scan is uploaded twice, the first result is returned instead of a
duplicate (NFR-08).
"""
import io
import re
from datetime import timedelta

from PIL import Image

from app import image_quality
from app.adapters.storage import Storage
from app.clock import Clock, parse_iso, to_iso
from app.config import Settings
from app.errors import Conflict, Forbidden, Invalid, NotFound, TooLarge
from app.ml import DiseaseClassifier, SeveritySegmenter
from app.repository import (DIAGNOSES, FEEDBACK, SCANS, AlreadyExistsError, Repository,
                            new_id)
from app.schemas import FeedbackIn, Role
from app.services.farms import FarmService
from app.services.forecast import ForecastService
from app.services.knowledge_base import KnowledgeBaseService

SCAN_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png")}
STAFF = {Role.agronomist.value, Role.admin.value}
UNCERTAIN_ADVICE = ("The result is uncertain. Retake the photo in good light with the leaf inside "
                    "the frame, or ask an agronomist to review it.")


class ScanService:
    def __init__(self, repo: Repository, storage: Storage, classifier: DiseaseClassifier,
                 segmenter: SeveritySegmenter, kb: KnowledgeBaseService, farms: FarmService,
                 forecast: ForecastService, clock: Clock, settings: Settings) -> None:
        self.repo = repo
        self.storage = storage
        self.classifier = classifier
        self.segmenter = segmenter
        self.kb = kb
        self.farms = farms
        self.forecast = forecast
        self.clock = clock
        self.settings = settings

    # ------------------------------------------------------------- rules ----
    def severity_level(self, pct: float) -> str:
        if pct >= self.settings.severity_high_from_pct:
            return "high"
        if pct >= self.settings.severity_medium_from_pct:
            return "medium"
        return "low"

    # ------------------------------------------------------------ submit ----
    def submit(self, user: dict, farm_id: str, crop_type: str, image: bytes,
               scan_id: str | None = None, captured_at: str | None = None) -> dict:
        farm = self.farms.get_owned(user, farm_id)
        scan_id = scan_id or new_id()
        if not SCAN_ID.match(scan_id):
            raise Invalid("scan_id must be 8-64 letters, digits, '-' or '_'")
        existing = self.repo.get(SCANS, scan_id)
        if existing:
            return self._existing(user, existing)

        if len(image) > self.settings.max_image_bytes:
            raise TooLarge(f"The image must be {self.settings.max_image_bytes // 1_000_000} MB or less")
        if crop_type not in self.farms.crops_of(farm_id):
            raise Invalid("The crop must be one of the crops of this farm")
        quality = image_quality.check(image, self.settings.blur_threshold)
        if not quality.ok:
            raise Invalid(quality.reason)
        fmt = Image.open(io.BytesIO(image)).format
        if fmt not in FORMATS:
            raise Invalid("Only JPEG and PNG images are accepted")

        now = self.clock.now()
        if captured_at:
            try:
                taken = parse_iso(captured_at)
            except ValueError as exc:
                raise Invalid("captured_at must be an ISO-8601 date and time") from exc
            if taken > now + timedelta(minutes=5):
                raise Invalid("captured_at cannot be in the future")
        else:
            taken = now

        ext, content_type = FORMATS[fmt]
        scan = {
            "scan_id": scan_id, "farm_id": farm_id, "user_id": user["user_id"],
            "crop_type": crop_type, "captured_at": to_iso(taken),
            "image_url": self.storage.upload("scans", image, ext, content_type),
        }
        try:
            self.repo.create(SCANS, scan_id, scan)
        except AlreadyExistsError:
            return self._existing(user, self.repo.get(SCANS, scan_id))
        self._store_diagnosis(scan, image, farm)
        return self.detail(user, scan_id)

    def _store_diagnosis(self, scan: dict, image: bytes, farm: dict) -> None:
        try:
            self.repo.create(DIAGNOSES, scan["scan_id"], self._diagnose(scan, image, farm))
        except AlreadyExistsError:
            pass  # a parallel retry finished first; keep its result

    def _existing(self, user: dict, scan: dict) -> dict:
        if scan["user_id"] != user["user_id"]:
            raise Conflict("This scan_id is already used")
        if self.repo.get(DIAGNOSES, scan["scan_id"]) is None:
            # The scan was saved but its diagnosis failed (e.g. a crash); the
            # app's retry from the offline queue finishes it from the stored image.
            farm = self.farms.get(scan["farm_id"])
            self._store_diagnosis(scan, self.storage.download(scan["image_url"]), farm)
        return self.detail(user, scan["scan_id"])

    def _diagnose(self, scan: dict, image: bytes, farm: dict) -> dict:
        pred = self.classifier.classify(image, scan["crop_type"])
        diagnosis = {
            "diagnosis_id": scan["scan_id"], "scan_id": scan["scan_id"], "disease_id": None,
            "weather_id": None, "reviewed_by": None,
            "confidence": round(min(max(pred.confidence, 0.0), 1.0), 4),
            "status": "uncertain", "affected_area_pct": None, "severity_level": None,
            "overlay_url": None, "spread_risk": None,
        }
        if (pred.label is None or pred.confidence < self.settings.confidence_threshold
                or (pred.crop and pred.crop != scan["crop_type"])):
            return diagnosis
        if pred.label.lower() == "healthy":
            return {**diagnosis, "status": "confirmed", "affected_area_pct": 0.0}
        disease = self.kb.find_active(pred.label, scan["crop_type"])
        if disease is None:  # label not (or no longer) in the knowledge base
            return diagnosis
        return self._complete(diagnosis, disease, image, scan, farm)

    def _complete(self, diagnosis: dict, disease: dict, image: bytes, scan: dict, farm: dict) -> dict:
        seg = self.segmenter.segment(image)
        level = self.severity_level(seg.affected_area_pct)
        weather = self.forecast.current_weather(farm["latitude"], farm["longitude"])
        risk, _ = self.forecast.risk(disease["name"], scan["crop_type"], level, weather)
        return {
            **diagnosis, "status": "confirmed", "disease_id": disease["disease_id"],
            "affected_area_pct": seg.affected_area_pct, "severity_level": level,
            "overlay_url": self.storage.upload("overlays", seg.overlay_png, "png", "image/png"),
            "weather_id": weather.get("weather_id"), "spread_risk": risk,
        }

    # ------------------------------------------------------------ reading ----
    def load(self, user: dict, diagnosis_id: str) -> tuple[dict, dict, dict]:
        diagnosis = self.repo.get(DIAGNOSES, diagnosis_id)
        if diagnosis is None:
            raise NotFound("Diagnosis not found")
        scan = self.repo.get(SCANS, diagnosis["scan_id"])
        farm = self.farms.get(scan["farm_id"])
        if not (scan["user_id"] == user["user_id"] or farm["owner_id"] == user["user_id"]
                or user["role"] in STAFF):
            raise Forbidden("You do not have access to this diagnosis")
        return diagnosis, scan, farm

    def _out(self, diagnosis: dict, scan: dict, full: bool) -> dict:
        disease = self.kb.get(diagnosis["disease_id"]) if diagnosis["disease_id"] else None
        if diagnosis["status"] == "uncertain":
            label = "Uncertain"
        else:
            label = disease["name"] if disease else "Healthy"
        out = {
            **diagnosis, "farm_id": scan["farm_id"], "user_id": scan["user_id"],
            "crop_type": scan["crop_type"], "captured_at": scan["captured_at"], "label": label,
            "image_url": self.storage.link(scan["image_url"]),
            "overlay_url": self.storage.link(diagnosis["overlay_url"]),
            "advice": UNCERTAIN_ADVICE if diagnosis["status"] == "uncertain" else None,
        }
        if full:
            weather = self.forecast.weather_by_id(diagnosis["weather_id"])
            out["weather"] = weather
            if diagnosis["spread_risk"] and weather and disease:
                out["spread_risk_explanation"] = self.forecast.risk(
                    disease["name"], scan["crop_type"], diagnosis["severity_level"], weather)[1]
            out["treatments"] = self.kb.treatments_for(disease["disease_id"]) if disease else []
            out["feedback"] = self.repo.get(FEEDBACK, diagnosis["diagnosis_id"])
        return out

    def detail(self, user: dict, diagnosis_id: str) -> dict:
        diagnosis, scan, _ = self.load(user, diagnosis_id)
        return self._out(diagnosis, scan, full=True)

    def history(self, user: dict, status: str | None = None, crop: str | None = None,
                date_from: str | None = None, date_to: str | None = None,
                q: str | None = None, farm_id: str | None = None) -> list[dict]:
        """FR-10: saved diagnoses, filtered by status, crop, date and disease name."""
        if user["role"] in STAFF:
            scans = self.repo.find(SCANS)
        else:
            own = {s["scan_id"]: s for s in self.repo.find(SCANS, user_id=user["user_id"])}
            for farm in self.repo.find("farms", owner_id=user["user_id"]):
                own.update({s["scan_id"]: s for s in self.repo.find(SCANS, farm_id=farm["farm_id"])})
            scans = list(own.values())
        results = []
        for scan in scans:
            if farm_id and scan["farm_id"] != farm_id:
                continue
            if crop and scan["crop_type"] != crop:
                continue
            day = scan["captured_at"][:10]
            if (date_from and day < date_from) or (date_to and day > date_to):
                continue
            diagnosis = self.repo.get(DIAGNOSES, scan["scan_id"])
            if diagnosis is None or (status and diagnosis["status"] != status):
                continue
            item = self._out(diagnosis, scan, full=False)
            if q and q.lower() not in item["label"].lower():
                continue
            results.append(item)
        return sorted(results, key=lambda d: d["captured_at"], reverse=True)

    # -------------------------------------------------------- spread risk ----
    def refresh_spread_risk(self, user: dict, diagnosis_id: str) -> dict:
        """SD-2 getSpreadRisk: recalculate with the current (or cached) weather."""
        diagnosis, scan, farm = self.load(user, diagnosis_id)
        weather = self.forecast.current_weather(farm["latitude"], farm["longitude"])
        if diagnosis["status"] != "confirmed" or not diagnosis["disease_id"]:
            return {"spread_risk": None, "weather": weather,
                    "explanation": "Spread risk is calculated for confirmed diseases only."}
        disease = self.kb.get(diagnosis["disease_id"])
        level, text = self.forecast.risk(disease["name"], scan["crop_type"],
                                         diagnosis["severity_level"], weather)
        if level is not None:
            self.repo.update(DIAGNOSES, diagnosis_id,
                             {"spread_risk": level, "weather_id": weather["weather_id"]})
        return {"spread_risk": level, "explanation": text, "weather": weather}

    # ------------------------------------------------------------- review ----
    def review(self, agronomist: dict, diagnosis_id: str, disease_id: str | None) -> dict:
        """An agronomist confirms or corrects a diagnosis (UC-01 extension)."""
        diagnosis, scan, farm = self.load(agronomist, diagnosis_id)
        if disease_id is None:
            diagnosis.update({"status": "confirmed", "disease_id": None, "affected_area_pct": 0.0,
                              "severity_level": None, "overlay_url": None, "spread_risk": None})
        else:
            disease = self.kb.get(disease_id)
            if disease["archived"]:
                raise Invalid("This disease is archived")
            if disease["crop_type"] != scan["crop_type"]:
                raise Invalid("This disease does not affect the scanned crop")
            image = self.storage.download(scan["image_url"])
            diagnosis = self._complete(diagnosis, disease, image, scan, farm)
        diagnosis["reviewed_by"] = agronomist["user_id"]
        self.repo.put(DIAGNOSES, diagnosis_id, diagnosis)
        return self.detail(agronomist, diagnosis_id)

    # ----------------------------------------------------------- feedback ----
    def add_feedback(self, user: dict, diagnosis_id: str, data: FeedbackIn) -> dict:
        _, scan, farm = self.load(user, diagnosis_id)
        if user["user_id"] not in (scan["user_id"], farm["owner_id"]):
            raise Forbidden("Only the farmer who took the scan can rate it")
        feedback = {"feedback_id": new_id(), "diagnosis_id": diagnosis_id,
                    "correct": data.correct, "comment": data.comment}
        try:
            return self.repo.create(FEEDBACK, diagnosis_id, feedback)
        except AlreadyExistsError as exc:
            raise Conflict("Feedback was already given for this diagnosis") from exc
