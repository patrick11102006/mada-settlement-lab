"""Point d'entrée FastAPI — Mada Settlement Lab.

Sprint 1 — uniquement /health et /ready pour valider que le serveur tourne.
Les endpoints métier (auth, submissions, audit) viendront dans les prochains sprints.
"""
from fastapi import FastAPI

app = FastAPI(
    title="Mada Settlement Lab",
    version="0.1.0",
    description=(
        "Plateforme académique de collecte, validation, consolidation et audit "
        "de déclarations financières synthétiques. Données fictives uniquement."
    ),
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness probe — le serveur répond-il ?"""
    return {"status": "ok", "service": "mada-settlement-lab", "version": "0.1.0"}


@app.get("/ready", tags=["ops"])
def ready() -> dict:
    """Readiness probe — trivial aujourd'hui, deviendra un check DB plus tard."""
    return {"status": "ready"}


@app.get("/", tags=["ops"])
def root() -> dict:
    """Petite aide pour qui ouvre le navigateur."""
    return {
        "message": "Mada Settlement Lab API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }
