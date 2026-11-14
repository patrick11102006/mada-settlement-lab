"""Ecriture et lecture du journal d'audit (acces base de donnees)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .audit_chain import GENESIS_HASH, canonical_json, seal_event
from .config import get_settings
from .models import AuditEvent

LOCK_KEY = 7340101  # verrou applicatif : serialise l'ecriture de la chaine
DEV_KEY = "dev-only-audit-key-change-me"


def get_key() -> str:
    settings = get_settings()
    if settings.APP_ENV != "dev" and settings.AUDIT_HMAC_KEY == DEV_KEY:
        raise RuntimeError("AUDIT_HMAC_KEY par defaut interdite hors environnement dev")
    return settings.AUDIT_HMAC_KEY


def record_event(db: Session, *, action: str, resource_type: str, resource_id: str | None = None,
                 actor_id: uuid.UUID | None = None, outcome: str = "SUCCESS",
                 payload: dict | None = None, commit: bool = True) -> AuditEvent:
    """Ajoute un evenement a la fin de la chaine.

    Le verrou garantit qu'un seul evenement a la fois lit la queue et s'y rattache.
    Les payloads ne doivent jamais contenir de mot de passe, de token ni de contenu sensible.
    """
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_KEY})
    last = db.scalar(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
    seq = 1 if last is None else last.seq + 1
    previous_hash = GENESIS_HASH if last is None else last.event_hash

    event_id = uuid.uuid4()
    ts = datetime.now(timezone.utc)
    payload_text = canonical_json(payload or {})
    resource_id = None if resource_id is None else str(resource_id)[:80]
    sealed = seal_event(
        get_key(), seq=seq, event_id=event_id, timestamp=ts, actor_id=actor_id,
        action=action[:80], resource_type=resource_type[:50], resource_id=resource_id,
        outcome=outcome, payload_text=payload_text, previous_hash=previous_hash,
    )
    event = AuditEvent(
        id=event_id, seq=seq, timestamp=ts, actor_id=actor_id, action=action[:80],
        resource_type=resource_type[:50], resource_id=resource_id, outcome=outcome,
        payload=payload_text, previous_hash=previous_hash, **sealed,
    )
    db.add(event)
    if commit:
        db.commit()
    else:
        db.flush()
    return event


def iter_events(db: Session, batch: int = 1000):
    """Parcourt tout le journal par ordre de seq, par lots (memoire bornee)."""
    last = 0
    while True:
        rows = db.scalars(
            select(AuditEvent).where(AuditEvent.seq > last).order_by(AuditEvent.seq).limit(batch)
        ).all()
        if not rows:
            return
        yield from rows
        last = rows[-1].seq
