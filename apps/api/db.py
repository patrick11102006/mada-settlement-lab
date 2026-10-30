"""Session SQLAlchemy + Base déclarative."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Base déclarative pour tous les modèles."""
    pass


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI qui fournit une session par requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
