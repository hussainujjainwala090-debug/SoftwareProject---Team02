"""TC-08 / TC-14 and NFR-09: weather, cache and spread risk (SD-2 alt fragment)."""
from datetime import timedelta

from app.adapters.weather import WeatherReading
from test_scans import upload

API = "/api/v1"


def weather(client, headers, farm):
    return client.get(f"{API}/farms/{farm['farm_id']}/weather", headers=headers).json()


def test_live_weather_is_fetched_and_stored(client, farmer, farm, container):
    w = weather(client, farmer, farm)
    assert w["available"] and w["notice"] is None
    assert (w["temperature"], w["humidity"], w["rainfall"]) == (34.0, 78.0, 0.0)
    assert len(container.repo.find("weather_records")) == 1


def test_recent_record_is_reused(client, farmer, farm, container):
    weather(client, farmer, farm)
    container.clock.at += timedelta(minutes=20)
    weather(client, farmer, farm)
    assert container.weather.calls == 1


def test_outage_uses_cache_up_to_6_hours_with_notice(client, farmer, farm, container):
    weather(client, farmer, farm)
    container.weather.available = False
    container.clock.at += timedelta(hours=5, minutes=59)
    w = weather(client, farmer, farm)
    assert w["available"] and "unavailable" in w["notice"] and w["temperature"] == 34.0


def test_outage_with_stale_cache_shows_unavailable(client, farmer, farm, container):
    weather(client, farmer, farm)
    container.weather.available = False
    container.clock.at += timedelta(hours=6, minutes=1)
    w = weather(client, farmer, farm)
    assert w["available"] is False and w["temperature"] is None


def test_scan_during_outage_without_cache_has_no_spread_risk(client, farmer, farm, container):
    container.weather.available = False
    d = upload(client, farmer, farm).json()
    assert d["status"] == "confirmed" and d["spread_risk"] is None and d["weather"] is None


def test_spread_risk_endpoint_recalculates_with_new_weather(client, farmer, farm, container):
    d = upload(client, farmer, farm).json()
    container.weather.reading = WeatherReading(temperature=24, humidity=92, rainfall=8)
    container.clock.at += timedelta(hours=1)
    r = client.get(f"{API}/diagnoses/{d['diagnosis_id']}/spread-risk", headers=farmer).json()
    assert r["spread_risk"] == "high" and "very humid" in r["explanation"]
    again = client.get(f"{API}/diagnoses/{d['diagnosis_id']}", headers=farmer).json()
    assert again["spread_risk"] == "high"


def test_spread_risk_unavailable_message(client, farmer, farm, container):
    d = upload(client, farmer, farm).json()
    container.weather.available = False
    container.clock.at += timedelta(hours=7)
    r = client.get(f"{API}/diagnoses/{d['diagnosis_id']}/spread-risk", headers=farmer).json()
    assert r["spread_risk"] is None and "unavailable" in r["explanation"]
