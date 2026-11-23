"""File storage for leaf images, overlay images and PDF reports (NFR-12).

The database keeps a storage reference ("local://..." or "gs://bucket/...") in
image_url, overlay_url and pdf_url. links() turns a reference into a URL the
app can open: a direct local URL, or a signed Cloud Storage URL that expires.
"""
import re
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Protocol

_SAFE = re.compile(r"^[a-z_]+/[0-9a-f]{32}\.(jpg|png|pdf)$")


class Storage(Protocol):
    def upload(self, folder: str, data: bytes, ext: str, content_type: str) -> str:
        """Store bytes and return the storage reference."""
        ...

    def download(self, ref: str) -> bytes: ...

    def link(self, ref: str | None) -> str | None:
        """A URL the client can open for this reference."""
        ...


class LocalFileStorage:
    """Writes files under a local folder; served by GET /files/... (memory mode)."""

    def __init__(self, base_dir: str | Path, public_base_url: str) -> None:
        self._base = Path(base_dir)
        self._url = public_base_url.rstrip("/")

    def upload(self, folder: str, data: bytes, ext: str, content_type: str) -> str:
        rel = f"{folder}/{uuid.uuid4().hex}.{ext}"
        path = self._base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"local://{rel}"

    def path_for(self, rel: str) -> Path | None:
        """Resolve a relative file path, refusing anything outside the store."""
        if not _SAFE.match(rel):
            return None
        path = self._base / rel
        return path if path.is_file() else None

    def download(self, ref: str) -> bytes:
        path = self.path_for(ref.removeprefix("local://"))
        if path is None:
            raise FileNotFoundError(ref)
        return path.read_bytes()

    def link(self, ref: str | None) -> str | None:
        if not ref:
            return None
        return f"{self._url}/files/{ref.removeprefix('local://')}"


class FirebaseStorage:
    def __init__(self, firebase_app, bucket_name: str, link_ttl_days: int = 7) -> None:
        from firebase_admin import storage

        self._bucket = storage.bucket(bucket_name, app=firebase_app)
        self._ttl = timedelta(days=link_ttl_days)

    def upload(self, folder: str, data: bytes, ext: str, content_type: str) -> str:
        name = f"{folder}/{uuid.uuid4().hex}.{ext}"
        self._bucket.blob(name).upload_from_string(data, content_type=content_type)
        return f"gs://{self._bucket.name}/{name}"

    def _blob(self, ref: str):
        return self._bucket.blob(ref.removeprefix(f"gs://{self._bucket.name}/"))

    def download(self, ref: str) -> bytes:
        return self._blob(ref).download_as_bytes()

    def link(self, ref: str | None) -> str | None:
        if not ref:
            return None
        return self._blob(ref).generate_signed_url(expiration=self._ttl, version="v4")
