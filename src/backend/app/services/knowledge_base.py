"""Treatment and knowledge-base service (FR-09, FR-17; SD-3).

Diseases(disease_id, name UNIQUE, crop_type, symptoms, archived) and
Treatments(treatment_id, disease_id, type, guidance, safety_warning).
Entries are archived and restored, never deleted, so saved diagnoses keep
their disease (decision agreed for FR-17).
"""
from app.errors import Conflict, NotFound
from app.repository import DISEASES, TREATMENTS, Repository, new_id
from app.schemas import DiseaseIn

TYPE_ORDER = {"organic": 0, "chemical": 1, "preventive": 2}


class KnowledgeBaseService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    # ----------------------------------------------------------- reading ----
    def treatments_for(self, disease_id: str) -> list[dict]:
        rows = self.repo.find(TREATMENTS, disease_id=disease_id)
        return sorted(rows, key=lambda t: (TYPE_ORDER[t["type"]], t["treatment_id"]))

    def with_treatments(self, disease: dict) -> dict:
        return {**disease, "treatments": self.treatments_for(disease["disease_id"])}

    def get(self, disease_id: str) -> dict:
        disease = self.repo.get(DISEASES, disease_id)
        if disease is None:
            raise NotFound("Disease not found")
        return disease

    def search(self, crop: str | None = None, q: str | None = None,
             include_archived: bool = False) -> list[dict]:
        filters = {"crop_type": crop} if crop else {}
        rows = self.repo.find(DISEASES, **filters)
        if not include_archived:
            rows = [d for d in rows if not d["archived"]]
        if q:
            rows = [d for d in rows if q.lower() in d["name"].lower()]
        return [self.with_treatments(d) for d in sorted(rows, key=lambda d: d["name"].lower())]

    def find_active(self, name: str, crop: str) -> dict | None:
        """Disease matching a classifier label for the scanned crop, if active."""
        for d in self.repo.find(DISEASES, crop_type=crop):
            if d["name"].lower() == name.lower() and not d["archived"]:
                return d
        return None

    # ----------------------------------------------------------- writing ----
    def _check_name_free(self, name: str, except_id: str | None = None) -> None:
        for d in self.repo.find(DISEASES):
            if d["name"].lower() == name.lower() and d["disease_id"] != except_id:
                raise Conflict(f"A disease named '{d['name']}' already exists")

    def _replace_treatments(self, disease_id: str, data: DiseaseIn) -> None:
        for t in self.repo.find(TREATMENTS, disease_id=disease_id):
            self.repo.delete(TREATMENTS, t["treatment_id"])
        for t in data.treatments:
            t_id = new_id()
            self.repo.create(TREATMENTS, t_id, {
                "treatment_id": t_id, "disease_id": disease_id, "type": t.type.value,
                "guidance": t.guidance, "safety_warning": t.safety_warning,
            })

    def create(self, data: DiseaseIn) -> dict:
        self._check_name_free(data.name)
        disease = {
            "disease_id": new_id(), "name": data.name, "crop_type": data.crop_type.value,
            "symptoms": data.symptoms, "archived": False,
        }
        self.repo.create(DISEASES, disease["disease_id"], disease)
        self._replace_treatments(disease["disease_id"], data)
        return self.with_treatments(disease)

    def update(self, disease_id: str, data: DiseaseIn) -> dict:
        self.get(disease_id)
        self._check_name_free(data.name, except_id=disease_id)
        disease = self.repo.update(DISEASES, disease_id, {
            "name": data.name, "crop_type": data.crop_type.value, "symptoms": data.symptoms,
        })
        self._replace_treatments(disease_id, data)
        return self.with_treatments(disease)

    def set_archived(self, disease_id: str, archived: bool) -> dict:
        self.get(disease_id)
        return self.with_treatments(self.repo.update(DISEASES, disease_id, {"archived": archived}))

    def seed(self, entries: list[DiseaseIn]) -> int:
        """Insert entries whose name is not in the knowledge base yet."""
        added = 0
        for entry in entries:
            if not any(d["name"].lower() == entry.name.lower() for d in self.repo.find(DISEASES)):
                self.create(entry)
                added += 1
        return added
