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
| Backend (`src/backend`) | Working: all 5 services, 31 API endpoints, all tests passing |
| ML (`src/ml`) | Working: MobileNetV2 disease classifier (93.0% test accuracy on PlantVillage tomato and pepper), severity segmentation, spread-risk rules |
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
  ml/agriscan_ml/   classifier (train, evaluate, wrapper), severity segmentation, spread risk
  ml/models/        trained model files (git-ignored; created by training)
  tests/            pytest: backend/ and ml/
Docs/               design documents, diagrams, test evidence
```

## Prerequisites
- Python 3.10 or newer (tested with 3.13)
- Flutter SDK (for the mobile app, once added)
- A Firebase project only for `firebase` mode; the backend runs and is tested without one

## Installation
Backend and ML (Windows PowerShell; on macOS/Linux use `source .venv/bin/activate`). Tested on Python 3.13; the code avoids 3.11-only features so 3.10 should work, but has not been run on it.
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

## Disease classifier (ML)
Without a trained model the backend still runs, but every scan is "Uncertain". To train and use the model:

**1. Make an ML environment at a short path.** TensorFlow's files are too deep for Windows' 260-character path limit if the environment sits inside the project folder (unless long paths are enabled in Windows).
```powershell
python -m venv C:\Users\<you>\agriscan-ml-venv
C:\Users\<you>\agriscan-ml-venv\Scripts\Activate.ps1
pip install tensorflow -r src/backend/requirements.txt
```
This one environment can run the backend, the tests and the ML scripts.

**2. Get the data.** Download *Plant_leaf_diseases_dataset_without_augmentation.zip* (PlantVillage, Mendeley Data, doi:10.17632/tywbtsjrjv.1, about 830 MB) and extract the 12 tomato and bell-pepper classes to a short folder:
```powershell
cd src/ml
python -m agriscan_ml.prepare_data <path-to-zip> C:\Users\<you>\agriscan-data\pv
```

**3. Train (about 10 minutes on a CPU) and evaluate:**
```powershell
python -m agriscan_ml.train --image-dir C:\Users\<you>\agriscan-data\pv
python -m agriscan_ml.evaluate --image-dir C:\Users\<you>\agriscan-data\pv
```
This writes `src/ml/models/classifier.keras`, `labels.json` and `eval.json`. The backend loads them automatically at start-up (paths in `AGRISCAN_CLASSIFIER_MODEL_PATH` and `AGRISCAN_CLASSIFIER_LABELS_PATH`) when it runs in the ML environment.

Method: transfer learning with MobileNetV2 (ImageNet weights, frozen) and a softmax layer trained on its features; within each class the photos are split 80/10/10 into train, validation and test by file order, the same every run. Crops the model was not trained on (date palm, cucumber) and predictions for a different crop than the one selected are shown as "Uncertain".

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
The tests need no Firebase project, internet or trained model: they use the in-memory store, a fake weather service, a fake classifier and synthetic leaf images. One classifier test needs TensorFlow and is skipped without it. The trained model itself is checked with `python -m agriscan_ml.evaluate` (see *Disease classifier*).

## Testing
Results from 22 Nov 2026, branch `feature/backend`. Full output is in [Docs/test-evidence](Docs/test-evidence).

| Run | Result |
|---|---|
| Unit and API tests (`pytest`, with TensorFlow installed) | **151 passed, 0 failed**, statement coverage 86%; the uncovered code is mainly the real Firebase adapters and the training/evaluation scripts, which are run directly instead ([backend_pytest.txt](Docs/test-evidence/backend_pytest.txt)) |
| Disease classifier on 2,058 unseen PlantVillage test photos (NFR-03, target 85%) | **93.05% accuracy**; 89.2% of photos are above the 0.70 confidence threshold and 97.1% of those are correct; the rest are shown as "Uncertain" ([classifier_eval.txt](Docs/test-evidence/classifier_eval.txt), [classifier_training_eval.json](Docs/test-evidence/classifier_training_eval.json)) |
| Real photos through `POST /scans` with the trained model | 11 of 12 classes diagnosed correctly, 1 shown as "Uncertain", both wrong-crop scans "Uncertain" ([real_photo_scans.txt](Docs/test-evidence/real_photo_scans.txt)) |
| End-to-end smoke test over HTTP, live Open-Meteo weather | **19/19 steps passed** ([smoke_test.txt](Docs/test-evidence/smoke_test.txt)) |
| Sample PDF report from the smoke run | [sample_report.pdf](Docs/test-evidence/sample_report.pdf) |

Tests by test case. IDs come from the Requirements Traceability Matrix: TC-01 to TC-18 test FR-01 to FR-18, TC-19 to TC-32 test the NFRs. Only the backend side is covered here; the app side of each case comes with the Flutter app.

| Test case | What is checked (backend) | Test file |
|---|---|---|
| TC-01 (FR-01) | Missing/invalid token gives 401; unregistered users get 403; register once per account and email; no self-made admins; configured admin email must be verified | `test_auth_users.py` |
| TC-02 (FR-02) | Farm create/edit, coordinate ranges, crop list, no repeated crops, only the owner edits | `test_farms.py` |
| TC-03 (FR-03) | Blurry, dark and non-image uploads are refused; crop must belong to the farm | `test_image_quality.py`, `test_scans.py` |
| TC-04 (FR-04) | Confident prediction is stored as confirmed with label and confidence; healthy leaves; classifier wrapper; every classifier label has a knowledge-base entry; real photos through the API | `test_scans.py`, `test_classifier.py`, `real_photo_scans.txt` |
| TC-05 (FR-05) | Below 0.70, wrong crop, unknown label or no model gives "Uncertain" with retake/agronomist advice and no segmentation; agronomist confirms or corrects | `test_scans.py`, `test_review_feedback.py` |
| TC-06 (FR-06) | Affected area within 2 points of the known lesion area on synthetic leaves; low/medium/high bands | `test_severity.py`, `test_scans.py` |
| TC-07 (FR-07) | Red overlay produced, stored and downloadable | `test_severity.py`, `test_scans.py` |
| TC-08 (FR-08) | Spread-risk levels and explanations; recalculated with new weather | `test_spread_risk.py`, `test_weather_forecast.py` |
| TC-09 (FR-09) | Organic, chemical and preventive treatments, each with a safety warning | `test_scans.py`, `test_knowledge_base.py` |
| TC-10 (FR-10) | History filters by status, crop, date and disease name; users only see their own | `test_scans.py` |
| TC-11 (FR-11) | Push alert sent to the farm owner when risk is high, none in dry weather | `test_reports_dashboard.py` |
| TC-12 (FR-12) | Same offline scan uploaded twice gives one diagnosis; a retry after a failed diagnosis completes it | `test_scans.py` |
| TC-13 (FR-13) | Dashboard totals, scans per week, common diseases, climate alert | `test_reports_dashboard.py` |
| TC-14 (FR-14) | Open-Meteo parsing and errors; weather stored and reused | `test_weather_client.py`, `test_weather_forecast.py` |
| TC-15 (FR-15) | PDF generated, stored and downloadable by link; only allowed users | `test_reports_dashboard.py` |
| TC-16 (FR-16) | One feedback per diagnosis, only by the farmer | `test_review_feedback.py` |
| TC-17 (FR-17) | Admin add/edit/archive/restore; no delete; duplicates and invalid entries refused; archived diseases not used for new scans, old diagnoses keep them | `test_knowledge_base.py`, `test_scans.py` |
| TC-18 (FR-18) | Admin create/disable/enable/change role/remove accounts; disabled users locked out; accuracy trend from feedback | `test_auth_users.py`, `test_review_feedback.py` |
| TC-20 (NFR-02) | Uploads over 1 MB refused (the app-side compression test comes with the app) | `test_scans.py` |
| TC-21 (NFR-03) | Classifier accuracy 93.05% on 2,058 unseen PlantVillage photos (target 85%) | `classifier_eval.txt` |
| TC-22 (NFR-04) | Mean IoU of 0.70 or more on synthetic leaves only (real masks still needed) | `test_severity.py` |
| TC-25 (NFR-08) | No duplicate scans or diagnoses on retry | `test_scans.py` |
| TC-26 (NFR-09) | Fault injection: weather service down, cache used up to 6 h with notice, then "unavailable" | `test_weather_forecast.py` |
| TC-28 (NFR-11) | Every admin endpoint refuses farmer, farm owner and agronomist tokens (36 cases) | `test_auth_users.py` |

Not covered yet: TC-19 and TC-23 (performance and load, NFR-01 and NFR-06), TC-24 (uptime), TC-27 (TLS, depends on the deployment), TC-29 to TC-31 (privacy, usability and compatibility acceptance tests with the app), TC-32 (code analysis).

Known limits of this prototype (to be stated in the report):
- The classifier is trained on PlantVillage, which has lab photos of single leaves on plain backgrounds. Accuracy on real field photos will be lower, and the model covers only tomato and bell pepper: date palm and cucumber need the team's own labelled photos.
- Severity uses a colour rule inside the leaf outline. It matches synthetic test leaves and gives plausible values on PlantVillage photos, but it misses pale or grey lesions, and NFR-04 (mean IoU of 0.70 or more) needs leaf masks labelled on real farm photos.
- The blur threshold (20) was set from PlantVillage photos; it should be checked again with real phone photos.
- Spread risk is rule-based because there is no labelled spread data.
- The starter knowledge-base treatments (`src/backend/app/seed_data.py`) are general guidance written for the prototype and must be checked by an agronomist before real use.
- The Firestore, Cloud Storage, Cloud Messaging and Firebase Auth adapters are written but not yet run against a real Firebase project; all tests use the in-memory versions.
- Performance and load targets (NFR-01, NFR-06) and uptime (NFR-07) have not been measured.
