"""TC-14: Open-Meteo client parsing and failure handling (FR-14), without network."""
import httpx
import pytest

from app.adapters.weather import OpenMeteoClient, WeatherUnavailableError

URL = "https://api.open-meteo.com/v1/forecast"


def fake_get(status=200, body=None, exc=None):
    def _get(url, params, timeout):
        if exc:
            raise exc
        assert params["latitude"] == 24.21 and "relative_humidity_2m" in params["current"]
        assert "precipitation" in params["hourly"] and params["forecast_hours"] == 24
        return httpx.Response(status, json=body, request=httpx.Request("GET", url))
    return _get


def test_parses_current_weather(monkeypatch):
    body = {"current": {"temperature_2m": 33.4, "relative_humidity_2m": 61, "precipitation": 0.2}}
    monkeypatch.setattr(httpx, "get", fake_get(body=body))
    r = OpenMeteoClient(URL).fetch(24.21, 55.74)
    assert (r.temperature, r.humidity, r.rainfall) == (33.4, 61.0, 0.2)


@pytest.mark.parametrize("kwargs", [
    {"status": 503, "body": {}},
    {"body": {"unexpected": True}},
    {"exc": httpx.ConnectTimeout("timeout")},
])
def test_errors_become_weather_unavailable(monkeypatch, kwargs):
    monkeypatch.setattr(httpx, "get", fake_get(**kwargs))
    with pytest.raises(WeatherUnavailableError):
        OpenMeteoClient(URL).fetch(24.21, 55.74)


def test_parses_24_hour_forecast(monkeypatch):
    body = {"current": {"temperature_2m": 33.4, "relative_humidity_2m": 61, "precipitation": 0.2},
            "hourly": {"temperature_2m": [33, 30, 27], "relative_humidity_2m": [60, 75, 90],
                       "precipitation": [0, 0.5, 4]}}
    monkeypatch.setattr(httpx, "get", fake_get(body=body))
    r = OpenMeteoClient(URL).fetch(24.21, 55.74)
    assert [(h.temperature, h.humidity, h.rainfall) for h in r.forecast] == [
        (33.0, 60.0, 0.0), (30.0, 75.0, 0.5), (27.0, 90.0, 4.0)]


def test_broken_forecast_keeps_current_weather(monkeypatch):
    body = {"current": {"temperature_2m": 33.4, "relative_humidity_2m": 61, "precipitation": 0.2},
            "hourly": {"temperature_2m": [33], "relative_humidity_2m": [60, 75]}}
    monkeypatch.setattr(httpx, "get", fake_get(body=body))
    r = OpenMeteoClient(URL).fetch(24.21, 55.74)
    assert r.temperature == 33.4 and r.forecast == ()
