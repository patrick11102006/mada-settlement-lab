"""Génère N événements d'audit de test (mesure de performance).
Usage : python -m scripts.gen_audit_events 1000
"""
import sys

from apps.api.audit import record_event
from apps.api.db import SessionLocal

n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
with SessionLocal() as db:
    for i in range(n):
        record_event(db, action="PERF_TEST", resource_type="audit_log", resource_id=str(i), payload={"i": i})
print(n, "événements créés")
