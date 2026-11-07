import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Submission
from ..models import ValidationError as ValidationErrorRow
from ..storage import upload_file
from ..validation import validate_csv

router = APIRouter()

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 Mo


def _error_to_dict(e: ValidationErrorRow) -> dict:
    return {
        "row_number": e.row_number,
        "field": e.field,
        "rule_code": e.rule_code,
        "message": e.message,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_submission(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = file.filename or ""

    # 1. Contrôles d'entrée : type et taille
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Seuls les fichiers .csv sont acceptés")
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Fichier trop volumineux (max 5 Mo)")

    # 2. Checksum et anti-doublon (idempotence)
    checksum = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Submission).where(Submission.checksum == checksum))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Fichier déjà soumis (ID: {existing.id})")

    # 3. Stockage objet puis enregistrement : statut RECU
    upload_file(content, f"{checksum}_{filename}")
    submission = Submission(filename=filename, checksum=checksum, status="RECU")
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # 4. Validation : statut EN_VALIDATION
    submission.status = "EN_VALIDATION"
    db.commit()
    errors = validate_csv(content)

    # 5. Résultat : ACCEPTE ou REJETE
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


@router.get("/{submission_id}")
def get_submission(submission_id: uuid.UUID, db: Session = Depends(get_db)):
    s = db.get(Submission, submission_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Déclaration introuvable")
    return {
        "id": s.id,
        "filename": s.filename,
        "checksum": s.checksum,
        "status": s.status,
        "received_at": s.received_at,
        "processed_at": s.processed_at,
    }


@router.get("/{submission_id}/errors")
def get_submission_errors(submission_id: uuid.UUID, db: Session = Depends(get_db)):
    if db.get(Submission, submission_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Déclaration introuvable")
    rows = db.scalars(
        select(ValidationErrorRow)
        .where(ValidationErrorRow.submission_id == submission_id)
        .order_by(ValidationErrorRow.row_number)
    ).all()
    return {"submission_id": submission_id, "error_count": len(rows), "errors": [_error_to_dict(r) for r in rows]}
