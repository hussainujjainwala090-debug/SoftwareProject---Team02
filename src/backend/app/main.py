"""AgriScan backend (application tier of ARCH-1).

Run:  uvicorn app.main:app --reload       (from src/backend)
Docs: http://localhost:8000/docs
"""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.adapters.storage import LocalFileStorage
from app.api import alerts, farms, knowledge_base, scans, users
from app.config import Settings, get_settings
from app.container import Container, build_container
from app.errors import ServiceError
from app.seed_data import SEED_DISEASES

log = logging.getLogger("agriscan")
API = "/api/v1"


async def _alert_loop(c: Container, minutes: int) -> None:
    while True:
        await asyncio.sleep(minutes * 60)
        try:
            results = await asyncio.to_thread(c.forecast.check_alerts)
            log.info("Climate alert check: %d farms, %d alerts sent",
                     len(results), sum(r["sent"] for r in results))
        except Exception:  # keep the schedule running
            log.exception("Climate alert check failed")


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.seed_demo_data:
            added = container.kb.seed(SEED_DISEASES)
            log.info("Knowledge base seed: %d entries added", added)
        task = None
        if settings.alert_interval_minutes > 0:
            task = asyncio.create_task(_alert_loop(container, settings.alert_interval_minutes))
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="AgriScan API", version="0.1.0", lifespan=lifespan)
    app.state.container = container
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "mode": settings.mode}

    for module in (users, farms, scans, knowledge_base, alerts):
        app.include_router(module.router, prefix=API)

    if isinstance(container.storage, LocalFileStorage):
        @app.get("/files/{folder}/{name}", include_in_schema=False)
        def local_file(folder: str, name: str):
            """Memory mode only: serve stored images and PDFs (unguessable names)."""
            path = container.storage.path_for(f"{folder}/{name}")
            if path is None:
                raise HTTPException(404, "File not found")
            return FileResponse(path)

    return app


app = create_app()
