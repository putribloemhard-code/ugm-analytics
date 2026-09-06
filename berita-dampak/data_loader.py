"""Loading data (MySQL) untuk dashboard analisis dampak berita UGM.

Dipakai bareng oleh semua halaman (lihat pages_app/) supaya tidak ada
duplikasi koneksi/query -- @st.cache_resource dan @st.cache_data di sini
di-cache di level proses Streamlit, jadi tetap satu cache walau diimpor
dari banyak modul halaman berbeda.
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
import streamlit as st

# Kredensial MySQL dibaca dari .env di root project (JANGAN di-commit; lihat .gitignore).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@st.cache_resource
def _get_engine():
    """Engine SQLAlchemy ke MySQL, di-cache lintas rerun (cache_resource: koneksi
    tidak bisa/perlu di-pickle seperti DataFrame biasa di cache_data)."""
    host = os.environ["MYSQL_HOST"]
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ["MYSQL_USER"]
    password = os.environ["MYSQL_PASSWORD"]
    db = os.environ["MYSQL_DB"]
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
    # pool_recycle: buang koneksi setelah 1 jam idle (server Streamlit long-lived
    # bisa idle lama antar rerun -- hindari "MySQL server has gone away").
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


@st.cache_resource(ttl=300)
def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
                    pd.DataFrame]:
    # cache_resource (bukan cache_data): dataframe dipakai read-only oleh semua
    # halaman (di-.copy() dulu sebelum dimodifikasi -- lihat page_dampak.py),
    # jadi tidak perlu pickle/deep-copy tiap kali dipanggil (cache_data selalu
    # copy demi proteksi mutasi -- mahal untuk 13 tabel sekaligus, termasuk
    # yang >100rb baris).
    engine = _get_engine()
    berita = pd.read_sql("SELECT * FROM berita_berita", engine)
    topik = pd.read_sql("SELECT * FROM berita_berita_topik", engine)
    ringkas = pd.read_sql("SELECT * FROM berita_ringkasan_topik_tahun", engine)
    sitemap = pd.read_sql("SELECT url, lastmod FROM berita_sitemap", engine)
    bk = pd.read_sql("SELECT * FROM berita_berita_kepmen_all", engine)
    bs = pd.read_sql("SELECT * FROM berita_berita_sdg_all", engine)
    rp = pd.read_sql("SELECT * FROM berita_ringkasan_pilar", engine)
    rpt = pd.read_sql("SELECT * FROM berita_ringkasan_pilar_tahun", engine)
    rsa = pd.read_sql("SELECT * FROM berita_ringkasan_sdg_all", engine)
    ss = pd.read_sql("SELECT * FROM berita_sitemap_sdg", engine)
    rsg = pd.read_sql("SELECT * FROM berita_ringkasan_sdg_sitemap", engine)
    rsgt = pd.read_sql("SELECT * FROM berita_ringkasan_sdg_sitemap_tahun", engine)
    uk = pd.read_sql("SELECT * FROM berita_unit_kerja", engine)
    return berita, topik, ringkas, sitemap, bk, bs, rp, rpt, rsa, ss, rsg, rsgt, uk


@st.cache_data(ttl=300)
def load_narasi_cache() -> dict:
    """Narasi hasil rangkaian LLM (Gemini), digenerate mingguan lewat
    scripts/generate_narasi_llm.py -> tabel berita_narasi_cache. Dipakai HANYA
    saat filter sidebar masih posisi default (semua tahun/tema/sumber/pilar/
    SDG) -- kalau tabel belum ada / kosong / gagal baca, fallback otomatis ke
    narasi template (generate_executive_summary / generate_impact_insight),
    dashboard tetap jalan normal tanpa LLM.
    """
    try:
        engine = _get_engine()
        df = pd.read_sql("SELECT cache_key, narasi FROM berita_narasi_cache", engine)
        return dict(zip(df["cache_key"], df["narasi"]))
    except Exception:  # noqa: BLE001
        return {}


@st.cache_data(ttl=300)
def load_ringkasan_beranda() -> dict:
    """3 angka ringkas untuk mini-preview halaman Beranda -- pakai COUNT(*)
    langsung di MySQL (bukan pd.read_sql SELECT * lalu dihitung di pandas),
    supaya Beranda tetap ringan dan tidak perlu menarik seluruh 13 tabel
    (dipakai load() untuk halaman analisis) hanya demi 3 angka ini."""
    engine = _get_engine()
    total_berita = pd.read_sql("SELECT COUNT(*) AS n FROM berita_berita", engine)["n"].iloc[0]
    n_dampak = pd.read_sql(
        "SELECT COUNT(DISTINCT url) AS n FROM berita_berita_kepmen_all", engine
    )["n"].iloc[0]
    total_sitemap = pd.read_sql(
        "SELECT COUNT(DISTINCT url) AS n FROM berita_sitemap", engine
    )["n"].iloc[0]
    return {
        "total_berita": int(total_berita),
        "n_dampak": int(n_dampak),
        "total_sitemap": int(total_sitemap),
    }
