import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.validation import validate_csv

H = "period,indicator_code,amount,currency\n"
client = TestClient(app)
DATA = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def found(errors):
    return [(e["rule_code"], e["row_number"]) for e in errors]


def test_duplicate_is_flagged_on_second_occurrence():
    c = (H + "2026-01,LOANS,100,MGA\n2026-01,LOANS,200,MGA\n").encode()
    assert found(validate_csv(c)) == [("DUPLICATE_ROW", 3)]


def test_same_indicator_in_other_currency_is_not_a_duplicate():
    c = (H + "2026-01,LOANS,100,MGA\n2026-01,LOANS,100,EUR\n").encode()
    assert validate_csv(c) == []


def test_ratio_above_one_is_flagged_but_bounds_are_accepted():
    assert found(validate_csv((H + "2026-01,NPL_RATIO,1.5,MGA\n").encode())) == [("RATIO_OUT_OF_RANGE", 2)]
    assert validate_csv((H + "2026-01,NPL_RATIO,1,MGA\n2026-02,NPL_RATIO,0,MGA\n").encode()) == []


def test_invalid_rows_are_not_also_reported_as_duplicates():
    c = (H + "2026-01,LOANS,-5,MGA\n2026-01,LOANS,-5,MGA\n").encode()
    assert [e["rule_code"] for e in validate_csv(c)] == ["AMOUNT_NEGATIVE", "AMOUNT_NEGATIVE"]


def test_amount_above_limit_is_rejected_at_validation():
    c = (H + "2026-01,LOANS,99999999999999999,MGA\n").encode()
    assert found(validate_csv(c)) == [("AMOUNT_TOO_LARGE", 2)]


def test_inconsistency_dataset():
    content = (DATA / "invalid" / "inconsistencies.csv").read_bytes()
    assert found(validate_csv(content)) == [("DUPLICATE_ROW", 4), ("RATIO_OUT_OF_RANGE", 5)]


def test_quality_endpoint_requires_token():
    assert client.get(f"/submissions/{uuid.uuid4()}/quality").status_code == 401
