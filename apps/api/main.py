"""Point d'entrée FastAPI - Mada Settlement Lab."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db
from .routers import admin, audit, auth, records, submissions, users
from .storage import init_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_storage()
    except Exception as exc:  # MinIO peut démarrer plus lentement que l'API
        print(f"[warn] init_storage a échoué : {exc}")
    yield


app = FastAPI(
    title="Mada Settlement Lab",
    version="0.5.0",
    description=(
        "Plateforme sécurisée de contrôle qualité, de traçabilité et d'audit des données "
        "financières. Données fictives uniquement."
    ),
    lifespan=lifespan,
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "service": "mada-settlement-lab", "version": "0.5.0"}


@app.get("/ready", tags=["ops"])
def ready(db: Session = Depends(get_db)) -> dict:
    """Readiness probe : vérifie la connexion à la base."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "not-ready", "database": "error", "error": str(exc)}


@app.get("/", tags=["ops"])
def root() -> dict:
    return {"message": "Mada Settlement Lab API", "docs": "/docs", "health": "/health"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(submissions.router, prefix="/submissions", tags=["submissions"])
app.include_router(records.router, prefix="/records", tags=["records"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
