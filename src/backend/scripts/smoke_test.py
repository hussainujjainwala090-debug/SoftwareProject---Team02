"""End-to-end smoke test against a running backend in memory mode.

Start the server first (from src/backend):
    set AGRISCAN_ADMIN_EMAILS=["admin@example.com"]      (PowerShell: $env:AGRISCAN_ADMIN_EMAILS='["admin@example.com"]')
    uvicorn app.main:app --port 8000
Then run:
    python scripts/smoke_test.py [http://localhost:8000]

Walks through UC-01, UC-02 and UC-03 over real HTTP with development tokens
and a synthetic leaf photo, and prints each step.
"""
import io
import sys
import uuid

import httpx
import numpy as np
from PIL import Image

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
API = f"{BASE}/api/v1"
RUN = uuid.uuid4().hex[:6]


def token(uid: str, email: str) -> dict:
    return {"Authorization": f"Bearer dev:{uid}-{RUN}:{email}"}


def leaf_png() -> bytes:
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:256, 0:256]
    leaf = ((xx - 128) / 100) ** 2 + ((yy - 128) / 70) ** 2 <= 1
    spots = ((xx - 95) ** 2 + (yy - 115) ** 2 <= 625) | ((xx - 160) ** 2 + (yy - 140) ** 2 <= 625)
    rgb = np.full((256, 256, 3), 125.0)
    rgb[leaf] = (55, 145, 45)
    rgb[leaf & spots] = (125, 70, 25)
    rgb += rng.normal(0, 10, rgb.shape)
    out = io.BytesIO()
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(out, format="PNG")
    return out.getvalue()


def step(label: str, resp: httpx.Response, expect: int) -> dict | list:
    ok = resp.status_code == expect
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: HTTP {resp.status_code}")
    if not ok:
        print("       ", resp.text[:300])
        sys.exit(1)
    return resp.json() if resp.content and "json" in resp.headers.get("content-type", "") else {}


def main() -> None:
    c = httpx.Client(timeout=30)
    step("Health", c.get(f"{BASE}/health"), 200)
    admin = token("smoke-admin", "admin@example.com")
    farmer = token("smoke-farmer", f"farmer-{RUN}@example.com")
    agro = token("smoke-agro", f"agro-{RUN}@example.com")

    step("Request without token is rejected", c.get(f"{API}/farms"), 401)
    me = step("Admin registers (configured admin email)",
              c.post(f"{API}/users/register", json={"name": "Admin"}, headers=admin), 201)
    print("        role:", me["role"])
    step("Farmer registers", c.post(f"{API}/users/register", json={"name": "Aisha K.", "role": "farmer"},
                                    headers=farmer), 201)
    step("Agronomist registers", c.post(f"{API}/users/register",
                                        json={"name": "Omar S.", "role": "agronomist"}, headers=agro), 201)
    step("Farmer is refused from admin pages", c.get(f"{API}/admin/users", headers=farmer), 403)

    farm = step("Create farm profile (FR-02)", c.post(f"{API}/farms", headers=farmer, json={
        "name": "Al Ain palm farm", "latitude": 24.2075, "longitude": 55.7447,
        "crops": ["date_palm", "tomato"]}), 201)
    w = step("Live weather for the farm (FR-14)", c.get(f"{API}/farms/{farm['farm_id']}/weather",
                                                         headers=farmer), 200)
    print(f"        available={w['available']} temp={w.get('temperature')} "
          f"humidity={w.get('humidity')} rain={w.get('rainfall')} notice={w.get('notice')}")

    form = {"farm_id": farm["farm_id"], "crop_type": "tomato", "scan_id": f"smoke-{RUN}"}
    d = step("Upload leaf scan (FR-03/04)", c.post(f"{API}/scans", headers=farmer, data=form,
             files={"image": ("leaf.png", leaf_png(), "image/png")}), 201)
    print(f"        label={d['label']} status={d['status']} confidence={d['confidence']}")
    again = step("Same scan_id uploaded again (offline retry)", c.post(
        f"{API}/scans", headers=farmer, data=form,
        files={"image": ("leaf.png", leaf_png(), "image/png")}), 201)
    print("        same diagnosis returned:", again["diagnosis_id"] == d["diagnosis_id"])

    diseases = step("Agronomist reads knowledge base", c.get(f"{API}/diseases", params={"crop": "tomato"},
                                                             headers=agro), 200)
    blight = next(x for x in diseases if x["name"] == "Tomato early blight")
    r = step("Agronomist reviews the diagnosis", c.post(
        f"{API}/diagnoses/{d['diagnosis_id']}/review", json={"disease_id": blight["disease_id"]},
        headers=agro), 200)
    print(f"        label={r['label']} severity={r['severity_level']} "
          f"affected={r['affected_area_pct']}% spread_risk={r['spread_risk']}")
    print(f"        treatments={[t['type'] for t in r['treatments']]}")
    step("Overlay image can be opened", c.get(r["overlay_url"]), 200)

    step("Farmer gives feedback (FR-16)", c.post(f"{API}/diagnoses/{d['diagnosis_id']}/feedback",
                                                  json={"correct": True}, headers=farmer), 201)
    rep = step("Export PDF report (FR-15)", c.post(f"{API}/diagnoses/{d['diagnosis_id']}/reports",
                                                    headers=farmer), 201)
    pdf = c.get(rep["pdf_url"])
    print(f"        PDF bytes={len(pdf.content)} starts with %PDF: {pdf.content[:4] == b'%PDF'}")
    hist = step("History (FR-10)", c.get(f"{API}/diagnoses", headers=farmer), 200)
    print("        entries:", len(hist))
    dash = step("Dashboard (FR-13)", c.get(f"{API}/farms/{farm['farm_id']}/dashboard", headers=farmer), 200)
    print(f"        scans={dash['total_scans']} climate_alert={dash['climate_alert']['spread_risk']}")
    step("Admin: model accuracy (FR-18)", c.get(f"{API}/admin/model-accuracy", headers=admin), 200)
    step("Admin: climate alert check (FR-11)", c.post(f"{API}/admin/alerts/check", headers=admin), 200)
    print("All smoke steps passed.")


if __name__ == "__main__":
    main()
