"""Consultation et verification du journal d'audit (roles auditeur et admin)."""
import json
import time
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import get_key, iter_events, record_event
from ..audit_chain import GENESIS_HASH, verify_chain
from ..db import get_db
from ..models import AuditEvent, User
from ..security import require_role

router = APIRouter()
AUDIT_ROLES = ("auditeur", "admin")


def _payload(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return text


@router.get("/events")
def list_events(
    action: str | None = None,
    before_seq: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(*AUDIT_ROLES)),
):
    """Evenements du plus recent au plus ancien."""
    limit = max(1, min(limit, 200))
    q = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit)
    if action:
        q = q.where(AuditEvent.action == action.upper())
    if before_seq is not None:
        q = q.where(AuditEvent.seq < before_seq)
    return [
        {
            "seq": e.seq, "timestamp": e.timestamp, "actor_id": e.actor_id, "action": e.action,
            "resource_type": e.resource_type, "resource_id": e.resource_id, "outcome": e.outcome,
            "payload": _payload(e.payload), "event_hash": e.event_hash,
        }
        for e in db.scalars(q).all()
    ]


@router.get("/head")
def head(db: Session = Depends(get_db), _user: User = Depends(require_role(*AUDIT_ROLES))):
    """Tete de chaine : a conserver hors de la base comme ancre de confiance."""
    last = db.scalar(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
    if last is None:
        return {"seq": 0, "event_hash": GENESIS_HASH}
    return {"seq": last.seq, "event_hash": last.event_hash, "timestamp": last.timestamp}


@router.get("/verify")
def verify(
    expect_seq: int | None = None,
    expect_hash: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(*AUDIT_ROLES)),
):
    if (expect_seq is None) != (expect_hash is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "expect_seq et expect_hash vont ensemble")
    uid = user.id
    start = time.perf_counter()
    result = verify_chain(iter_events(db), get_key(), expect_seq, expect_hash)
    elapsed = time.perf_counter() - start
    record_event(
        db, action="AUDIT_VERIFIED", resource_type="audit_log", actor_id=uid,
        outcome="SUCCESS" if result.ok else "FAILURE",
        payload={"ok": result.ok, "count": result.count, "break_seq": result.break_seq},
    )
    return {**asdict(result), "duration_s": round(elapsed, 3)}
