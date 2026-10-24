import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, dashboard, findings, organizations, reports, scans
from app.core.config import settings
from app.database import Base, engine
from app import models  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Alembic is the deployment migration path; create_all keeps fresh local SQLite runs simple.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", description="Authorized, non-destructive attack surface inventory and assessment.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins.split(","), allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])
app.include_router(organizations.router)
app.include_router(scans.router)
app.include_router(assets.router)
app.include_router(findings.router)
app.include_router(dashboard.router)
app.include_router(reports.router)


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "surfaceguard-api"}