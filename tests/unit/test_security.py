from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.security import (
    can_access_submission, create_access_token, decode_access_token,
    hash_password, require_role, verify_password,
)

client = TestClient(app)
ORG_A, ORG_B = uuid.uuid4(), uuid.uuid4()


def test_password_hash_roundtrip():
    h = hash_password("MotDePasse-Long-123")
    assert h != "MotDePasse-Long-123"
    assert verify_password("MotDePasse-Long-123", h)
    assert not verify_password("autre", h)


def test_token_roundtrip_and_tampering():
    token = create_access_token("abc", "declarant")
    assert decode_access_token(token)["role"] == "declarant"
    assert decode_access_token(token + "x") == {}


def test_declarant_cannot_access_other_organization():
    user = SimpleNamespace(role="declarant", organization_id=ORG_A)
    assert can_access_submission(user, SimpleNamespace(organization_id=ORG_A))
    assert not can_access_submission(user, SimpleNamespace(organization_id=ORG_B))


def test_declarant_without_organization_has_no_access():
    user = SimpleNamespace(role="declarant", organization_id=None)
    assert not can_access_submission(user, SimpleNamespace(organization_id=None))


@pytest.mark.parametrize("role", ["analyste", "auditeur", "admin"])
def test_read_all_roles_access_everything(role):
    user = SimpleNamespace(role=role, organization_id=None)
    assert can_access_submission(user, SimpleNamespace(organization_id=ORG_A))


def test_require_role_rejects_wrong_role():
    checker = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        checker(user=SimpleNamespace(role="declarant"))
    assert exc.value.status_code == 403
    assert checker(user=SimpleNamespace(role="admin")).role == "admin"


@pytest.mark.parametrize("method,url", [
    ("get", "/users/me"), ("get", "/submissions/"),
    ("post", "/admin/organizations"), ("post", "/admin/users"),
])
def test_protected_endpoints_require_token(method, url):
    assert getattr(client, method)(url).status_code == 401


def test_upload_without_token_is_rejected():
    r = client.post("/submissions/", files={"file": ("a.csv", b"x", "text/csv")})
    assert r.status_code == 401
