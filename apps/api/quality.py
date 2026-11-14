"""Règles de cohérence entre lignes d'un même fichier (contrôle qualité)."""
import pandas as pd

PERIOD_RE = r"^\d{4}-(0[1-9]|1[0-2])$"
MAX_AMOUNT = 1e16  # limite de la colonne Numeric(20,4)


def _err(row: int, field: str, code: str, message: str) -> dict:
    return {"row_number": row, "field": field, "rule_code": code, "message": message}


def cross_row_rules(df: pd.DataFrame, allowed_indicators, allowed_currencies) -> list[dict]:
    """Détecte les incohérences qu'une vérification ligne par ligne ne voit pas.

    - DUPLICATE_ROW : même (période, indicateur, devise) qu'une ligne précédente.
    - RATIO_OUT_OF_RANGE : NPL_RATIO supérieur à 1.
    Seules les lignes sans autre erreur sont examinées.
    """
    amount = pd.to_numeric(df["amount"], errors="coerce")
    clean = (
        df["period"].str.match(PERIOD_RE)
        & df["indicator_code"].isin(allowed_indicators)
        & df["currency"].isin(allowed_currencies)
        & (amount.abs() < MAX_AMOUNT)
        & (amount >= 0)
    )
    errors: list[dict] = []

    ratio_bad = clean & (df["indicator_code"] == "NPL_RATIO") & (amount > 1)
    for idx in df.index[ratio_bad.to_numpy()]:
        errors.append(
            _err(int(idx) + 2, "amount", "RATIO_OUT_OF_RANGE",
                 f"Un ratio doit être compris entre 0 et 1 (valeur : {df.at[idx, 'amount']!r})")
        )

    sub = df[clean]
    dup = sub.duplicated(subset=["period", "indicator_code", "currency"], keep="first")
    for idx in sub.index[dup.to_numpy()]:
        errors.append(
            _err(int(idx) + 2, "indicator_code", "DUPLICATE_ROW",
                 "Ligne en double : même période, indicateur et devise qu'une ligne précédente")
        )
    return errors
