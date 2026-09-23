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
# Dimuat API untuk ruang kerja akreditasi: generate Word dan ekstraksi AI (api/app/domain/source.py).
COPY akreditasi/scripts/generate_template.py /app/akreditasi/scripts/generate_template.py
COPY akreditasi/scripts/ekstraksi_akreditasi.py /app/akreditasi/scripts/ekstraksi_akreditasi.py
COPY deploy/migrate_mysql_to_postgres.py /app/migrate_mysql_to_postgres.py
# Data kurasi mata kuliah dibaca service story dari disk (bukan dari Postgres/MySQL).
# Tanpa baris ini, blok `mata_kuliah` di endpoint story akan tersedia:false di container
# (endpoint berita tetap hidup — itu memang desainnya, tapi panel MK hilang).
# PDF Ringkasan tidak di-copy: tidak dibaca kode (hanya sumber angka resmi/dokumentasi).
COPY "matkul-sustainability/data/Deskripsi Matkul Kepmen.csv" "/app/matkul-sustainability/data/Deskripsi Matkul Kepmen.csv"

RUN useradd --system --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
