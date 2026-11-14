from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_event
from ..db import get_db
from ..models import User
from ..security import create_access_token, verify_password

router = APIRouter()


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username[:200]
    user = db.scalar(select(User).where(User.email == email))
    # Meme message pour "inconnu" et "mauvais mot de passe" : pas de fuite d'information
    if not user or not verify_password(form_data.password, user.password_hash):
        record_event(
            db, action="LOGIN_FAILED", resource_type="user",
            resource_id=str(user.id) if user else None,
            outcome="FAILURE", payload={"email": email, "reason": "bad_credentials"},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect")
    if not user.active:
        record_event(
            db, action="LOGIN_FAILED", resource_type="user", resource_id=str(user.id),
            actor_id=user.id, outcome="FAILURE", payload={"email": email, "reason": "inactive"},
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Compte désactivé")
    token = create_access_token(subject=str(user.id), role=user.role)
    record_event(
        db, action="LOGIN_SUCCESS", resource_type="user", resource_id=str(user.id),
        actor_id=user.id, payload={"role": user.role},
    )
    return {"access_token": token, "token_type": "bearer"}
