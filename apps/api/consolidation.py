"""Consolidation d'un dépôt ACCEPTE vers financial_records (atomique et idempotente)."""
import io
import uuid
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import FinancialRecord, Submission

BATCH_SIZE = 1000
MAX_ABS_AMOUNT = Decimal(10) ** 16  # limite de Numeric(20,4)


class ConsolidationError(Exception):
    """Erreur métier : le dépôt ne peut pas être consolidé."""


def parse_records(content: bytes) -> list[dict]:
    """Transforme le CSV (déjà validé) en lignes prêtes à insérer.

    row_number = numéro de ligne dans le fichier (l'en-tête est la ligne 1),
    comme dans le rapport d'erreurs.
    """
    df = pd.read_csv(io.StringIO(content.decode("utf-8-sig")), dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    rows = []
    for line, rec in enumerate(df.to_dict("records"), start=2):
        try:
            amount = Decimal(rec["amount"])
        except InvalidOperation as exc:
            raise ConsolidationError(f"Ligne {line} : montant illisible") from exc
        if not amount.is_finite() or abs(amount) >= MAX_ABS_AMOUNT:
            raise ConsolidationError(f"Ligne {line} : montant hors limites")
        rows.append(
            {
                "row_number": line,
                "period": rec["period"],
                "indicator_code": rec["indicator_code"],
                "amount": amount,
                "currency": rec["currency"],
            }
        )
    return rows


def consolidate_submission(db: Session, submission: Submission, content: bytes) -> int:
    """Insère les lignes une seule fois et passe le dépôt à CONSOLIDE.

    Renvoie le nombre de lignes réellement insérées (0 si déjà consolidé).
    Tout est dans une transaction : en cas d'erreur, l'appelant fait rollback.
    """
    if submission.status == "CONSOLIDE":
        return 0
    if submission.status != "ACCEPTE":
        raise ConsolidationError(f"Statut {submission.status} : seul ACCEPTE peut être consolidé")
    if submission.organization_id is None:
        raise ConsolidationError("Dépôt sans organisation : consolidation impossible")

    rows = parse_records(content)
    inserted = 0
    for start in range(0, len(rows), BATCH_SIZE):
        chunk = [
            {
                "id": uuid.uuid4(),
                "submission_id": submission.id,
                "organization_id": submission.organization_id,
                **r,
            }
            for r in rows[start : start + BATCH_SIZE]
        ]
        stmt = (
            pg_insert(FinancialRecord)
            .values(chunk)
            .on_conflict_do_nothing(constraint="uq_record_submission_row")
        )
        inserted += len(db.execute(stmt.returning(FinancialRecord.id)).all())

    submission.status = "CONSOLIDE"
    db.commit()
    return inserted
