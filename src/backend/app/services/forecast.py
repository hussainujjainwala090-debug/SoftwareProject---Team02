"""Forecast and alert service (FR-08, FR-11, FR-14, NFR-09; SD-2).

Weather rule:
  1. A WeatherRecord for the location younger than weather_refresh_minutes is reused.
  2. Otherwise the external service is called and a new WeatherRecord is stored.
  3. If the service fails, the newest record no older than weather_cache_max_hours
     (6 h) is used with a notice.
  4. If there is none, weather and spread risk are shown as unavailable.

Forecast (FR-14): the next 24 hours come with each fetch. WeatherRecords has no
forecast columns (DB-1), so the forecast is kept in memory next to its record:
it is shown while that record is used and is gone after a restart. Climate
alerts (FR-11) use the worst hour of the forecast as well as the current
weather.
"""
import logging
from datetime import timedelta

from app.adapters.messaging import Messenger
from app.adapters.weather import HourlyWeather, WeatherClient, WeatherUnavailableError
from app.clock import Clock, parse_iso, to_iso
from app.config import Settings
from app.ml import SpreadRiskModel
from app.repository import FARMS, USERS, WEATHER_RECORDS, Repository, new_id
from app.services.farms import FarmService

log = logging.getLogger(__name__)
LEVEL_RANK = {"low": 0, "medium": 1, "high": 2}


def _round(value: float) -> float:
    # About 1 km, so nearby requests share one cached record.
    return round(value, 2)


class ForecastService:
    def __init__(self, repo: Repository, weather: WeatherClient, risk_model: SpreadRiskModel,
                 messenger: Messenger, farms: FarmService, clock: Clock, settings: Settings) -> None:
        self.repo = repo
        self.weather = weather
        self.risk_model = risk_model
        self.messenger = messenger
        self.farms = farms
        self.clock = clock
        self.settings = settings
        self._forecasts: dict[str, tuple[HourlyWeather, ...]] = {}  # weather_id -> hours

    # ------------------------------------------------------------ weather ----
    def _out(self, record: dict, notice: str | None = None) -> dict:
        hours = self._forecasts.get(record["weather_id"])
        forecast = {
            "hours": len(hours),
            "max_temperature": max(h.temperature for h in hours),
            "max_humidity": max(h.humidity for h in hours),
            "total_rainfall": round(sum(h.rainfall for h in hours), 1),
        } if hours else None
        return {"available": True, "notice": notice, "forecast": forecast, **{k: record[k] for k in (
            "weather_id", "temperature", "humidity", "rainfall", "fetched_at")}}

    def current_weather(self, latitude: float, longitude: float) -> dict:
        lat, lon = _round(latitude), _round(longitude)
        now = self.clock.now()
        records = sorted(self.repo.find(WEATHER_RECORDS, latitude=lat, longitude=lon),
                         key=lambda r: r["fetched_at"], reverse=True)
        latest = records[0] if records else None
        age = now - parse_iso(latest["fetched_at"]) if latest else None

        if latest and age <= timedelta(minutes=self.settings.weather_refresh_minutes):
            return self._out(latest)
        try:
            reading = self.weather.fetch(lat, lon)
        except WeatherUnavailableError as exc:
            log.warning("Weather service unavailable: %s", exc)
            if latest and age <= timedelta(hours=self.settings.weather_cache_max_hours):
                hours = age.total_seconds() / 3600
                return self._out(latest, notice=(
                    f"Weather service unavailable. Showing data from {hours:.1f} hours ago."))
            return {"available": False, "notice": (
                "Weather data unavailable: the weather service cannot be reached and no data "
                f"from the last {self.settings.weather_cache_max_hours} hours is stored.")}
        record = {
            "weather_id": new_id(), "latitude": lat, "longitude": lon,
            "temperature": reading.temperature, "humidity": reading.humidity,
            "rainfall": reading.rainfall, "fetched_at": to_iso(now),
        }
        self.repo.create(WEATHER_RECORDS, record["weather_id"], record)
        if reading.forecast:
            self._forecasts[record["weather_id"]] = reading.forecast
        return self._out(record)

    def weather_by_id(self, weather_id: str | None) -> dict | None:
        record = self.repo.get(WEATHER_RECORDS, weather_id) if weather_id else None
        return self._out(record) if record else None

    # --------------------------------------------------------- spread risk ----
    def risk(self, disease: str | None, crop: str, severity_level: str | None,
             weather: dict) -> tuple[str | None, str]:
        if not weather["available"]:
            return None, "Spread risk unavailable because there is no recent weather data."
        r = self.risk_model.predict(disease, crop, severity_level,
                                    weather["temperature"], weather["humidity"], weather["rainfall"])
        return r.level, r.explanation

    def farm_risk(self, farm: dict) -> dict:
        """Spread risk for the farm's crops now and in the next 24 hours
        (dashboard alert card and push alerts, FR-11)."""
        weather = self.current_weather(farm["latitude"], farm["longitude"])
        hours = self._forecasts.get(weather.get("weather_id") or "", ())
        best: tuple[str | None, str] = (None, "No crops registered for this farm.")
        for crop in self.farms.crops_of(farm["farm_id"]):
            level, text = self.risk(None, crop, None, weather)
            if level is None:
                best = (None, text)
                break
            for hour in hours:
                r = self.risk_model.predict(None, crop, None, hour.temperature, hour.humidity,
                                            hour.rainfall)
                if LEVEL_RANK[r.level] > LEVEL_RANK[level]:
                    level, text = r.level, f"In the next 24 hours: {r.explanation}"
            if best[0] is None or LEVEL_RANK[level] > LEVEL_RANK[best[0]]:
                best = (level, text)
        return {"spread_risk": best[0], "explanation": best[1], "weather": weather}

    # -------------------------------------------------------------- alerts ----
    def check_alerts(self) -> list[dict]:
        """Check every farm and push an alert when the risk is high (FR-11)."""
        results = []
        for farm in self.repo.find(FARMS):
            risk = self.farm_risk(farm)
            sent = False
            if risk["spread_risk"] == "high":
                owner = self.repo.get(USERS, farm["owner_id"])
                if owner and owner.get("fcm_token"):
                    try:
                        self.messenger.send(
                            owner["fcm_token"], f"Climate alert: {farm['name']}",
                            risk["explanation"],
                            {"farm_id": farm["farm_id"], "spread_risk": "high"})
                        sent = True
                    except Exception as exc:  # one failed push must not stop the others
                        log.warning("Push to farm %s failed: %s", farm["farm_id"], exc)
            results.append({"farm_id": farm["farm_id"], "spread_risk": risk["spread_risk"],
                            "explanation": risk["explanation"], "sent": sent})
        return results
