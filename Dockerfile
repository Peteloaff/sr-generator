# SR Generator API — container for Google Cloud Run (or any Docker host).
#
#   docker build -t sr-generator-api .
#   docker run -p 8080:8080 --env-file .env sr-generator-api
#
# Cloud Run injects $PORT (default 8080). The entrypoint runs Alembic migrations,
# then starts uvicorn.

FROM python:3.12-slim

# ffmpeg is needed even though imageio-ffmpeg bundles a binary, because the slim
# image lacks the shared libs the bundled build links against; the system package
# is smaller and more reliable in a container.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY pyproject.toml ./
COPY sr ./sr
COPY alembic ./alembic
COPY alembic.ini ./
COPY docker-entrypoint.sh ./

# [cloud] adds psycopg (Postgres) + boto3 (S3 / Supabase Storage).
RUN pip install --no-cache-dir ".[cloud,rq]" \
    && chmod +x docker-entrypoint.sh \
    && useradd -m -u 1000 app \
    && mkdir -p /app/storage /tmp/sr-work \
    && chown -R app:app /app /tmp/sr-work

USER app

EXPOSE 8080
ENTRYPOINT ["./docker-entrypoint.sh"]
