FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY api ./api
COPY core ./core
COPY static ./static
COPY templates ./templates
COPY scripts/backfill_backdrops.py ./scripts/
COPY scripts/backfill_db_backup.py ./scripts/
COPY scripts/backfill_moods.py ./scripts/
COPY scripts/backfill_posters.py ./scripts/
COPY scripts/normalize_genres.py ./scripts/
COPY scripts/sqlite_maintenance.py ./scripts/

RUN mkdir -p data reports

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
