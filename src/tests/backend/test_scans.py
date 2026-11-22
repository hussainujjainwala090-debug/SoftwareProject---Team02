"""TC-03 to TC-07, TC-09, TC-10, TC-12: the scan and diagnosis workflow (SD-1)."""
import pytest

from app.ml import Prediction
from conftest import register
from images import leaf_jpeg, leaf_png

API = "/api/v1"


def upload(client, headers, farm, image=None, crop="tomato", **form):
    return client.post(f"{API}/scans", headers=headers,
                       data={"farm_id": farm["farm_id"], "crop_type": crop, **form},
                       files={"image": ("leaf.jpg", image or leaf_jpeg(), "image/jpeg")})


def test_confident_scan_gives_full_diagnosis(client, farmer, farm):
    resp = upload(client, farmer, farm)
    assert resp.status_code == 201, resp.text
    d = resp.json()
    assert d["status"] == "confirmed" and d["label"] == "Tomato early blight"
    assert d["confidence"] == 0.91
    assert 10 <= d["affected_area_pct"] <= 25 and d["severity_level"] in ("low", "medium")
    assert d["overlay_url"].startswith("http://testserver/files/overlays/")
    assert {t["type"] for t in d["treatments"]} == {"organic", "chemical", "preventive"}
    assert all(t["safety_warning"] for t in d["treatments"])
    assert d["weather"]["available"] and d["spread_risk"] in ("low", "medium", "high")
    assert d["spread_risk_explanation"]


def test_stored_images_can_be_opened(client, farmer, farm):
    d = upload(client, farmer, farm).json()
    for url in (d["image_url"], d["overlay_url"]):
        assert client.get(url.removeprefix("http://testserver")).status_code == 200


def test_low_confidence_is_uncertain_without_segmentation(client, farmer, farm, container):
    container.classifier.prediction = Prediction("Tomato early blight", "tomato", 0.55)
    d = upload(client, farmer, farm).json()
    assert d["status"] == "uncertain" and d["label"] == "Uncertain"
    assert d["disease_id"] is None and d["overlay_url"] is None and d["severity_level"] is None
    assert "agronomist" in d["advice"] and "Retake" in d["advice"]


def test_threshold_boundary_counts_as_confident(client, farmer, farm, container):
    container.classifier.prediction = Prediction("Tomato early blight", "tomato", 0.70)
    assert upload(client, farmer, farm).json()["status"] == "confirmed"


@pytest.mark.parametrize("prediction", [
    Prediction("Tomato early blight", "pepper", 0.95),   # model sees another crop
    Prediction("Unknown blight", "tomato", 0.95),         # label not in knowledge base
    Prediction(None, None, 0.0),                          # no model installed
])
def test_unusable_predictions_are_uncertain(client, farmer, farm, container, prediction):
    container.classifier.prediction = prediction
    assert upload(client, farmer, farm).json()["status"] == "uncertain"


def test_healthy_leaf(client, farmer, farm, container):
    container.classifier.prediction = Prediction("healthy", "tomato", 0.97)
    d = upload(client, farmer, farm, image=leaf_jpeg(lesion_radius=0)).json()
    assert d["status"] == "confirmed" and d["label"] == "Healthy" and d["affected_area_pct"] == 0.0


def test_blurry_photo_asks_for_retake(client, farmer, farm):
    resp = upload(client, farmer, farm, image=leaf_png(blur=4))
    assert resp.status_code == 422 and "blurry" in resp.json()["detail"]


def test_image_over_1mb_is_rejected(client, farmer, farm):
    assert upload(client, farmer, farm, image=b"\xff" * 1_000_001).status_code == 413


def test_crop_must_belong_to_farm(client, farmer, farm):
    assert upload(client, farmer, farm, crop="cucumber").status_code == 422


def test_only_farm_owner_can_scan(client, farm):
    other = register(client, "farmer2")
    assert upload(client, other, farm).status_code == 403


def test_offline_reupload_with_same_scan_id_is_not_duplicated(client, farmer, farm, container):
    first = upload(client, farmer, farm, scan_id="offline-0001", captured_at="2026-11-20T08:00:00Z")
    again = upload(client, farmer, farm, scan_id="offline-0001", captured_at="2026-11-20T08:00:00Z")
    assert first.status_code == again.status_code == 201
    assert first.json()["diagnosis_id"] == again.json()["diagnosis_id"] == "offline-0001"
    assert first.json()["captured_at"] == "2026-11-20T08:00:00+00:00"
    assert len(container.repo.find("scans")) == 1 and len(container.repo.find("diagnoses")) == 1


def test_scan_id_of_another_user_is_a_conflict(client, farmer, farm):
    upload(client, farmer, farm, scan_id="shared-0001")
    other = register(client, "farmer2", role="farm_owner")
    other_farm = client.post(f"{API}/farms", headers=other, json={
        "name": "B", "latitude": 1, "longitude": 1, "crops": ["tomato"]}).json()
    assert upload(client, other, other_farm, scan_id="shared-0001").status_code == 409


@pytest.mark.parametrize("form", [{"scan_id": "bad id!"}, {"captured_at": "yesterday"},
                                  {"captured_at": "2030-01-01T00:00:00Z"}])
def test_bad_scan_metadata_is_rejected(client, farmer, farm, form):
    assert upload(client, farmer, farm, **form).status_code == 422


def test_history_lists_and_filters(client, farmer, farm, container):
    upload(client, farmer, farm, captured_at="2026-11-15T10:00:00Z")
    container.classifier.prediction = Prediction(None, None, 0.2)
    upload(client, farmer, farm, captured_at="2026-11-19T10:00:00Z")

    def ids(**params):
        return [d["label"] for d in client.get(f"{API}/diagnoses", params=params, headers=farmer).json()]

    assert ids() == ["Uncertain", "Tomato early blight"]  # newest first
    assert ids(status="confirmed") == ["Tomato early blight"]
    assert ids(status="uncertain") == ["Uncertain"]
    assert ids(q="blight") == ["Tomato early blight"]
    assert ids(date_from="2026-11-16") == ["Uncertain"]
    assert ids(crop="date_palm") == []


def test_other_farmers_cannot_open_a_diagnosis(client, farmer, farm):
    d = upload(client, farmer, farm).json()
    other = register(client, "farmer2")
    assert client.get(f"{API}/diagnoses/{d['diagnosis_id']}", headers=other).status_code == 403
    assert client.get(f"{API}/diagnoses", headers=other).json() == []


def test_agronomist_sees_all_diagnoses(client, farmer, farm, agronomist):
    upload(client, farmer, farm)
    assert len(client.get(f"{API}/diagnoses", headers=agronomist).json()) == 1


def test_archived_disease_is_not_used_for_new_scans_but_history_keeps_it(client, farmer, farm, admin):
    first = upload(client, farmer, farm).json()
    client.post(f"{API}/admin/diseases/{first['disease_id']}/archive", headers=admin)
    assert upload(client, farmer, farm).json()["status"] == "uncertain"
    old = client.get(f"{API}/diagnoses/{first['diagnosis_id']}", headers=farmer).json()
    assert old["label"] == "Tomato early blight" and old["treatments"]
