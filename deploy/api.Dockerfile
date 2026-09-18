FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/api

WORKDIR /app

COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY api/app /app/api/app
COPY berita-dampak/scripts /app/berita-dampak/scripts
COPY akreditasi/scripts/registry_kebutuhan_data.py /app/akreditasi/scripts/registry_kebutuhan_data.py
COPY deploy/bootstrap_duckdb.py /app/bootstrap_duckdb.py
COPY deploy/migrate_mysql_to_postgres.py /app/migrate_mysql_to_postgres.py

RUN useradd --system --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
