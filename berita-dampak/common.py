"""Konstanta, styling, dan helper yang dipakai bareng oleh semua halaman
dashboard (lihat pages_app/) -- supaya tidak ada duplikasi antar halaman.
"""

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, utk shared/

from shared.style import apply_custom_css  # noqa: E402
from scripts.keywords import KEYWORDS  # noqa: E402
from scripts.kepmen_sdg import (  # noqa: E402
    SDG_NAMA,
    TOPIK_KEPMEN,
    TOPIK_KEPMEN_ALL,
    TEMA_KEPMEN_LENGKAP,
    WARNA_PILAR,
    sdg_label,
)
from scripts.kepmen_sdg import LABEL_TOPIC_ALL as LABEL_TOPIC  # noqa: E402
from scripts.unit_kerja import UNIT_KERJA  # noqa: E402

# 44 fakultas/sekolah/unit kerja, diurutkan Fakultas -> Sekolah -> Unit Kerja
# (lalu alfabetis per kategori) supaya gampang di-scan/cari di multiselect.
_URUTAN_KATEGORI = {"Fakultas": 0, "Sekolah": 1, "Unit Kerja": 2}
UNIT_KERJA_OPSI = sorted(
    UNIT_KERJA.keys(),
    key=lambda k: (_URUTAN_KATEGORI[UNIT_KERJA[k]["kategori"]], UNIT_KERJA[k]["nama"]),
)
WARNA_KATEGORI = {"Fakultas": "#3949ab", "Sekolah": "#00897b", "Unit Kerja": "#8e24aa"}

# Semua keyword (14 tema resmi Kepmen) untuk breakdown.
KEYWORDS_ALL = dict(KEYWORDS)
KEYWORDS_ALL.update({k: v["keywords"] for k, v in TEMA_KEPMEN_LENGKAP.items()})

# 14 tema dikelompokkan per pilar (urutan sesuai LABEL_TOPIC) -- dipakai untuk
# pecah dropdown tema jadi 1 per pilar, bukan 1 dropdown raksasa isi 14 tema.
TOPIK_PER_PILAR = {
    p: [k for k in LABEL_TOPIC if TOPIK_KEPMEN_ALL[k]["dampak"] == p]
    for p in ["Lingkungan", "Ekonomi", "Sosial"]
}
PILAR_ICON_SIDEBAR = {"Lingkungan": "🌳", "Ekonomi": "💼", "Sosial": "🤝"}
PILAR_ICON = PILAR_ICON_SIDEBAR

STOPWORDS = set(
    """dan di ke dari yang untuk dengan pada dalam sebagai oleh ini itu atau
    serta akan telah dapat tidak juga para bagi agar karena antara melalui
    terhadap tentang hingga sampai setelah sebelum ketika saat secara merupakan
    menjadi adalah yaitu yakni tahun baru kembali lebih paling sangat ada bisa
    harus sudah sedang masih semua setiap berbagai sebuah suatu satu dua tiga
    indonesia universitas ugm gadjah mada the and for with from that this are
    was were has have had will its their into about through during after
    before more most also can could should would may of to in is it on at by
    an be as or you your we our they them his her not but what when where how
    why do does did done up out off over under antara""".split()
)


def token_freq(df: pd.DataFrame) -> Counter:
    """Frekuensi kata pada judul + deskripsi (stopword dibuang)."""
    c: Counter = Counter()
    teks = df["judul"].fillna("") + " " + df["deskripsi"].fillna("")
    for t in teks:
        for kata in re.findall(r"[a-z]{3,}", t.lower()):
            if kata not in STOPWORDS:
                c[kata] += 1
    return c


def hover_keterangan(fig, keterangan: str):
    """Tambahkan baris penjelasan ke tooltip hover semua trace.

    Disisipkan sebelum kotak nama trace (<extra>) sehingga angka default
    (x/y/z + hover_data) tetap tampil, ditambah penjelasan cara hitung.
    """
    sisip = f"<br><span style='font-size:11px'>{keterangan}</span>"
    for tr in fig.data:
        ht = getattr(tr, "hovertemplate", None) or ""
        if "<extra>" in ht:
            tr.hovertemplate = ht.replace("<extra>", sisip + "<extra>", 1)
        elif ht:
            tr.hovertemplate = ht + sisip
        else:
            nama = getattr(tr, "name", "") or ""
            header = f"{nama}<br>" if nama else ""
            tr.hovertemplate = header + "%{x} — %{y}" + sisip + "<extra></extra>"
    return fig


def penjelasan(teks: str):
    """Caption penjelasan di bawah chart: tujuan & cara hitung angka."""
    st.caption(f"💡 {teks}")


# Konfigurasi toolbar kamera Plotly -- WAJIB dipakai di semua st.plotly_chart
# supaya tombol unduh gambar (kamera, pojok kanan atas chart) selalu terlihat.
PLOTLY_CONFIG = {"displaylogo": False}


CSS = """
<style>
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1200px; }

/* Metric cards -- netral biar aman di light & dark theme */
div[data-testid="stMetric"] {
    background: rgba(128,128,128,0.07);
    border: 1px solid rgba(128,128,128,0.16);
    border-radius: 12px;
    padding: 14px 16px 10px;
}
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] * {
    font-size: 1.25rem !important; font-weight: 700; line-height: 1.3 !important;
    white-space: normal !important; overflow: visible !important;
    text-overflow: unset !important; overflow-wrap: break-word !important;
}
div[data-testid="stMetricLabel"] { font-size: 0.8rem; opacity: 0.75; }

/* Narasi/insight box */
div[data-testid="stAlertContentInfo"] { font-size: 0.97rem; line-height: 1.6; }
div[data-testid="stNotification"] { border-radius: 12px; }

/* Kartu pilar dampak */
.pilar-card {
    border-radius: 14px;
    padding: 18px 12px 14px;
    text-align: center;
    transition: box-shadow 0.15s ease;
    height: 100%;
    box-sizing: border-box;
}
.pilar-card-icon { font-size: 2.1rem; line-height: 1; margin-bottom: 2px; }
.pilar-card-name {
    font-size: 0.95rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px;
}
.pilar-card-count { font-size: 2.4rem; font-weight: 800; line-height: 1.15; margin-top: 6px; }
.pilar-card-unit { font-size: 0.78rem; opacity: 0.65; margin-bottom: 10px; }
.pilar-card-theme {
    font-size: 0.83rem; opacity: 0.85;
    border-top: 1px solid rgba(128,128,128,0.22);
    padding-top: 8px; margin-top: 2px; min-height: 3.4em;
}

/* Kartu shortcut Beranda -- SATU elemen <a> (kartu + tombol "Buka ->" jadi
   satu blok HTML, lihat pages_app/beranda.py) supaya ukurannya menyesuaikan
   diri sendiri, bukan digabung dari dua elemen Streamlit terpisah (custom
   div + st.button). display:flex + footer margin-top:auto membuat
   "Buka ->" selalu menempel di bawah kartu apa pun panjang teks
   deskripsinya, dan kartu tetap rata tinggi lewat height:100% (kolomnya
   sendiri sudah stretch align, lihat shared/style.py). */
.home-card {
    display: flex;
    flex-direction: column;
    border-radius: 16px;
    padding: 24px 18px;
    text-align: center;
    border: 1px solid rgba(128,128,128,0.2);
    background: rgba(128,128,128,0.05);
    height: 100%;
    box-sizing: border-box;
    text-decoration: none;
    transition: box-shadow 0.15s ease, border-color 0.15s ease;
}
/* `<a>` punya warna+underline default browser/tema Streamlit dgn spesifisitas
   lebih tinggi dari `color:inherit` biasa -- paksa pakai warna teks tema
   (var Streamlit) supaya kartu ini terlihat SAMA seperti versi <div> lama,
   bukan seperti link biru pada umumnya. */
.home-card,
.home-card * {
    text-decoration: none !important;
    color: var(--text-color, inherit) !important;
}
.home-card:hover {
    border-color: rgba(128,128,128,0.4);
    box-shadow: 0 4px 14px rgba(0,0,0,0.08);
}
.home-card-icon { font-size: 2.4rem; line-height: 1; margin-bottom: 8px; }
.home-card-title { font-size: 1.05rem; font-weight: 700; margin-bottom: 6px; }
.home-card-desc { font-size: 0.85rem; opacity: 0.75; }
.home-card-footer {
    margin-top: auto;
    padding-top: 16px;
    font-size: 0.85rem;
    font-weight: 600;
    border-top: 1px solid rgba(128,128,128,0.2);
}
</style>
"""


def inject_css():
    apply_custom_css()
    st.markdown(CSS, unsafe_allow_html=True)


def load_data_or_stop():
    """Load data + narasi cache dari MySQL; tampilkan pesan error & st.stop()
    kalau gagal (dipanggil di awal tiap halaman yang butuh data)."""
    from data_loader import load, load_narasi_cache

    try:
        data = load()
        narasi_cache = load_narasi_cache()
        return data, narasi_cache
    except KeyError as e:
        st.error(f"Variabel environment {e} belum diset. Isi file .env di root project "
                 "(MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB).")
        st.stop()
    except Exception as e:
        st.error(f"Gagal terhubung/membaca data dari MySQL: {e}")
        st.info(
            "Cek: (1) service MySQL sudah berjalan di host/port yang dikonfigurasi, "
            "(2) kredensial di .env (MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/"
            "MYSQL_DB) sudah benar, (3) user MySQL sudah punya akses ke database "
            "tsb, (4) tabel berprefix 'berita_' sudah ada (lihat migrasi_ke_mysql.py)."
        )
        st.stop()
