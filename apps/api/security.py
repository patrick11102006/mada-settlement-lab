"""Hachage de mot de passe, JWT et contrôle d'accès par rôle (RBAC)."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User

settings = get_settings()

ROLES = ("declarant", "analyste", "auditeur", "admin")
READ_ALL_ROLES = ("analyste", "auditeur", "admin")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return {}


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except (ValueError, TypeError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.active:
        raise unauthorized
    return user


def require_role(*roles: str) -> Callable:
    """Dépendance FastAPI : exige que l'utilisateur ait l'un des rôles donnés."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Rôle insuffisant")
        return user

    return checker


def can_access_submission(user, submission) -> bool:
    """Un déclarant n'accède qu'aux dépôts de son organisation."""
    if user.role in READ_ALL_ROLES:
        return True
    return user.organization_id is not None and user.organization_id == submission.organization_id
