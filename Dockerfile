# Backend image (API + worker share it). Optional - see docker-compose.yml.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY sr ./sr
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir -e ".[rq]"

EXPOSE 8000
CMD ["uvicorn", "sr.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
