"""Dashboard Streamlit analisis dampak berita UGM (multi-page).

Sumber: MySQL ugm_analytics (tabel berita_berita, berita_berita_topik,
berita_ringkasan_topik_tahun, berita_sitemap, dst. — prefix "berita_", nama
tabel diwarisi dari migrasi awal DuckDB->MySQL; sejak 2026-08-29 seluruh
pipeline (scripts/update_mingguan.py) baca/tulis MySQL langsung, tidak ada
lagi DuckDB perantara -- lihat scripts/db.py dan PIPELINE.md).

Struktur halaman (lihat pages_app/):
  Beranda
  Analisis Dampak Universitas -> Dampak Saja, Dampak x SDGs
  SDGs
  Akreditasi

Loading data (MySQL) ada di data_loader.py; konstanta/helper yang dipakai
bareng antar halaman ada di common.py -- supaya tidak ada duplikasi kode.

Jalankan: streamlit run dashboard_berita_dampak.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(page_title="Analisis Dampak UGM", layout="wide", page_icon="🎓")

beranda = st.Page("pages_app/beranda.py", title="Beranda", icon="🏠", default=True)
dampak_saja = st.Page("pages_app/dampak_saja.py", title="Dampak", icon="📊")
dampak_sdgs = st.Page("pages_app/dampak_sdgs.py", title="Dampak × SDGs", icon="🌍")
sdgs = st.Page("pages_app/sdgs.py", title="SDGs", icon="🎯")
akreditasi = st.Page("pages_app/akreditasi.py", title="Akreditasi", icon="📄")

pg = st.navigation(
    {
        "": [beranda],
        "Analisis Dampak Universitas": [dampak_saja, dampak_sdgs],
        "SDGs": [sdgs],
        "Akreditasi": [akreditasi],
    }
)
pg.run()
