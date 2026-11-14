"""Gestion des organisations et des utilisateurs (admin uniquement)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_event
from ..db import get_db
from ..models import Organization, User
from ..security import ROLES, hash_password, require_role

router = APIRouter()


class OrganizationCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)


class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=128)
    role: str
    organization_id: uuid.UUID | None = None


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    aid = admin.id
    if db.scalar(select(Organization).where(Organization.code == payload.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Code d'organisation déjà utilisé")
    org = Organization(code=payload.code, name=payload.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    record_event(
        db, action="ORGANIZATION_CREATED", resource_type="organization", resource_id=str(org.id),
        actor_id=aid, payload={"code": org.code},
    )
    return {"id": org.id, "code": org.code, "name": org.name}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    aid = admin.id
    if payload.role not in ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Rôle invalide : {ROLES}")
    if payload.role == "declarant" and payload.organization_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Un déclarant doit avoir une organisation")
    if payload.organization_id and db.get(Organization, payload.organization_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation introuvable")
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email déjà utilisé")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        organization_id=payload.organization_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    record_event(
        db, action="USER_CREATED", resource_type="user", resource_id=str(user.id), actor_id=aid,
        payload={
            "email": user.email, "role": user.role,
            "organization_id": None if user.organization_id is None else str(user.organization_id),
        },
    )
    return {"id": user.id, "email": user.email, "role": user.role, "organization_id": user.organization_id}
