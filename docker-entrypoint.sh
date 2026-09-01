#!/usr/bin/env sh
set -e

# Apply any pending schema migrations, then serve.
# On a scale-to-zero service two instances can start at once; Alembic takes a
# lock, so the loser retries once and then no-ops.
echo "sr-generator: alembic upgrade head"
alembic upgrade head || {
  echo "migration failed once, retrying in 3s..."
  sleep 3
  alembic upgrade head
}

exec uvicorn sr.api.main:app --host 0.0.0.0 --port "${PORT:-8080}" --workers "${WEB_CONCURRENCY:-1}"
