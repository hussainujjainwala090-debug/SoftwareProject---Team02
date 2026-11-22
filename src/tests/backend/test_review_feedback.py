"""TC-05 (agronomist review), TC-16 (feedback) and FR-18 accuracy monitoring."""
from app.ml import Prediction
from conftest import register
from test_scans import upload

API = "/api/v1"


def uncertain_scan(client, farmer, farm, container):
    container.classifier.prediction = Prediction(None, None, 0.3)
    return upload(client, farmer, farm).json()


def disease_id(client, headers, name):
    return next(d["disease_id"] for d in client.get(f"{API}/diseases", headers=headers).json()
                if d["name"] == name)


def test_agronomist_confirms_uncertain_diagnosis(client, farmer, farm, agronomist, container):
    d = uncertain_scan(client, farmer, farm, container)
    did = disease_id(client, agronomist, "Tomato leaf mold")
    resp = client.post(f"{API}/diagnoses/{d['diagnosis_id']}/review", json={"disease_id": did},
                       headers=agronomist)
    assert resp.status_code == 200, resp.text
    r = resp.json()
    assert r["status"] == "confirmed" and r["label"] == "Tomato leaf mold"
    assert r["reviewed_by"] and r["severity_level"] and r["overlay_url"]
    assert r["treatments"]


def test_agronomist_can_mark_healthy(client, farmer, farm, agronomist, container):
    d = uncertain_scan(client, farmer, farm, container)
    r = client.post(f"{API}/diagnoses/{d['diagnosis_id']}/review", json={"disease_id": None},
                    headers=agronomist).json()
    assert r["label"] == "Healthy" and r["status"] == "confirmed"


def test_review_rejects_wrong_crop_and_archived(client, farmer, farm, agronomist, admin, container):
    d = uncertain_scan(client, farmer, farm, container)
    url = f"{API}/diagnoses/{d['diagnosis_id']}/review"
    pepper = disease_id(client, admin, "Pepper bacterial spot")
    assert client.post(url, json={"disease_id": pepper}, headers=agronomist).status_code == 422
    mold = disease_id(client, admin, "Tomato leaf mold")
    client.post(f"{API}/admin/diseases/{mold}/archive", headers=admin)
    assert client.post(url, json={"disease_id": mold}, headers=agronomist).status_code == 422


def test_farmers_cannot_review(client, farmer, farm, container):
    d = uncertain_scan(client, farmer, farm, container)
    resp = client.post(f"{API}/diagnoses/{d['diagnosis_id']}/review", json={"disease_id": None},
                       headers=farmer)
    assert resp.status_code == 403


def test_feedback_is_stored_once(client, farmer, farm):
    d = upload(client, farmer, farm).json()
    url = f"{API}/diagnoses/{d['diagnosis_id']}/feedback"
    resp = client.post(url, json={"correct": False, "comment": "It was leaf mold"}, headers=farmer)
    assert resp.status_code == 201
    assert client.post(url, json={"correct": True}, headers=farmer).status_code == 409
    shown = client.get(f"{API}/diagnoses/{d['diagnosis_id']}", headers=farmer).json()["feedback"]
    assert shown["correct"] is False and shown["comment"] == "It was leaf mold"


def test_only_the_farmer_can_give_feedback(client, farmer, farm, agronomist):
    d = upload(client, farmer, farm).json()
    resp = client.post(f"{API}/diagnoses/{d['diagnosis_id']}/feedback", json={"correct": True},
                       headers=agronomist)
    assert resp.status_code == 403


def test_model_accuracy_from_feedback(client, farmer, farm, admin):
    for correct in (True, True, False):
        d = upload(client, farmer, farm).json()
        client.post(f"{API}/diagnoses/{d['diagnosis_id']}/feedback", json={"correct": correct},
                    headers=farmer)
    acc = client.get(f"{API}/admin/model-accuracy", headers=admin).json()
    assert acc["total_feedback"] == 3 and acc["overall_accuracy"] == 0.667
    assert acc["weeks"][0]["week"] == "2026-W47"


def test_model_accuracy_with_no_feedback(client, admin):
    assert client.get(f"{API}/admin/model-accuracy", headers=admin).json() == {
        "total_feedback": 0, "overall_accuracy": None, "weeks": []}


def test_review_of_unknown_diagnosis_is_404(client, agronomist):
    assert client.post(f"{API}/diagnoses/nope/review", json={"disease_id": None},
                       headers=agronomist).status_code == 404


def test_disabled_agronomist_cannot_review(client, farmer, farm, admin, container):
    agro = register(client, "agro2", role="agronomist")
    d = uncertain_scan(client, farmer, farm, container)
    users = client.get(f"{API}/admin/users", headers=admin).json()
    uid = next(u["user_id"] for u in users if u["email"] == "agro2@test.com")
    client.post(f"{API}/admin/users/{uid}/disable", headers=admin)
    resp = client.post(f"{API}/diagnoses/{d['diagnosis_id']}/review", json={"disease_id": None},
                       headers=agro)
    assert resp.status_code == 403
