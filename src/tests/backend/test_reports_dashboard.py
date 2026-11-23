"""TC-15 (PDF report), TC-13 (dashboard) and TC-11 (climate alerts)."""
from app.adapters.weather import HourlyWeather, WeatherReading
from app.ml import Prediction
from conftest import register
from test_scans import upload

API = "/api/v1"


def test_pdf_report_is_generated_stored_and_shareable(client, farmer, farm):
    d = upload(client, farmer, farm).json()
    resp = client.post(f"{API}/diagnoses/{d['diagnosis_id']}/reports", headers=farmer)
    assert resp.status_code == 201
    report = resp.json()
    pdf = client.get(report["pdf_url"].removeprefix("http://testserver"))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    listed = client.get(f"{API}/diagnoses/{d['diagnosis_id']}/reports", headers=farmer).json()
    assert [r["report_id"] for r in listed] == [report["report_id"]]


def test_report_for_uncertain_diagnosis(client, farmer, farm, container):
    container.classifier.prediction = Prediction(None, None, 0.1)
    d = upload(client, farmer, farm).json()
    assert client.post(f"{API}/diagnoses/{d['diagnosis_id']}/reports", headers=farmer).status_code == 201


def test_report_text_contains_ui7_sections(container, client, farmer, farm):
    d = upload(client, farmer, farm).json()
    diagnosis, scan, farm_doc = container.scans.load(container.users.by_firebase_uid("farmer1"),
                                                     d["diagnosis_id"])
    pdf = container.reports.build_pdf(diagnosis, scan, farm_doc, "2026-11-21T10:00:00+00:00")
    assert pdf.startswith(b"%PDF") and len(pdf) > 5_000


def test_other_users_cannot_create_reports(client, farmer, farm):
    d = upload(client, farmer, farm).json()
    other = register(client, "farmer2")
    assert client.post(f"{API}/diagnoses/{d['diagnosis_id']}/reports", headers=other).status_code == 403


def test_dashboard_counts(client, farmer, farm, container):
    upload(client, farmer, farm, captured_at="2026-11-20T10:00:00Z")
    upload(client, farmer, farm, captured_at="2026-11-10T10:00:00Z")
    container.classifier.prediction = Prediction(None, None, 0.1)
    upload(client, farmer, farm)
    dash = client.get(f"{API}/farms/{farm['farm_id']}/dashboard", headers=farmer).json()
    assert dash["total_scans"] == 3 and dash["diseases_found"] == 1 and dash["uncertain"] == 1
    assert dash["common_diseases"] == [{"disease": "Tomato early blight", "count": 2}]
    weeks = {w["week"]: w["scans"] for w in dash["scans_per_week"]}
    assert weeks == {"2026-W44": 0, "2026-W45": 0, "2026-W46": 1, "2026-W47": 2}
    assert dash["climate_alert"]["weather"]["available"]


def test_climate_alert_is_pushed_when_risk_is_high(client, farmer, farm, admin, container):
    client.put(f"{API}/users/me/fcm-token", json={"fcm_token": "phone-1"}, headers=farmer)
    container.weather.reading = WeatherReading(temperature=24, humidity=92, rainfall=7)
    results = client.post(f"{API}/admin/alerts/check", headers=admin).json()
    assert results == [{"farm_id": farm["farm_id"], "spread_risk": "high",
                        "explanation": results[0]["explanation"], "sent": True}]
    assert container.messenger.sent[0]["token"] == "phone-1"


def test_no_alert_in_dry_weather(client, farmer, farm, admin, container):
    client.put(f"{API}/users/me/fcm-token", json={"fcm_token": "phone-1"}, headers=farmer)
    container.weather.reading = WeatherReading(temperature=40, humidity=15, rainfall=0)
    results = client.post(f"{API}/admin/alerts/check", headers=admin).json()
    assert results[0]["sent"] is False and container.messenger.sent == []


def rainy_night():
    # Dry and hot now, but humid and rainy later today.
    return WeatherReading(temperature=40, humidity=15, rainfall=0, forecast=(
        HourlyWeather(38, 20, 0), HourlyWeather(24, 92, 6), HourlyWeather(22, 95, 3)))


def test_farm_weather_includes_24_hour_forecast(client, farmer, farm, container):
    container.weather.reading = rainy_night()
    w = client.get(f"{API}/farms/{farm['farm_id']}/weather", headers=farmer).json()
    assert w["forecast"] == {"hours": 3, "max_temperature": 38.0, "max_humidity": 95.0,
                             "total_rainfall": 9.0}


def test_alert_is_pushed_for_risky_forecast(client, farmer, farm, admin, container):
    client.put(f"{API}/users/me/fcm-token", json={"fcm_token": "phone-1"}, headers=farmer)
    container.weather.reading = rainy_night()
    results = client.post(f"{API}/admin/alerts/check", headers=admin).json()
    assert results[0]["spread_risk"] == "high" and results[0]["sent"] is True
    assert results[0]["explanation"].startswith("In the next 24 hours:")
