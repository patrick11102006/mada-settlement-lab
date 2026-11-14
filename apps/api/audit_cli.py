"""CLI de verification du journal d'audit.

  python -m apps.api.audit_cli verify
  python -m apps.api.audit_cli verify --expect-seq N --expect-hash H   (avec ancre de confiance)
  python -m apps.api.audit_cli head [--shell]

Codes de sortie : 0 = chaine intacte, 1 = rupture detectee, 2 = erreur d'usage.
"""
import argparse
import sys
import time

from sqlalchemy import select

from .audit import get_key, iter_events
from .audit_chain import GENESIS_HASH, verify_chain
from .db import SessionLocal
from .models import AuditEvent

REASONS = {
    "SEQUENCE_GAP": "evenement manquant ou numerotation modifiee",
    "PREVIOUS_HASH_MISMATCH": "lien avec l'evenement precedent rompu",
    "PAYLOAD_HASH_MISMATCH": "contenu (payload) modifie",
    "EVENT_HASH_MISMATCH": "evenement modifie (ou mauvaise cle HMAC)",
    "TRUNCATED": "journal tronque par rapport a l'ancre",
    "ANCHOR_MISMATCH": "le hash a la position de l'ancre ne correspond pas",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="audit_cli", description="Verification du journal d'audit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="verifie toute la chaine")
    v.add_argument("--expect-seq", type=int, help="seq de l'ancre de confiance")
    v.add_argument("--expect-hash", help="event_hash de l'ancre de confiance")
    h = sub.add_parser("head", help="affiche la tete de chaine (a conserver comme ancre)")
    h.add_argument("--shell", action="store_true", help="sortie utilisable avec eval")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.cmd == "head":
            last = db.scalar(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
            seq, hsh = (0, GENESIS_HASH) if last is None else (last.seq, last.event_hash)
            if args.shell:
                print(f"HEAD_SEQ={seq}")
                print(f"HEAD_HASH={hsh}")
            else:
                print(f"seq={seq}\nhash={hsh}")
            return 0

        if (args.expect_seq is None) != (args.expect_hash is None):
            print("--expect-seq et --expect-hash vont ensemble", file=sys.stderr)
            return 2
        start = time.perf_counter()
        result = verify_chain(iter_events(db), get_key(), args.expect_seq, args.expect_hash)
        elapsed = time.perf_counter() - start

    if result.ok:
        print(f"[OK] {result.count} evenements, chaine intacte, duree {elapsed:.2f} s")
        print(f"     tete : seq={result.head_seq} hash={result.head_hash}")
        return 0
    print(f"[ALERTE] Rupture a l'index {result.break_seq} ({result.reason}) : "
          f"{REASONS.get(result.reason, '')}")
    print(f"         detail : {result.detail}")
    print(f"         {result.count} evenement(s) verifie(s) avant la rupture, duree {elapsed:.2f} s")
    return 1


if __name__ == "__main__":
    sys.exit(main())
