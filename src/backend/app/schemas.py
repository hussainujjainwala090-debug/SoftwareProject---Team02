"""Request and response models. Field names follow the data design (Table DB-1)."""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    farmer = "farmer"
    farm_owner = "farm_owner"
    agronomist = "agronomist"
    admin = "admin"


class Crop(str, Enum):
    # Predefined crop list from UI-2 (FR-02).
    date_palm = "date_palm"
    tomato = "tomato"
    cucumber = "cucumber"
    pepper = "pepper"
    other = "other"


class Status(str, Enum):
    confirmed = "confirmed"
    uncertain = "uncertain"


class Level(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TreatmentType(str, Enum):
    organic = "organic"
    chemical = "chemical"
    preventive = "preventive"


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ------------------------------------------------------------------ users ----
class RegisterIn(_In):
    name: str = Field(min_length=1, max_length=100)
    role: Role = Role.farmer


class FcmTokenIn(_In):
    fcm_token: str = Field(min_length=1, max_length=4096)


class AdminCreateUserIn(_In):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)
    role: Role


class RoleIn(_In):
    role: Role


class UserOut(BaseModel):
    user_id: str
    name: str
    email: str
    role: Role
    disabled: bool = False


# ------------------------------------------------------------------ farms ----
class FarmIn(_In):
    name: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    crops: list[Crop] = Field(min_length=1)


class FarmOut(BaseModel):
    farm_id: str
    owner_id: str
    name: str
    latitude: float
    longitude: float
    crops: list[Crop]


# --------------------------------------------------------- knowledge base ----
class TreatmentIn(_In):
    type: TreatmentType
    guidance: str = Field(min_length=1, max_length=2000)
    safety_warning: str = Field(min_length=1, max_length=1000)


class TreatmentOut(TreatmentIn):
    model_config = ConfigDict(extra="ignore")
    treatment_id: str
    disease_id: str


class DiseaseIn(_In):
    name: str = Field(min_length=1, max_length=120)
    crop_type: Crop
    symptoms: str | None = Field(default=None, max_length=2000)
    treatments: list[TreatmentIn] = Field(default_factory=list)


class DiseaseOut(BaseModel):
    disease_id: str
    name: str
    crop_type: Crop
    symptoms: str | None
    archived: bool
    treatments: list[TreatmentOut] = []


# ---------------------------------------------------------------- weather ----
class WeatherOut(BaseModel):
    available: bool
    notice: str | None = None
    weather_id: str | None = None
    temperature: float | None = None
    humidity: float | None = None
    rainfall: float | None = None
    fetched_at: str | None = None


class SpreadRiskOut(BaseModel):
    spread_risk: Level | None
    explanation: str
    weather: WeatherOut


# -------------------------------------------------------------- diagnoses ----
class FeedbackIn(_In):
    correct: bool
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(FeedbackIn):
    model_config = ConfigDict(extra="ignore")
    feedback_id: str
    diagnosis_id: str


class ReviewIn(_In):
    """Agronomist decision. disease_id=None confirms the leaf as healthy."""

    disease_id: str | None


class DiagnosisOut(BaseModel):
    diagnosis_id: str
    scan_id: str
    farm_id: str
    user_id: str
    crop_type: Crop
    captured_at: str
    label: str  # disease name, "Healthy" or "Uncertain"
    status: Status
    disease_id: str | None
    confidence: float
    affected_area_pct: float | None
    severity_level: Level | None
    spread_risk: Level | None
    spread_risk_explanation: str | None = None
    image_url: str | None
    overlay_url: str | None
    reviewed_by: str | None
    advice: str | None = None
    weather: WeatherOut | None = None
    treatments: list[TreatmentOut] = []
    feedback: FeedbackOut | None = None


class ReportOut(BaseModel):
    report_id: str
    diagnosis_id: str
    pdf_url: str
    created_at: str


# -------------------------------------------------------------- dashboard ----
class WeekCount(BaseModel):
    week: str  # ISO week, e.g. "2026-W47"
    scans: int
    avg_affected_area_pct: float | None


class DiseaseCount(BaseModel):
    disease: str
    count: int


class DashboardOut(BaseModel):
    farm_id: str
    total_scans: int
    diseases_found: int
    uncertain: int
    scans_per_week: list[WeekCount]
    common_diseases: list[DiseaseCount]
    climate_alert: SpreadRiskOut


class AccuracyWeek(BaseModel):
    week: str
    feedback: int
    correct: int
    accuracy: float


class AccuracyOut(BaseModel):
    total_feedback: int
    overall_accuracy: float | None
    weeks: list[AccuracyWeek]


class AlertOut(BaseModel):
    farm_id: str
    spread_risk: Level | None
    explanation: str
    sent: bool
