"""TC-01: registration, login token check and roles (FR-01, FR-18, NFR-11)."""
import pytest

from conftest import ADMIN_EMAIL, auth, register

API = "/api/v1"

# Every admin-only endpoint (method, path, json body).
ADMIN_ENDPOINTS = [
    ("get", "/admin/users", None),
    ("post", "/admin/users", {"name": "X", "email": "x@test.com", "password": "secret123", "role": "farmer"}),
    ("patch", "/admin/users/someid/role", {"role": "farmer"}),
    ("post", "/admin/users/someid/disable", None),
    ("post", "/admin/users/someid/enable", None),
    ("delete", "/admin/users/someid", None),
    ("get", "/admin/model-accuracy", None),
    ("post", "/admin/diseases", {"name": "X", "crop_type": "tomato", "treatments": []}),
    ("put", "/admin/diseases/someid", {"name": "X", "crop_type": "tomato", "treatments": []}),
    ("post", "/admin/diseases/someid/archive", None),
    ("post", "/admin/diseases/someid/restore", None),
    ("post", "/admin/alerts/check", None),
]


def test_requests_without_token_are_rejected(client):
    assert client.get(f"{API}/users/me").status_code == 401
    assert client.get(f"{API}/farms").status_code == 401


def test_invalid_token_is_rejected(client):
    resp = client.get(f"{API}/users/me", headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401


def test_signed_in_but_unregistered_user_is_told_to_register(client):
    resp = client.get(f"{API}/users/me", headers=auth("newuser"))
    assert resp.status_code == 403 and "register" in resp.json()["detail"]


def test_register_then_me(client):
    headers = register(client, "aisha", role="farm_owner")
    me = client.get(f"{API}/users/me", headers=headers).json()
    assert me["name"] == "Aisha" and me["role"] == "farm_owner" and me["email"] == "aisha@test.com"


def test_register_twice_is_a_conflict(client):
    headers = register(client, "aisha")
    resp = client.post(f"{API}/users/register", json={"name": "A", "role": "farmer"}, headers=headers)
    assert resp.status_code == 409


def test_same_email_on_another_account_is_a_conflict(client):
    register(client, "aisha", email="same@test.com")
    resp = client.post(f"{API}/users/register", json={"name": "B"},
                       headers=auth("other", "SAME@test.com"))
    assert resp.status_code == 409


def test_users_cannot_make_themselves_admin(client):
    resp = client.post(f"{API}/users/register", json={"name": "Eve", "role": "admin"},
                       headers=auth("eve"))
    assert resp.status_code == 403


def test_configured_admin_email_gets_admin_role(client):
    headers = register(client, "boss", email=ADMIN_EMAIL)
    assert client.get(f"{API}/users/me", headers=headers).json()["role"] == "admin"


def test_register_validates_input(client):
    resp = client.post(f"{API}/users/register", json={"name": "", "role": "farmer"}, headers=auth("x"))
    assert resp.status_code == 422


def test_fcm_token_is_saved(client, farmer, container):
    resp = client.put(f"{API}/users/me/fcm-token", json={"fcm_token": "tok-123"}, headers=farmer)
    assert resp.status_code == 200
    assert container.users.by_firebase_uid("farmer1")["fcm_token"] == "tok-123"


@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS)
@pytest.mark.parametrize("role", ["farmer", "farm_owner", "agronomist"])
def test_non_admins_are_rejected_from_every_admin_endpoint(client, method, path, body, role):
    headers = register(client, f"user_{role}", role=role)
    resp = getattr(client, method)(f"{API}{path}", headers=headers,
                                   **({"json": body} if body else {}))
    assert resp.status_code == 403


def test_admin_disable_enable_change_role_and_remove(client, admin, farmer):
    users = client.get(f"{API}/admin/users", headers=admin).json()
    target = next(u for u in users if u["email"] == "farmer1@test.com")
    assert target["disabled"] is False

    resp = client.post(f"{API}/admin/users/{target['user_id']}/disable", headers=admin)
    assert resp.json()["disabled"] is True
    assert client.get(f"{API}/users/me", headers=farmer).status_code == 403  # locked out

    client.post(f"{API}/admin/users/{target['user_id']}/enable", headers=admin)
    assert client.get(f"{API}/users/me", headers=farmer).status_code == 200

    resp = client.patch(f"{API}/admin/users/{target['user_id']}/role", json={"role": "agronomist"},
                        headers=admin)
    assert resp.json()["role"] == "agronomist"

    assert client.delete(f"{API}/admin/users/{target['user_id']}", headers=admin).status_code == 204
    assert client.get(f"{API}/users/me", headers=farmer).status_code == 403


def test_admin_creates_account(client, admin, container):
    resp = client.post(f"{API}/admin/users", headers=admin, json={
        "name": "Omar S.", "email": "omar@test.com", "password": "secret123", "role": "agronomist"})
    assert resp.status_code == 201 and resp.json()["role"] == "agronomist"
    assert any(a["email"] == "omar@test.com" for a in container.accounts.accounts.values())


def test_admin_cannot_lock_themselves_out(client, admin):
    me = client.get(f"{API}/users/me", headers=admin).json()
    assert client.post(f"{API}/admin/users/{me['user_id']}/disable", headers=admin).status_code == 422
    assert client.delete(f"{API}/admin/users/{me['user_id']}", headers=admin).status_code == 422
    resp = client.patch(f"{API}/admin/users/{me['user_id']}/role", json={"role": "farmer"}, headers=admin)
    assert resp.status_code == 422
