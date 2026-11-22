# AgriScan - Crop Health Monitoring App

SWE 401 Software Engineering, Abu Dhabi University, Fall 2026 (Team 02)

## Team members
- Zeeshan Shams
- Zuhair Mohiyuddin
- Hussain Naeem Ujjainwala

## Problem
Farmers often spot crop diseases late, and expert advice is not always within reach. AgriScan lets a farmer photograph a leaf, get a disease diagnosis with severity and treatment advice, and receive weather-based risk alerts.

## Key features
- Register, log in and manage farm profiles and crops
- Capture or upload a leaf photo and get a diagnosis (offline captures are queued and sent later)
- Severity estimate and treatment recommendations
- Scan history and a dashboard with climate alerts
- PDF report export
- Admin knowledge base for diseases and treatments

## Technologies
- Mobile app: Flutter (Dart), SQLite offline queue
- Backend: Python FastAPI
- ML: TensorFlow CNN for disease classification
- Data: Firebase (Firestore, Cloud Storage, Cloud Messaging, Authentication)
- Weather: Open-Meteo (free, no API key), cached for up to 6 hours
- PDF: ReportLab; tests: pytest

## Project status
| Part | Status |
|---|---|
| Design (Docs/) | Complete |
| Backend (`src/backend`) | Working: all 5 services, 28 endpoints, 144 tests passing |
| ML (`src/ml`) | Severity segmentation and spread-risk rules working; CNN classifier training next |
| Mobile app (`src/app`) | Not started |

## Repository layout
```
src/
  backend/          FastAPI application tier
    app/api/        REST routes (/api/v1/...)
    app/services/   Auth/role, Scan, Forecast and alert, Treatment/KB, Report, Dashboard
    app/adapters/   Firebase Auth, Cloud Storage, Cloud Messaging, weather (each with a fake)
    app/repository.py  Firestore and in-memory document store
    firebase/       Firestore and Storage security rules, emulator config
    scripts/        smoke_test.py (end-to-end check of a running server)
  ml/agriscan_ml/   severity segmentation, spread-risk model (classifier to follow)
  tests/            pytest: backend/ and ml/
Docs/               design documents, diagrams, test evidence
```

## Prerequisites
- Python 3.10 or newer (tested with 3.13)
- Flutter SDK (for the mobile app, once added)
- A Firebase project only for `firebase` mode; the backend runs and is tested without one

## Installation
Backend and ML (Windows PowerShell; on macOS/Linux use `source .venv/bin/activate`):
```powershell
cd src/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
`requirements.txt` also installs the local ML package (`src/ml`) in editable mode.

## Configuration
Settings are environment variables starting with `AGRISCAN_`. Copy `src/backend/.env.example` to `src/backend/.env` and edit it. `.env` and key files are git-ignored: **never commit secrets**.

| Variable | Meaning | Default |
|---|---|---|
| `AGRISCAN_MODE` | `memory` (no Firebase needed: in-memory data, local files, dev tokens) or `firebase` | `memory` |
| `AGRISCAN_FIREBASE_CREDENTIALS` | Path to the Firebase service-account JSON (kept outside the repo) | empty |
| `AGRISCAN_FIREBASE_STORAGE_BUCKET` | Cloud Storage bucket name | empty |
| `AGRISCAN_ADMIN_EMAILS` | JSON list of emails that become admin when they register | `[]` |
| `AGRISCAN_CONFIDENCE_THRESHOLD` | Below this the diagnosis is "Uncertain" (FR-05) | `0.70` |
| `AGRISCAN_SEVERITY_MEDIUM_FROM_PCT` / `_HIGH_FROM_PCT` | Affected-area bands for low/medium/high (FR-06) | `15` / `40` |
| `AGRISCAN_WEATHER_PROVIDER` | `open-meteo` or `fake` (offline demo) | `open-meteo` |
| `AGRISCAN_WEATHER_CACHE_MAX_HOURS` | Oldest weather used when the service is down (NFR-09) | `6` |
| `AGRISCAN_ALERT_INTERVAL_MINUTES` | Minutes between climate-alert checks, 0 = off (FR-11) | `0` |
| `AGRISCAN_PUBLIC_BASE_URL` | Address clients use to open stored files in memory mode | `http://localhost:8000` |

**Authentication.** Every request needs `Authorization: Bearer <token>`. In `firebase` mode the token is a Firebase ID token from the app's sign-in. In `memory` mode only, development tokens are accepted: `dev:<uid>:<email>` (for example `dev:aisha:aisha@example.com`). The backend refuses to start in `firebase` mode with development tokens.

**Firebase mode.** Create a Firebase project, enable Authentication (email/password), Firestore, Cloud Storage and Cloud Messaging, download a service-account key to a folder outside the repo and set the two Firebase variables. Deploy the security rules (they block direct client access; all data goes through the backend):
```powershell
cd src/backend/firebase
firebase deploy --only firestore:rules,storage
```

## How to run
```powershell
cd src/backend
.venv\Scripts\Activate.ps1
$env:AGRISCAN_ADMIN_EMAILS='["admin@example.com"]'
uvicorn app.main:app --reload --port 8000
```
- Interactive API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

Main endpoints (all under `/api/v1`):

| Area | Endpoints |
|---|---|
| Users (FR-01, FR-18) | `POST /users/register`, `GET /users/me`, `PUT /users/me/fcm-token`, admin: `GET/POST /admin/users`, `PATCH /admin/users/{id}/role`, `POST /admin/users/{id}/disable` or `/enable`, `DELETE /admin/users/{id}` |
| Farms (FR-02, FR-13, FR-14) | `POST/GET /farms`, `GET/PUT /farms/{id}`, `GET /farms/{id}/weather`, `GET /farms/{id}/dashboard` |
| Scans and diagnoses (FR-03 to FR-10, FR-16) | `POST /scans` (multipart: `farm_id`, `crop_type`, `image`, optional `scan_id`, `captured_at`), `GET /diagnoses?status=&crop=&date_from=&date_to=&q=`, `GET /diagnoses/{id}`, `GET /diagnoses/{id}/spread-risk`, `POST /diagnoses/{id}/review`, `POST /diagnoses/{id}/feedback` |
| Reports (FR-15) | `POST/GET /diagnoses/{id}/reports` |
| Knowledge base (FR-09, FR-17) | `GET /diseases`, `GET /diseases/{id}`, admin: `POST /admin/diseases`, `PUT /admin/diseases/{id}`, `POST /admin/diseases/{id}/archive` or `/restore` |
| Monitoring and alerts (FR-11, FR-18) | `GET /admin/model-accuracy`, `POST /admin/alerts/check` |

## How to test
From the repository root, with the backend virtual environment active:
```powershell
python -m pytest
```
With coverage:
```powershell
python -m pytest --cov=app --cov=agriscan_ml --cov-report=term-missing
```
End-to-end check against a running server (start the server as in *How to run*, then in a second terminal):
```powershell
python src/backend/scripts/smoke_test.py http://localhost:8000
```
The tests need no Firebase project, internet or trained model: they use the in-memory store, a fake weather service, a fake classifier and synthetic leaf images.

## Testing
Results from 22 Nov 2026, branch `feature/backend`. Full output is in [Docs/test-evidence](Docs/test-evidence).

| Run | Result |
|---|---|
| Unit and API tests (`pytest`) | **144 passed, 0 failed**, statement coverage 92% ([backend_pytest.txt](Docs/test-evidence/backend_pytest.txt)) |
| End-to-end smoke test over HTTP, live Open-Meteo weather | **19/19 steps passed** ([smoke_test.txt](Docs/test-evidence/smoke_test.txt)) |
| Sample PDF report from the smoke run | [sample_report.pdf](Docs/test-evidence/sample_report.pdf) |

Tests by test case (TC numbers from the traceability matrix):

| Test case | What is checked | Test file |
|---|---|---|
| TC-01 (FR-01, NFR-11) | Missing/invalid token gives 401; unregistered or disabled users get 403; no self-made admins; every admin endpoint refuses farmer, farm owner and agronomist (36 cases); admin create/disable/enable/role/remove | `test_auth_users.py` |
| TC-02 (FR-02) | Farm create/edit, coordinate ranges, crop list, no repeated crops, only the owner edits | `test_farms.py` |
| TC-03 (FR-03, NFR-02) | Blurry, dark, non-image and over-1 MB uploads are refused; crop must belong to the farm | `test_image_quality.py`, `test_scans.py` |
| TC-04, TC-05 (FR-04, FR-05) | Confident result is confirmed; below 0.70, wrong crop or unknown label gives "Uncertain" with retake/agronomist advice and no segmentation; agronomist confirms or corrects | `test_scans.py`, `test_review_feedback.py` |
| TC-06, TC-07 (FR-06, FR-07) | Affected area within 2 points of the known lesion area on synthetic leaves; red overlay produced | `test_severity.py` |
| TC-08, TC-14 (FR-08, FR-14, NFR-09) | Weather reused, cached up to 6 h with a notice, "unavailable" after 6 h; spread-risk levels | `test_weather_forecast.py`, `test_weather_client.py`, `test_spread_risk.py` |
| TC-09, TC-17 (FR-09, FR-17) | Treatments by type with safety warnings; admin add/edit/archive/restore; duplicates and invalid entries refused; archived diseases are not used for new scans but old diagnoses keep them | `test_knowledge_base.py`, `test_scans.py` |
| TC-10, TC-12 (FR-10, FR-12, NFR-08) | History filters; uploading the same offline scan twice returns one diagnosis | `test_scans.py` |
| TC-11, TC-13, TC-15, TC-16 (FR-11, FR-13, FR-15, FR-16) | Push alert when risk is high; dashboard counts; PDF generated and downloadable; one feedback per diagnosis; accuracy trend for the admin | `test_reports_dashboard.py`, `test_review_feedback.py` |

Known limits of this prototype (to be stated in the report):
- The disease classifier is not trained yet, so every new scan is "Uncertain" until an agronomist reviews it or the model is added (next step).
- Severity uses a colour rule. It matches synthetic test leaves well, but NFR-04 (mean IoU of 0.70 or more) needs leaf masks labelled on real farm photos.
- Spread risk is rule-based because there is no labelled spread data.
- The Firestore, Cloud Storage, Cloud Messaging and Firebase Auth adapters are written but not yet run against a real Firebase project; all tests use the in-memory versions.
- Performance and load targets (NFR-01, NFR-06) and uptime (NFR-07) have not been measured.
