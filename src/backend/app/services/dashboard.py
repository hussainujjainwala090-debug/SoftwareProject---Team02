"""Dashboard (FR-13; UI-6) and model monitoring from feedback (FR-18; UI-8 Reports tab)."""
from collections import Counter, defaultdict
from datetime import timedelta

from app.clock import Clock, iso_week, to_iso
from app.repository import DIAGNOSES, DISEASES, FEEDBACK, SCANS, Repository
from app.services.farms import FarmService
from app.services.forecast import ForecastService

WEEKS = 4
TOP_DISEASES = 5


class DashboardService:
    def __init__(self, repo: Repository, farms: FarmService, forecast: ForecastService,
                 clock: Clock) -> None:
        self.repo = repo
        self.farms = farms
        self.forecast = forecast
        self.clock = clock

    def farm_dashboard(self, user: dict, farm_id: str) -> dict:
        farm = self.farms.get_visible(user, farm_id)
        now = self.clock.now()
        weeks = [iso_week(to_iso(now - timedelta(weeks=i))) for i in range(WEEKS - 1, -1, -1)]

        per_week: dict[str, list] = {w: [] for w in weeks}
        disease_counts: Counter[str] = Counter()
        uncertain = 0
        scans = self.repo.find(SCANS, farm_id=farm_id)
        for scan in scans:
            diagnosis = self.repo.get(DIAGNOSES, scan["scan_id"])
            if diagnosis is None:
                continue
            week = iso_week(scan["captured_at"])
            if week in per_week:
                per_week[week].append(diagnosis)
            if diagnosis["status"] == "uncertain":
                uncertain += 1
            elif diagnosis["disease_id"]:
                disease_counts[diagnosis["disease_id"]] += 1

        def avg_pct(diagnoses: list) -> float | None:
            values = [d["affected_area_pct"] for d in diagnoses
                      if d["status"] == "confirmed" and d["disease_id"]]
            return round(sum(values) / len(values), 1) if values else None

        names = {d["disease_id"]: d["name"] for d in self.repo.find(DISEASES)}
        return {
            "farm_id": farm_id,
            "total_scans": len(scans),
            "diseases_found": len(disease_counts),
            "uncertain": uncertain,
            "scans_per_week": [{"week": w, "scans": len(per_week[w]),
                                "avg_affected_area_pct": avg_pct(per_week[w])} for w in weeks],
            "common_diseases": [{"disease": names.get(d, "unknown"), "count": c}
                                for d, c in disease_counts.most_common(TOP_DISEASES)],
            "climate_alert": self.forecast.farm_risk(farm),
        }

    def model_accuracy(self) -> dict:
        """Share of diagnoses that farmers marked correct, per ISO week of the scan."""
        by_week: dict[str, list[bool]] = defaultdict(list)
        for fb in self.repo.find(FEEDBACK):
            scan = self.repo.get(SCANS, fb["diagnosis_id"])
            if scan:
                by_week[iso_week(scan["captured_at"])].append(fb["correct"])
        weeks = [{"week": w, "feedback": len(v), "correct": sum(v),
                  "accuracy": round(sum(v) / len(v), 3)} for w, v in sorted(by_week.items())]
        total = sum(w["feedback"] for w in weeks)
        correct = sum(w["correct"] for w in weeks)
        return {"total_feedback": total,
                "overall_accuracy": round(correct / total, 3) if total else None,
                "weeks": weeks}
