from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.security import require_role

client = TestClient(app)


@pytest.mark.parametrize("url", ["/audit/events", "/audit/head", "/audit/verify"])
def test_audit_endpoints_require_token(url):
    assert client.get(url).status_code == 401


@pytest.mark.parametrize("role", ["auditeur", "admin"])
def test_auditor_and_admin_can_read_audit(role):
    checker = require_role("auditeur", "admin")
    assert checker(user=SimpleNamespace(role=role)).role == role


@pytest.mark.parametrize("role", ["declarant", "analyste"])
def test_other_roles_cannot_read_audit(role):
    checker = require_role("auditeur", "admin")
    with pytest.raises(HTTPException) as exc:
        checker(user=SimpleNamespace(role=role))
    assert exc.value.status_code == 403
