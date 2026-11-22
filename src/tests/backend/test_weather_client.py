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
