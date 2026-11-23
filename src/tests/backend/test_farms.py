"""TC-02: farm profile and crop selection (FR-02)."""
import pytest

from conftest import register

API = "/api/v1/farms"
FARM = {"name": "Al Ain palm farm", "latitude": 24.2, "longitude": 55.7, "crops": ["date_palm"]}


def test_create_and_list_farm(client, farmer):
    created = client.post(API, json={**FARM, "crops": ["tomato", "date_palm", "tomato"]},
                          headers=farmer).json()
    assert created["crops"] == ["date_palm", "tomato"]  # a crop is never repeated
    farms = client.get(API, headers=farmer).json()
    assert [f["farm_id"] for f in farms] == [created["farm_id"]]


@pytest.mark.parametrize("change", [
    {"latitude": 91}, {"longitude": -181}, {"name": ""}, {"crops": []}, {"crops": ["banana"]},
    {"owner_id": "someone-else"},
])
def test_invalid_farm_is_rejected(client, farmer, change):
    assert client.post(API, json={**FARM, **change}, headers=farmer).status_code == 422


def test_update_changes_crops(client, farmer, farm):
    resp = client.put(f"{API}/{farm['farm_id']}", headers=farmer,
                      json={**FARM, "name": "New name", "crops": ["pepper"]})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New name" and resp.json()["crops"] == ["pepper"]


def test_other_farmers_cannot_see_or_edit(client, farm):
    other = register(client, "farmer2")
    assert client.get(f"{API}/{farm['farm_id']}", headers=other).status_code == 403
    assert client.put(f"{API}/{farm['farm_id']}", json=FARM, headers=other).status_code == 403
    assert client.get(API, headers=other).json() == []


def test_agronomist_can_view_but_not_create_or_edit(client, agronomist, farm):
    assert client.get(f"{API}/{farm['farm_id']}", headers=agronomist).status_code == 200
    assert client.put(f"{API}/{farm['farm_id']}", json=FARM, headers=agronomist).status_code == 403
    assert client.post(API, json=FARM, headers=agronomist).status_code == 403


def test_unknown_farm_is_404(client, farmer):
    assert client.get(f"{API}/does-not-exist", headers=farmer).status_code == 404
