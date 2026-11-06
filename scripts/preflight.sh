#!/usr/bin/env bash
# Vérification pré-build : requirements, Dockerfile, main.py, submissions.py, docker-compose.yml
OK=0; KO=0
ok(){ echo "  [OK] $1"; OK=$((OK+1)); }
ko(){ echo "  [KO] $1"; KO=$((KO+1)); }
has(){   # has "description" fichier "regex"
  if [ -f "$2" ] && grep -Eiq "$3" "$2"; then ok "$1"; else ko "$1"; fi
}
hasnt(){ # hasnt "description" fichier "regex"
  if [ -f "$2" ] && ! grep -Eiq "$3" "$2"; then ok "$1"; else ko "$1"; fi
}
exists(){ if [ -f "$2" ]; then ok "$1"; else ko "$1 (fichier introuvable : $2)"; fi; }

echo "=== ÉTAPE 2 : requirements.txt ==="
R=requirements.txt
exists "requirements.txt existe" $R
if [ -f $R ]; then
  if file $R | grep -qi "UTF-16"; then ko "encodage UTF-16 (doit être UTF-8)"; else ok "encodage lisible (pas UTF-16)"; fi
  L=$(wc -l < $R)
  if [ "$L" -ge 10 ]; then ok "au moins 10 lignes ($L)"; else ko "trop court ($L lignes)"; fi
fi
for p in fastapi uvicorn sqlalchemy psycopg alembic pydantic-settings python-multipart python-jose passlib bcrypt boto3; do
  has "dépendance : $p" $R "^$p"
done
has "bcrypt épinglé à 4.0.1" $R "^bcrypt==4\.0\.1"

echo ""
echo "=== ÉTAPE 3 : infra/docker/api.Dockerfile ==="
D=infra/docker/api.Dockerfile
exists "Dockerfile existe" $D
has   "image de base python:3.11-slim"         $D "^FROM python:3\.11-slim"
has   "COPY requirements.txt"                  $D "^COPY requirements\.txt"
has   "pip install -r requirements.txt"        $D "pip install.*-r requirements\.txt"
has   "vérification d'imports au build"        $D "import fastapi, uvicorn, boto3"
has   "COPY apps"                              $D "^COPY apps"
has   "COPY alembic.ini"                       $D "^COPY alembic\.ini"
has   "utilisateur non-root (USER app)"        $D "^USER app"
has   "HEALTHCHECK présent"                    $D "^HEALTHCHECK"
has   "CMD python -m uvicorn"                  $D "python.*-m.*uvicorn"
hasnt "pas de multi-stage cassé (--prefix=/install)" $D "--prefix=/install"
exists ".dockerignore existe" .dockerignore
has   ".dockerignore exclut .venv"             .dockerignore "^\.venv"
has   ".dockerignore exclut .env"              .dockerignore "^\.env"

echo ""
echo "=== ÉTAPE 4 : main.py et submissions.py ==="
M=apps/api/main.py
S=apps/api/routers/submissions.py
exists "main.py existe" $M
has   "main.py : import asynccontextmanager"   $M "from contextlib import asynccontextmanager"
has   "main.py : import init_storage"          $M "from \.storage import init_storage"
has   "main.py : fonction lifespan"            $M "async def lifespan"
has   "main.py : appel init_storage()"         $M "init_storage\(\)"
has   "main.py : FastAPI(... lifespan=lifespan)" $M "lifespan *= *lifespan"
has   "main.py : import du routeur submissions" $M "from \.routers import .*submissions"
has   "main.py : include_router submissions"   $M "include_router\(submissions\.router"
has   "main.py : include_router auth"          $M "include_router\(auth\.router"
has   "main.py : include_router users"         $M "include_router\(users\.router"
exists "submissions.py existe" $S
hasnt "submissions.py : plus de on_event"      $S "on_event"
hasnt "submissions.py : n'importe plus init_storage" $S "init_storage"
has   "submissions.py : import upload_file"    $S "from \.\.storage import upload_file"
has   "submissions.py : calcul SHA-256"        $S "hashlib\.sha256"
has   "submissions.py : réponse 409 doublon"   $S "HTTP_409_CONFLICT|409"
exists "storage.py existe" apps/api/storage.py
has   "models.py : classe Submission"          apps/api/models.py "class Submission"

echo ""
echo "=== ÉTAPE 5 : docker-compose.yml (MinIO) ==="
C=docker-compose.yml
exists "docker-compose.yml existe" $C
if [ -f $C ]; then
  MINIO_BLOCK=$(awk '/^  minio:/{f=1;next} /^  [A-Za-z_-]+:/{f=0} /^[A-Za-z]/{f=0} f' $C)
  if echo "$MINIO_BLOCK" | grep -q "image:"; then ok "service minio trouvé"; else ko "service minio introuvable"; fi
  if echo "$MINIO_BLOCK" | grep -q "healthcheck"; then ko "healthcheck minio présent (à retirer)"; else ok "pas de healthcheck minio"; fi
  if echo "$MINIO_BLOCK" | grep -Eq "image: *minio/minio|quay\.io/minio"; then ko "image minio obsolète (minio/minio ou quay.io)"; else ok "image minio non obsolète"; fi
  has "api : DATABASE_URL vers db:5432"        $C "DATABASE_URL=.*@db:5432"
  has "api : MINIO_ENDPOINT=minio:9000"        $C "MINIO_ENDPOINT=minio:9000"
  has "volume msl_miniodata déclaré"           $C "msl_miniodata"
  has "volume msl_pgdata déclaré"              $C "msl_pgdata"
  if docker compose config -q 2>/dev/null; then ok "YAML valide (docker compose config)"; else ko "YAML invalide : lance 'docker compose config' pour voir l'erreur"; fi
  IMG=$(echo "$MINIO_BLOCK" | grep "image:" | head -1 | sed 's/.*image: *//' | tr -d '"\r ')
  echo "  [..] image minio déclarée : $IMG"
  if [ -n "$IMG" ]; then
    if docker manifest inspect "$IMG" >/dev/null 2>&1; then ok "le tag MinIO existe sur le registre"; else ko "tag MinIO introuvable (vérifie l'onglet Tags sur Docker Hub)"; fi
  fi
fi

echo ""
echo "=== SÉCURITÉ ==="
if git check-ignore -q .env; then ok ".env est ignoré par Git"; else ko ".env n'est PAS ignoré par Git"; fi
if git ls-files --error-unmatch .env >/dev/null 2>&1; then ko ".env est suivi par Git !"; else ok ".env n'est pas suivi par Git"; fi

echo ""
echo "================================"
echo " Résultat : $OK OK / $KO KO"
echo "================================"
[ "$KO" -eq 0 ] && echo "Tout est bon, tu peux reconstruire." || echo "Corrige les [KO] puis relance : bash scripts/preflight.sh"
exit $KO
