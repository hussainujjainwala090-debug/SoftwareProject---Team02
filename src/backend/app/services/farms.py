"""Farm profile service (FR-02).

Farms(farm_id, owner_id, name, latitude, longitude) and
FarmCrops(farm_crop_id, farm_id, crop_type) with (farm_id, crop_type) not repeated.
"""
from app.errors import Forbidden, NotFound
from app.repository import FARM_CROPS, FARMS, Repository, new_id
from app.schemas import Crop, FarmIn, Role

STAFF = {Role.agronomist.value, Role.admin.value}


class FarmService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def crops_of(self, farm_id: str) -> list[str]:
        return sorted(fc["crop_type"] for fc in self.repo.find(FARM_CROPS, farm_id=farm_id))

    def to_out(self, farm: dict) -> dict:
        return {**farm, "crops": self.crops_of(farm["farm_id"])}

    def _set_crops(self, farm_id: str, crops: list[Crop]) -> None:
        wanted = {c.value for c in crops}  # a set: a crop is never repeated
        existing = {fc["crop_type"]: fc for fc in self.repo.find(FARM_CROPS, farm_id=farm_id)}
        for crop, row in existing.items():
            if crop not in wanted:
                self.repo.delete(FARM_CROPS, row["farm_crop_id"])
        for crop in sorted(wanted - existing.keys()):
            fc_id = new_id()
            self.repo.create(FARM_CROPS, fc_id, {"farm_crop_id": fc_id, "farm_id": farm_id, "crop_type": crop})

    def create(self, user: dict, data: FarmIn) -> dict:
        farm = {
            "farm_id": new_id(),
            "owner_id": user["user_id"],
            "name": data.name,
            "latitude": data.latitude,
            "longitude": data.longitude,
        }
        self.repo.create(FARMS, farm["farm_id"], farm)
        self._set_crops(farm["farm_id"], data.crops)
        return self.to_out(farm)

    def get(self, farm_id: str) -> dict:
        farm = self.repo.get(FARMS, farm_id)
        if farm is None:
            raise NotFound("Farm not found")
        return farm

    def get_visible(self, user: dict, farm_id: str) -> dict:
        farm = self.get(farm_id)
        if farm["owner_id"] != user["user_id"] and user["role"] not in STAFF:
            raise Forbidden("You do not have access to this farm")
        return farm

    def get_owned(self, user: dict, farm_id: str) -> dict:
        farm = self.get(farm_id)
        if farm["owner_id"] != user["user_id"] and user["role"] != Role.admin.value:
            raise Forbidden("Only the farm owner can change this farm")
        return farm

    def update(self, user: dict, farm_id: str, data: FarmIn) -> dict:
        self.get_owned(user, farm_id)
        farm = self.repo.update(FARMS, farm_id, {
            "name": data.name, "latitude": data.latitude, "longitude": data.longitude,
        })
        self._set_crops(farm_id, data.crops)
        return self.to_out(farm)

    def list_for(self, user: dict) -> list[dict]:
        farms = self.repo.find(FARMS) if user["role"] == Role.admin.value else \
            self.repo.find(FARMS, owner_id=user["user_id"])
        return [self.to_out(f) for f in sorted(farms, key=lambda f: f["name"].lower())]
