# ADR-0002 : journal d'audit chaîné par HMAC-SHA256

## Contexte
Il faut détecter toute altération d'un événement d'audit (US-13, US-14).

## Décision
Chaque événement porte `previous_hash` et `event_hash = HMAC-SHA256(clé, champs canoniques)`.
La clé (`AUDIT_HMAC_KEY`) est hors base de données. Un numéro `seq` continu détecte les
suppressions intermédiaires. L'écriture est sérialisée par un verrou PostgreSQL.
Une CLI (`python -m apps.api.audit_cli verify`) rejoue la chaîne et indique l'index de rupture.

## Conséquences et limites
- Un SHA-256 simple se recalcule intégralement par quiconque accède à la base ; le HMAC exige la clé.
- La suppression des **derniers** événements n'est détectable qu'avec une ancre externe
  (`--expect-seq`, `--expect-hash`) conservée hors de la base.
- La clé et la base sont sur la même machine : un attaquant qui contrôle l'API peut forger la chaîne.
  Durcissement prévu : signature gérée (Vault Transit), stockage immuable, rôle SQL en insertion seule.
- Rotation de clé non gérée (il faudrait un identifiant de clé par événement).
- L'événement est écrit après la transaction métier, pas dans la même (amélioration : outbox).
