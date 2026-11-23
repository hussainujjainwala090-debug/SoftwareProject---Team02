"""TC-17: admin knowledge base (FR-09, FR-17; SD-3). Entries are archived, never deleted."""
import pytest

API = "/api/v1"
ENTRY = {
    "name": "Cucumber powdery mildew", "crop_type": "cucumber", "symptoms": "White powder on leaves",
    "treatments": [
        {"type": "organic", "guidance": "Milk spray weekly", "safety_warning": "Test on one leaf first"},
        {"type": "preventive", "guidance": "Improve airflow", "safety_warning": "None"},
    ],
}


def test_seeded_entries_are_listed_with_treatments(client, farmer):
    diseases = client.get(f"{API}/diseases", params={"crop": "tomato"}, headers=farmer).json()
    assert len(diseases) == 9
    assert all(d["treatments"] and not d["archived"] for d in diseases)


def test_admin_adds_edits_archives_and_restores(client, admin, farmer):
    created = client.post(f"{API}/admin/diseases", json=ENTRY, headers=admin)
    assert created.status_code == 201
    did = created.json()["disease_id"]

    edited = client.put(f"{API}/admin/diseases/{did}", headers=admin, json={
        **ENTRY, "symptoms": "White powdery patches",
        "treatments": [{"type": "chemical", "guidance": "Registered fungicide",
                        "safety_warning": "Follow the label"}]}).json()
    assert edited["symptoms"] == "White powdery patches"
    assert [t["type"] for t in edited["treatments"]] == ["chemical"]

    assert client.post(f"{API}/admin/diseases/{did}/archive", headers=admin).json()["archived"]
    farmer_view = client.get(f"{API}/diseases", params={"crop": "cucumber"}, headers=farmer).json()
    assert farmer_view == []
    admin_view = client.get(f"{API}/diseases", headers=admin,
                            params={"crop": "cucumber", "include_archived": True}).json()
    assert admin_view[0]["archived"] is True

    assert client.post(f"{API}/admin/diseases/{did}/restore", headers=admin).json()["archived"] is False


def test_there_is_no_delete_endpoint(client, admin):
    did = client.post(f"{API}/admin/diseases", json=ENTRY, headers=admin).json()["disease_id"]
    assert client.delete(f"{API}/admin/diseases/{did}", headers=admin).status_code == 405


def test_duplicate_name_is_rejected(client, admin):
    client.post(f"{API}/admin/diseases", json=ENTRY, headers=admin)
    resp = client.post(f"{API}/admin/diseases", json={**ENTRY, "name": "cucumber POWDERY mildew"},
                       headers=admin)
    assert resp.status_code == 409


@pytest.mark.parametrize("change", [
    {"name": ""},
    {"crop_type": "banana"},
    {"treatments": [{"type": "organic", "guidance": "x"}]},             # missing safety warning
    {"treatments": [{"type": "magic", "guidance": "x", "safety_warning": "y"}]},
])
def test_invalid_entries_are_not_saved(client, admin, change):
    resp = client.post(f"{API}/admin/diseases", json={**ENTRY, **change}, headers=admin)
    assert resp.status_code == 422
    names = [d["name"] for d in client.get(f"{API}/diseases", headers=admin).json()]
    assert ENTRY["name"] not in names


def test_search_by_name(client, farmer):
    names = [d["name"] for d in client.get(f"{API}/diseases", params={"q": "spot"}, headers=farmer).json()]
    assert "Tomato bacterial spot" in names and "Tomato early blight" not in names
