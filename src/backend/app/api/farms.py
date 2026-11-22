"""Farm profile (FR-02), farm weather (FR-14) and dashboard (FR-13)."""
from fastapi import APIRouter, Depends, status

from app.container import Container
from app.schemas import DashboardOut, FarmIn, FarmOut, WeatherOut
from app.security import get_container, get_current_user, grower

router = APIRouter(prefix="/farms", tags=["farms"])


@router.post("", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
def create_farm(body: FarmIn, user: dict = Depends(grower), c: Container = Depends(get_container)):
    return c.farms.create(user, body)


@router.get("", response_model=list[FarmOut])
def list_farms(user: dict = Depends(get_current_user), c: Container = Depends(get_container)):
    return c.farms.list_for(user)


@router.get("/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: str, user: dict = Depends(get_current_user),
             c: Container = Depends(get_container)):
    return c.farms.to_out(c.farms.get_visible(user, farm_id))


@router.put("/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: str, body: FarmIn, user: dict = Depends(grower),
                c: Container = Depends(get_container)):
    return c.farms.update(user, farm_id, body)


@router.get("/{farm_id}/weather", response_model=WeatherOut)
def farm_weather(farm_id: str, user: dict = Depends(get_current_user),
                 c: Container = Depends(get_container)):
    farm = c.farms.get_visible(user, farm_id)
    return c.forecast.current_weather(farm["latitude"], farm["longitude"])


@router.get("/{farm_id}/dashboard", response_model=DashboardOut)
def dashboard(farm_id: str, user: dict = Depends(get_current_user),
              c: Container = Depends(get_container)):
    return c.dashboard.farm_dashboard(user, farm_id)
