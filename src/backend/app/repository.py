"""Document store used by every service.

Firestore does not enforce primary keys, foreign keys, UNIQUE or NOT NULL, so the
services check those rules before writing (see Table DB-1). Two implementations
share this interface:

* MemoryRepository  - a dict per collection, used by the tests and memory mode.
* FirestoreRepository - Cloud Firestore through the Firebase Admin SDK.

Collection names match the 10 entities of the data design.
"""
import copy
import threading
import uuid
from typing import Any, Protocol

USERS = "users"
FARMS = "farms"
FARM_CROPS = "farm_crops"
SCANS = "scans"
DIAGNOSES = "diagnoses"
DISEASES = "diseases"
TREATMENTS = "treatments"
WEATHER_RECORDS = "weather_records"
FEEDBACK = "feedback"
REPORTS = "reports"

Doc = dict[str, Any]


class AlreadyExistsError(Exception):
    """Raised by create() when a document with the same id exists."""


def new_id() -> str:
    return uuid.uuid4().hex


class Repository(Protocol):
    def get(self, collection: str, doc_id: str) -> Doc | None: ...

    def create(self, collection: str, doc_id: str, data: Doc) -> Doc:
        """Insert a new document; raise AlreadyExistsError if the id is taken."""
        ...

    def put(self, collection: str, doc_id: str, data: Doc) -> Doc: ...

    def update(self, collection: str, doc_id: str, fields: Doc) -> Doc: ...

    def delete(self, collection: str, doc_id: str) -> None: ...

    def find(self, collection: str, **equals: Any) -> list[Doc]:
        """Documents whose fields equal every given value (all documents if none)."""
        ...


class MemoryRepository:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Doc]] = {}
        self._lock = threading.Lock()

    def _col(self, collection: str) -> dict[str, Doc]:
        return self._data.setdefault(collection, {})

    def get(self, collection: str, doc_id: str) -> Doc | None:
        with self._lock:
            doc = self._col(collection).get(doc_id)
            return copy.deepcopy(doc) if doc is not None else None

    def create(self, collection: str, doc_id: str, data: Doc) -> Doc:
        with self._lock:
            col = self._col(collection)
            if doc_id in col:
                raise AlreadyExistsError(f"{collection}/{doc_id}")
            col[doc_id] = copy.deepcopy(data)
            return copy.deepcopy(data)

    def put(self, collection: str, doc_id: str, data: Doc) -> Doc:
        with self._lock:
            self._col(collection)[doc_id] = copy.deepcopy(data)
            return copy.deepcopy(data)

    def update(self, collection: str, doc_id: str, fields: Doc) -> Doc:
        with self._lock:
            col = self._col(collection)
            if doc_id not in col:
                raise KeyError(f"{collection}/{doc_id}")
            col[doc_id].update(copy.deepcopy(fields))
            return copy.deepcopy(col[doc_id])

    def delete(self, collection: str, doc_id: str) -> None:
        with self._lock:
            self._col(collection).pop(doc_id, None)

    def find(self, collection: str, **equals: Any) -> list[Doc]:
        with self._lock:
            return [
                copy.deepcopy(d)
                for d in self._col(collection).values()
                if all(d.get(k) == v for k, v in equals.items())
            ]


class FirestoreRepository:
    """Cloud Firestore implementation (firebase mode)."""

    def __init__(self, client: Any) -> None:
        self._db = client

    def get(self, collection: str, doc_id: str) -> Doc | None:
        snap = self._db.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def create(self, collection: str, doc_id: str, data: Doc) -> Doc:
        from google.api_core.exceptions import AlreadyExists

        try:
            self._db.collection(collection).document(doc_id).create(data)
        except AlreadyExists as exc:
            raise AlreadyExistsError(f"{collection}/{doc_id}") from exc
        return data

    def put(self, collection: str, doc_id: str, data: Doc) -> Doc:
        self._db.collection(collection).document(doc_id).set(data)
        return data

    def update(self, collection: str, doc_id: str, fields: Doc) -> Doc:
        ref = self._db.collection(collection).document(doc_id)
        ref.update(fields)
        return ref.get().to_dict()

    def delete(self, collection: str, doc_id: str) -> None:
        self._db.collection(collection).document(doc_id).delete()

    def find(self, collection: str, **equals: Any) -> list[Doc]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._db.collection(collection)
        for key, value in equals.items():
            query = query.where(filter=FieldFilter(key, "==", value))
        return [snap.to_dict() for snap in query.stream()]
