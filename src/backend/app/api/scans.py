"""Scan upload and diagnoses (FR-03 to FR-10, FR-15, FR-16)."""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.container import Container
from app.errors import TooLarge
from app.schemas import (Crop, DiagnosisOut, FeedbackIn, FeedbackOut, ReportOut, ReviewIn,
                         SpreadRiskOut, Status)
from app.security import agronomist_only, get_container, get_current_user, grower

router = APIRouter(tags=["scans"])


@router.post("/scans", response_model=DiagnosisOut, status_code=status.HTTP_201_CREATED)
async def submit_scan(
    farm_id: str = Form(...),
    crop_type: Crop = Form(...),
    image: UploadFile = File(...),
    scan_id: str | None = Form(None, description="Client id; makes offline re-uploads safe"),
    captured_at: str | None = Form(None, description="ISO time the photo was taken"),
    user: dict = Depends(grower),
    c: Container = Depends(get_container),
):
    data = await image.read(c.settings.max_image_bytes + 1)
    if len(data) > c.settings.max_image_bytes:
        raise TooLarge("The image must be 1 MB or less")
    return c.scans.submit(user, farm_id, crop_type.value, data, scan_id, captured_at)


@router.get("/diagnoses", response_model=list[DiagnosisOut])
def history(
    status_filter: Status | None = Query(None, alias="status"),
    crop: Crop | None = None,
    date_from: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    q: str | None = Query(None, max_length=100),
    farm_id: str | None = None,
    user: dict = Depends(get_current_user),
    c: Container = Depends(get_container),
):
    return c.scans.history(user, status_filter.value if status_filter else None,
                           crop.value if crop else None, date_from, date_to, q, farm_id)


@router.get("/diagnoses/{diagnosis_id}", response_model=DiagnosisOut)
def get_diagnosis(diagnosis_id: str, user: dict = Depends(get_current_user),
                  c: Container = Depends(get_container)):
    return c.scans.detail(user, diagnosis_id)


@router.get("/diagnoses/{diagnosis_id}/spread-risk", response_model=SpreadRiskOut)
def spread_risk(diagnosis_id: str, user: dict = Depends(get_current_user),
                c: Container = Depends(get_container)):
    return c.scans.refresh_spread_risk(user, diagnosis_id)


@router.post("/diagnoses/{diagnosis_id}/review", response_model=DiagnosisOut)
def review(diagnosis_id: str, body: ReviewIn, user: dict = Depends(agronomist_only),
           c: Container = Depends(get_container)):
    return c.scans.review(user, diagnosis_id, body.disease_id)


@router.post("/diagnoses/{diagnosis_id}/feedback", response_model=FeedbackOut,
             status_code=status.HTTP_201_CREATED)
def feedback(diagnosis_id: str, body: FeedbackIn, user: dict = Depends(get_current_user),
             c: Container = Depends(get_container)):
    return c.scans.add_feedback(user, diagnosis_id, body)


@router.post("/diagnoses/{diagnosis_id}/reports", response_model=ReportOut,
             status_code=status.HTTP_201_CREATED)
def create_report(diagnosis_id: str, user: dict = Depends(get_current_user),
                  c: Container = Depends(get_container)):
    return c.reports.generate(user, diagnosis_id)


@router.get("/diagnoses/{diagnosis_id}/reports", response_model=list[ReportOut])
def list_reports(diagnosis_id: str, user: dict = Depends(get_current_user),
                 c: Container = Depends(get_container)):
    return c.reports.list_for(user, diagnosis_id)
