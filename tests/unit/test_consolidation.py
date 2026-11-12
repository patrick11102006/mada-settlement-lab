import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from apps.api.consolidation import ConsolidationError, consolidate_submission, parse_records
from apps.api.main import app
from apps.api.validation import validate_csv

client = TestClient(app)
HEADER = "period,indicator_code,amount,currency\n"


def test_parse_records_keeps_file_line_numbers_and_decimals():
    rows = parse_records((HEADER + "2026-01,DEPOSITS,1500000.50,MGA\n2026-01,NPL_RATIO,0.042,MGA\n").encode())
    assert [r["row_number"] for r in rows] == [2, 3]
    assert rows[0]["amount"] == Decimal("1500000.50")
    assert rows[1]["amount"] == Decimal("0.042")
    assert rows[0]["currency"] == "MGA"


def test_parse_records_rejects_out_of_range_amount():
    with pytest.raises(ConsolidationError):
        parse_records((HEADER + "2026-01,LOANS,99999999999999999,MGA\n").encode())


def test_infinity_is_rejected_by_validation():
    errors = validate_csv((HEADER + "2026-01,LOANS,inf,MGA\n").encode())
    assert [e["rule_code"] for e in errors] == ["AMOUNT_NOT_NUMERIC"]


def test_only_accepted_submissions_are_consolidated():
    s = SimpleNamespace(status="REJETE", organization_id=uuid.uuid4(), id=uuid.uuid4())
    with pytest.raises(ConsolidationError):
        consolidate_submission(db=None, submission=s, content=b"")


def test_already_consolidated_is_a_noop():
    s = SimpleNamespace(status="CONSOLIDE", organization_id=uuid.uuid4(), id=uuid.uuid4())
    assert consolidate_submission(db=None, submission=s, content=b"") == 0


def test_submission_without_organization_is_refused():
    s = SimpleNamespace(status="ACCEPTE", organization_id=None, id=uuid.uuid4())
    with pytest.raises(ConsolidationError):
        consolidate_submission(db=None, submission=s, content=b"")


@pytest.mark.parametrize("method,url", [
    ("get", "/records/"),
    ("get", "/records/summary"),
    ("post", f"/submissions/{uuid.uuid4()}/consolidate"),
])
def test_new_endpoints_require_token(method, url):
    assert getattr(client, method)(url).status_code == 401
