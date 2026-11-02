# ===== Étape 1 : Builder (installe les dépendances) =====
FROM python:3.11-slim AS builder
WORKDIR /build
# Installe les outils de build
RUN pip install --no-cache-dir --upgrade pip build
# Copie uniquement les fichiers nécessaires pour les dépendances
COPY requirements.txt .
# Installe les dépendances dans un dossier isolé
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===== Étape 2 : Runtime (image finale légère) =====
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Installe curl pour le healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

WORKDIR /app

# Copie les dépendances depuis le builder
COPY --from=builder /install /usr/local
# Copie le code source
COPY apps ./apps
COPY alembic.ini .

# Sécurité : on n'exécute pas en root
USER app

EXPOSE 8000

# Healthcheck natif Docker
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Lancement de l'API
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
