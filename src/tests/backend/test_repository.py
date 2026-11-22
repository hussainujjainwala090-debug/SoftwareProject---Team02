"""In-memory store used by memory mode and the tests."""
import pytest

from app.repository import AlreadyExistsError, MemoryRepository


def test_create_refuses_duplicate_ids():
    repo = MemoryRepository()
    repo.create("scans", "s1", {"scan_id": "s1"})
    with pytest.raises(AlreadyExistsError):
        repo.create("scans", "s1", {"scan_id": "s1"})


def test_find_filters_on_every_field_and_returns_copies():
    repo = MemoryRepository()
    repo.put("farms", "a", {"farm_id": "a", "owner_id": "u1", "name": "A"})
    repo.put("farms", "b", {"farm_id": "b", "owner_id": "u2", "name": "B"})
    found = repo.find("farms", owner_id="u1")
    assert [f["farm_id"] for f in found] == ["a"]
    found[0]["name"] = "changed"
    assert repo.get("farms", "a")["name"] == "A"


def test_update_missing_document_raises():
    with pytest.raises(KeyError):
        MemoryRepository().update("farms", "nope", {"name": "x"})
