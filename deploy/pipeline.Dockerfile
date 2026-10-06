# Pipeline berita mingguan (berita-dampak/scripts/update_mingguan.py) untuk dijalankan cron di server:
#   docker compose run --rm pipeline
# Container sekali jalan (profil "pipeline", tidak ikut `docker compose up`). Menulis ke mysql-reader;
# salinan ke PostgreSQL dilakukan terpisah oleh `migrate_mysql_to_postgres.py --sinkron-berita`
# (lihat deploy/update_berita.sh).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/berita-dampak

COPY deploy/pipeline.requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY berita-dampak/scripts ./scripts
COPY berita-dampak/docs/kepmen_361_ocr.txt ./docs/kepmen_361_ocr.txt

RUN useradd --system --uid 10001 --create-home appuser \
    && mkdir -p data \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "scripts/update_mingguan.py"]
