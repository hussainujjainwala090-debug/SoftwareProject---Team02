"""External weather service client (FR-14).

Open-Meteo is used because it is free and needs no API key, so no secret is
required. Any provider that returns temperature, humidity and rainfall can be
swapped in behind the WeatherClient interface.
"""
from dataclasses import dataclass
from typing import Protocol

import httpx


class WeatherUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class HourlyWeather:
    temperature: float  # degrees C
    humidity: float  # relative humidity, %
    rainfall: float  # mm in that hour


@dataclass(frozen=True)
class WeatherReading:
    temperature: float  # degrees C
    humidity: float  # relative humidity, %
    rainfall: float  # mm in the current hour
    forecast: tuple[HourlyWeather, ...] = ()  # next FORECAST_HOURS hours (FR-14)


FORECAST_HOURS = 24


class WeatherClient(Protocol):
    def fetch(self, latitude: float, longitude: float) -> WeatherReading: ...


class OpenMeteoClient:
    def __init__(self, base_url: str, timeout_s: float = 5.0) -> None:
        self._url = base_url
        self._timeout = timeout_s

    def fetch(self, latitude: float, longitude: float) -> WeatherReading:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation",
            "forecast_hours": FORECAST_HOURS,
        }
        try:
            resp = httpx.get(self._url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            body = resp.json()
            cur = body["current"]
            return WeatherReading(
                temperature=float(cur["temperature_2m"]),
                humidity=float(cur["relative_humidity_2m"]),
                rainfall=float(cur["precipitation"]),
                forecast=_hourly(body.get("hourly")),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise WeatherUnavailableError(str(exc)) from exc


def _hourly(hourly: dict | None) -> tuple[HourlyWeather, ...]:
    """Parse the hourly forecast. A missing or broken forecast does not make the
    current weather unavailable; it is just left out."""
    try:
        rows = zip(hourly["temperature_2m"], hourly["relative_humidity_2m"],
                   hourly["precipitation"], strict=True)
        return tuple(HourlyWeather(float(t), float(h), float(r))
                     for t, h, r in rows)[:FORECAST_HOURS]
    except (KeyError, TypeError, ValueError):
        return ()


class FakeWeatherClient:
    """Returns a fixed reading; set available=False to simulate an outage."""

    def __init__(self, reading: WeatherReading | None = None) -> None:
        self.reading = reading or WeatherReading(temperature=34.0, humidity=78.0, rainfall=0.0)
        self.available = True
        self.calls = 0

    def fetch(self, latitude: float, longitude: float) -> WeatherReading:
        self.calls += 1
        if not self.available:
            raise WeatherUnavailableError("fake outage")
        return self.reading
