import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Submission, User
from ..models import ValidationError as ValidationErrorRow
from ..security import READ_ALL_ROLES, can_access_submission, get_current_user, require_role
from ..storage import upload_file
from ..validation import validate_csv

router = APIRouter()

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 Mo


def _get_accessible_submission(db: Session, submission_id: uuid.UUID, user: User) -> Submission:
    """Renvoie le dépôt, ou 404 s'il n'existe pas OU si l'utilisateur n'y a pas droit."""
    s = db.get(Submission, submission_id)
    if s is None or not can_access_submission(user, s):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Déclaration introuvable")
    return s


@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_submission(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("declarant")),
):
    if user.organization_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Utilisateur sans organisation")

    filename = (file.filename or "")[:255]
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Seuls les fichiers .csv sont acceptés")
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Fichier trop volumineux (max 5 Mo)")

    checksum = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(Submission).where(
            Submission.organization_id == user.organization_id, Submission.checksum == checksum
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Fichier déjà soumis (ID: {existing.id})")

    # Clé d'objet maîtrisée par le serveur : jamais le nom de fichier de l'utilisateur
    upload_file(content, f"{user.organization_id}/{checksum}.csv")

    submission = Submission(
        organization_id=user.organization_id,
        submitted_by=user.id,
        filename=filename,
        checksum=checksum,
        status="RECU",
    )
    db.add(submission)
    try:
        db.commit()
    except IntegrityError:  # deux dépôts identiques simultanés
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Fichier déjà soumis")
    db.refresh(submission)

    submission.status = "EN_VALIDATION"
    db.commit()
    errors = validate_csv(content)

    if errors:
        db.add_all([ValidationErrorRow(submission_id=submission.id, **e) for e in errors])
        submission.status = "REJETE"
    else:
        submission.status = "ACCEPTE"
    submission.processed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "id": submission.id,
        "filename": submission.filename,
        "checksum": checksum,
        "status": submission.status,
        "error_count": len(errors),
        "errors_preview": errors[:10],
    }


@router.get("/")
def list_submissions(
    status_filter: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 200))
    query = select(Submission).order_by(Submission.received_at.desc()).limit(limit)
    if user.role not in READ_ALL_ROLES:
        query = query.where(Submission.organization_id == user.organization_id)
    if status_filter:
        query = query.where(Submission.status == status_filter.upper())
    rows = db.scalars(query).all()
    return [
        {"id": s.id, "filename": s.filename, "status": s.status,
         "organization_id": s.organization_id, "received_at": s.received_at}
        for s in rows
    ]


@router.get("/{submission_id}")
def get_submission(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = _get_accessible_submission(db, submission_id, user)
    return {
        "id": s.id, "filename": s.filename, "checksum": s.checksum, "status": s.status,
        "organization_id": s.organization_id, "received_at": s.received_at,
        "processed_at": s.processed_at,
    }


@router.get("/{submission_id}/errors")
def get_submission_errors(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_accessible_submission(db, submission_id, user)
    rows = db.scalars(
        select(ValidationErrorRow)
        .where(ValidationErrorRow.submission_id == submission_id)
        .order_by(ValidationErrorRow.row_number)
    ).all()
    return {
        "submission_id": submission_id,
        "error_count": len(rows),
        "errors": [
            {"row_number": r.row_number, "field": r.field, "rule_code": r.rule_code, "message": r.message}
            for r in rows
        ],
    }
