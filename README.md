# Mada Settlement Lab


Plateforme sécurisée de contrôle qualité, de traçabilité et d'audit des données financières.

Application Web permettant de recevoir des déclarations financières **fictives**, de vérifier leur
conformité, de détecter les incohérences et d'assurer leur traçabilité.

**Stack** : React, Tailwind CSS (à venir), Python, FastAPI, PostgreSQL, MinIO, Docker.

[![CI Pipeline](https://github.com/patrick11102006/mada-settlement-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/patrick11102006/mada-settlement-lab/actions/workflows/ci.yml)

Plateforme academique de collecte, validation, consolidation et audit de
declarations financieres **synthetiques**.

> ⚠️ **Disclaimer** — Projet academique independant. Toutes les organisations,
> transactions et donnees sont fictives. Ce projet ne represente ni l'architecture,
> ni les procedures, ni les systemes internes d'une institution financiere reelle.

## Statut
🚧 En construction — Sprint 0 (cadrage et squelette).

## Stack prevue
- Backend : FastAPI + PostgreSQL + MinIO
- Frontend : Next.js
- Observabilite : Prometheus + Grafana
- CI/CD : GitHub Actions (Gitleaks, Semgrep, Trivy)

![Branch protection activée sur main et develop](image.png)

## Journal d'audit

Les actions sensibles (connexion, dépôt, validation, consolidation, administration, accès refusé)
produisent un événement chaîné par HMAC-SHA256. Vérification : `python -m apps.api.audit_cli verify`
(signale l'index de rupture). Limites et choix : voir `docs/adr/0002-audit-hash-chain.md`.
