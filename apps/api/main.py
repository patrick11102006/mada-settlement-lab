"""Point d'entrée FastAPI — Mada Settlement Lab.

Sprint 1 : /health, /ready
Sprint 2 : /users (liste les utilisateurs depuis PostgreSQL)
"""
from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import engine, get_db
from .models import User

app = FastAPI(
    title="Mada Settlement Lab",
    version="0.2.0",
    description=(
        "Plateforme académique de collecte, validation, consolidation et audit "
        "de déclarations financières synthétiques. Données fictives uniquement."
    ),
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "service": "mada-settlement-lab", "version": "0.2.0"}


@app.get("/ready", tags=["ops"])
def ready(db: Session = Depends(get_db)) -> dict:
    """Readiness probe — vérifie la connexion DB."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "not-ready", "database": "error", "error": str(exc)}


@app.get("/users", tags=["users"])
def list_users(db: Session = Depends(get_db)) -> list[dict]:
    """Liste les utilisateurs (vide au début — on en ajoutera un à l'étape 8)."""
    rows = db.scalars(select(User).order_by(User.created_at)).all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "active": u.active,
        }
        for u in rows
    ]


@app.get("/", tags=["ops"])
def root() -> dict:
    return {
        "message": "Mada Settlement Lab API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
        "users": "/users",
    }