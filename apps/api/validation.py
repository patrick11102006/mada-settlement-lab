"""Validation des fichiers CSV de déclaration (Pandera).

validate_csv est pure : elle prend des octets et renvoie une liste d'erreurs.
Elle ne touche ni la base ni MinIO, donc elle se teste facilement.
"""
import io

import pandas as pd

try:
    import pandera.pandas as pa
except ImportError:  # anciennes versions de pandera
    import pandera as pa
from pandera.errors import SchemaErrors

from .quality import MAX_AMOUNT, cross_row_rules

REQUIRED_COLUMNS = ["period", "indicator_code", "amount", "currency"]
ALLOWED_INDICATORS = {"DEPOSITS", "LOANS", "NPL_RATIO"}
ALLOWED_CURRENCIES = {"MGA", "EUR", "USD"}
MAX_ERRORS = 1000  # protège la base contre un fichier qui génère trop d'erreurs

MESSAGES = {
    "PERIOD_FORMAT": "La période doit être au format AAAA-MM (mois de 01 à 12)",
    "INDICATOR_UNKNOWN": "Code indicateur inconnu",
    "AMOUNT_NOT_NUMERIC": "Le montant doit être un nombre fini",
    "AMOUNT_TOO_LARGE": "Le montant dépasse la limite autorisée (10^16)",
    "AMOUNT_NEGATIVE": "Le montant ne peut pas être négatif",
    "CURRENCY_UNKNOWN": "Devise non autorisée (MGA, EUR ou USD)",
}


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _not_too_large(series: pd.Series) -> pd.Series:
    """Faux seulement pour une valeur finie dont la valeur absolue dépasse la limite."""
    a = _num(series).abs()
    return ~((a >= MAX_AMOUNT) & (a < float("inf")))


SCHEMA = pa.DataFrameSchema(
    {
        "period": pa.Column(
            checks=[
                pa.Check(
                    lambda s: s.str.match(r"^\d{4}-(0[1-9]|1[0-2])$"),
                    name="PERIOD_FORMAT",
                )
            ]
        ),
        "indicator_code": pa.Column(
            checks=[pa.Check(lambda s: s.isin(ALLOWED_INDICATORS), name="INDICATOR_UNKNOWN")]
        ),
        "amount": pa.Column(
            checks=[
                pa.Check(lambda s: _num(s).abs() < float("inf"), name="AMOUNT_NOT_NUMERIC"),
                pa.Check(_not_too_large, name="AMOUNT_TOO_LARGE"),
                pa.Check(lambda s: _num(s).fillna(0) >= 0, name="AMOUNT_NEGATIVE"),
            ]
        ),
        "currency": pa.Column(
            checks=[pa.Check(lambda s: s.isin(ALLOWED_CURRENCIES), name="CURRENCY_UNKNOWN")]
        ),
    },
    strict=False,
)


def _err(row: int, field: str | None, code: str, message: str) -> dict:
    return {"row_number": row, "field": field, "rule_code": code, "message": message}


def validate_csv(content: bytes) -> list[dict]:
    """Renvoie la liste des erreurs. Liste vide = fichier valide.

    row_number = numéro de ligne dans le fichier (l'en-tête est la ligne 1).
    row_number = 0 pour une erreur qui concerne le fichier entier.
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [_err(0, None, "INVALID_ENCODING", "Le fichier doit être encodé en UTF-8")]

    if not text.strip():
        return [_err(0, None, "EMPTY_FILE", "Le fichier est vide")]

    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return [_err(0, None, "INVALID_CSV", f"CSV illisible : {str(exc)[:150]}")]

    df.columns = [str(c).strip() for c in df.columns]

    errors: list[dict] = []
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            errors.append(_err(0, col, "MISSING_COLUMN", f"Colonne obligatoire absente : {col}"))
    for col in df.columns:
        if col not in REQUIRED_COLUMNS:
            errors.append(_err(0, col, "UNEXPECTED_COLUMN", f"Colonne non prévue : {col}"))
    if any(e["rule_code"] == "MISSING_COLUMN" for e in errors):
        return errors  # inutile de contrôler les lignes sans le bon schéma

    if df.empty:
        return errors + [_err(0, None, "NO_ROWS", "Le fichier ne contient aucune ligne de données")]

    try:
        SCHEMA.validate(df, lazy=True)
    except SchemaErrors as exc:
        for _, case in exc.failure_cases.iterrows():
            idx = case["index"]
            row = 0 if pd.isna(idx) else int(idx) + 2
            code = str(case["check"])
            value = str(case["failure_case"])[:80]
            message = f"{MESSAGES.get(code, 'Règle non respectée')} (valeur : {value!r})"
            errors.append(_err(row, str(case["column"]), code, message))

    # Contrôle qualité entre lignes (doublons, ratios hors bornes)
    errors.extend(cross_row_rules(df, ALLOWED_INDICATORS, ALLOWED_CURRENCIES))

    errors.sort(key=lambda e: (e["row_number"], e["field"] or ""))
    return errors[:MAX_ERRORS]
