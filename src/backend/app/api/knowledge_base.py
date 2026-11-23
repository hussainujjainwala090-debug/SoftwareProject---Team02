"""Knowledge base: read by everyone signed in, managed by the admin (FR-09, FR-17; SD-3)."""
from fastapi import APIRouter, Depends, Query, status

from app.container import Container
from app.schemas import Crop, DiseaseIn, DiseaseOut
from app.security import admin_only, get_container, get_current_user

router = APIRouter(tags=["knowledge base"])


@router.get("/diseases", response_model=list[DiseaseOut])
def list_diseases(
    crop: Crop | None = None,
    q: str | None = Query(None, max_length=100),
    include_archived: bool = False,
    user: dict = Depends(get_current_user),
    c: Container = Depends(get_container),
):
    # Only the admin sees archived entries.
    show_archived = include_archived and user["role"] == "admin"
    return c.kb.search(crop.value if crop else None, q, show_archived)


@router.get("/diseases/{disease_id}", response_model=DiseaseOut)
def get_disease(disease_id: str, _: dict = Depends(get_current_user),
                c: Container = Depends(get_container)):
    return c.kb.with_treatments(c.kb.get(disease_id))


@router.post("/admin/diseases", response_model=DiseaseOut, status_code=status.HTTP_201_CREATED)
def create_disease(body: DiseaseIn, _: dict = Depends(admin_only),
                   c: Container = Depends(get_container)):
    return c.kb.create(body)


@router.put("/admin/diseases/{disease_id}", response_model=DiseaseOut)
def update_disease(disease_id: str, body: DiseaseIn, _: dict = Depends(admin_only),
                   c: Container = Depends(get_container)):
    return c.kb.update(disease_id, body)


@router.post("/admin/diseases/{disease_id}/archive", response_model=DiseaseOut)
def archive(disease_id: str, _: dict = Depends(admin_only), c: Container = Depends(get_container)):
    return c.kb.set_archived(disease_id, True)


@router.post("/admin/diseases/{disease_id}/restore", response_model=DiseaseOut)
def restore(disease_id: str, _: dict = Depends(admin_only), c: Container = Depends(get_container)):
    return c.kb.set_archived(disease_id, False)
