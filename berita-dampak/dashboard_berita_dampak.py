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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "akreditasi" / "scripts"))

st.set_page_config(page_title="Analisis Dampak UGM", layout="wide", page_icon="🎓")


def _user_login() -> dict | None:
    """Cuma utk memutuskan menu mana yang tampil (Profil: sudah login; Admin:
    admin). Halaman Profil & Admin tetap menjaga dirinya sendiri (wajib_login /
    page_admin.render), jadi kalau cek ini gagal (mis. MySQL putus) cukup
    sembunyikan menunya -- jangan jatuhkan dashboard."""
    try:
        from auth_akreditasi import pulihkan_user

        return pulihkan_user()
    except Exception:  # noqa: BLE001
        return None


_user = _user_login()

# Tanpa icon: logo gambar dipasang lewat CSS (common.css_ikon_sidebar) karena
# st.Page(icon=...) tidak menerima file gambar. Kalau icon emoji TETAP diisi,
# menu akan menampilkan DUA ikon (emoji + logo) sekaligus.
# Catatan: "Dampak" sementara TANPA ikon sama sekali -- logonya
# (shared/assets/logo/dampak.png) belum ada.
beranda = st.Page("pages_app/beranda.py", title="Beranda", default=True)
dampak_saja = st.Page("pages_app/dampak_saja.py", title="Dampak", url_path="dampak")
dampak_sdgs = st.Page("pages_app/dampak_sdgs.py", title="Dampak × SDGs", url_path="dampak-sdgs")
sdgs = st.Page("pages_app/sdgs.py", title="SDGs", url_path="sdgs")
akreditasi = st.Page("pages_app/akreditasi.py", title="Akreditasi", url_path="akreditasi")
# Profil & Admin tetap TERDAFTAR utk semua orang, cuma disembunyikan dari menu
# (visibility "hidden") -- supaya URL /profil & /admin yang diketik langsung
# tetap mendarat di halaman yang menampilkan form login / penolakan, bukan
# "page not found".
profil = st.Page("pages_app/profil.py", title="Profil Saya", icon="👤", url_path="profil",
                 visibility="visible" if _user else "hidden")
admin = st.Page("pages_app/admin.py", title="Admin", icon="🛡️", url_path="admin",
                visibility="visible" if _user and _user["is_admin"] else "hidden")

pg = st.navigation(
    {
        "": [beranda],
        "Analisis Dampak Universitas": [dampak_saja, dampak_sdgs],
        "SDGs": [sdgs],
        "Akreditasi": [akreditasi, profil, admin],
    }
)

from common import css_ikon_sidebar  # noqa: E402

st.html(css_ikon_sidebar())
pg.run()
