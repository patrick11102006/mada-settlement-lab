"""Lecture des données consolidées, avec isolation par organisation."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import FinancialRecord, User
from ..security import READ_ALL_ROLES, get_current_user

router = APIRouter()


def _scoped(query, user: User):
    """Un déclarant ne voit que les lignes de son organisation."""
    if user.role not in READ_ALL_ROLES:
        query = query.where(FinancialRecord.organization_id == user.organization_id)
    return query


@router.get("/")
def list_records(
    period: str | None = None,
    indicator_code: str | None = None,
    organization_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 500))
    q = select(FinancialRecord).order_by(
        FinancialRecord.period, FinancialRecord.submission_id, FinancialRecord.row_number
    )
    q = _scoped(q, user)
    if period:
        q = q.where(FinancialRecord.period == period)
    if indicator_code:
        q = q.where(FinancialRecord.indicator_code == indicator_code.upper())
    if organization_id and user.role in READ_ALL_ROLES:
        q = q.where(FinancialRecord.organization_id == organization_id)
    rows = db.scalars(q.limit(limit).offset(max(0, offset))).all()
    return [
        {
            "submission_id": r.submission_id,
            "organization_id": r.organization_id,
            "row_number": r.row_number,
            "period": r.period,
            "indicator_code": r.indicator_code,
            "amount": str(r.amount),
            "currency": r.currency,
        }
        for r in rows
    ]


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Totaux par période, indicateur et devise (on n'additionne jamais deux devises)."""
    q = (
        select(
            FinancialRecord.period,
            FinancialRecord.indicator_code,
            FinancialRecord.currency,
            func.count().label("lines"),
            func.sum(FinancialRecord.amount).label("total"),
        )
        .group_by(FinancialRecord.period, FinancialRecord.indicator_code, FinancialRecord.currency)
        .order_by(FinancialRecord.period, FinancialRecord.indicator_code)
    )
    q = _scoped(q, user)
    return [
        {"period": p, "indicator_code": i, "currency": c, "lines": n, "total": str(t)}
        for p, i, c, n, t in db.execute(q).all()
    ]
