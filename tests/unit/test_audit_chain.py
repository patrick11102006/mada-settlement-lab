import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from apps.api.audit_chain import (
    GENESIS_HASH, canonical_json, compute_event_hash, iso_utc, payload_hash, seal_event, verify_chain,
)

KEY = "cle-de-test-audit"


def make_chain(n, key=KEY):
    events, prev = [], GENESIS_HASH
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for seq in range(1, n + 1):
        f = dict(seq=seq, event_id=uuid.uuid4(), timestamp=base + timedelta(seconds=seq),
                 actor_id=uuid.uuid4(), action="TEST_ACTION", resource_type="submission",
                 resource_id=f"res-{seq}", outcome="SUCCESS",
                 payload_text=canonical_json({"n": seq}), previous_hash=prev)
        sealed = seal_event(key, **f)
        events.append(SimpleNamespace(
            id=f["event_id"], seq=seq, timestamp=f["timestamp"], actor_id=f["actor_id"],
            action=f["action"], resource_type=f["resource_type"], resource_id=f["resource_id"],
            outcome=f["outcome"], payload=f["payload_text"], previous_hash=prev, **sealed))
        prev = sealed["event_hash"]
    return events


def test_payload_hash_ignores_key_order():
    a, b = canonical_json({"b": 1, "a": 2}), canonical_json({"a": 2, "b": 1})
    assert a == b and payload_hash(a) == payload_hash(b)


def test_timestamp_is_normalized_to_utc():
    plus3 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    utc = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    assert iso_utc(plus3) == iso_utc(utc)


def test_valid_chain_is_intact():
    r = verify_chain(make_chain(5), KEY)
    assert r.ok and r.count == 5 and r.head_seq == 5


def test_empty_chain_is_intact():
    r = verify_chain([], KEY)
    assert r.ok and r.count == 0 and r.head_seq == 0


def test_modified_action_is_detected():
    chain = make_chain(5)
    chain[2].action = "AUTRE_ACTION"
    r = verify_chain(chain, KEY)
    assert not r.ok and r.break_seq == 3 and r.reason == "EVENT_HASH_MISMATCH"


def test_modified_payload_is_detected():
    chain = make_chain(5)
    chain[1].payload = canonical_json({"n": 999})
    r = verify_chain(chain, KEY)
    assert not r.ok and r.break_seq == 2 and r.reason == "PAYLOAD_HASH_MISMATCH"


def test_forged_hash_without_key_is_detected():
    chain = make_chain(5)
    chain[2].action = "AUTRE_ACTION"
    chain[2].event_hash = compute_event_hash("mauvaise-cle", chain[2])  # l'attaquant n'a pas la cle
    r = verify_chain(chain, KEY)
    assert not r.ok and r.break_seq == 3 and r.reason == "EVENT_HASH_MISMATCH"


def test_deleted_middle_event_is_detected():
    chain = make_chain(6)
    del chain[3]  # supprime l'evenement 4
    r = verify_chain(chain, KEY)
    assert not r.ok and r.break_seq == 4 and r.reason == "SEQUENCE_GAP"


def test_deleted_first_event_is_detected():
    r = verify_chain(make_chain(5)[1:], KEY)
    assert not r.ok and r.break_seq == 1 and r.reason == "SEQUENCE_GAP"


def test_rewritten_chain_with_other_key_is_detected():
    r = verify_chain(make_chain(5, key="cle-attaquant"), KEY)
    assert not r.ok and r.break_seq == 1 and r.reason == "EVENT_HASH_MISMATCH"


def test_truncation_needs_external_anchor():
    chain = make_chain(5)
    anchor = chain[-1].event_hash
    truncated = chain[:4]
    assert verify_chain(truncated, KEY).ok is True              # sans ancre : non detecte
    r = verify_chain(truncated, KEY, 5, anchor)                 # avec ancre : detecte
    assert not r.ok and r.reason == "TRUNCATED" and r.break_seq == 5
    longer = make_chain(7)                                      # des evenements ajoutes apres l'ancre sont normaux
    assert verify_chain(longer, KEY, 5, longer[4].event_hash).ok is True
