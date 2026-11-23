"""Climate alert check (FR-11). Runs on a schedule (see main.py) or on demand by an admin."""
from fastapi import APIRouter, Depends

from app.container import Container
from app.schemas import AlertOut
from app.security import admin_only, get_container

router = APIRouter(tags=["alerts"])


@router.post("/admin/alerts/check", response_model=list[AlertOut])
def check_alerts(_: dict = Depends(admin_only), c: Container = Depends(get_container)):
    return c.forecast.check_alerts()
