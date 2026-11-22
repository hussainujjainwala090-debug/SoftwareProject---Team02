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
- Weather: external weather service API

## Project status
The analysis and design phases are complete (requirements, use cases, UML diagrams, architecture, data design, UI mockups). They are in the Docs folder. Implementation is in progress, so the source code, tests and run steps below will be filled in as each part is committed.

## Prerequisites
- Flutter SDK, Python 3.10 or newer, a Firebase project

## Installation
Will be added with the first code commit (backend: pip install -r requirements.txt; app: flutter pub get).

## Configuration
Firebase credentials and the weather API key will be set through environment variables. No secrets are stored in this repository.

## How to run
Will be added with the first code commit.

## How to test
Will be added with the first code commit.
