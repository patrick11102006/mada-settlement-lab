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


class _FakeResult:
    def __init__(self, n):
        self._n = n

    def all(self):
        return [object()] * self._n


class _FakeDB:
    """Simule la base : renvoie n lignes insérées (RETURNING), 0 en cas de conflit."""

    def __init__(self, inserted_per_batch):
        self._n = inserted_per_batch
        self.committed = False

    def execute(self, stmt):
        return _FakeResult(self._n)

    def commit(self):
        self.committed = True


def _accepted():
    return SimpleNamespace(status="ACCEPTE", organization_id=uuid.uuid4(), id=uuid.uuid4())


def test_inserted_count_comes_from_returning_not_rowcount():
    content = (HEADER + "2026-01,LOANS,1,MGA\n2026-01,DEPOSITS,2,MGA\n2026-01,NPL_RATIO,0.1,MGA\n").encode()
    s, db = _accepted(), _FakeDB(3)
    assert consolidate_submission(db, s, content) == 3
    assert s.status == "CONSOLIDE" and db.committed


def test_conflicts_insert_nothing_but_submission_becomes_consolidated():
    content = (HEADER + "2026-01,LOANS,1,MGA\n").encode()
    s, db = _accepted(), _FakeDB(0)
    assert consolidate_submission(db, s, content) == 0
    assert s.status == "CONSOLIDE"
