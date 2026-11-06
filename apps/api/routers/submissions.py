import hashlib

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Submission
from ..storage import upload_file

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_submission(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Lire le contenu
    content = await file.read()

    # 2. Calculer le checksum SHA-256
    checksum = hashlib.sha256(content).hexdigest()

    # 3. Vérifier les doublons (idempotence)
    existing = db.scalar(select(Submission).where(Submission.checksum == checksum))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Fichier déjà soumis (ID: {existing.id})",
        )

    # 4. Envoyer dans MinIO
    object_name = f"{checksum}_{file.filename}"
    upload_file(content, object_name)

    # 5. Enregistrer en base
    submission = Submission(filename=file.filename, checksum=checksum, status="RECU")
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {
        "id": submission.id,
        "filename": submission.filename,
        "checksum": checksum,
        "status": submission.status,
    }
