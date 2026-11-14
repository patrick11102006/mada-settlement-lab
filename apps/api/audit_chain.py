"""Logique pure de la chaine d'audit : hachage, scellement et verification.

Aucun acces base de donnees ici : tout est testable sans PostgreSQL.
event_hash = HMAC-SHA256(cle, JSON canonique des champs de l'evenement, previous_hash inclus).
"""
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64


def canonical_json(data) -> str:
    """JSON deterministe : cles triees, sans espaces."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def payload_hash(payload_text: str) -> str:
    return hashlib.sha256(payload_text.encode("utf-8")).hexdigest()


def iso_utc(ts: datetime) -> str:
    """Horodatage normalise en UTC, a la microseconde : meme valeur quel que soit le fuseau."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _mac(key: str, body: str) -> str:
    return hmac.new(key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def _body(*, seq, event_id, timestamp, actor_id, action, resource_type,
          resource_id, outcome, p_hash, previous_hash) -> str:
    return canonical_json({
        "seq": int(seq),
        "id": str(event_id),
        "timestamp": iso_utc(timestamp),
        "actor_id": None if actor_id is None else str(actor_id),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "payload_hash": p_hash,
        "previous_hash": previous_hash,
    })


def seal_event(key: str, *, seq, event_id, timestamp, actor_id, action, resource_type,
               resource_id, outcome, payload_text, previous_hash) -> dict:
    """Calcule payload_hash et event_hash d'un nouvel evenement."""
    p_hash = payload_hash(payload_text)
    body = _body(seq=seq, event_id=event_id, timestamp=timestamp, actor_id=actor_id,
                 action=action, resource_type=resource_type, resource_id=resource_id,
                 outcome=outcome, p_hash=p_hash, previous_hash=previous_hash)
    return {"payload_hash": p_hash, "event_hash": _mac(key, body)}


def compute_event_hash(key: str, e) -> str:
    """Recalcule l'event_hash d'un evenement stocke (objet avec les memes attributs)."""
    return _mac(key, _body(seq=e.seq, event_id=e.id, timestamp=e.timestamp, actor_id=e.actor_id,
                           action=e.action, resource_type=e.resource_type,
                           resource_id=e.resource_id, outcome=e.outcome,
                           p_hash=e.payload_hash, previous_hash=e.previous_hash))


def _eq(a: str, b: str) -> bool:
    return hmac.compare_digest(str(a).encode("utf-8"), str(b).encode("utf-8"))


@dataclass
class VerifyResult:
    ok: bool
    count: int                      # evenements verifies avant la rupture (ou au total)
    break_seq: int | None = None    # index (seq) de la rupture
    reason: str | None = None
    detail: str | None = None
    head_seq: int = 0
    head_hash: str = GENESIS_HASH


def verify_chain(events, key: str, expected_head_seq: int | None = None,
                 expected_head_hash: str | None = None) -> VerifyResult:
    """Parcourt la chaine dans l'ordre et signale la premiere rupture.

    L'ancre (expected_head_*) est une reference de confiance conservee hors de la base :
    elle seule permet de detecter la suppression des derniers evenements.
    """
    expected_seq, prev_hash, count, last_seq = 1, GENESIS_HASH, 0, 0
    anchor_hash = None
    for e in events:
        if e.seq != expected_seq:
            return VerifyResult(False, count, expected_seq, "SEQUENCE_GAP",
                                f"numero attendu {expected_seq}, trouve {e.seq}")
        if not _eq(e.previous_hash, prev_hash):
            return VerifyResult(False, count, e.seq, "PREVIOUS_HASH_MISMATCH",
                                "le lien avec l'evenement precedent est rompu")
        if not _eq(payload_hash(e.payload), e.payload_hash):
            return VerifyResult(False, count, e.seq, "PAYLOAD_HASH_MISMATCH",
                                "le contenu (payload) a ete modifie")
        if not _eq(compute_event_hash(key, e), e.event_hash):
            return VerifyResult(False, count, e.seq, "EVENT_HASH_MISMATCH",
                                "l'evenement a ete modifie, ou la cle HMAC ne correspond pas")
        count += 1
        if expected_head_seq is not None and e.seq == expected_head_seq:
            anchor_hash = e.event_hash
        prev_hash, expected_seq, last_seq = e.event_hash, expected_seq + 1, e.seq

    if expected_head_seq is not None:
        if last_seq < expected_head_seq:
            return VerifyResult(False, count, last_seq + 1, "TRUNCATED",
                                f"ancre a {expected_head_seq}, journal termine a {last_seq}",
                                last_seq, prev_hash)
        if anchor_hash is None or not _eq(anchor_hash, expected_head_hash or ""):
            return VerifyResult(False, count, expected_head_seq, "ANCHOR_MISMATCH",
                                "le hash a la position de l'ancre ne correspond pas",
                                last_seq, prev_hash)
    return VerifyResult(True, count, None, None, None, last_seq, prev_hash)
