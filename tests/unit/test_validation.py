from pathlib import Path

from apps.api.validation import validate_csv

DATA = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def codes(errors):
    return [e["rule_code"] for e in errors]


def test_valid_file_has_no_errors():
    content = (DATA / "valid" / "declaration_2026_01.csv").read_bytes()
    assert validate_csv(content) == []


def test_missing_column_is_reported():
    content = (DATA / "invalid" / "missing_column.csv").read_bytes()
    errors = validate_csv(content)
    assert len(errors) == 1
    assert errors[0]["rule_code"] == "MISSING_COLUMN"
    assert errors[0]["field"] == "currency"


def test_business_errors_have_row_field_code_message():
    content = (DATA / "invalid" / "business_errors.csv").read_bytes()
    errors = validate_csv(content)
    assert codes(errors) == [
        "PERIOD_FORMAT",
        "INDICATOR_UNKNOWN",
        "AMOUNT_NEGATIVE",
        "AMOUNT_NOT_NUMERIC",
        "CURRENCY_UNKNOWN",
    ]
    assert [e["row_number"] for e in errors] == [3, 4, 5, 6, 7]
    for e in errors:
        assert e["field"] and e["message"]


def test_header_only_file_is_rejected():
    content = (DATA / "edge-cases" / "header_only.csv").read_bytes()
    assert codes(validate_csv(content)) == ["NO_ROWS"]


def test_empty_file():
    assert codes(validate_csv(b"")) == ["EMPTY_FILE"]


def test_invalid_encoding():
    assert codes(validate_csv(b"\xff\xfe\x00\x01\x80")) == ["INVALID_ENCODING"]
